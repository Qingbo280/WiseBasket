"""Private, fail-closed receipt-image masking before any external model call.

OCR is deliberately run on each profile's actual pixels. Only a strict private
receipt identity can be returned to the API; no raw OCR text, unmasked image,
or identity field is ever passed on to a cloud provider.
"""

from __future__ import annotations

import hashlib
import math
import re
from statistics import median
from dataclasses import dataclass, field
from typing import Any

import cv2
import numpy as np

from .models import ReceiptIdentity
from .paddle_receipt_parser import extract_receipt_identity, parse_receipt_lines
from .receipt_service import extract_paddle_tokens


_PHONE = re.compile(
    r"(?<!\d)(?:\+?60[\s-]?|0)(?:1[0-9]|[2-9])[\s-]?(?:\d[\s-]?){7,9}(?!\d)"
)
_LONG_NUMBER = re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")
_PERSON_CONTEXT = re.compile(
    r"\b(?:operator|staff|cashier|employee|attendant|clerk|juruwang|kasir|"
    r"served\s+by|nama|name|owner\s+name)\b", re.I,
)
_TRANSACTION_CONTEXT = re.compile(
    r"\b(?:invoice|receipt\s*(?:no|number|#)|slip|transaction|trans(?=\s*[:#])|"
    r"trace|reference|ref(?=\s*(?:no|#|:))|approval|authorization|"
    r"terminal|tid|mid|batch\s*(?:no|num)|card|kad|ahli|member(?:ship)?|"
    r"loyalty|reward|points?)\b", re.I,
)
_PHONE_CONTEXT = re.compile(r"\b(?:tel|telephone|phone|fax|mobile|handphone|contact|whatsapp)\b", re.I)
_ITEM_CODE_CONTEXT = re.compile(r"\b(?:bar\s*code|ean|sku|product\s*code|item\s*code)\b", re.I)
_SUMMARY = re.compile(r"\b(?:sub[ -]?total|total(?:\s+sales)?|amount\s+due|grand\s+total)\b", re.I)


class RedactionError(ValueError):
    pass


@dataclass(frozen=True)
class RedactedReceipt:
    image_bytes: bytes
    width: int
    height: int
    sha256: str
    mask_counts: dict[str, int]
    identity: ReceiptIdentity | None = None
    purchase_lines: list[dict[str, Any]] = field(default_factory=list)


def _rect(box: Any, width: int, height: int) -> tuple[int, int, int, int]:
    if not isinstance(box, list) or len(box) != 4:
        raise RedactionError("Sensitive OCR token has no usable location")
    try:
        raw = [float(value) for value in box]
    except (TypeError, ValueError, OverflowError) as exc:
        raise RedactionError("Sensitive OCR token has no usable location") from exc
    if (not all(math.isfinite(value) for value in raw)
            or raw[2] <= raw[0] or raw[3] <= raw[1]):
        raise RedactionError("Sensitive OCR token has no usable location")
    x1, y1, x2, y2 = [int(round(value)) for value in raw]
    if x2 <= 0 or y2 <= 0 or x1 >= width or y1 >= height:
        raise RedactionError("Sensitive OCR token has no usable location")
    pad = max(6, int((y2 - y1) * 0.25))
    rect = (max(0, x1 - pad), max(0, y1 - pad), min(width, x2 + pad), min(height, y2 + pad))
    if rect[0] >= rect[2] or rect[1] >= rect[3]:
        raise RedactionError("Sensitive OCR token has no usable location")
    return rect


def _machine_code_boxes(image: np.ndarray) -> list[tuple[int, int, int, int]]:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    height, width = gray.shape
    found: list[tuple[int, int, int, int]] = []
    detector = cv2.QRCodeDetector()
    ok, points = detector.detect(gray)
    if ok and points is not None:
        x, y, w, h = cv2.boundingRect(points.astype(np.int32))
        found.append((x, y, x + w, y + h))
    # Only confirmed machine-code geometry is masked. A generic Sobel stripe
    # contour also matches ordinary receipt text and used to erase item rows.
    barcode_module = getattr(cv2, "barcode", None)
    if barcode_module is not None and hasattr(barcode_module, "BarcodeDetector"):
        detector = barcode_module.BarcodeDetector()
        ok, points = detector.detect(gray)
        if ok and points is not None:
            for quadrilateral in np.asarray(points).reshape(-1, 4, 2):
                x, y, w, h = cv2.boundingRect(quadrilateral.astype(np.int32))
                found.append((x, y, x + w, y + h))
    return found


def _is_ean13(value: str) -> bool:
    """Public product EANs are not payment-card or customer identifiers."""
    if len(value) != 13 or not value.isdigit():
        return False
    expected = (10 - sum(int(digit) * (1 if index % 2 == 0 else 3)
                         for index, digit in enumerate(value[:-1])) % 10) % 10
    return expected == int(value[-1])


def _is_instore_variable_code(value: str) -> bool:
    """GS1 prefix 2 (02, 20-29) marks restricted-circulation in-store codes.

    Supermarkets print these 13-digit internal codes on weighed-item price
    rows (e.g. Jaya Grocer ``2107369001126 KG``); their EAN check digit does
    not follow the public-GTIN algorithm, so they fail ``_is_ean13``. They
    are printed product data, never payment-card or customer identifiers.
    """
    return len(value) == 13 and value.isdigit() and value.startswith("2")


def _is_payment_card(value: str) -> bool:
    if not value.isdigit() or not 13 <= len(value) <= 19:
        return False
    digits = [int(digit) for digit in value]
    total = 0
    for index, digit in enumerate(reversed(digits)):
        if index % 2:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


def _rows(tokens: list[dict[str, Any]], width: int, height: int) -> list[list[dict[str, Any]]]:
    """Group OCR text by its actual text height, not a fixed pixel grid."""
    located: list[tuple[float, float, dict[str, Any]]] = []
    for token in tokens:
        box = token.get("box")
        _rect(box, width, height)  # all OCR positions must be valid, not just PII positions
        center = (float(box[1]) + float(box[3])) / 2
        located.append((center, float(box[3]) - float(box[1]), token))
    located.sort(key=lambda item: (item[0], float(item[2]["box"][0])))
    rows: list[list[dict[str, Any]]] = []
    centers: list[float] = []
    heights: list[float] = []
    for center, token_height, token in located:
        if rows and abs(center - centers[-1]) <= max(4.0, min(token_height, heights[-1]) * 0.45):
            rows[-1].append(token)
            count = len(rows[-1])
            centers[-1] = (centers[-1] * (count - 1) + center) / count
            heights[-1] = max(heights[-1], token_height)
        else:
            rows.append([token])
            centers.append(center)
            heights.append(token_height)
    for row in rows:
        row.sort(key=lambda token: float(token["box"][0]))
    return rows


def _item_band(
    rows: list[list[dict[str, Any]]], height: int,
) -> tuple[int, int, list[list[dict[str, Any]]]]:
    """Retain the item section only; headers and payment footers can contain unseen PII.

    This is deliberately conservative: an unfamiliar receipt layout stays local
    instead of uploading a possibly identifying header/footer to a provider.
    """
    texts = [" ".join(str(token.get("text") or "") for token in row) for row in rows]
    items = parse_receipt_lines(texts)
    source_rows = sorted({row_id - 1 for item in items for row_id in item.source_row_ids})
    if len(items) < 2 or not source_rows:
        raise RedactionError("Receipt item section cannot be located safely")
    first_index = source_rows[0]
    summary_indices = [index for index in range(first_index + 1, len(rows)) if _SUMMARY.search(texts[index])]
    if not summary_indices:
        raise RedactionError("Receipt payment boundary cannot be located safely")
    summary_index = summary_indices[0]
    line_heights = [float(token["box"][3]) - float(token["box"][1])
                    for row in rows for token in row]
    pad = max(3, round(median(line_heights) * 0.3))
    start = max(0, round(min(float(token["box"][1]) for token in rows[first_index])) - pad)
    end = min(height, round(min(float(token["box"][1]) for token in rows[summary_index])))
    if end <= start or end - start < max(40, height * 0.05):
        raise RedactionError("Receipt item section cannot be located safely")
    item_rows = [rows[index] for index in source_rows if first_index <= index < summary_index]
    if len(item_rows) < 2:
        raise RedactionError("Receipt item section cannot be located safely")
    return start, end, item_rows


def _overlap_share(first: tuple[int, int, int, int], second: tuple[int, int, int, int]) -> float:
    intersection = max(0, min(first[2], second[2]) - max(first[0], second[0])) * max(
        0, min(first[3], second[3]) - max(first[1], second[1])
    )
    area = max(1, (first[2] - first[0]) * (first[3] - first[1]))
    return intersection / area


def _verify_masked(image_bytes: bytes, width: int, height: int) -> None:
    """Reject recognised residual identifiers after masking.

    OCR cannot prove that every character was seen, so the structural item
    band remains the primary privacy boundary; this is an additional check.
    """
    try:
        tokens = extract_paddle_tokens(image_bytes)
        if not tokens:
            raise RedactionError("Masked receipt has no verifiable item text")
        rows = _rows(tokens, width, height)
    except RedactionError:
        raise
    except Exception as exc:
        raise RedactionError("Masked receipt could not be verified") from exc
    for row in rows:
        value = " ".join(str(token.get("text") or "") for token in row)
        if (_PHONE.search(value) or _PHONE_CONTEXT.search(value)
                or _PERSON_CONTEXT.search(value) or _TRANSACTION_CONTEXT.search(value)):
            raise RedactionError("Masked receipt may retain sensitive text")
        for match in _LONG_NUMBER.finditer(value):
            digits = re.sub(r"\D", "", match.group())
            if (_is_payment_card(digits) and not _is_ean13(digits)
                    and not _is_instore_variable_code(digits)):
                raise RedactionError("Masked receipt may retain sensitive text")


def redact_receipt(image_bytes: bytes, profile: str = "normal") -> RedactedReceipt:
    if profile not in {"normal", "enhanced"}:
        raise RedactionError("Unknown redaction profile")
    if not image_bytes or len(image_bytes) > 8 * 1024 * 1024:
        raise RedactionError("Invalid image size")
    image = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
    if image is None or image.size == 0:
        raise RedactionError("Image cannot be decoded")
    height, width = image.shape[:2]
    if width * height > 25_000_000:
        raise RedactionError("Image dimensions exceed limit")
    if profile == "enhanced":
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        lab[:, :, 0] = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(lab[:, :, 0])
        image = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
    # Each invocation, including enhanced, gets fresh OCR coordinates.
    ok, encoded_for_ocr = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 90])
    if not ok or not encoded_for_ocr.size:
        raise RedactionError("Image cannot be encoded")
    try:
        tokens = extract_paddle_tokens(encoded_for_ocr.tobytes())
        machine_boxes = _machine_code_boxes(image)
    except Exception as exc:
        raise RedactionError("Sensitive-area detection unavailable") from exc
    if not tokens:
        raise RedactionError("Receipt text could not be checked for sensitive information")
    counts = {"phone": 0, "long_number": 0, "context": 0, "machine_code": 0}
    boxes: list[tuple[int, int, int, int]] = []
    rows = _rows(tokens, width, height)
    item_start, item_end, item_rows = _item_band(rows, height)
    # Derive this only inside the private inference service from its existing
    # original-pixel OCR pass. The provider still sees only masked item pixels.
    local_identity = extract_receipt_identity([
        " ".join(str(token.get("text") or "") for token in row) for row in rows
    ])
    item_token_ids = {id(token) for row in item_rows for token in row}
    for row in rows:
        value = " ".join(str(token.get("text") or "") for token in row)
        category = ("phone" if _PHONE.search(value) or _PHONE_CONTEXT.search(value)
                    else "context" if _PERSON_CONTEXT.search(value) or _TRANSACTION_CONTEXT.search(value)
                    else None)
        if category:
            # Names and payment references can span several OCR tokens on the
            # same physical row; redact the entire row, but not adjacent items.
            for token in row:
                boxes.append(_rect(token["box"], width, height))
            counts[category] += 1
            continue
        # Bare long values remain conservative, but EAN-13 and GS1 in-store
        # variable codes (especially those on barcode/price rows) are public
        # product data.
        for token in row:
            token_text = str(token.get("text") or "")
            for match in _LONG_NUMBER.finditer(token_text):
                digits = re.sub(r"\D", "", match.group())
                if (_is_ean13(digits) or _ITEM_CODE_CONTEXT.search(value)
                        or (_is_instore_variable_code(digits) and not _is_payment_card(digits))
                        or (id(token) in item_token_ids and not _is_payment_card(digits))):
                    continue
                boxes.append(_rect(token["box"], width, height))
                counts["long_number"] += 1
    for box in machine_boxes:
        boxes.append(_rect(list(box), width, height))
        counts["machine_code"] += 1
    for item_row in item_rows:
        for token in item_row:
            item_rect = _rect(token["box"], width, height)
            if any(_overlap_share(item_rect, mask) > 0.2 for mask in boxes):
                raise RedactionError("Redaction would obscure receipt item data")
    for x1, y1, x2, y2 in boxes:
        cv2.rectangle(image, (x1, y1), (x2, y2), (0, 0, 0), thickness=-1)
    cv2.rectangle(image, (0, 0), (width - 1, item_start), (255, 255, 255), thickness=-1)
    cv2.rectangle(image, (0, item_end), (width - 1, height - 1), (255, 255, 255), thickness=-1)
    # Small receipt fonts can lose characters after a second lossy encode.
    ok, encoded = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 98])
    if not ok or not encoded.size:
        raise RedactionError("Masked image cannot be encoded")
    result = encoded.tobytes()
    if cv2.imdecode(np.frombuffer(result, np.uint8), cv2.IMREAD_COLOR) is None:
        raise RedactionError("Masked image cannot be decoded")
    _verify_masked(result, width, height)
    # Reuse the original private pass. These fields stay on the internal
    # response and are never sent to a provider or logged as OCR text.
    permitted_rows = {index + 1 for index, row in enumerate(rows)
                      if all(id(token) in item_token_ids for token in row)}
    purchases = [
        {"name": item.name, "qty": item.qty, "unit": item.unit, "price_rm": item.price_rm,
         "price_basis": item.price_basis, "source_row_ids": item.source_row_ids}
        for item in parse_receipt_lines([" ".join(str(token.get("text") or "") for token in row) for row in rows])
        if set(item.source_row_ids) <= permitted_rows
        and not (_PERSON_CONTEXT.search(item.name) or _TRANSACTION_CONTEXT.search(item.name)
                 or _PHONE_CONTEXT.search(item.name) or _PHONE.search(item.name))
    ]
    return RedactedReceipt(result, width, height, hashlib.sha256(result).hexdigest(), counts, local_identity, purchases[:300])
