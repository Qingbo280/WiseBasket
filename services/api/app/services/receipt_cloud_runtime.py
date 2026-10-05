"""Cloud receipt orchestration with private redaction and committed budget holds."""

from __future__ import annotations

import base64
import hashlib
import logging
import time
import uuid
from dataclasses import dataclass, field
from decimal import Decimal

import httpx

from ..config import Settings
from ..db import AsyncSessionLocal
from .receipt_cloud_budget import CloudBudgetUnavailable, reserve_receipt_cloud_call
from .receipt_cloud_contract import (
    ReceiptExtraction, ReceiptHeader, choose_extraction, masked_item_quality_score, quality_score,
)
from .receipt_cloud_providers import ProviderConfig, estimate_kimi_input_tokens, extract


log = logging.getLogger(__name__)


@dataclass(frozen=True)
class CloudReceiptResult:
    extraction: ReceiptExtraction
    private_header: ReceiptHeader | None
    private_purchase_lines: list[dict] = field(default_factory=list)


def _price_version_verified(settings: Settings, version: str) -> bool:
    """A single env value can acknowledge each independently priced provider."""
    return version in {part.strip() for part in settings.receipt_cloud_price_version.replace(";", ",").split(",")}


def _known_returned_model(result: ReceiptExtraction, settings: Settings) -> bool:
    """Reject an unknown routed model even though the cost hold remains spent."""
    if result.provider == "deepseek":
        return (_price_version_verified(settings, "deepseek-v4.1-flash-2026-09-10")
                and result.returned_model in {"deepseek-flash", "deepseek-v4.1-flash", "DeepSeek-V4.1-Flash"})
    if result.provider == "kimi":
        return (_price_version_verified(settings, "kimi-k3-cny-2026-09-24-fx-floor-5")
                and result.returned_model == "kimi-k3")
    if result.provider == "azure":
        return result.returned_model == "prebuilt-receipt"
    return False


def provider_config(settings: Settings) -> ProviderConfig | None:
    if not settings.receipt_cloud_enabled or not settings.receipt_cloud_keys_rotated:
        return None
    if settings.receipt_cloud_provider == "deepseek":
        return ProviderConfig("deepseek", settings.deepseek_model, settings.deepseek_base_url, settings.deepseek_api_key)
    if settings.receipt_cloud_provider == "kimi":
        return ProviderConfig("kimi", settings.kimi_model, settings.kimi_base_url, settings.kimi_api_key)
    if settings.receipt_cloud_provider == "azure":
        return ProviderConfig("azure", "prebuilt-receipt", settings.azure_document_intelligence_endpoint,
                              settings.azure_document_intelligence_key)
    return None


def price_ceiling_usd(config: ProviderConfig, settings: Settings) -> Decimal | None:
    """Conservative per-call hold; unknown model/price version disables payment.

    DeepSeek's 2026-09-10 V4.1 Flash peak prices are $0.30/M input and
    $1.20/M output. The vision guide caps one image at 1024 input tokens;
    this route caps output at 4096. $0.02 is above that plus prompt overhead.
    Kimi K3: official China API price RMB20/M uncached input and RMB100/M
    output. Image input tokens vary by resolution; there is NO fixed 1024
    token/image ceiling. Each paid call is preceded by the official estimator
    and refused above 4000 estimated input tokens. With a 4096 completion cap
    and conservative exchange floor 5 CNY/USD, USD0.12 also leaves margin for
    estimator error. It is a reservation, not a guarantee of the final bill.
    Azure F0 has no paid tier billing; $0.02 is reserved conservatively anyway.
    """
    if (config.provider == "deepseek" and config.model in {"deepseek-flash", "deepseek-v4-flash"}
            and _price_version_verified(settings, "deepseek-v4.1-flash-2026-09-10")):
        return Decimal("0.0200")
    if (config.provider == "kimi" and config.model == "kimi-k3"
            and _price_version_verified(settings, "kimi-k3-cny-2026-09-24-fx-floor-5")):
        return Decimal("0.1200")
    if (config.provider == "azure" and config.model == "prebuilt-receipt"
            and settings.azure_document_intelligence_sku == "F0"
            and _price_version_verified(settings, "azure-f0-2024-11-30")):
        return Decimal("0.0200")
    return None


async def _redact(
    client: httpx.AsyncClient, image_b64: str, profile: str, inference_url: str, deadline: float,
) -> tuple[bytes, ReceiptHeader | None, list[dict]]:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("Receipt redaction deadline elapsed")
    response = await client.post(
        f"{inference_url.rstrip('/')}/receipt/redact",
        json={"image_base64": image_b64, "profile": profile},
        timeout=remaining,
    )
    response.raise_for_status()
    data = response.json()
    image = base64.b64decode(data["image_base64"], validate=True)
    if not image or len(image) > 4_000_000:
        raise ValueError("Redacted image exceeds provider limit")
    if (data.get("policy_version") != "item-band-v2" or data.get("mime_type") != "image/jpeg"
            or not image.startswith(b"\xff\xd8")
            or hashlib.sha256(image).hexdigest() != data.get("sha256")
            or not 0 < int(data.get("width", 0)) * int(data.get("height", 0)) <= 25_000_000):
        raise ValueError("Invalid masked image response")
    private_header = None
    if isinstance(data.get("identity"), dict):
        try:
            private_header = ReceiptHeader.model_validate(data["identity"])
            if not all((private_header.merchant, private_header.date, private_header.time,
                        private_header.receipt_number, private_header.total is not None)):
                private_header = None
        except ValueError:
            # Bad OCR metadata cannot weaken the redaction guarantee or block
            # otherwise reviewable item lines. It only disables dedup.
            pass
    # Optional for rolling deployments with the older inference contract.
    # Purchase-only evidence is internal: only `image` goes to the provider.
    purchase_lines = data.get("purchase_lines")
    purchase_lines = [row for row in purchase_lines[:300] if isinstance(row, dict)] if isinstance(purchase_lines, list) else []
    return image, private_header, purchase_lines


async def _reserved_extract(
    client: httpx.AsyncClient, receipt_id: uuid.UUID, image: bytes, deadline: float,
    config: ProviderConfig, ceiling: Decimal, settings: Settings,
) -> ReceiptExtraction:
    if deadline <= time.monotonic():
        raise TimeoutError("Receipt provider deadline elapsed")
    async with AsyncSessionLocal() as db:
        attempt_no = await reserve_receipt_cloud_call(
            db, receipt_id, config.provider, config.model, ceiling,
            monthly_limit_usd=Decimal(str(settings.receipt_cloud_monthly_budget_usd)),
        )
        await db.commit()  # a failed/timeout request still consumes its hold
    if config.provider == "kimi":
        await estimate_kimi_input_tokens(client, image, deadline, config)
    result = await extract(client, image, deadline, config)
    if not _known_returned_model(result, settings):
        raise ValueError("Unknown provider response model")
    log.info(
        "receipt cloud call receipt=%s attempt=%d provider=%s requested_model=%s returned_model=%s prompt_tokens=%s completion_tokens=%s latency_ms=%s quality=%s",
        receipt_id, attempt_no, config.provider, config.model, result.returned_model,
        result.prompt_tokens, result.completion_tokens, result.latency_ms, quality_score(result),
    )
    return result


async def extract_cloud_receipt(
    client: httpx.AsyncClient, receipt_id: uuid.UUID, image_b64: str,
    deadline: float, settings: Settings,
) -> CloudReceiptResult | None:
    config = provider_config(settings)
    if config is None or not config.api_key:
        return None
    ceiling = price_ceiling_usd(config, settings)
    if ceiling is None:
        return None
    # Leave time to persist the review rows (or run local fallback) before
    # the receipt's hard 240-second processing deadline.
    cloud_deadline = deadline - 8
    if cloud_deadline - time.monotonic() < 20:
        return None
    # First profile and its enhanced retry are independently re-OCR'd/masked.
    first_image, first_header, first_lines = await _redact(client, image_b64, "normal", settings.inference_url, cloud_deadline)
    first = await _reserved_extract(client, receipt_id, first_image, cloud_deadline, config, ceiling, settings)
    if masked_item_quality_score(first) >= Decimal("0.75") or cloud_deadline - time.monotonic() < 30:
        return CloudReceiptResult(first, first_header, first_lines)
    try:
        second_image, second_header, second_lines = await _redact(client, image_b64, "enhanced", settings.inference_url, cloud_deadline)
        second = await _reserved_extract(client, receipt_id, second_image, cloud_deadline, config, ceiling, settings)
    except (CloudBudgetUnavailable, httpx.HTTPError, TimeoutError, ValueError) as exc:
        log.warning("receipt cloud retry unavailable receipt=%s type=%s", receipt_id, type(exc).__name__)
        return CloudReceiptResult(first, first_header, first_lines)
    # Two OCR profiles that disagree on the purchase identity cannot safely
    # activate the logical duplicate check, regardless of which item draft wins.
    private_header = first_header or second_header
    if first_header is not None and second_header is not None and first_header != second_header:
        private_header = None
    chosen = choose_extraction(first, second)
    return CloudReceiptResult(chosen, private_header, second_lines if chosen is second else first_lines)
