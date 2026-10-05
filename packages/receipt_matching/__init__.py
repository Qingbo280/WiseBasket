"""Shared pure helpers for Epic 6 receipt->food matching.

Single source for both the API service and the Celery worker (both images
COPY packages/). RapidFuzz provides lightweight, deterministic text ranking.
"""
from __future__ import annotations

import math
import re
import unicodedata

from rapidfuzz import fuzz

from .abbreviations import expand_receipt_label

__all__ = ["expand_receipt_label", "normalize_receipt_item_label"]

# Below this cosine similarity an OCR line is left UNMATCHED rather than
# silently attached to the wrong food (user confirms/adjusts in the app).
DEFAULT_MATCH_THRESHOLD = 0.55
TEXT_MATCH_THRESHOLD = 0.88
TOKEN_SUBSET_CANDIDATE_CAP = 0.85
KEYWORD_SUGGESTION_CAP = 0.87
LETTER_ZERO_LETTER = re.compile(r"(?<=[a-zA-Z])0(?=[a-zA-Z])")
RECEIPT_PRICE = re.compile(r"\b(?:rm|myr)\s*\d+(?:[.,]\d{1,2})?\b", re.IGNORECASE)
RECEIPT_PACK_SIZE = re.compile(
    r"^(?:\d+(?:[.,]\d+)?(?:g|kg|ml|l|pcs?|pc|s|biji|unit|pack)|[a-z]?\d+(?:s|pcs?|biji))$",
    re.IGNORECASE,
)
RECEIPT_MULTIPACK = re.compile(r"^\d+x$", re.IGNORECASE)
RECEIPT_PROMOTION_TOKENS = frozenset({"disc", "discount", "free", "promo", "save", "sale"})


def normalize_receipt_item_label(value: str) -> str:
    """Remove receipt metadata that should not affect food-name matching.

    The original OCR label is retained for review. This is an extra matching
    signal that removes price, pack-size and promotion tokens only.
    """
    without_price = RECEIPT_PRICE.sub(" ", value)
    cleaned: list[str] = []
    for token in re.findall(r"[^\s]+", without_price):
        normalized_token = token.strip(".,;:()[]{}!@#$%^&*_+=|\\/'\"")
        if not normalized_token:
            continue
        lowered = normalized_token.casefold()
        if (
            lowered in RECEIPT_PROMOTION_TOKENS
            or lowered == "x"
            or normalized_token.isdigit()
            or RECEIPT_PACK_SIZE.fullmatch(normalized_token)
            or RECEIPT_MULTIPACK.fullmatch(normalized_token)
        ):
            continue
        cleaned.append(normalized_token)
    return " ".join(cleaned)


def normalize_label(value: str) -> str:
    """Normalise a label for matching while preserving the displayed OCR text.

    OCR frequently reads an uppercase ``O`` as ``0`` within a word. Restricting
    that repair to a letter-zero-letter pattern avoids changing numeric product
    sizes such as ``A30S`` or prices.
    """
    repaired = LETTER_ZERO_LETTER.sub("O", value)
    decomposed = unicodedata.normalize("NFKD", repaired).casefold()
    without_marks = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(re.sub(r"[^\w]+", " ", without_marks).split())


def compact_label(value: str) -> str:
    """Return a space-free label so OCR word-boundary mistakes still match."""
    return "".join(normalize_label(value).split())


def text_similarity(label: str, alias: str) -> float:
    """Rank OCR labels without auto-accepting an alias that is only a subset.

    Token-set matching is valuable for ranking labels with retailer or package
    words, but a subset alone must remain below the auto-match threshold. The
    user can still confirm it from the returned candidates and create an alias.
    """
    if compact_label(label) == compact_label(alias):
        return 1.0
    character_score = fuzz.ratio(label, alias) / 100
    reordered_token_score = fuzz.token_sort_ratio(label, alias) / 100
    subset_candidate_score = (
        fuzz.token_set_ratio(label, alias) / 100 * TOKEN_SUBSET_CANDIDATE_CAP
    )
    return max(character_score, reordered_token_score, subset_candidate_score)


def _keyword_suggestion_score(label: str, alias: str) -> float:
    """Score an alias by whole-word/prefix overlap, below auto-match level.

    Receipt labels are often abbreviated (``CHICK FILLET``), while catalogue
    aliases use complete words (``whole chicken``). This is intentionally a
    *suggestion* signal only: no food is selected from it automatically.
    """
    label_tokens = [token for token in label.split() if len(token) >= 3]
    alias_tokens = [token for token in alias.split() if len(token) >= 3]
    if not label_tokens or not alias_tokens:
        return 0.0
    matches = [
        label_token
        for label_token in label_tokens
        if any(
            label_token == alias_token
            or (len(label_token) >= 4 and alias_token.startswith(label_token))
            or (len(alias_token) >= 4 and label_token.startswith(alias_token))
            for alias_token in alias_tokens
        )
    ]
    if not matches:
        return 0.0
    # More independent matching words rank higher, but stay strictly below
    # TEXT_MATCH_THRESHOLD so the confirmation UI—not the matcher—chooses.
    return min(KEYWORD_SUGGESTION_CAP, 0.84 + 0.01 * len(set(matches)))


def match_text_candidates(
    labels: list[str],
    aliases: list[tuple[str, str]],
    threshold: float = TEXT_MATCH_THRESHOLD,
    k: int = 3,
) -> tuple[str | None, float | None, list[tuple[str, float]]]:
    """Rank canonical foods from controlled English/Malay/retailer aliases.

    Exact normalised aliases are accepted immediately. Fuzzy scores provide
    review candidates only unless they clear the conservative threshold.
    """
    normalized_labels = [normalize_label(label) for label in labels if normalize_label(label)]
    best_scores: dict[str, float] = {}
    for food_id, alias in aliases:
        normalized_alias = normalize_label(alias)
        if not normalized_alias:
            continue
        for label in normalized_labels:
            score = max(
                text_similarity(label, normalized_alias),
                _keyword_suggestion_score(label, normalized_alias),
            )
            best_scores[food_id] = max(best_scores.get(food_id, 0.0), score)
    ranked = sorted(best_scores.items(), key=lambda item: (-item[1], item[0]))
    candidates = [(food_id, round(score, 4)) for food_id, score in ranked[:k] if score > 0]
    if not ranked or ranked[0][1] < threshold:
        return None, None, candidates
    return ranked[0][0], round(ranked[0][1], 4), candidates


def cosine(a: list[float], b: list[float]) -> float:
    """Cosine similarity of two equal-length vectors; 0.0 for empty/degenerate input."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    for x, y in zip(a, b):
        dot += x * y
        norm_a += x * x
        norm_b += y * y
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (math.sqrt(norm_a) * math.sqrt(norm_b))


def best_match(
    vector: list[float] | None,
    foods: list[tuple[str, list[float]]],
    threshold: float = DEFAULT_MATCH_THRESHOLD,
) -> tuple[str | None, float | None]:
    """Best-scoring canonical food for one OCR line embedding.

    Returns (canonical_food_id, score), or (None, None) when no candidate
    clears the threshold - the line stays UNMATCHED for user review.
    """
    if not vector:
        return None, None
    best_id: str | None = None
    best_score = 0.0
    for food_id, emb in foods:
        score = cosine(vector, emb)
        if score > best_score:
            best_id, best_score = food_id, score
    if best_id is None or best_score < threshold:
        return None, None
    return best_id, round(best_score, 4)


def match_candidates(
    vectors: list[list[float]] | None,
    foods: list[tuple[str, list[float]]],
    threshold: float = DEFAULT_MATCH_THRESHOLD,
    k: int = 3,
) -> tuple[str | None, float | None, list[tuple[str, float]]]:
    """Match one OCR line against the food catalogue using MULTIPLE line
    embeddings (e.g. the printed name AND the OCR model's abbreviation
    expansion of it) — a food's score is its best cosine over those vectors.

    Returns (best_canonical_food_id, best_score, top_k_candidates):
    - best pair is (None, None) when nothing clears `threshold` — the printed
      fail-closed gate is unchanged, the line stays UNMATCHED.
    - top_k_candidates is ALWAYS returned (un-gated, scores included, zero
      scores dropped) so the confirmation UI can offer near-miss picks; the
      user makes the final call. Empty when there is no line vector at all.
    """
    if not vectors:
        return None, None, []
    scored = [
        (food_id, max(cosine(v, emb) for v in vectors))
        for food_id, emb in foods
    ]
    scored.sort(key=lambda t: (-t[1], t[0]))  # deterministic tiebreak by id
    top = [(food_id, round(score, 4)) for food_id, score in scored[:k] if score > 0.0]
    if not scored or scored[0][1] < threshold:
        return None, None, top
    return scored[0][0], round(scored[0][1], 4), top


def best_pair_score(
    left: list[list[float]],
    right: list[list[float]],
) -> float:
    """Highest cosine similarity across two vector sets (0.0 when either is empty).

    Used by recipe semantic recall: pantry-food embeddings vs one recipe's
    ingredient embeddings - the strongest single "ingredient bridge".
    """
    if not left or not right:
        return 0.0
    return max(cosine(a, b) for a in left for b in right)
