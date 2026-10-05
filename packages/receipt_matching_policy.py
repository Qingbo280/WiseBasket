"""Trust boundary between receipt candidate ranking and automatic proposals."""
from __future__ import annotations

from dataclasses import dataclass
import re

from rapidfuzz import fuzz

from packages.receipt_matching import compact_label, normalize_label


# These are lexical relevance scores, not calibrated probabilities. Hybrid
# character/token-F1 scoring dampens single-word garbage (e.g. CHICKEN RAMEN
# -> whole chicken scores far below a true match), and review candidates are
# un-gated Top-3 suggestions: any positive signal may be shown for manual
# pick, while only exact evidence may preselect.
# Sanity floor (2026-10-02, measured on real receipts): below 0.30 the hybrid
# score is character-similarity noise - an out-of-catalogue purchase like
# "PEAR-GOLDEN 2S (CHN) C10" scored ~0.24 against seasonings and must surface
# NO suggestion (the reviewer skips or hand-picks), while genuine weak brand
# hits (AQINA CHIKEN -> chicken thigh 0.42+) stay visible. Model catalogue
# hints bypass this floor in combine_review_candidates.
RECEIPT_CANDIDATE_SANITY_FLOOR = 0.30


def _informative_tokens(value: str) -> list[str]:
    """Ignore pack sizes/counts when comparing a product name to food names."""
    return [
        token for token in normalize_label(value).split()
        if not any(character.isdigit() for character in token)
    ]


def _token_f1(label: str, alias: str) -> float:
    """Count each shared whole/prefix token once, penalising unmatched words."""
    label_tokens = _informative_tokens(label)
    alias_tokens = _informative_tokens(alias)
    if not label_tokens or not alias_tokens:
        return 0.0

    remaining_labels = list(label_tokens)
    remaining_aliases = list(alias_tokens)
    matches = 0
    # Exact token matches take precedence over looser prefix matches.
    for token in label_tokens:
        if token in remaining_aliases:
            remaining_labels.remove(token)
            remaining_aliases.remove(token)
            matches += 1
    for token in remaining_labels:
        for index, candidate in enumerate(remaining_aliases):
            if (
                (len(token) >= 4 and candidate.startswith(token))
                or (len(candidate) >= 4 and token.startswith(candidate))
            ):
                remaining_aliases.pop(index)
                matches += 1
                break
    return 2 * matches / (len(label_tokens) + len(alias_tokens))


def _receipt_candidate_score(label: str, alias: str) -> float:
    normal_label = normalize_label(label)
    normal_alias = normalize_label(alias)
    if not normal_label or not normal_alias:
        return 0.0
    if compact_label(label) == compact_label(alias):
        return 1.0
    character_score = max(
        fuzz.ratio(normal_label, normal_alias),
        fuzz.token_sort_ratio(normal_label, normal_alias),
    ) / 100
    return 0.55 * character_score + 0.45 * _token_f1(label, alias)


def verified_product_expansion(label: str) -> str | None:
    """A tiny reviewed product-name bridge, never automatic confirmation.

    Some Malaysian brand lines omit the food type entirely. The Sommerset
    Cottage product is Gardenia bread (not cottage cheese); Gardenia's own
    catalogue lists it as bread. This remains candidate-only evidence.
    """
    normalized = normalize_label(label)
    if "sommerset cottage" in normalized or "somerset cottage" in normalized:
        return "sliced bread"
    # Costco lists Bostani Belgian Chocolate Thins 500g:
    # https://www.costco.co.uk/Grocery-Household/Grocery-Delivery/Bostani-Belgian-Chocolate-Thins-500g/p/334550
    # BUSTANI is a receipt spelling; the distinctive thin-filled family is
    # required. Brand alone (including Bostani biscuits) is insufficient.
    if re.search(r"\b(?:bostani|bustani)\b", normalized) and re.search(r"\bthin\s*filled\b", normalized):
        return "chocolate confectionery"
    # Manufacturer lists PEEL FRESH Orange (and these fruit variants) as juice.
    # https://www.marigold.com.my/peel-fresh/ . Brand alone is insufficient.
    if (re.search(r"\bpeel\s*fresh\b", normalized)
            and re.search(r"\b(?:orange|apple|mango|guava|grape|mixed\s+fruit)\b", normalized)
            and re.search(r"\d+(?:[.,]\d+)?\s*(?:ml|l)\b", label, re.I)):
        return "fruit juice drink"
    return None


def receipt_food_form_allowed(label: str, food_names: list[str]) -> bool:
    """A printed juice form cannot be repaired into raw fruit by any hint.

    Volume-labelled fruit has the same incompatibility, but supplies no
    positive juice identity by itself. Canonical names, not IDs, set the form.
    """
    raw = normalize_label(label)
    juice = (bool(re.search(r"\b(?:juice|jus)\b", raw))
             or verified_product_expansion(label) == "fruit juice drink")
    liquid_fruit = bool(re.search(r"\b(?:orange|apple|mango|guava|grape)\b", raw)
                        and re.search(r"\d+(?:[.,]\d+)?\s*(?:ml|l)\b", label, re.I))
    names = [normalize_label(name) for name in food_names]
    if not (juice or liquid_fruit):
        return True
    return any(re.search(r"\b(?:juice|jus)\b", name) for name in names)


def _rank_receipt_candidates(
    labels: list[str],
    candidate_only_labels: list[str],
    aliases: list[tuple[str, str]],
) -> list[tuple[str, float]]:
    # The expansion may improve suggestions, but equal scores favour printed
    # receipt evidence. Neither signal changes the exact-only preselect gate.
    best: dict[str, tuple[float, int]] = {}
    for food_id, alias in aliases:
        for source_priority, source_labels in ((1, labels), (0, candidate_only_labels)):
            for label in source_labels:
                score = _receipt_candidate_score(label, alias)
                if score < RECEIPT_CANDIDATE_SANITY_FLOOR:
                    continue
                ranking = (score, source_priority)
                if ranking > best.get(food_id, (0.0, -1)):
                    best[food_id] = ranking
    ranked = sorted(best.items(), key=lambda item: (-item[1][0], -item[1][1], item[0]))
    return [(food_id, round(ranking[0], 4)) for food_id, ranking in ranked[:3]]


@dataclass(frozen=True)
class ReceiptMatch:
    food_id: str | None
    score: float | None
    candidates: list[tuple[str, float]]
    basis: str


def propose_receipt_food(
    labels: list[str],
    canonical_names: list[tuple[str, str]],
    candidate_aliases: list[tuple[str, str]],
    trusted_retailer_aliases: list[tuple[str, str]] | None = None,
    candidate_only_labels: list[str] | None = None,
) -> ReceiptMatch:
    """Only unique exact canonical or verified retailer aliases may preselect.

    ``labels`` are printed/cleaned receipt evidence eligible for an exact match.
    Expansions belong in ``candidate_only_labels``: like legacy global aliases
    and fuzzy matches, they may improve Top 3 ranking but cannot preselect.
    Ambiguous exact names remain unselected.
    """
    normalized_labels = {normalize_label(label) for label in labels} - {""}
    names_by_id: dict[str, list[str]] = {}
    for food_id, name in canonical_names:
        names_by_id.setdefault(food_id, []).append(name)
    allowed_ids = {food_id for food_id, names in names_by_id.items()
                   if all(receipt_food_form_allowed(label, names) for label in labels)}
    candidate_pool = canonical_names + candidate_aliases + (trusted_retailer_aliases or [])
    candidate_pool = [(food_id, name) for food_id, name in candidate_pool if food_id in allowed_ids]
    reviewed_expansions = [expanded for label in labels if (expanded := verified_product_expansion(label))]
    candidates = _rank_receipt_candidates(labels, (candidate_only_labels or []) + reviewed_expansions, candidate_pool)
    for basis, aliases in (
        ("CANONICAL_EXACT", canonical_names),
        ("RETAILER_ALIAS_EXACT", trusted_retailer_aliases or []),
    ):
        exact_ids = {
            food_id for food_id, name in aliases
            if food_id in allowed_ids and normalize_label(name) in normalized_labels
        }
        if len(exact_ids) == 1:
            food_id = next(iter(exact_ids))
            return ReceiptMatch(food_id, 1.0, candidates, basis)
        if len(exact_ids) > 1:
            return ReceiptMatch(None, None, candidates, "CANDIDATE")
    return ReceiptMatch(None, None, candidates, "CANDIDATE")
