"""Provider-independent, deliberately conservative receipt extraction contract."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field, field_validator
from packages.receipt_purchase_rules import is_receipt_metadata


def _amount(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        result = Decimal(str(value).replace(",", "").replace("RM", "").strip())
    except (ValueError, ArithmeticError):
        return None
    if not result.is_finite() or result < 0 or result > Decimal("9999999999.99"):
        return None
    return result


class ReceiptHeader(BaseModel):
    merchant: str | None = Field(default=None, max_length=240)
    date: str | None = Field(default=None, max_length=32)
    time: str | None = Field(default=None, max_length=32)
    receipt_number: str | None = Field(default=None, max_length=120)
    currency: str | None = Field(default=None, max_length=8)
    total: Decimal | None = None

    @field_validator("total", mode="before")
    @classmethod
    def valid_total(cls, value: Any) -> Decimal | None:
        return _amount(value)


class ExtractedLine(BaseModel):
    name_raw: str = Field(min_length=1, max_length=240)
    # A model's interpretation is a review/ranking hint, never proof of identity.
    name_expanded: str | None = Field(default=None, max_length=240)
    quantity: Decimal | None = None
    unit: str | None = Field(default=None, max_length=24)
    unit_price: Decimal | None = None
    line_total: Decimal | None = None
    confidence: Decimal | None = None
    source_order: int | None = Field(default=None, ge=0, le=10000)

    @field_validator("name_expanded", mode="before")
    @classmethod
    def valid_expansion(cls, value: Any) -> str | None:
        if not isinstance(value, str):
            return None
        value = value.strip()
        return value or None

    @field_validator("quantity", "unit_price", "line_total", mode="before")
    @classmethod
    def valid_number(cls, value: Any) -> Decimal | None:
        return _amount(value)

    @field_validator("unit", mode="before")
    @classmethod
    def valid_unit(cls, value: Any) -> Any:
        # Retailers use GM for grams. Normalize the spelling only; do not
        # derive purchased mass from product names or multiply multipacks.
        return "g" if isinstance(value, str) and value.strip().casefold() == "gm" else value

    @field_validator("confidence", mode="before")
    @classmethod
    def valid_confidence(cls, value: Any) -> Decimal | None:
        result = _amount(value)
        return result if result is not None and result <= 1 else None


class ReceiptExtraction(BaseModel):
    header: ReceiptHeader = Field(default_factory=ReceiptHeader)
    lines: list[ExtractedLine] = Field(default_factory=list, max_length=300)
    provider: str = Field(max_length=32)
    requested_model: str = Field(max_length=120)
    returned_model: str | None = Field(default=None, max_length=120)
    prompt_tokens: int | None = Field(default=None, ge=0)
    completion_tokens: int | None = Field(default=None, ge=0)
    latency_ms: int | None = Field(default=None, ge=0)

    @field_validator("lines")
    @classmethod
    def purchase_rows_only(cls, lines: list[ExtractedLine]) -> list[ExtractedLine]:
        # Shared across DeepSeek, Kimi and Azure; a provider prompt alone
        # cannot enforce that totals, payment and tax rows are not purchases.
        return [line for line in lines if not is_receipt_metadata(line.name_raw)]


def quality_score(extraction: ReceiptExtraction) -> Decimal:
    """Six fixed components; score is for retry/ranking, never confirmation."""
    lines = extraction.lines
    if not lines:
        return Decimal("0")
    valid = [line for line in lines if line.name_raw.strip() and line.line_total is not None]
    if not valid:
        return Decimal("0")
    valid_rate = Decimal(len(valid)) / Decimal(len(lines))
    numeric_fields = sum(line.quantity is not None for line in valid) + sum(line.unit_price is not None for line in valid) + len(valid)
    numeric_rate = Decimal(numeric_fields) / Decimal(3 * len(valid))
    header = extraction.header
    header_rate = Decimal(sum(bool(value) for value in (
        header.merchant, header.date, header.time, header.receipt_number, header.currency, header.total is not None,
    ))) / Decimal(6)
    amount_sum = sum((line.line_total for line in valid), Decimal(0))
    total_ok = header.total is not None and abs(amount_sum - header.total) <= Decimal("0.05")
    # Coverage is only a weak proxy without a gold set; no score can prove recall.
    coverage = min(Decimal(len(valid)) / Decimal(5), Decimal(1))
    keys = [(line.name_raw.casefold().strip(), line.line_total) for line in valid]
    duplicate_rate = Decimal(len(keys) - len(set(keys))) / Decimal(len(keys))
    result = (Decimal("0.35") * valid_rate + Decimal("0.20") * numeric_rate
              + Decimal("0.15") * header_rate + Decimal("0.15") * int(total_ok)
              + Decimal("0.10") * coverage + Decimal("0.05") * (1 - duplicate_rate))
    return result.quantize(Decimal("0.0001"))


def masked_item_quality_score(extraction: ReceiptExtraction) -> Decimal:
    """Retry signal for item-band-v2, where header/total are deliberately hidden.

    The ordinary quality score includes header and receipt-total checks and
    therefore tops out near 0.70 on a correctly redacted image. Using its old
    0.75 retry gate always consumed the second paid call even for complete
    product rows. This score considers only reviewable purchase-row quality.
    """
    lines = extraction.lines
    if not lines:
        return Decimal("0")
    valid = [line for line in lines if line.name_raw.strip() and line.line_total is not None]
    if not valid:
        return Decimal("0")
    valid_rate = Decimal(len(valid)) / Decimal(len(lines))
    numeric_fields = sum(line.quantity is not None for line in valid) + sum(
        line.unit_price is not None for line in valid
    ) + len(valid)
    numeric_rate = Decimal(numeric_fields) / Decimal(3 * len(valid))
    keys = [(line.name_raw.casefold().strip(), line.line_total) for line in valid]
    duplicate_rate = Decimal(len(keys) - len(set(keys))) / Decimal(len(keys))
    result = (Decimal("0.60") * valid_rate + Decimal("0.30") * numeric_rate
              + Decimal("0.10") * (1 - duplicate_rate))
    return result.quantize(Decimal("0.0001"))


def choose_extraction(first: ReceiptExtraction, second: ReceiptExtraction | None) -> ReceiptExtraction:
    """Never merge two guesses; exact quality ties keep the first attempt."""
    return second if second is not None and quality_score(second) > quality_score(first) else first
