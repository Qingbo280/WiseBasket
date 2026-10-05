"""Strict, fail-closed normalization of uncertain receipt labels with an LLM."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Awaitable, Callable

from packages.receipt_matching import match_text_candidates


RECEIPT_NORMALIZER_SYSTEM_PROMPT = """Normalize one Malaysian grocery receipt label.
Return JSON only with item_name and confidence. Do not infer quantity, unit,
price, food IDs, brands, or products unsupported by the OCR label. When
catalogue candidates are supplied, use one only when the OCR supports it."""
MIN_CONFIDENCE = 0.8


@dataclass(frozen=True)
class NormalizedReceiptLabel:
    item_name: str
    confidence: float


async def normalize_uncertain_receipt_label(
    raw_label: str,
    complete: Callable[[str, str], Awaitable[str | None]],
) -> NormalizedReceiptLabel | None:
    """Return validated AI cleanup, or None so deterministic matching continues."""
    try:
        response = await complete(RECEIPT_NORMALIZER_SYSTEM_PROMPT, raw_label)
        payload = json.loads(response or "")
        if not isinstance(payload, dict):
            return None
        if set(payload) != {"item_name", "confidence"}:
            return None
        item_name = str(payload.get("item_name") or "").strip()
        confidence = float(payload.get("confidence"))
        if not item_name or len(item_name) > 240 or confidence < MIN_CONFIDENCE or confidence > 1:
            return None
        return NormalizedReceiptLabel(item_name, confidence)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None


async def normalize_unmatched_receipt_label(
    labels: list[str],
    aliases: list[tuple[str, str]],
    complete: Callable[[str, str], Awaitable[str | None]],
) -> NormalizedReceiptLabel | None:
    """Ask AI only after deterministic matching leaves a line unconfirmed."""
    food_id, _, candidates = match_text_candidates(labels, aliases)
    if food_id is not None:
        return None

    candidate_food_ids = {food_id for food_id, _ in candidates}
    candidate_names = sorted(
        {
            alias.strip()
            for food_id, alias in aliases
            if food_id in candidate_food_ids and alias.strip()
        },
        key=str.casefold,
    )[:12]
    prompt = labels[0] if labels else ""
    if candidate_names:
        prompt += "\nCatalogue candidates (may be unrelated):\n" + "\n".join(
            f"- {name}" for name in candidate_names
        )
    normalized = await normalize_uncertain_receipt_label(prompt, complete)
    if normalized is None:
        return None
    if normalized.item_name.casefold() in {label.casefold() for label in labels}:
        return None
    return normalized
