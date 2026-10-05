"""Deterministic conversion of PaddleOCR text boxes into receipt drafts."""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation
from statistics import median

from .models import ReceiptIdentity, ReceiptLine
from packages.receipt_purchase_rules import is_receipt_metadata


PRICE_AT_END = re.compile(r"(?<!\d)(\d+(?:\.\d{2}))(?:\s*[A-Za-z]|\s+\d[A-Za-z]?)?\s*$")
LEADING_BARCODE = re.compile(r"^\s*\d{7,}(?:\s+)?")
TAX_RATE_ROW = re.compile(r"^\s*\d+(?:\.\d+)?%")
TAX_AMOUNT_ROW = re.compile(r"^\s*(?:GST|SST)\s+\d+\.\d{2}\s*$", re.IGNORECASE)
BARCODE_PRICE_ROW = re.compile(
    r"^\s*\d{7,}\s*uni[t1il]*\s+1\s*(?:x|×|[^\d\s])\s*"
    r"\d+\.\d{2}\s+(?P<price>\d+\.\d{2})\s*$",
    re.IGNORECASE,
)
PREFIXED_BARCODE_PRICE_ROW = re.compile(
    r"^\s*1\s*(?:x|×|[^\d\s])\s*\d{7,}(?:\s*(?P<name>.*?))?\s+"
    r"(?P<price>\d+\.\d{2})\s*$",
    re.IGNORECASE,
)
DISCOUNT_AMOUNT = re.compile(r"(?:-|–)\s*(?P<amount>\d+\.\d{2})\s*$")
TRAILING_ITEM_COUNT = re.compile(r"\s*\*+\s*\d+\s*$")
QTY_AND_UNIT = re.compile(
    r"\b(\d+(?:\.\d+)?)\s*(kg|gm|g|l|ml|pcs?|pack|pkt|biji|unit)\b",
    re.IGNORECASE,
)
QUANTITY_MULTIPLIER_ONLY = re.compile(
    r"^(?P<qty>\d+(?:\.\d+)?)\s*(?P<unit>kg|gm|g|l|ml|pcs?|pkt|pack)?\s*"
    r"[x×]\s*\d+(?:\.\d{2})?$", re.IGNORECASE,
)
# Weighed-item price rows print unit first, then weight x unit price
# (Jaya Grocer: "2107369001126 KG 0.456x24.70 11.26"). The leading 13-digit
# in-store code is a product identifier, never a quantity.
WEIGHED_UNIT_PRICE = re.compile(
    r"\b(kg|gm|g)\b[\s:]{0,4}(?<![\d./])(\d+(?:\.\d+)?)\s*[x×]\s*\d+\.\d{2}\s*$",
    re.IGNORECASE,
)
NON_FOOD_PREFIXES = (
    "total",
    "grand total",
    "amount due",
    "jumlah besar",
    "subtotal",
    "sub total",
    "cash",
    "change",
    "balance",
    "visa",
    "mastercard",
    "debit",
    "credit",
    "mydebit",
    "rounding",
    "duitnow",
    "item ",
    "qty ",
    "saving",
    "amex",
    "approcode",
    "auth code",
    "my lotus",
    "sign up",
    "thank",
    "barcode ",
    "wechat",
    "unionpay",
)
NON_FOOD_WORDS = (
    "plastic bag", "shopping bag", "carrier bag", "pp hoven bag", "pp woven bag",
)
NON_FOOD_CHARGES = re.compile(
    r"^(?:(?:gst|sst)\b(?=\s*(?:\d+(?:\.\d+)?%|tax\b|amount\b))|"
    r"sales\s+(?:and\s+service\s+)?tax|service\s+(?:tax|charge)|"
    r"membership\s+(?:fee|charge)|member\s+(?:fee|charge))\b",
    re.IGNORECASE,
)
NON_FOOD_PAYMENT = re.compile(
    r"^(?:fp\s+group\s+app\s*\$|paid\s+by\s+\S+|payment\s+via\s+\S+|"
    r"eligible\s*:\s*(?:union|fp)(?:/\s*(?:union|fp))?\s+mbr\s+benefit\b)",
    re.IGNORECASE,
)
# Receipts sometimes glue the time straight onto the year ("17/09/202619:11:31").
_DATE = re.compile(r"(?<!\d)(\d{1,4})[./-](\d{1,2})[./-](\d{2,4})(?=\d{1,2}:\d{2}|[^\d]|$)")
# A 4-digit year may immediately precede the time in the glued form.
_TIME = re.compile(r"(?:(?<!\d)|(?<=\d{4}))(\d{1,2}):(\d{2})(?::(\d{2}))?\s*(AM|PM)?\b", re.IGNORECASE)
_RECEIPT_NUMBER = re.compile(
    r"\b(?:receipt|resit|invoice|inv|bill|transaction|trans|trx|order)\s*"
    r"(?:no\.?|number|id|#)?\s*[:#-]?\s*([A-Z0-9][A-Z0-9/-]{3,39})\b",
    re.IGNORECASE,
)
_TOTAL_LABEL = re.compile(
    r"^(?:grand\s+total|total(?:\s+sales)?(?:\s+incl\s+(?:svc\s+)?tax)?|"
    r"amount\s+due|jumlah\s+besar)\b(?!\s+(?:items?|qty|savings?))",
    re.IGNORECASE,
)
_IDENTITY_SKIP_MERCHANT = re.compile(
    r"\b(?:receipt|resit|invoice|tax|bill|cashier|staff|operator|tel|phone|"
    r"address|jalan|jln|lot|date|time|total|sst|gst|customer|member|"
    r"transaction|register|terminal|welcome|thank)\b",
    re.IGNORECASE,
)
ROW_TOLERANCE_PX = 14


def token_coordinates(token: dict) -> tuple[float, float]:
    """Return the top-left coordinate of one PaddleOCR token."""
    box = token.get("box")
    if not isinstance(box, list) or len(box) < 2:
        return 0.0, 0.0
    return float(box[0]), float(box[1])


def _polygon_slope(token: dict) -> float | None:
    """Return the left-to-right text slope when Paddle provides a polygon."""
    polygon = token.get("polygon")
    if not isinstance(polygon, list) or len(polygon) < 2:
        return None
    first, second = polygon[0], polygon[1]
    if not (
        isinstance(first, list)
        and isinstance(second, list)
        and len(first) >= 2
        and len(second) >= 2
    ):
        return None
    dx = float(second[0]) - float(first[0])
    if abs(dx) < 1:
        return None
    slope = (float(second[1]) - float(first[1])) / dx
    return slope if abs(slope) <= 0.35 else None


def _receipt_skew_slope(tokens: list[dict]) -> float:
    """Estimate page skew from OCR word polygons, conservatively."""
    slopes = [slope for token in tokens if (slope := _polygon_slope(token)) is not None]
    return float(median(slopes)) if len(slopes) >= 2 else 0.0


def order_ocr_tokens(tokens: list[dict]) -> list[str]:
    """Combine detected words into visual rows in deterministic reading order."""
    tokens = unique_ocr_detections(tokens)
    rows: dict[int, list[tuple[float, str]]] = defaultdict(list)
    skew_slope = _receipt_skew_slope(tokens)
    ordered_tokens = sorted(
        (
            (
                (
                    token_coordinates(token)[0],
                    token_coordinates(token)[1] - skew_slope * token_coordinates(token)[0],
                ),
                str(token.get("text") or "").strip(),
            )
            for token in tokens
        ),
        key=lambda item: (item[0][1], item[0][0]),
    )
    current_row = -1
    current_y: float | None = None
    for (x, y), text in ordered_tokens:
        if not text:
            continue
        if current_y is None or abs(y - current_y) > ROW_TOLERANCE_PX:
            current_row += 1
            current_y = y
        rows[current_row].append((x, text))
    return [
        " ".join(text for _, text in sorted(row_tokens))
        for _, row_tokens in sorted(rows.items())
    ]


def unique_ocr_detections(tokens: list[dict]) -> list[dict]:
    """Suppress repeated detection of the same text at the same location.

    Text or food identity alone cannot prove duplication: two printed chicken
    purchases must survive. Without usable geometry, keep the detection.
    """
    kept: list[dict] = []
    boxes_by_text: dict[str, list[list]] = defaultdict(list)
    for token in tokens:
        text = " ".join(str(token.get("text") or "").casefold().split())
        box = token.get("box")
        if not isinstance(box, list) or len(box) < 4 or box[2] <= box[0] or box[3] <= box[1]:
            kept.append(token)
            continue
        area = (box[2] - box[0]) * (box[3] - box[1])
        duplicate = False
        for previous in boxes_by_text[text]:
            overlap = max(0, min(box[2], previous[2]) - max(box[0], previous[0])) * max(
                0, min(box[3], previous[3]) - max(box[1], previous[1])
            )
            previous_area = (previous[2] - previous[0]) * (previous[3] - previous[1])
            if overlap / (area + previous_area - overlap) >= 0.85:
                duplicate = True
                break
        if not duplicate:
            kept.append(token)
            boxes_by_text[text].append(box)
    return kept


def normalized_row(value: str) -> str:
    return " ".join(re.sub(r"[^\w]+", " ", value.lower()).split())


def is_non_food_row(value: str) -> bool:
    normalized = normalized_row(value)
    return (
        TAX_RATE_ROW.match(value.strip()) is not None
        or TAX_AMOUNT_ROW.match(value.strip()) is not None
        or NON_FOOD_CHARGES.match(value.strip()) is not None
        or NON_FOOD_PAYMENT.match(value.strip()) is not None
        or " card" in f" {normalized} "
        or is_receipt_metadata(value)
        or any(
            word in normalized for word in NON_FOOD_WORDS
        )
    )


def _unique_date(rows: list[str]) -> str | None:
    values: set[str] = set()
    for row in rows:
        for match in _DATE.finditer(row):
            first, middle, last = match.groups()
            try:
                if len(first) == 4:
                    parsed = date(int(first), int(middle), int(last))
                else:
                    year = int(last) + (2000 if len(last) == 2 else 0)
                    parsed = date(year, int(middle), int(first))
            except ValueError:
                continue
            if 2020 <= parsed.year <= 2100:
                values.add(parsed.isoformat())
    return next(iter(values)) if len(values) == 1 else None


def _unique_time(rows: list[str]) -> str | None:
    values: set[str] = set()
    for row in rows:
        for match in _TIME.finditer(row):
            hour, minute, second, period = match.groups()
            h, m, s = int(hour), int(minute), int(second or 0)
            if period:
                if not 1 <= h <= 12:
                    continue
                h = (h % 12) + (12 if period.upper() == "PM" else 0)
            if h <= 23 and m <= 59 and s <= 59:
                values.add(f"{h:02d}:{m:02d}:{s:02d}")
    return next(iter(values)) if len(values) == 1 else None


def extract_receipt_identity(rows: list[str]) -> ReceiptIdentity | None:
    """Extract a *strict* identity locally; never guess missing duplicate keys.

    This metadata is returned only to the private API. The cloud model still
    receives only the item-band image with header and footer masked away.
    """
    item_rows = {row_id for line in parse_receipt_lines(rows) for row_id in line.source_row_ids}
    if not item_rows:
        return None
    first_item = min(item_rows)
    merchant = next((
        row.strip() for row in rows[: first_item - 1]
        if 3 <= len(row.strip()) <= 80
        and sum(char.isalpha() for char in row) >= 3
        and not PRICE_AT_END.search(row)
        and not _IDENTITY_SKIP_MERCHANT.search(row)
        and not _DATE.search(row)
    ), None)
    metadata_rows = [row for index, row in enumerate(rows, 1) if index not in item_rows]
    numbers = {
        match.group(1).upper()
        for row in metadata_rows
        for match in _RECEIPT_NUMBER.finditer(row)
        if any(char.isdigit() for char in match.group(1))
        # "Invoice 25/09/2026" is a date, not a stable transaction number.
        # A missing number must disable logical dedup rather than invent one.
        and _DATE.fullmatch(match.group(1)) is None
        # Pure 13+ digit runs are barcodes; alphanumeric invoice numbers with
        # letter prefixes (Jaya Grocer "JGSG2626019002345") are stable IDs.
        and not re.fullmatch(r"[\d\s/.-]*\d{13}[\d\s/.-]*", match.group(1))
    }
    totals: set[Decimal] = set()
    for row in metadata_rows:
        if not _TOTAL_LABEL.match(row.strip()):
            continue
        amount = PRICE_AT_END.search(row.strip())
        if amount is None:
            continue
        try:
            total = Decimal(amount.group(1))
        except InvalidOperation:
            continue
        if Decimal("0") <= total <= Decimal("9999999999.99"):
            totals.add(total)
    parsed_date = _unique_date(metadata_rows)
    parsed_time = _unique_time(metadata_rows)
    if not (merchant and len(numbers) == 1 and len(totals) == 1 and parsed_date and parsed_time):
        return None
    return ReceiptIdentity(
        merchant=merchant, date=parsed_date, time=parsed_time,
        receipt_number=next(iter(numbers)), total=str(next(iter(totals))),
    )


def remove_leading_barcode(value: str) -> str:
    """Drop barcode digits that PaddleOCR placed before a product label."""
    return LEADING_BARCODE.sub("", value).strip()


def barcode_price(value: str) -> float | None:
    """Return a price from a barcode/UNIT row, if it is a retail line item."""
    match = BARCODE_PRICE_ROW.match(value)
    return float(match.group("price")) if match else None


def prefixed_barcode_price(value: str) -> tuple[str | None, float] | None:
    """Read a common row layout: ``1x<barcode> [name] <line total>``."""
    match = PREFIXED_BARCODE_PRICE_ROW.match(value)
    if match is None:
        return None
    name = clean_product_name(str(match.group("name") or "")) or None
    return name, float(match.group("price"))


def discount_amount(value: str) -> float | None:
    """Return an immediate line-item discount, never a standalone purchase."""
    normalized = normalized_row(value)
    if not normalized.startswith(("disc", "discount", "promo")):
        return None
    match = DISCOUNT_AMOUNT.search(value)
    return float(match.group("amount")) if match else None


def clean_product_name(value: str) -> str:
    """Remove a printed count suffix without changing the OCR label itself."""
    return TRAILING_ITEM_COUNT.sub("", value).strip()


def looks_like_product_name(value: str) -> bool:
    """Keep plausible descriptions while waiting for their barcode/price row."""
    letters = sum(character.isalpha() for character in value)
    return letters >= 4 and not is_non_food_row(value)


def parse_receipt_lines(rows: list[str]) -> list[ReceiptLine]:
    """Create conservative item drafts from OCR rows; uncertain rows are omitted."""
    lines: list[ReceiptLine] = []
    pending_name: str | None = None
    pending_price: float | None = None
    last_line: ReceiptLine | None = None
    pending_row_id: int | None = None
    for row_id, row in enumerate(rows, 1):
        clean_row = " ".join(row.split())
        if not clean_row:
            pending_name = None
            pending_price = None
            continue
        discount = discount_amount(clean_row)
        if discount is not None:
            if last_line and last_line.price_rm is not None:
                adjusted_price = round(last_line.price_rm - discount, 2)
                if adjusted_price >= 0:
                    last_line.price_rm = adjusted_price
            pending_name = None
            pending_price = None
            continue
        if is_non_food_row(clean_row):
            pending_name = None
            pending_price = None
            continue
        prefixed_item = prefixed_barcode_price(clean_row)
        if prefixed_item is not None:
            item_name, item_price = prefixed_item
            pending_name = None
            if item_name:
                last_line = ReceiptLine(
                    name=item_name,
                    source_row_ids=[row_id],
                    qty=1.0,
                    unit="pcs",
                    price_rm=item_price,
                )
                lines.append(last_line)
                pending_price = None
            else:
                pending_price = item_price
                pending_row_id = row_id
            continue
        paired_price = barcode_price(clean_row)
        if paired_price is not None:
            if pending_name:
                last_line = ReceiptLine(
                    name=pending_name,
                    source_row_ids=[pending_row_id, row_id],
                    qty=1.0,
                    unit="pcs",
                    price_rm=paired_price,
                )
                lines.append(last_line)
            pending_name = None
            pending_price = None
            continue
        price_match = PRICE_AT_END.search(clean_row)
        if price_match is None:
            if pending_price is not None and looks_like_product_name(clean_row):
                last_line = ReceiptLine(
                    name=clean_product_name(clean_row),
                    source_row_ids=[pending_row_id, row_id],
                    price_basis="BARCODE_PRICE_BEFORE_NAME" if pending_row_id + 1 == row_id else None,
                    qty=1.0,
                    unit="pcs",
                    price_rm=pending_price,
                )
                lines.append(last_line)
                pending_price = None
                continue
            if looks_like_product_name(clean_row):
                pending_name = clean_product_name(clean_row)
                pending_row_id = row_id
            continue
        price_rm = float(price_match.group(1))
        # Leading barcode digits (glued unit suffix included) are product
        # codes, never quantities; strip them before any quantity reading.
        item_text = remove_leading_barcode(clean_row[: price_match.start()].strip())
        weighed = WEIGHED_UNIT_PRICE.search(item_text)
        qty_match = None if weighed else QTY_AND_UNIT.search(item_text)
        qty = float(weighed.group(2)) if weighed else (float(qty_match.group(1)) if qty_match else None)
        unit = weighed.group(1).lower() if weighed else (qty_match.group(2).lower() if qty_match else None)
        multiplier_only = None if weighed else QUANTITY_MULTIPLIER_ONLY.fullmatch(item_text)
        if multiplier_only and multiplier_only.group("unit"):
            qty = float(multiplier_only.group("qty"))
            unit = multiplier_only.group("unit").lower()
        if unit == "gm":
            unit = "g"
        if weighed is not None:
            item_text = (item_text[: weighed.start()] + item_text[weighed.end():]).strip()
        elif qty_match:
            item_text = (item_text[: qty_match.start()] + item_text[qty_match.end() :]).strip()
            # Same-row package size + explicit outer pack count establishes
            # a total; private dimensional evidence always denotes that total.
            outer_count = re.search(r"\b(\d+)\s*(?:packs?|pkts?)\b", item_text, re.I)
            if unit in {"kg", "g", "l", "ml"} and outer_count and 1 <= int(outer_count[1]) <= 20:
                qty *= int(outer_count[1])
                item_text = (item_text[:outer_count.start()] + item_text[outer_count.end():]).strip()
        name = remove_leading_barcode(" ".join(item_text.split()))
        source_row_ids = [row_id]
        if pending_name and (multiplier_only or weighed or sum(character.isalpha() for character in name) < 3):
            name = pending_name
            source_row_ids = [pending_row_id, row_id]
        if sum(character.isalpha() for character in name) < 3:
            if weighed is not None and last_line is not None:
                # A bare weighed-price row after a named item is a second
                # weighed purchase of that same product (never a new name).
                name = last_line.name
                source_row_ids = [row_id]
            else:
                pending_name = None
                pending_price = None
                continue
        if not name or len(name) > 120:
            continue
        last_line = ReceiptLine(name=name, qty=qty, unit=unit, price_rm=price_rm, source_row_ids=source_row_ids)
        lines.append(last_line)
        pending_name = None
        pending_price = None
    return lines
