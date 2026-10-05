"""Request/response contracts for the PaddleOCR receipt service."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class ReceiptExtractRequest(BaseModel):
    # base64-encoded receipt photo (JPEG/PNG), already cropped/redacted upstream.
    image_base64: str = Field(..., min_length=64)
    # Optional free-text hint, e.g. store name or expected language mix.
    hint: Optional[str] = Field(default=None, max_length=256)


class ReceiptRedactRequest(BaseModel):
    image_base64: str = Field(..., min_length=64)
    profile: str = Field(default="normal", pattern="^(normal|enhanced)$")


class ReceiptIdentity(BaseModel):
    """Private OCR-derived duplicate key; absent unless every field is clear."""

    merchant: str = Field(min_length=3, max_length=80)
    date: str = Field(max_length=10)
    time: str = Field(max_length=8)
    receipt_number: str = Field(min_length=4, max_length=40)
    total: str = Field(max_length=13)


class ReceiptQuantityEvidence(BaseModel):
    """Internal purchase evidence only; no receipt header or personal data."""
    name: str = Field(max_length=240)
    qty: Optional[float] = None
    unit: Optional[str] = Field(default=None, max_length=24)
    price_rm: Optional[float] = None
    price_basis: Optional[str] = None
    source_row_ids: List[int] = Field(default_factory=list)


class ReceiptRedactResponse(BaseModel):
    image_base64: str
    mime_type: str = "image/jpeg"
    policy_version: str
    width: int
    height: int
    sha256: str
    mask_counts: dict[str, int]
    # Internal-only metadata from the private OCR pass; never sent to cloud.
    identity: Optional[ReceiptIdentity] = None
    purchase_lines: List[ReceiptQuantityEvidence] = Field(default_factory=list, max_length=300)


class ReceiptLine(BaseModel):
    name: str
    source_row_ids: List[int] = Field(default_factory=list)
    price_basis: Optional[str] = None
    # OCR model's abbreviation expansion of `name` ("AUS CH OY BL GF" ->
    # "Australian chilled oyster blade beef"); None when unsure. Used for
    # semantic matching only — the printed name stays authoritative for display.
    expanded_name: Optional[str] = None
    qty: Optional[float] = None
    unit: Optional[str] = None  # e.g. "kg", "g", "pcs", "pack"
    price_rm: Optional[float] = None
    confidence: Optional[str] = None  # "high" | "medium" | "low"


class ReceiptExtractResponse(BaseModel):
    model: str = "paddleocr-local"
    lines: List[ReceiptLine] = Field(default_factory=list)
    identity: Optional[ReceiptIdentity] = None
    raw_text: str = ""  # model output before normalisation (audit/debug)
    error: Optional[str] = None  # set when extraction failed fail-closed


class HealthResponse(BaseModel):
    status: str = "ok"
    paddle_loaded: bool = False
    receipt_backend: str = "paddleocr"
