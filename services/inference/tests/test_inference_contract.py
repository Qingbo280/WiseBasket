"""Public contract tests for the PaddleOCR inference service."""

import base64
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import receipt_service  # noqa: E402
from app.main import app  # noqa: E402
from app.models import HealthResponse, ReceiptExtractResponse  # noqa: E402


IMAGE_B64 = base64.b64encode(b"\xff\xd8" + b"test-image" * 10).decode()


@pytest.mark.asyncio
async def test_extract_rejects_invalid_base64():
    result = await receipt_service.extract_receipt("!!!not-base64!!!")

    assert result.error and result.error.startswith("invalid image")


@pytest.mark.asyncio
async def test_extract_busy_rejected_without_running_paddle():
    async with receipt_service.extract_lock:
        result = await receipt_service.extract_receipt(IMAGE_B64)
        assert result.error and result.error.startswith("busy")


def test_receipt_endpoint_returns_http_429_while_busy(monkeypatch):
    async def return_busy(image_base64, hint=None):
        return ReceiptExtractResponse(error="busy: another receipt is being processed, retry later")

    monkeypatch.setattr(receipt_service, "extract_receipt", return_busy)

    response = TestClient(app).post("/receipt/extract", json={"image_base64": IMAGE_B64})

    assert response.status_code == 429


def test_health_contract_describes_paddle_backend():
    health = HealthResponse()

    assert health.receipt_backend == "paddleocr"
    assert health.status == "ok"
    assert health.paddle_loaded is False
