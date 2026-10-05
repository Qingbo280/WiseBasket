# Epic 6 pure-matching unit tests (no DB, no inference).
from __future__ import annotations

from packages.receipt_matching import (
    DEFAULT_MATCH_THRESHOLD,
    best_match,
    best_pair_score,
    cosine,
    match_candidates,
    match_text_candidates,
    normalize_label,
    normalize_receipt_item_label,
)


def test_cosine_identical_vectors_is_one():
    assert cosine([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]) == 1.0


def test_cosine_orthogonal_vectors_is_zero():
    assert cosine([1.0, 0.0, 0.0], [0.0, 1.0, 0.0]) == 0.0


def test_cosine_degenerate_input_is_zero():
    assert cosine([], [1.0]) == 0.0
    assert cosine([0.0, 0.0], [1.0, 1.0]) == 0.0
    assert cosine([1.0], [1.0, 2.0]) == 0.0  # length mismatch


def test_best_match_picks_highest_scoring_food():
    foods = [
        ("SF-A", [1.0, 0.0, 0.0]),
        ("SF-B", [0.0, 1.0, 0.0]),
    ]
    food_id, score = best_match([0.9, 0.1, 0.0], foods)
    assert food_id == "SF-A"
    assert score is not None and 0.9 < score <= 1.0


def test_best_match_below_threshold_returns_none():
    foods = [("SF-A", [1.0, 0.0, 0.0])]
    food_id, score = best_match([0.2, 0.9, 0.0], foods, threshold=DEFAULT_MATCH_THRESHOLD)
    assert food_id is None
    assert score is None


def test_best_match_empty_food_table_returns_none():
    assert best_match([1.0, 0.0], []) == (None, None)
    assert best_match(None, [("SF-A", [1.0])]) == (None, None)


def test_best_pair_score_uses_strongest_bridge():
    pantry = [[1.0, 0.0, 0.0]]
    ingredients = [[0.0, 1.0, 0.0], [0.95, 0.05, 0.0]]
    score = best_pair_score(pantry, ingredients)
    assert score > 0.99


def test_best_pair_score_empty_side_is_zero():
    assert best_pair_score([], [[1.0]]) == 0.0
    assert best_pair_score([[1.0]], []) == 0.0


# --- match_candidates: expanded-name multi-vector matching + top-3 picks -----


def test_match_candidates_picks_best_across_line_vectors():
    """The printed name vector is weak but the expansion vector nails it."""
    foods = [
        ("SF-BEEF", [1.0, 0.0, 0.0]),
        ("SF-PORK", [0.0, 1.0, 0.0]),
    ]
    food_id, score, top = match_candidates([[0.3, 0.9, 0.0], [0.95, 0.05, 0.0]], foods)
    assert food_id == "SF-BEEF"  # best over BOTH vectors wins, not the first
    assert score is not None and score > 0.9
    assert top[0] == ("SF-BEEF", score)


def test_match_candidates_gate_unchanged_but_topk_ungated():
    """Below threshold -> (None, None) as before, but candidates still offered."""
    foods = [("SF-A", [1.0, 0.0, 0.0]), ("SF-B", [0.0, 1.0, 0.0]), ("SF-C", [0.0, 0.0, 1.0])]
    # 0.976 best cosine < the 0.99 threshold used here -> gate rejects,
    # demonstrating the gate and the top-k list are independent.
    food_id, score, top = match_candidates([[0.2, 0.9, 0.0]], foods, threshold=0.99)
    assert food_id is None and score is None
    # top-k returned regardless of the gate, best first, deterministic order;
    # SF-C is orthogonal (score 0) so the zero-score filter drops it.
    assert [c[0] for c in top] == ["SF-B", "SF-A"]
    assert all(0.0 < c[1] <= 1.0 for c in top)


def test_match_candidates_empty_vector_returns_nothing():
    assert match_candidates(None, [("SF-A", [1.0])]) == (None, None, [])
    assert match_candidates([], [("SF-A", [1.0])]) == (None, None, [])


def test_match_candidates_drops_zero_scores():
    foods = [("SF-A", [1.0, 0.0]), ("SF-B", [0.0, 1.0])]
    _, _, top = match_candidates([[1.0, 0.0]], foods, k=3)
    assert [c[0] for c in top] == ["SF-A"]  # orthogonal food dropped, no zeros


def test_normalize_label_removes_case_punctuation_and_extra_spaces():
    assert normalize_label("  BAWANG-MERAH / 250g  ") == "bawang merah 250g"


def test_normalize_label_repairs_zero_only_when_it_is_inside_a_word():
    assert normalize_label("BEAN SPR0UT CLEANED") == "bean sprout cleaned"
    assert normalize_label("S0MMERSET C0TTAGE") == "sommerset cottage"
    assert normalize_label("FARM TABLE EGG A30S") == "farm table egg a30s"


def test_receipt_item_normalization_removes_price_pack_and_promotion_noise():
    assert normalize_receipt_item_label("KANGKUNG 250G RM3.50 PROMO") == "KANGKUNG"
    assert normalize_receipt_item_label("BERAS 2 X 5KG SAVE RM2") == "BERAS"
    assert normalize_receipt_item_label("TELUR GRED A 10S RM8.90") == "TELUR GRED A"


def test_receipt_item_normalization_preserves_product_words_for_matching():
    cleaned = normalize_receipt_item_label("SAYUR KANGKUNG 300G RM2.99")
    food_id, score, _ = match_text_candidates([cleaned], [("SF074", "sayur kangkung")])
    assert food_id == "SF074"
    assert score == 1.0


def test_text_matching_ignores_ocr_word_boundary_mistakes():
    food_id, score, candidates = match_text_candidates(
        ["FARM TABLEEGG A30S"],
        [("SF-EGG", "farm table egg a30s")],
    )

    assert food_id == "SF-EGG"
    assert score == 1.0
    assert candidates == [("SF-EGG", 1.0)]


def test_text_matching_ranks_subset_food_without_auto_confirming_it():
    food_id, score, candidates = match_text_candidates(
        ["ARIZONA PINEAPPLE"],
        [("SF-PINEAPPLE", "pineapple"), ("SF-APPLE", "apple")],
    )

    assert food_id is None
    assert score is None
    assert candidates[0] == ("SF-PINEAPPLE", 0.85)


def test_text_matching_auto_confirms_after_user_has_added_exact_alias():
    food_id, score, candidates = match_text_candidates(
        ["ARIZONA PINEAPPLE"],
        [("SF-PINEAPPLE", "pineapple"), ("SF-PINEAPPLE", "arizona pineapple")],
    )

    assert food_id == "SF-PINEAPPLE"
    assert score == 1.0
    assert candidates[0] == ("SF-PINEAPPLE", 1.0)


def test_text_matching_suggests_ingredient_keyword_for_eggs_without_selecting_it():
    food_id, score, candidates = match_text_candidates(
        ["FARM TABLE EGG A30S"],
        [
            ("SF-EGG", "chicken egg"),
            ("SF-EGGPLANT", "round eggplant"),
        ],
    )

    assert food_id is None
    assert score is None
    assert candidates[0] == ("SF-EGG", 0.85)


def test_text_matching_suggests_prefix_keyword_for_chicken_fillet_without_selecting_it():
    food_id, score, candidates = match_text_candidates(
        ["CHICK FILLET"],
        [("SF-CHICKEN", "whole chicken"), ("SF-EGG", "chicken egg")],
    )

    assert food_id is None
    assert score is None
    assert candidates[0] == ("SF-CHICKEN", 0.85)


def test_keyword_suggestions_include_multiple_possible_chicken_foods():
    food_id, score, candidates = match_text_candidates(
        ["CHICK FILLET"],
        [("SF-WHOLE", "whole chicken"), ("SF-BREAST", "chicken breast")],
    )

    assert food_id is None
    assert score is None
    assert [food_id for food_id, _ in candidates] == ["SF-BREAST", "SF-WHOLE"]


def test_text_matching_prefers_exact_malay_alias():
    food_id, score, candidates = match_text_candidates(
        ["BAWANG KECIL MERAH"],
        [("SF054", "bawang kecil merah"), ("SF069", "bawang putih")],
    )

    assert food_id == "SF054"
    assert score == 1.0
    assert candidates[0] == ("SF054", 1.0)


def test_text_matching_returns_candidates_but_rejects_weak_auto_match():
    food_id, score, candidates = match_text_candidates(
        ["SA PREMIUM"],
        [("SF054", "bawang kecil merah"), ("SF069", "bawang putih")],
    )

    assert food_id is None
    assert score is None
    assert candidates
