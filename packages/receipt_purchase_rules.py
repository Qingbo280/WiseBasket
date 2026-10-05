"""Pure receipt purchase evidence; prices never determine quantities."""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any

_NUMBER = r"(?:RM\s*)?[+\-]?\d+(?:[.,]\d+)?"
_SUMMARY = re.compile(r"^(?:grand\s+total|sub[ -]?total|total(?:\s+(?:sales|amount|due|items?))?|amount\s+due|jumlah\s+besar|rounding|cash|change|balance|discount|saving|debit|credit|payment|membership|(?:gst|sst)(?:\s+(?:tax|amount))?)(?:\s*[:=]?\s*(?:" + _NUMBER + r"%?\s*)*)$", re.I)
_META = re.compile(
    r"^(?:total\s+(?:\(\s*gst\s+incl\s*\)|sales\s+incl\s+svc\s+tax)(?:\s|$)|"
    r"(?:gst|sst)\s+(?:\(\s*\d+(?:\.\d+)?%\s*\)|reg\s+no\b)|"
    r"item\s+\d+\s+sub[ -]?total\b|quantity\s*:\s*\d+\s+units?\b|saving\s+[\d.]+\s+rounding\b|"
    r"wechat(?:cb)?(?:\s|$)|sales\s+(?:and\s+service\s+)?tax|service\s+(?:tax|charge)|"
    r"member(?:ship)?\s+(?:fee|charge|no\b|number\b|points\b)|"
    r"paid\s+by\b|payment\s+(?:via|method|received)\b|"
    r"(?:visa|mastercard|mydebit|amex|wechat|unionpay|duitnow)(?:\s|$)|"
    r"(?:[a-z]*\s+)?card\s+(?:\d|RM\b)|auth\s+code\b|approcode\b|"
    r"my\s+lotus['’]?s?\s+points\b|sign\s+up\s+now\b|thank[- ]?you\s+for\b|"
    r"fp\s+group\s+app\s*\$|eligible\s*:\s*(?:union|fp).*mbr\s+benefit\b|"
    r"barcode\s*[:#]|(?:item|qty)\s+(?:count|total)\b|"
    # Item/Qty tally rows ("Item 4", "Qty 3.9") are summary counts; OCR may
    # misread "Item" (e.g. "Iten"), so the subtotal check below is separate.
    r"(?:item|iten|qty)\s+\d+(?:\.\d+)?\s*(?:$|(?=\s+(?:sub|spec|disc|total))))", re.I,
)


def is_receipt_metadata(label: str) -> bool:
    """Exclude receipt summaries/payment, never a substring in a product name."""
    value = " ".join(label.split()).strip()
    return bool(_SUMMARY.fullmatch(value) or _META.match(value)
                or re.fullmatch(r"\d+(?:\.\d+)?%\s+\d.*", value)
                # A masked card PAN (``54567149****9108 MASTER``) is payment
                # evidence, never a product, wherever it sits in the row.
                or re.search(r"\d{3,}\s*\*{2,}\s*\d{2,}", value)
                # "SubTotal" never appears inside a genuine product name; an
                # OCR-misread prefix ("Iten 4 SubTotal") must not leak it in.
                or re.search(r"\bsub\s*-?\s*total\b", value, re.I))


def _decimal(value: Any) -> Decimal | None:
    try:
        number = Decimal(str(value).replace(",", "."))
    except (InvalidOperation, ValueError):
        return None
    return number if number.is_finite() and number > 0 else None


def printed_measure(label: str) -> tuple[Decimal, str] | None:
    """One printed mass/volume, with ambiguous inner multipacks left unknown."""
    label = re.sub(r"\s*\*+\s*1\s*$", "", label)
    # Product JAN4902105051108 is 425g TOTAL for five servings, not 5 x 425g.
    # https://www.nissin.com/jp/product/items/13426/
    verified = re.fullmatch(r"(?:\d{7,}\s+)?NISSIN\s+CHICKEN\s+RAMEN\s*5\s*P\s*X\s*425\s*G\s*", label, re.I)
    if not verified and re.search(r"\d\s*(?:P(?:ACKS?)?\s*)?[X×*]\s*\d|(?:KG|GM|G|ML|L)\s*[X×*]\s*\d", label, re.I):
        return None
    if re.search(r"(?:/|\bPER\b|@)\s*(?:\d+(?:[.,]\d+)?\s*)?(?:KG|GM|G|ML|L)\b|\b\d+(?:[.,]\d+)?\s*(?:KG|GM|G|ML|L)\s*(?:@|/|PER\b)", label, re.I):
        return None
    matches = list(re.finditer(r"(?<![\d.,])(\d+(?:[.,]\d+)?)\s*(KG|GM|G|ML|L)\b", label, re.I))
    if len(matches) != 1:
        return None
    amount = _decimal(matches[0][1])
    unit = matches[0][2].lower()
    if amount is None:
        return None
    amount *= Decimal("0.001") if unit in {"gm", "g", "ml"} else Decimal(1)
    return (amount, "l" if unit in {"ml", "l"} else "kg") if Decimal("0.005") <= amount <= 20 else None


def printed_egg_count(label: str) -> Decimal | None:
    if not re.search(r"\b(?:eggs?|telur)\b", label, re.I):
        return None
    match = re.search(r"(?:^|[^A-Z0-9])[A-D]?(\d{1,2})\s*(?:'?S|PCS?|BIJI)\b", label, re.I)
    return Decimal(match[1]) if match and 4 <= int(match[1]) <= 60 else None


def purchase_name_key(label: str) -> str:
    """Ignore packaging, retaining product words for private evidence alignment."""
    label = re.sub(r"(?<![\d.,])\d+(?:[.,]\d+)?\s*(?:kg|gm|g|ml|l)\b", " ", label, flags=re.I)
    words = [word for word in re.findall(r"[a-z0-9]+", label.lower())
             if not any(char.isdigit() for char in word) and word not in {"kg", "gm", "g", "ml", "l", "unit", "pc", "pcs", "pkt", "pack"}]
    return "".join(words)


def private_quantity_evidence(label: str, charge: Any, private_lines: list[dict]) -> tuple[Decimal, str] | None:
    """Require the same name and a unique quantity; charge only disambiguates.

    Two equal-price purchases with different weights must remain unknown.
    No quantity is calculated from either charge or catalogue prices.
    """
    key = purchase_name_key(label)
    if not key:
        return None
    matches = [row for row in private_lines if isinstance(row, dict)
               and purchase_name_key(str(row.get("name") or "")) == key]
    price = _decimal(charge)
    if price is not None:
        matches = [row for row in matches if _decimal(row.get("price_rm")) in {None, price}]
    if len(matches) > 1 and price is None:
        return None
    pairs = set()
    for row in matches:
        qty = _decimal(row.get("qty"))
        unit = str(row.get("unit") or "").lower()
        if qty is not None and unit in {"kg", "g", "gm", "l", "ml", "pc", "pcs", "pack", "pkt", "unit"}:
            pairs.add((qty, unit))
    return next(iter(pairs)) if len(pairs) == 1 else None


def ground_purchase_quantity(label: str, quantity: Any, unit: Any, charge: Any,
                             private_lines: list[dict] | None = None) -> tuple[Decimal | None, str | None]:
    """Only printed size/count or aligned private OCR can establish a mass.

    Cloud count fields remain reviewable count fields; a bare per-kg label
    never supports a mass, even when the provider supplies quantity=1.
    """
    private = private_quantity_evidence(label, charge, private_lines or [])
    qty = _decimal(quantity)
    raw_unit = str(unit or "").strip().lower()
    # Provider integers/count units alone cannot establish a stock mass.
    printed_count = re.search(r"\b(\d+)\s*(?:packs?|pkts?|units?|pcs?)\b", label, re.I)
    count = private[0] if private and private[1] in {"pack", "pkt", "unit", "pc", "pcs"} else _decimal(printed_count[1]) if printed_count else None
    count = count if count is not None and count == count.to_integral() and 1 <= count <= 20 else Decimal(1)
    if private and private[1] in {"kg", "g", "gm", "l", "ml"}:
        amount, private_unit = private
        return (amount / 1000, "kg" if private_unit in {"g", "gm"} else "l") if private_unit in {"g", "gm", "ml"} else private
    eggs = printed_egg_count(label)
    if eggs is not None:
        # 30 pcs is the carton content, while 2 packs means two cartons.
        outer_packs = re.search(r"\b(\d+)\s*(?:packs?|pkts?)\b", label, re.I)
        egg_multiplier = private[0] if private and private[1] in {"pack", "pkt"} else _decimal(outer_packs[1]) if outer_packs else Decimal(1)
        if egg_multiplier is None or egg_multiplier != egg_multiplier.to_integral() or not 1 <= egg_multiplier <= 20:
            egg_multiplier = Decimal(1)
        return eggs * egg_multiplier, "pcs"
    measure = printed_measure(label)
    if measure is not None:
        return measure[0] * count, measure[1]
    if private:
        return private
    if raw_unit in {"kg", "g", "gm", "gram", "grams", "kilogram", "kilograms", "l", "ml", "litre", "liter"}:
        return None, None
    return qty, raw_unit or None
