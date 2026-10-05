"""WiseBasket local inference service: PaddleOCR receipt extraction."""

from __future__ import annotations

import asyncio
import base64

from fastapi import FastAPI, HTTPException

from . import receipt_service
from .receipt_redaction import RedactionError, redact_receipt
from .models import (
    HealthResponse,
    ReceiptExtractRequest,
    ReceiptExtractResponse,
    ReceiptRedactRequest,
    ReceiptRedactResponse,
)

app = FastAPI(title="WiseBasket Inference", version="0.1.0")


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        paddle_loaded=receipt_service.paddle_loaded(),
    )


@app.post("/receipt/extract", response_model=ReceiptExtractResponse)
async def extract(req: ReceiptExtractRequest) -> ReceiptExtractResponse:
    result = await receipt_service.extract_receipt(req.image_base64, hint=req.hint)
    if result.error and result.error.startswith("busy"):
        raise HTTPException(429, result.error, headers={"Retry-After": "2"})
    return result


@app.post("/receipt/redact", response_model=ReceiptRedactResponse)
async def redact(req: ReceiptRedactRequest) -> ReceiptRedactResponse:
    if receipt_service.extract_lock.locked():
        raise HTTPException(429, "busy", headers={"Retry-After": "2"})
    try:
        original = receipt_service.decode_image(req.image_base64)
    except Exception as exc:
        raise HTTPException(422, "invalid image") from exc
    async with receipt_service.extract_lock:
        try:
            result = await asyncio.to_thread(redact_receipt, original, req.profile)
        except RedactionError as exc:
            raise HTTPException(422, str(exc)) from exc
    return ReceiptRedactResponse(
        image_base64=base64.b64encode(result.image_bytes).decode("ascii"),
        policy_version="item-band-v2",
        width=result.width, height=result.height, sha256=result.sha256,
        mask_counts=result.mask_counts,
        identity=result.identity,
        purchase_lines=result.purchase_lines,
    )
