from types import SimpleNamespace as N

from services.api.app.services.recipe_ranking import rank_recipe_suggestions


def record(recipe_id, *, name=None, role="MAIN_PROTEIN", food="SF006", status=True, present=1, semantic=0):
    suggestion = N(
        recipe_id=recipe_id, name=name or recipe_id,
        required_ingredient_count=1, required_match_count=present,
        semantic_score=semantic,
    )
    ingredient = N(canonical_food_id=food, required=True, ingredient_role=role, base_quantity_g=100)
    is_chicken_meat = food in {"SF006", "SF014"}
    catalogue_food = N(canonical_name="Whole chicken" if is_chicken_meat else "Chicken egg",
                       canonical_name_ms="Ayam seekor" if is_chicken_meat else "Telur ayam")
    summary = N(ingredients=(N(required=True, is_quantity_sufficient=status),))
    return suggestion, ((ingredient, catalogue_food),), summary


def test_known_sufficient_beats_present_but_unknown_and_semantic():
    rows = [record("unknown", status=None, semantic=1), record("sufficient", status=True)]
    assert [item.recipe_id for item in rank_recipe_suggestions(rows)] == ["sufficient", "unknown"]


def test_protein_cap_three_and_stable_id_tie():
    rows = [record(f"chicken-{index}", name="Same", food="SF006") for index in range(5)]
    rows.append(record("egg", name="Z Egg", food="SF018"))
    # Family overflow is demoted to the tail of its own tier, never dropped.
    assert [item.recipe_id for item in rank_recipe_suggestions(rows)] == [
        "chicken-0", "chicken-1", "chicken-2", "egg", "chicken-3", "chicken-4",
    ]


def test_reviewed_chicken_cut_matches_are_not_hidden_by_three_exact_recipes():
    rows = [record(f"exact-{index}", food="SF006", status=True) for index in range(3)]
    curry = record("curry", food="SF014", status=False)
    turmeric = record("turmeric", food="SF014", status=False)
    curry[0].matched_alternatives = {"SF014": "SF006"}
    turmeric[0].matched_alternatives = {"SF014": "SF006"}
    rows.extend((curry, turmeric))
    assert [item.recipe_id for item in rank_recipe_suggestions(
        rows, pantry_food_ids=frozenset({"SF006"}),
    )] == [
        "exact-0", "exact-1", "exact-2", "curry", "turmeric",
    ]


def test_substituted_chicken_dishes_share_the_normal_three_recipe_quota():
    rows = [record(f"chicken-{index}", food="SF014", status=False) for index in range(5)]
    for suggestion, _, _ in rows:
        suggestion.matched_alternatives = {"SF014": "SF013"}
    # The three-recipe quota demotes overflow to the tier tail, not out.
    assert [item.recipe_id for item in rank_recipe_suggestions(
        rows, pantry_food_ids=frozenset({"SF013"}),
    )] == ["chicken-0", "chicken-1", "chicken-2", "chicken-3", "chicken-4"]


def test_empty_pantry_returns_everything_in_name_order():
    # No total cap: all eligible recipes come back, still deterministically.
    rows = [record(f"recipe-{index:02d}", role="STAPLE", status=False, present=0) for index in range(15)]
    result = rank_recipe_suggestions(rows)
    assert len(result) == 15
    assert [item.recipe_id for item in result] == [f"recipe-{index:02d}" for index in range(15)]


def test_real_catalogue_chicken_egg_has_its_own_three_recipe_quota():
    rows = [record(f"chicken-{index}", food="SF006") for index in range(4)]
    rows += [record(f"egg-{index}", food="SF018") for index in range(4)]
    # Quotas demote each family's fourth dish to the tier tail, in order.
    assert [item.recipe_id for item in rank_recipe_suggestions(rows)] == [
        "chicken-0", "chicken-1", "chicken-2", "egg-0", "egg-1", "egg-2",
        "chicken-3", "egg-3",
    ]


def test_mixed_chicken_and_egg_recipe_counts_against_both_families():
    chicken = record("mixed", food="SF006")
    egg = record("egg", food="SF018")
    mixed = (chicken[0], chicken[1] + egg[1], N(ingredients=chicken[2].ingredients + egg[2].ingredients))
    mixed[0].required_ingredient_count = 2
    mixed[0].required_match_count = 2
    rows = [mixed] + [record(f"z-chicken-{index}", food="SF006") for index in range(3)]
    rows += [record(f"z-egg-{index}", food="SF018") for index in range(3)]
    assert [item.recipe_id for item in rank_recipe_suggestions(rows)] == [
        "mixed", "z-chicken-0", "z-chicken-1", "z-egg-0", "z-egg-1",
        "z-chicken-2", "z-egg-2",
    ]


def test_plan_food_is_secondary_ordering_hint_not_pantry_match():
    rows = [
        record("egg", name="A Egg", food="SF018", status=False, present=0),
        record("chicken", name="Z Chicken", food="SF006", status=False, present=0),
    ]
    assert [item.recipe_id for item in rank_recipe_suggestions(rows)] == ["egg", "chicken"]
    ranked = rank_recipe_suggestions(rows, planned_food_ids=frozenset({"SF006"}))
    assert [item.recipe_id for item in ranked] == ["chicken", "egg"]
    assert ranked[0].required_match_count == 0  # planned, not owned
    assert rows[1][2].ingredients[0].is_quantity_sufficient is False


def test_known_pantry_sufficiency_stays_ahead_of_unpurchased_plan_food():
    rows = [
        record("egg", name="A Egg", food="SF018", status=True, present=1),
        record("chicken", name="Z Chicken", food="SF006", status=False, present=0),
    ]
    # Three-tier contract: a pantry-owned main (tier 1) always beats a
    # planned-but-unpurchased hint (tier 2). pantry_food_ids makes the egg a
    # real pantry main, matching the fixture's sufficiency simulation.
    ranked = rank_recipe_suggestions(
        rows, pantry_food_ids=frozenset({"SF018"}),
        planned_food_ids=frozenset({"SF006"}),
    )
    assert [item.recipe_id for item in ranked] == ["egg", "chicken"]


def test_more_complete_pantry_recipe_beats_plan_hint_and_single_sufficient_ingredient():
    def entry(recipe_id, present, sufficient, planned=False):
        suggestion = N(recipe_id=recipe_id, name=recipe_id,
                       required_ingredient_count=4, required_match_count=present,
                       semantic_score=0)
        rows = tuple((N(canonical_food_id=f"{recipe_id}-{index}", required=True,
                        ingredient_role="STAPLE", base_quantity_g=100),
                      N(canonical_name="Rice", canonical_name_ms=None)) for index in range(4))
        summary = N(ingredients=tuple(N(required=True, is_quantity_sufficient=(
            True if index < sufficient else None)) for index in range(4)))
        return (suggestion, rows, summary)

    rows = [entry("less-complete", 1, 1), entry("more-complete", 3, 1)]
    # Pantry set mirrors each entry's required_match_count: the main-role
    # match ratio (not the raw required ratio) now ranks ahead of the plan
    # hint, so the fixture pantry must be consistent with the counts.
    ranked = rank_recipe_suggestions(
        rows,
        pantry_food_ids=frozenset({
            "less-complete-0",
            "more-complete-0", "more-complete-1", "more-complete-2",
        }),
        planned_food_ids=frozenset({"less-complete-0"}),
    )
    assert [item.recipe_id for item in ranked] == ["more-complete", "less-complete"]


def test_family_overflow_stays_inside_its_own_tier():
    # Four pantry-matched egg dishes: the fourth exceeds the egg family quota
    # and demotes to the tier-1 tail — but must still rank before a tier-2
    # planned dish. Family demotion never breaks the three-tier contract.
    rows = [record(f"egg-{index}", name=f"Egg {index}", food="SF018") for index in range(4)]
    planned_dish = record("chicken", name="A Planned Chicken", food="SF006", status=False, present=0)
    ranked = rank_recipe_suggestions(
        rows + [planned_dish],
        pantry_food_ids=frozenset({"SF018"}),
        planned_food_ids=frozenset({"SF006"}),
    )
    assert [item.recipe_id for item in ranked] == [
        "egg-0", "egg-1", "egg-2", "egg-3", "chicken",
    ]


def test_oil_match_no_longer_inflates_the_required_match_ratio():
    # Pantry owns egg/rice/oil. Recipe B's perfect required-match ratio came
    # only from cooking oil (COOKING_ESSENTIAL); recipe A has every main
    # ingredient but misses salt. The old required-match ratio floated B
    # above A; the main-role ratio ties them and the richer main coverage
    # wins. Oil never counts as a main ingredient anywhere.
    def entry(recipe_id, name, rows_spec, present):
        suggestion = N(recipe_id=recipe_id, name=name,
                       required_ingredient_count=len(rows_spec),
                       required_match_count=present,
                       matched_alternatives={}, semantic_score=0)
        rows = tuple(
            (N(canonical_food_id=food_id, required=True, ingredient_role=role,
               base_quantity_g=grams),
             N(canonical_name=food_id, canonical_name_ms=None))
            for food_id, role, grams in rows_spec
        )
        summary = N(ingredients=tuple(
            N(required=True, is_quantity_sufficient=True) for _ in rows_spec))
        return suggestion, rows, summary

    complete = entry("complete", "Main Complete",
                     (("SF018", "MAIN_PROTEIN", 100),
                      ("SF110", "STAPLE", 160),
                      ("SF150", "SEASONING", 5)), present=2)
    oil_boosted = entry("oil-boosted", "Oil Complete",
                        (("SF018", "MAIN_PROTEIN", 100),
                         ("SF120", "COOKING_ESSENTIAL", 20)), present=2)
    ranked = rank_recipe_suggestions(
        [oil_boosted, complete],
        pantry_food_ids=frozenset({"SF018", "SF110", "SF120"}),
    )
    assert [item.recipe_id for item in ranked] == ["complete", "oil-boosted"]


def test_owned_unknown_chicken_main_survives_top_ten_oil_only_recipes():
    oil_only = []
    for index in range(10):
        suggestion = N(recipe_id=f"oil-{index}", name=f"Oil {index}",
                       required_ingredient_count=2, required_match_count=1,
                       matched_alternatives={}, semantic_score=0)
        rows = (
            (N(canonical_food_id="SF120", required=True, ingredient_role="SEASONING",
               base_quantity_g=20), N(canonical_name="cooking oil", canonical_name_ms=None)),
            (N(canonical_food_id=f"veg-{index}", required=True,
               ingredient_role="MAIN_VEGETABLE", base_quantity_g=200),
             N(canonical_name="vegetable", canonical_name_ms=None)),
        )
        summary = N(ingredients=(N(required=True, is_quantity_sufficient=True),
                                 N(required=True, is_quantity_sufficient=False)))
        oil_only.append((suggestion, rows, summary))
    chicken = record("chicken", name="Chicken Curry", status=False, present=1)
    ranked = rank_recipe_suggestions(
        oil_only + [chicken], pantry_food_ids=frozenset({"SF006", "SF120"}),
    )
    assert ranked[0].recipe_id == "chicken"
    # No total cap: the tier-1 chicken main leads all ten oil-only recipes.
    assert len(ranked) == 11
    assert chicken[2].ingredients[0].is_quantity_sufficient is False


def test_reviewed_substitute_counts_as_owned_main_without_claiming_sufficiency():
    curry = record("curry", food="SF014", status=False, present=1)
    curry[0].matched_alternatives = {"SF014": "SF013"}
    oil = record("oil-only", role="SEASONING", food="SF120", status=True, present=1)
    ranked = rank_recipe_suggestions(
        [oil, curry], pantry_food_ids=frozenset({"SF013", "SF120"}),
    )
    assert [item.recipe_id for item in ranked] == ["curry", "oil-only"]


def test_recipe_browser_consumes_equivalent_oil_stock_once():
    from services.api.app.main import build_recipe_quantity_summary

    rows = [
        (N(canonical_food_id="SF120", required=True, base_quantity_g=500), None),
        (N(canonical_food_id="SF121", required=True, base_quantity_g=400), None),
    ]
    summary = build_recipe_quantity_summary(
        N(base_servings=1), rows, N(adults=1, children=0),
        (N(canonical_food_id="SF123", quantity=0.6, unit="kg", source="MANUAL"),),
    )
    assert sum(item.available_quantity_g or 0 for item in summary.ingredients) == 600
    assert summary.required_quantity_sufficient_count == 1


def test_three_tier_ordering_pantry_then_planned_then_rest():
    # Explicit three-tier contract (no-truncation regression guard): tier 1
    # pantry owns a main, tier 2 the week plan covers a required ingredient,
    # tier 3 the rest — even when a tier-3 recipe has fewer missing
    # ingredients than the tier-2 one.
    def entry(recipe_id, name, rows_spec, present):
        suggestion = N(recipe_id=recipe_id, name=name,
                       required_ingredient_count=len(rows_spec),
                       required_match_count=present,
                       matched_alternatives={}, semantic_score=0)
        rows = tuple(
            (N(canonical_food_id=food_id, required=True, ingredient_role=role,
               base_quantity_g=grams),
             N(canonical_name=food_id, canonical_name_ms=None))
            for food_id, role, grams in rows_spec
        )
        summary = N(ingredients=tuple(
            N(required=True, is_quantity_sufficient=False) for _ in rows_spec))
        return suggestion, rows, summary

    tier1 = entry("a-pantry", "A Pantry Dish",
                  (("SF018", "MAIN_PROTEIN", 100), ("SF120", "COOKING_ESSENTIAL", 20)), present=1)
    tier2 = entry("b-planned", "B Planned Dish",
                  (("SF006", "MAIN_PROTEIN", 200), ("SF120", "COOKING_ESSENTIAL", 20)), present=0)
    tier3 = entry("c-rest", "C Rest Dish",
                  (("SF0BR", "MAIN_VEGETABLE", 300),), present=0)
    ranked = rank_recipe_suggestions(
        [tier3, tier2, tier1],
        pantry_food_ids=frozenset({"SF018", "SF120"}),
        planned_food_ids=frozenset({"SF006"}),
    )
    assert [item.recipe_id for item in ranked] == ["a-pantry", "b-planned", "c-rest"]
    # Deterministic across runs.
    again = rank_recipe_suggestions(
        [tier1, tier2, tier3],
        pantry_food_ids=frozenset({"SF018", "SF120"}),
        planned_food_ids=frozenset({"SF006"}),
    )
    assert [item.recipe_id for item in again] == ["a-pantry", "b-planned", "c-rest"]
