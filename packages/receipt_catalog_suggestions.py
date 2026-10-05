"""Pure, review-only catalogue classification contract for receipt purchases.

Model output is an *ordered suggestion*, not a probability or proof that the
food was bought. It must never enter the exact-only preselection gate.
"""

from __future__ import annotations

import json
from typing import Any

from packages.receipt_matching import expand_receipt_label
from packages.receipt_matching_policy import receipt_food_form_allowed


CATALOGUE_SUGGESTION_PROMPT = """Map each Malaysian receipt purchase to the supplied canonical_food catalogue.
Return one JSON object with assignments [{index, ranked_food_ids}], exactly one per input item.
ranked_food_ids contains 0 to 3 different catalogue IDs, ordered most to least likely.
Use [] when the purchased product is nonfood, is absent from the catalogue, or its identity
cannot be inferred. Map the PURCHASED product, never an ingredient, flavour, sauce component,
or packaging word. For example chicken-flavoured noodles are instant noodles, not chicken;
chocolate biscuits are biscuits, not a cocoa ingredient; orange/apple juice is a juice
drink, not raw orange/apple fruit. A brand/variant of a category may
map to that category (e.g. a branded chocolate bar to chocolate confectionery). Exact
catalogue spelling is not required, but product type and food form must agree. If an exact
variant is not in the catalogue, a broad category is acceptable only when it denotes the
same kind of purchased food.
The printed name is authoritative. name_dictionary_expanded is a deterministic
abbreviation expansion, while name_expanded is an uncertain vision-model hint;
neither overrides the printed product. A speciality bakery loaf is not
necessarily sliced sandwich bread: do not map it to a catalogue item requiring
"sliced" unless the print supports that form. No prose, no invented IDs, no
extra fields."""

MAX_CATALOGUE_FOODS = 250
MAX_PURCHASE_LINES = 80
MAX_PROMPT_CHARS = 30_000


def build_catalogue_suggestion_prompt(
    lines: list[Any], canonical_names: list[tuple[str, str]],
) -> str:
    """Serialize only purchase names and active catalogue names, never headers."""
    if not 0 < len(lines) <= MAX_PURCHASE_LINES:
        raise ValueError("Unsupported catalogue-mapping line count")
    names: dict[str, list[str]] = {}
    for food_id, name in canonical_names:
        if not food_id or not name or len(food_id) > 32 or len(name) > 240:
            raise ValueError("Invalid active catalogue name")
        names.setdefault(food_id, []).append(name)
    if not 0 < len(names) <= MAX_CATALOGUE_FOODS:
        raise ValueError("Unsupported active catalogue size")
    catalog = [
        {"id": food_id, "names": " / ".join(names[food_id])}
        for food_id in sorted(names)
    ]
    products = [
        {"index": index, "name_raw": line.name_raw,
         "name_dictionary_expanded": expand_receipt_label(line.name_raw),
         "name_expanded": line.name_expanded}
        for index, line in enumerate(lines)
    ]
    prompt = (
        CATALOGUE_SUGGESTION_PROMPT + "\nCatalogue JSON:\n"
        + json.dumps(catalog, ensure_ascii=False, separators=(",", ":"))
        + "\nReceipt item JSON:\n"
        + json.dumps(products, ensure_ascii=False, separators=(",", ":"))
    )
    if len(prompt) > MAX_PROMPT_CHARS:
        raise ValueError("Catalogue-mapping prompt exceeds guarded size")
    return prompt


def parse_catalogue_suggestions(
    content: Any, count: int, active_ids: set[str],
) -> list[list[str]]:
    """Reject invented IDs, missing/duplicate lines and malformed responses."""
    if not isinstance(content, str) or len(content) > 80_000:
        raise ValueError("Invalid catalogue mapping response")
    value = json.loads(content)
    if not isinstance(value, dict) or set(value) != {"assignments"}:
        raise ValueError("Invalid catalogue mapping shape")
    rows = value["assignments"]
    if not isinstance(rows, list) or len(rows) != count:
        raise ValueError("Missing catalogue mapping rows")
    output: list[list[str] | None] = [None] * count
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"index", "ranked_food_ids"}:
            raise ValueError("Invalid catalogue mapping row")
        index, ranked = row["index"], row["ranked_food_ids"]
        if (type(index) is not int or not 0 <= index < count or output[index] is not None
                or not isinstance(ranked, list) or len(ranked) > 3
                or any(not isinstance(food_id, str) or food_id not in active_ids for food_id in ranked)
                or len(set(ranked)) != len(ranked)):
            raise ValueError("Invalid catalogue mapping ID or index")
        output[index] = ranked
    if any(row is None for row in output):
        raise ValueError("Missing catalogue mapping index")
    return [row for row in output if row is not None]


def combine_review_candidates(
    lexical: list[tuple[str, float]], model_ranked_ids: list[str],
    exact_selected_id: str | None,
    *, verified_review_ids: list[str] | None = None,
    purchase_label: str | None = None,
    canonical_names: list[tuple[str, str]] | None = None,
) -> list[tuple[str, float]]:
    """Merge ordinal model hints with lexical scores; exact evidence wins.

    The model's 0.80/0.77/0.74 values are rank markers, *not* calibrated
    confidence percentages. The API/mobile UI uses them only for ordering.
    """
    if purchase_label is not None and canonical_names is not None:
        names: dict[str, list[str]] = {}
        for food_id, name in canonical_names:
            names.setdefault(food_id, []).append(name)
        allowed = {food_id for food_id, values in names.items()
                   if receipt_food_form_allowed(purchase_label, values)}
        lexical = [(food_id, score) for food_id, score in lexical if food_id in allowed]
        model_ranked_ids = [food_id for food_id in model_ranked_ids if food_id in allowed]
    if exact_selected_id is not None:
        return lexical[:3]
    best = {food_id: score for food_id, score in lexical}
    for rank, food_id in enumerate(model_ranked_ids[:3]):
        best[food_id] = max(best.get(food_id, 0.0), round(0.80 - 0.03 * rank, 4))
    # Reviewed product-family evidence can outrank a conflicting model hint,
    # but never makes the purchase an exact/preselected match.
    verified = set(verified_review_ids or [])
    reviewed = [score for food_id, score in lexical if food_id in verified]
    if reviewed:
        # Mobile also sorts by numeric score. Keep the reviewed family ahead
        # there, rather than returning an ordering the client would undo.
        ceiling = min(reviewed) - 0.0001
        best = {food_id: score if food_id in verified else min(score, ceiling)
                for food_id, score in best.items()}
    return sorted(best.items(), key=lambda item: (-item[1], item[0]))[:3]
