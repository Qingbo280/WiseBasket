"""Receipt OCR using PaddleOCR and deterministic receipt-row parsing."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import math
import tempfile
from typing import Any, Optional

from .models import ReceiptExtractResponse
from .paddle_receipt_parser import extract_receipt_identity, order_ocr_tokens, parse_receipt_lines


logger = logging.getLogger(__name__)

MAX_IMAGE_BYTES = 8 * 1024 * 1024
extract_lock = asyncio.Lock()
paddle_ocr: Any | None = None


def decode_image(image_base64: str) -> bytes:
    data = base64.b64decode(image_base64, validate=True)
    if len(data) > MAX_IMAGE_BYTES:
        raise ValueError("image too large (max 8MB)")
    return data


def load_paddle_ocr() -> Any:
    """Create one CPU OCR pipeline lazily after the service starts."""
    global paddle_ocr
    if paddle_ocr is not None:
        return paddle_ocr
    try:
        from paddleocr import PaddleOCR
    except ImportError as exc:
        raise RuntimeError("PaddleOCR package is not installed") from exc
    paddle_ocr = PaddleOCR(
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
        text_detection_model_name="PP-OCRv5_mobile_det",
        text_recognition_model_name="PP-OCRv5_mobile_rec",
        device="cpu",
    )
    return paddle_ocr


def result_payload(result: Any) -> dict[str, Any]:
    """Read PaddleOCR v3 result objects without binding to one result class."""
    value = getattr(result, "json", result)
    if callable(value):
        value = value()
    if isinstance(value, str):
        value = json.loads(value)
    if not isinstance(value, dict):
        raise RuntimeError("PaddleOCR returned an unsupported result")
    nested = value.get("res")
    return nested if isinstance(nested, dict) else value


def bounding_box(value: Any) -> list[float]:
    """Convert PaddleOCR's rectangle or polygon representation to four values."""
    if hasattr(value, "tolist"):
        value = value.tolist()
    if not isinstance(value, list) or not value:
        raise ValueError("PaddleOCR returned an invalid text location")
    if isinstance(value[0], list):
        points = value
        coordinates = [
            float(min(point[0] for point in points)),
            float(min(point[1] for point in points)),
            float(max(point[0] for point in points)),
            float(max(point[1] for point in points)),
        ]
    elif len(value) >= 4:
        coordinates = [float(value[0]), float(value[1]), float(value[2]), float(value[3])]
    else:
        raise ValueError("PaddleOCR returned an invalid text location")
    if (not all(math.isfinite(number) for number in coordinates)
            or coordinates[2] <= coordinates[0] or coordinates[3] <= coordinates[1]):
        raise ValueError("PaddleOCR returned an invalid text location")
    return coordinates


def polygon(value: Any) -> list[list[float]] | None:
    """Keep Paddle's quadrilateral so row grouping can compensate page skew."""
    if hasattr(value, "tolist"):
        value = value.tolist()
    if not isinstance(value, list) or len(value) < 2 or not isinstance(value[0], list):
        return None
    try:
        return [[float(point[0]), float(point[1])] for point in value if len(point) >= 2]
    except (TypeError, ValueError):
        return None


def extract_paddle_tokens(image_bytes: bytes) -> list[dict[str, Any]]:
    """Run PaddleOCR and return only recognised text and its visual location."""
    suffix = ".jpg" if image_bytes.startswith(b"\xff\xd8") else ".png"
    with tempfile.NamedTemporaryFile(suffix=suffix) as image_file:
        image_file.write(image_bytes)
        image_file.flush()
        results = list(load_paddle_ocr().predict(image_file.name))
    tokens: list[dict[str, Any]] = []
    for result in results:
        payload = result_payload(result)
        texts = payload.get("rec_texts") or []
        polygons = payload.get("rec_polys")
        if polygons is None:
            polygons = []
        boxes = payload.get("rec_boxes")
        if boxes is None or len(boxes) == 0:
            boxes = polygons
        logger.info(
            "PaddleOCR result fields=%s recognised_text_count=%d box_count=%d",
            sorted(payload.keys()),
            len(texts),
            len(boxes),
        )
        if len(texts) != len(boxes):
            raise ValueError("PaddleOCR text and location counts differ")
        for index, (text, box) in enumerate(zip(texts, boxes)):
            cleaned_text = str(text).strip()
            if cleaned_text:
                token = {"text": cleaned_text, "box": bounding_box(box)}
                if index < len(polygons):
                    token_polygon = polygon(polygons[index])
                    if token_polygon:
                        token["polygon"] = token_polygon
                tokens.append(token)
    return tokens


def paddle_loaded() -> bool:
    return paddle_ocr is not None


async def extract_receipt(
    image_base64: str, hint: Optional[str] = None
) -> ReceiptExtractResponse:
    """Return conservative draft lines; a failure never fabricates receipt data."""
    del hint
    if extract_lock.locked():
        return ReceiptExtractResponse(
            lines=[], error="busy: another receipt is being processed, retry later"
        )
    try:
        image_bytes = decode_image(image_base64)
    except Exception as exc:
        return ReceiptExtractResponse(lines=[], error=f"invalid image: {exc}")

    async with extract_lock:
        try:
            tokens = await asyncio.to_thread(extract_paddle_tokens, image_bytes)
        except Exception as exc:
            logger.warning("PaddleOCR request failed: %s", exc)
            return ReceiptExtractResponse(
                lines=[], error=f"ocr backend unavailable: {exc}"
            )
    rows = order_ocr_tokens(tokens)
    return ReceiptExtractResponse(
        lines=parse_receipt_lines(rows),
        identity=extract_receipt_identity(rows),
        raw_text="\n".join(rows),
    )
