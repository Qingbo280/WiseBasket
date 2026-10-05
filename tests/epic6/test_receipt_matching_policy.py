from packages.receipt_matching_policy import propose_receipt_food, verified_product_expansion


def test_brand_heavy_label_keeps_weak_candidates_for_manual_pick():
    # Un-gated Top-3 review semantics (2026-10-02): a brand-heavy label keeps
    # its weak lexical suggestions visible for one-tap manual pick; only
    # exact evidence may preselect.
    result = propose_receipt_food(["AQINA CHIKEN BONELESS THIGH ABF"],
                                  [("THIGH", "chicken boneless thigh"), ("MILK", "milk")], [])
    assert result.food_id is None
    assert result.basis == "CANDIDATE"
    assert result.candidates[0][0] == "THIGH"


def test_out_of_catalogue_purchase_gets_no_candidates():
    # Sanity floor (2026-10-02): "PEAR-GOLDEN 2S (CHN) C10" has no pear in the
    # catalogue; ~0.24 character noise against seasonings must not suggest
    # fried rice seasoning - the reviewer skips or hand-picks instead.
    result = propose_receipt_food(
        ["PEAR-GOLDEN 2S (CHN) C10"],
        [("SF138", "fried rice seasoning"), ("SF137", "tomyam seasoning"), ("SF136", "chili powder")],
        [],
    )
    assert result.food_id is None
    assert result.candidates == []


def test_unique_canonical_exact_may_propose():
    result = propose_receipt_food(["BERAS"], [("RICE", "Beras")], [])
    assert (result.food_id, result.basis) == ("RICE", "CANONICAL_EXACT")


def test_legacy_alias_exact_and_fuzzy_are_candidates_only():
    result = propose_receipt_food(["SHOP RICE"], [("RICE", "Beras")], [("RICE", "Shop Rice")])
    assert result.food_id is None
    assert result.basis == "CANDIDATE"
    assert result.candidates[0][0] == "RICE"


def test_conflicting_canonical_names_do_not_autoselect():
    result = propose_receipt_food(["TOFU"], [("A", "Tofu"), ("B", "TOFU")], [])
    assert result.food_id is None
    assert result.basis == "CANDIDATE"


def test_only_verified_retailer_alias_may_autoselect():
    result = propose_receipt_food(["BRD WM"], [("BREAD", "Bread")], [], [("BREAD", "BRD WM")])
    assert (result.food_id, result.basis) == ("BREAD", "RETAILER_ALIAS_EXACT")


def test_expansion_exact_canonical_name_ranks_first_without_autoselecting():
    result = propose_receipt_food(
        ["AYM BRST"],
        [("WHOLE", "Whole Chicken"), ("BREAST", "Chicken Breast")],
        [],
        candidate_only_labels=["Chicken Breast"],
    )
    assert (result.food_id, result.score, result.basis) == (None, None, "CANDIDATE")
    assert result.candidates[0] == ("BREAST", 1.0)
    # Un-gated Top-3 (2026-10-02): a shared "chicken" token may trail as a
    # weak manual-pick suggestion, but hybrid scoring keeps it far below 1.0.
    assert all(score < 0.6 for _, score in result.candidates[1:])


def test_expansion_exact_trusted_alias_does_not_autoselect():
    result = propose_receipt_food(
        ["BRD WM"],
        [("BREAD", "Bread")],
        [],
        [("BREAD", "Wholemeal Bread")],
        candidate_only_labels=["Wholemeal Bread"],
    )
    assert (result.food_id, result.score, result.basis) == (None, None, "CANDIDATE")
    assert result.candidates[0] == ("BREAD", 1.0)


def test_expansion_candidate_ties_keep_food_id_order():
    result = propose_receipt_food(
        ["UNKNOWN"],
        [("B", "Rice"), ("A", "Rice")],
        [],
        candidate_only_labels=["Rice"],
    )
    assert (result.food_id, result.score, result.basis) == (None, None, "CANDIDATE")
    assert result.candidates[:2] == [("A", 1.0), ("B", 1.0)]


def test_chicken_fillet_expansion_ranks_specific_cut_without_autoselect():
    result = propose_receipt_food(
        ["CHICK FILLET"],
        [("WHOLE", "whole chicken"), ("BREAST", "chicken breast")],
        [],
        candidate_only_labels=["chicken breast"],
    )
    assert result.food_id is None
    assert result.candidates[0] == ("BREAST", 1.0)


def test_verified_sommerset_brand_is_bread_candidate_not_cheese():
    expansion = verified_product_expansion("SOMMERSET COTTAGE")
    assert expansion == "sliced bread"
    assert verified_product_expansion("ordinary cottage cheese") is None
    result = propose_receipt_food(
        ["SOMMERSET COTTAGE"],
        [("SF160", "sliced bread"), ("SF168", "cheese slices")], [],
        candidate_only_labels=[expansion],
    )
    assert result.food_id is None
    assert result.candidates[0] == ("SF160", 1.0)


def test_chicken_ramen_does_not_rank_plain_chicken():
    names = [("CHICKEN", "whole chicken"), ("NOODLES", "instant noodles (packet)")]
    without_expansion = propose_receipt_food(["NISSIN CHICKEN RAMEN 5PX425G"], names, [])
    # Un-gated candidates (2026-10-02): plain chicken may appear as a weak
    # manual-pick suggestion, but never preselects and stays dampened.
    assert without_expansion.food_id is None
    assert without_expansion.basis == "CANDIDATE"
    assert all(score < 0.5 for _, score in without_expansion.candidates)

    with_expansion = propose_receipt_food(
        ["NISSIN CHICKEN RAMEN 5PX425G"], names, [],
        candidate_only_labels=["instant noodles (packet)"],
    )
    assert with_expansion.food_id is None
    assert with_expansion.candidates[0] == ("NOODLES", 1.0)


def test_butter_loaf_does_not_rank_ingredient_butter():
    result = propose_receipt_food(
        ["BUTTER LOAF"],
        [("BUTTER", "butter"), ("BREAD", "sliced bread")],
        [],
    )
    # Un-gated candidates (2026-10-02): the ingredient may surface as a weak
    # manual-pick suggestion, but a shared word must never preselect it.
    assert result.food_id is None
    assert result.basis == "CANDIDATE"
    assert all(score < 0.7 for _, score in result.candidates)


def test_malay_alias_ranks_star_anise_above_other_spices():
    result = propose_receipt_food(
        ["MERIAH BUNGA LAWANG"],
        [("STAR_ANISE", "star anise"), ("CLOVES", "cloves")],
        [("STAR_ANISE", "bunga lawang"), ("CLOVES", "bunga cengkih")],
    )
    assert result.food_id is None
    assert result.candidates[0] == ("STAR_ANISE", 0.7858)


def test_nonfood_charge_does_not_get_food_candidates():
    result = propose_receipt_food(
        ["PLASTIC BAG CHARGE"],
        [("GARLIC", "garlic"), ("ONION", "onion"), ("BREAD", "sliced bread")],
        [],
    )
    # Sanity floor (2026-10-02): a charge row's sub-0.30 character noise is
    # dropped entirely; it never preselects and shows no suggestion.
    assert result.food_id is None
    assert result.basis == "CANDIDATE"
    assert result.candidates == []


def test_printed_exact_ranks_ahead_of_conflicting_exact_expansion():
    result = propose_receipt_food(
        ["BANANA"],
        [("ORANGE", "orange"), ("BANANA", "banana")],
        [],
        candidate_only_labels=["orange"],
    )
    assert result.food_id == "BANANA"
    assert result.candidates == [("BANANA", 1.0), ("ORANGE", 1.0)]


def test_bostani_thinfilled_is_review_only_chocolate_despite_conflicting_model_hint():
    from packages.receipt_catalog_suggestions import combine_review_candidates

    raw = "BUSTANI THINFILLED ASST500GM"
    assert verified_product_expansion(raw) == "chocolate confectionery"
    names = [("CHOCOLATE", "chocolate confectionery"), ("BISCUITS", "sweet biscuits"),
             ("POWDER", "chocolate drink powder")]
    result = propose_receipt_food([raw], names, [], candidate_only_labels=["sweet biscuits"])
    assert (result.food_id, result.score, result.basis) == (None, None, "CANDIDATE")
    combined = combine_review_candidates(result.candidates, ["BISCUITS"], result.food_id,
                                         verified_review_ids=["CHOCOLATE"])
    assert combined[0] == ("CHOCOLATE", 1.0)
    # The numeric score remains first even when mobile sorts the response.
    assert sorted(combined, key=lambda item: -item[1])[0][0] == "CHOCOLATE"
    # Un-gated candidates (2026-10-02): POWDER may trail as a weak suggestion,
    # but the reviewed family keeps it far from the top slot.
    assert all(score < 0.6 for food_id, score in combined if food_id == "POWDER")


def test_bostani_brand_alone_or_biscuits_does_not_get_chocolate_override():
    assert verified_product_expansion("BOSTANI") is None
    assert verified_product_expansion("BOSTANI SWEET BISCUITS 500GM") is None
    assert verified_product_expansion("OTHER THINFILLED ASST500GM") is None
    assert verified_product_expansion("BOSTANI THIN FILLED ASST 500GM") == "chocolate confectionery"
    assert verified_product_expansion("BOSTANI THIN & FILLED ASST 500GM") == "chocolate confectionery"
    result = propose_receipt_food(["BOSTANI SWEET BISCUITS 500GM"],
                                 [("CHOCOLATE", "chocolate confectionery"), ("BISCUITS", "sweet biscuits")],
                                 [], candidate_only_labels=["sweet biscuits"])
    assert result.food_id is None
    # Un-gated candidates (2026-10-02): weak trails may follow the 1.0 pick.
    assert result.candidates[0] == ("BISCUITS", 1.0)
    assert all(score < 0.6 for _, score in result.candidates[1:])


def test_peel_fresh_juice_family_is_review_only_and_blocks_raw_fruit_model_hint():
    from packages.receipt_catalog_suggestions import combine_review_candidates

    names = [("ORANGE", "orange"), ("JUICE", "fruit juice drink"), ("JUICE", "jus buah")]
    raw = "PEEL FRESH ORANGE 2L"
    assert verified_product_expansion(raw) == "fruit juice drink"
    result = propose_receipt_food([raw], names, [], candidate_only_labels=["orange"])
    assert result.food_id is None
    assert result.candidates == [("JUICE", 1.0)]
    combined = combine_review_candidates(result.candidates, ["ORANGE"], None,
                                         purchase_label=raw, canonical_names=names)
    assert combined == [("JUICE", 1.0)]
    assert verified_product_expansion("MARIGOLD ORANGE 2L") is None
    assert verified_product_expansion("PEEL FRESH") is None


def test_juice_form_guard_applies_to_trusted_aliases_without_changing_raw_fruit():
    names = [("APPLE", "apple"), ("ORANGE", "orange"), ("JUICE", "fruit juice drink")]
    result = propose_receipt_food(["APPLE JUICE"], names, [], [("APPLE", "APPLE JUICE")])
    assert result.food_id is None
    assert "APPLE" not in [food_id for food_id, _ in result.candidates]
    assert propose_receipt_food(["ORANGE"], names, []).food_id == "ORANGE"
    # Form guard + sanity floor (2026-10-02): a juice-form label never
    # suggests raw fruit; the dampened juice score is below the noise floor.
    assert propose_receipt_food(["ORANGE 2L"], names, [], candidate_only_labels=["orange"]).candidates == []
