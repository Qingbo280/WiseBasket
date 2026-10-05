"""Contract tests for the PaddleOCR-backed receipt extraction adapter."""

import base64
import sys
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import receipt_service  # noqa: E402


IMAGE_B64 = base64.b64encode(b"\xff\xd8\xff test-image").decode()


@pytest.mark.asyncio
async def test_extract_receipt_converts_paddle_tokens_to_review_lines(monkeypatch):
    monkeypatch.setattr(
        receipt_service,
        "extract_paddle_tokens",
        lambda image_bytes: [
            {"text": "BAWANG MERAH", "box": [10, 100, 160, 120]},
            {"text": "1.38", "box": [180, 100, 220, 120]},
        ],
    )

    result = await receipt_service.extract_receipt(IMAGE_B64)

    assert result.error is None
    assert result.raw_text == "BAWANG MERAH 1.38"
    assert [(line.name, line.price_rm) for line in result.lines] == [
        ("BAWANG MERAH", 1.38),
    ]
    assert result.identity is None  # a product line cannot invent a duplicate key


@pytest.mark.asyncio
async def test_extract_receipt_returns_local_identity_without_exposing_it_as_item(monkeypatch):
    rows = [
        "PASAR RAYA MAJU", "RECEIPT NO: R-2048", "23/09/2026 12:17",
        "AYAM 12.50", "BAWANG MERAH 1.38", "TOTAL 13.88",
    ]
    monkeypatch.setattr(receipt_service, "extract_paddle_tokens", lambda _image: [
        {"text": row, "box": [10, index * 30, 220, index * 30 + 18]}
        for index, row in enumerate(rows)
    ])

    result = await receipt_service.extract_receipt(IMAGE_B64)

    assert result.identity is not None
    assert result.identity.receipt_number == "R-2048"
    assert result.identity.total == "13.88"
    assert [line.name for line in result.lines] == ["AYAM", "BAWANG MERAH"]


@pytest.mark.asyncio
async def test_extract_receipt_fails_closed_when_paddle_backend_is_unavailable(monkeypatch):
    def raise_backend_error(image_bytes):
        raise RuntimeError("PaddleOCR is unavailable")

    monkeypatch.setattr(receipt_service, "extract_paddle_tokens", raise_backend_error)

    result = await receipt_service.extract_receipt(IMAGE_B64)

    assert result.lines == []
    assert result.error == "ocr backend unavailable: PaddleOCR is unavailable"
