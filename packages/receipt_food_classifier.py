"""Fail-closed AI gate for filtering non-food receipt OCR rows.

The model only classifies OCR text.  It never selects a canonical food: the
normal receipt matcher remains the authority for that subsequent step.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Awaitable, Callable


RECEIPT_FOOD_CLASSIFIER_SYSTEM_PROMPT = """Classify Malaysian grocery-receipt
OCR labels as FOOD, NON_FOOD, or UNCERTAIN. Return JSON only in this exact
shape: {"lines":[{"index":0,"kind":"FOOD","confidence":0.0}]}.

FOOD means a purchasable grocery or pantry item. NON_FOOD means receipt
metadata, payment/card details, totals, change, loyalty points, promotions,
or greetings. Use UNCERTAIN whenever a line could be a grocery item. Never
infer products, quantities, prices, brands, or catalogue IDs."""

MIN_NON_FOOD_CONFIDENCE = 0.95
MAX_CLASSIFIED_LINES = 60


@dataclass(frozen=True)
class ReceiptFoodClassification:
    kind: str
    confidence: float

    @property
    def should_skip(self) -> bool:
        return self.kind == "NON_FOOD" and self.confidence >= MIN_NON_FOOD_CONFIDENCE


async def classify_receipt_food_lines(
    labels: list[str],
    complete: Callable[[str, str], Awaitable[str | None]],
) -> dict[int, ReceiptFoodClassification]:
    """Return validated classifications keyed by OCR-row index.

    Any malformed, incomplete, timed-out, or uncertain response returns no
    skip decisions. This preserves lines for user review instead of deleting a
    possible grocery item.
    """
    if not labels:
        return {}
    payload = {"lines": [{"index": index, "label": label[:240]} for index, label in enumerate(labels[:MAX_CLASSIFIED_LINES])]}  # noqa: E501
    try:
        response = await complete(RECEIPT_FOOD_CLASSIFIER_SYSTEM_PROMPT, json.dumps(payload, ensure_ascii=False))
        decoded = json.loads(response or "")
        rows = decoded.get("lines") if isinstance(decoded, dict) and set(decoded) == {"lines"} else None
        if not isinstance(rows, list):
            return {}
        result: dict[int, ReceiptFoodClassification] = {}
        for row in rows:
            if not isinstance(row, dict) or set(row) != {"index", "kind", "confidence"}:
                return {}
            index, kind, confidence = row.get("index"), row.get("kind"), row.get("confidence")
            if not isinstance(index, int) or index < 0 or index >= len(payload["lines"]):
                return {}
            if kind not in {"FOOD", "NON_FOOD", "UNCERTAIN"} or index in result:
                return {}
            numeric_confidence = float(confidence)
            if not 0 <= numeric_confidence <= 1:
                return {}
            result[index] = ReceiptFoodClassification(kind, numeric_confidence)
        # A partial answer is not safe enough to remove any item.
        if set(result) != set(range(len(payload["lines"]))):
            return {}
        return result
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
