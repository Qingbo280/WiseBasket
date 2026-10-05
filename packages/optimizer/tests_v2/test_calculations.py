# Database-free V2 contracts; never import the API's destructive fixtures.
from decimal import Decimal as D
from pathlib import Path

import pytest

from packages.optimizer.wisebasket_optimizer.v2.calculations import (
    Household, Ingredient, Recipe, RecipeSelection, PantryStock, PurchaseOption,
    calculate_plan, display_kg,
)


def meal(recipe_id="chicken", protein="chicken"):
    return Recipe(recipe_id, D("2"), (
        Ingredient(protein, D("0.300")),
        Ingredient("rice", D("0.160")),
        Ingredient("oil", D("0.010")),
        Ingredient("garlic", D("0.005"), required=False),
    ))


def test_scaling_and_shared_pantry_conservation():
    result = calculate_plan(Household(1, 2), (
        RecipeSelection(meal(), 3), RecipeSelection(meal("soup"), 2),
    ), (PantryStock("chicken", D("0.500")),), (
        PurchaseOption("chicken", D("0.050"), D("12.80")),
        PurchaseOption("rice", D("2.000"), D("3.149")),
        PurchaseOption("oil", D("1.000"), D("6")),
    ), D("150"))
    chicken = result.items["chicken"]
    assert result.meal_count == 5
    assert chicken.demand_kg == D("1.500")
    assert chicken.pantry_used_kg == D("0.500")
    assert chicken.shortage_kg == D("1.000")
    assert chicken.purchase_kg == D("1.000")
    assert "garlic" not in result.items
    assert sum(a.pantry_used_kg for a in result.allocations if a.food_id == "chicken") == D("0.500")


def test_unknown_and_estimated_stock_do_not_reduce_purchases():
    result = calculate_plan(Household(1, 2), (RecipeSelection(meal(), 1),), (
        PantryStock("chicken", None, "UNKNOWN"),
        PantryStock("rice", D("10"), "ESTIMATED"),
        PantryStock("oil", D("1")),
    ), (PurchaseOption("chicken", D("0.050"), D("12.80")),
        PurchaseOption("rice", D("2"), D("3"))), D("150"))
    assert result.items["chicken"].shortage_kg == D("0.300")
    assert result.items["rice"].shortage_kg == D("0.160")
    assert result.items["oil"].purchase_kg == 0


def test_yield_pack_rounding_and_cost_use_full_precision():
    recipe = Recipe("cabbage", D("1"), (Ingredient("cabbage", D("1")),))
    result = calculate_plan(Household(1, 0), (RecipeSelection(recipe, 1),), (), (
        PurchaseOption("cabbage", D("0.050"), D("4.60"), D("0.72")),
    ), D("6"))
    item = result.items["cabbage"]
    assert item.purchase_units == 28
    assert item.purchase_kg == D("1.40")
    assert item.edible_surplus_kg == D("0.008")
    assert result.total_cost_rm == D("6.44")
    assert not result.within_budget
    assert result.extra_budget_rm == D("0.44")


def test_missing_price_blocks_shortage_but_not_pantry_only_food():
    recipe = Recipe("egg", D("1"), (Ingredient("egg", D("0.100")),))
    with pytest.raises(ValueError, match="purchase option.*egg"):
        calculate_plan(Household(1, 0), (RecipeSelection(recipe, 1),), (), (), D("150"))
    result = calculate_plan(Household(1, 0), (RecipeSelection(recipe, 1),),
        (PantryStock("egg", D("0.100")),), (), D("150"))
    assert result.total_cost_rm == 0


def test_optional_ingredient_requires_explicit_selection():
    result = calculate_plan(Household(1, 2),
        (RecipeSelection(meal(), 1, frozenset({"garlic"})),),
        tuple(PantryStock(fid, D("1")) for fid in ("chicken", "rice", "oil", "garlic")),
        (), D("150"))
    assert result.items["garlic"].demand_kg == D("0.005")


@pytest.mark.parametrize("value,expected", [("0", "0.00 kg"),
    ("0.005", "<0.01 kg"), ("0.160", "0.16 kg"), ("1.925", "1.93 kg")])
def test_display_never_changes_internal_quantities(value, expected):
    assert display_kg(D(value)) == expected


@pytest.mark.parametrize("factory", [
    lambda: Household(0, 0),
    lambda: Household(-1, 2),
    lambda: Ingredient("oil", D("0")),
    lambda: Ingredient("oil", D("NaN")),
    lambda: Recipe("bad", D("0"), (Ingredient("rice", D("1")),)),
    lambda: RecipeSelection(meal(), 0),
    lambda: PurchaseOption("rice", D("0"), D("3")),
    lambda: PurchaseOption("rice", D("1"), D("0")),
    lambda: PurchaseOption("rice", D("1"), D("3"), D("1.1")),
    lambda: PantryStock("rice", None, "CONFIRMED"),
])
def test_invalid_domain_inputs_are_rejected(factory):
    with pytest.raises(ValueError):
        factory()


def test_decimal_budget_is_checked_before_display_rounding():
    recipe = Recipe("rice", D("1"), (Ingredient("rice", D("0.01")),))
    result = calculate_plan(Household(1, 0), (RecipeSelection(recipe, 1),), (),
        (PurchaseOption("rice", D("0.01"), D("1.004")),), D("0.01"))
    assert result.total_cost_rm == D("0.01")
    assert not result.within_budget


def test_ten_meal_mimic_uses_confirmed_stock_and_frozen_uat_prices():
    # Illustrative recipes, not reviewed UAT recipes. Prices are a frozen
    # national UAT snapshot from 14-15 September 2026; no network access.
    def recipe(rid, quantities):
        return Recipe(rid, D("2"), tuple(Ingredient(fid, D(q)) for fid, q in quantities.items()))
    selections = (
        RecipeSelection(recipe("chicken-stir-fry", {"chicken": ".300", "carrot": ".100", "beans": ".100", "rice": ".160", "oil": ".010", "soy": ".015", "garlic": ".005"}), 3),
        RecipeSelection(recipe("beef-stir-fry", {"beef": ".250", "cabbage": ".200", "carrot": ".100", "rice": ".160", "oil": ".010", "soy": ".015", "garlic": ".005"}), 2),
        RecipeSelection(recipe("chicken-soup", {"chicken": ".300", "potato": ".150", "carrot": ".100", "cabbage": ".100", "rice": ".160", "spices": ".005"}), 3),
        RecipeSelection(recipe("egg-stir-fry", {"egg": ".200", "tomato": ".150", "cabbage": ".150", "rice": ".160", "oil": ".010", "garlic": ".005"}), 2),
    )
    pantry = (PantryStock("rice", D("2")), PantryStock("egg", D(".5")), PantryStock("oil", D(".2")))
    rows = {"chicken": (".05", "13.79", "1"), "beef": (".05", "34.90", "1"),
        "carrot": (".05", "3.99", ".89"), "beans": (".05", "7.99", ".92"),
        "cabbage": (".05", "4.60", ".72"), "potato": (".05", "3.20", ".93"),
        "tomato": (".05", "8", ".88"), "garlic": (".05", "9", ".92"),
        "soy": (".4", "14.706", "1"), "spices": (".25", "36.40", "1")}
    options = tuple(PurchaseOption(fid, *(D(v) for v in row)) for fid, row in rows.items())
    result = calculate_plan(Household(1, 2), selections, pantry, options, D("150"))
    assert result.meal_count == 10
    assert result.within_budget
    assert result.items["rice"].pantry_used_kg == D("1.600")
    assert result.items["egg"].pantry_used_kg == D(".400")
    assert result.items["oil"].pantry_used_kg == D(".070")
    assert result.items["cabbage"].purchase_kg == D("1.40")
    # Round the full-precision total, rather than adding rounded line costs.
    assert result.exact_cost_rm == D("74.9319")
    assert result.total_cost_rm == D("74.93")
    assert result == calculate_plan(Household(1, 2), selections, pantry, options, D("150"))


def test_household_scaling_retains_small_ingredients_and_additive_pantry_lots():
    recipe = Recipe("garlic", D("2"), (Ingredient("garlic", D(".005")),))
    result = calculate_plan(Household(1, 0), (RecipeSelection(recipe, 1),),
        (PantryStock("garlic", D(".001")), PantryStock("garlic", D(".0015"))), (), D("150"))
    assert result.items["garlic"].demand_kg == D(".0025")
    assert result.items["garlic"].pantry_used_kg == D(".0025")
    assert result.items["garlic"].purchase_kg == 0


def test_v1_has_no_public_entry_point_and_api_cannot_route_to_it():
    import packages.optimizer.wisebasket_optimizer as optimizer

    assert not hasattr(optimizer, "optimize")
    root = Path(__file__).resolve().parents[3]
    source = (root / "services/api/app/main.py").read_text(encoding="utf-8")
    route = source[source.index('@app.post("/api/v1/plans")'):]
    route = route[:route.index('@app.post("/api/v1/households")')]
    assert "PLANNER_V1_RETIRED" in route
    assert "_run_legacy_optimizer_db" not in route
    assert "_create_persisted_plan" not in route
    assert not (root / "packages/optimizer/wisebasket_optimizer/solver.py").exists()
    for retired in ("habits.py", "meals.py", "suggestions.py", "substitutes.py"):
        assert not (root / "packages/optimizer/wisebasket_optimizer" / retired).exists()


def test_recipe_planner_has_no_llm_ranking_path():
    root = Path(__file__).resolve().parents[3]
    source = (root / "services/api/app/main.py").read_text(encoding="utf-8")
    assert "LLMClient" not in source
    assert "rank_recipe_substitutions" not in source
    assert not (root / "services/api/app/services/worth_llm.py").exists()
    assert not (root / "services/api/app/services/recipe_substitution_ranking.py").exists()
