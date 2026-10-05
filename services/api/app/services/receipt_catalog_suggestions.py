"""Optional second, text-only cloud call for review-only canonical food hints.

The first vision call sees only a redacted image. This call sees only the
purchase names it extracted plus current ACTIVE catalogue names. The shared
per-receipt ledger allows at most two paid calls total; an enhanced-image
retry therefore leaves no allowance for this optional stage.
"""

from __future__ import annotations

import time
import uuid
from decimal import Decimal

import httpx

from packages.receipt_catalog_suggestions import (
    build_catalogue_suggestion_prompt, parse_catalogue_suggestions,
)
from ..config import Settings
from ..db import AsyncSessionLocal
from .receipt_cloud_budget import reserve_receipt_cloud_call
from .receipt_cloud_contract import ReceiptExtraction
from .receipt_cloud_providers import _validate_endpoint
from .receipt_cloud_runtime import _known_returned_model, price_ceiling_usd, provider_config


async def suggest_catalogue_foods(
    client: httpx.AsyncClient,
    receipt_id: uuid.UUID,
    extraction: ReceiptExtraction,
    canonical_names: list[tuple[str, str]],
    settings: Settings,
    deadline: float,
) -> list[list[str]] | None:
    """Return one ordered food-ID list per purchase; never preselect any ID.

    Validation happens before budget reservation. A committed reservation is
    never refunded, including HTTP/parse errors. Callers catch those errors
    and keep the deterministic lexical suggestions as their safe fallback.
    """
    if extraction.provider != "deepseek" or not extraction.lines:
        return None
    config = provider_config(settings)
    if config is None or config.provider != "deepseek":
        return None
    base = _validate_endpoint(config)
    ceiling = price_ceiling_usd(config, settings)
    if ceiling is None or deadline - time.monotonic() < 15:
        return None
    prompt = build_catalogue_suggestion_prompt(extraction.lines, canonical_names)
    active_ids = {food_id for food_id, _ in canonical_names}
    async with AsyncSessionLocal() as db:
        await reserve_receipt_cloud_call(
            db, receipt_id, config.provider, config.model, ceiling,
            monthly_limit_usd=Decimal(str(settings.receipt_cloud_monthly_budget_usd)),
        )
        await db.commit()
    response = await client.post(
        f"{base}/chat/completions",
        headers={"Authorization": f"Bearer {config.api_key}"},
        json={
            "model": config.model, "temperature": 0, "thinking": {"type": "disabled"},
            "response_format": {"type": "json_object"}, "max_tokens": 2048,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=max(1.0, deadline - time.monotonic()),
    )
    response.raise_for_status()
    data = response.json()
    returned = ReceiptExtraction(
        provider="deepseek", requested_model=config.model,
        returned_model=str(data.get("model") or "")[:120] or None,
    )
    if not _known_returned_model(returned, settings):
        raise ValueError("Unknown catalogue mapper model")
    choices = data.get("choices") or []
    if not choices or choices[0].get("finish_reason") == "length":
        raise ValueError("Truncated catalogue mapper output")
    return parse_catalogue_suggestions(
        choices[0].get("message", {}).get("content"), len(extraction.lines), active_ids,
    )
