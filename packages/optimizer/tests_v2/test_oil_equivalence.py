from decimal import Decimal as D

import pytest

from packages.optimizer.wisebasket_optimizer.v2.calculations import Household, PantryStock, PurchaseOption
from packages.optimizer.wisebasket_optimizer.v2.domain import (
    CookingStep, IngredientRole, MealType, QuantityBasis, RecipeIngredient,
    ReviewStatus, ReviewedRecipe,
)
from packages.optimizer.wisebasket_optimizer.v2.oil_equivalence import oil_group, oil_raw_kg
from packages.optimizer.wisebasket_optimizer.v2.optimizer import optimize_recipe_plan
from packages.optimizer.wisebasket_optimizer.v2.safety import FoodSafety
from services.api.app.planner_v2_service import PlannerV2Catalog, create_plan_v2
from services.api.app.schemas import PlannerV2CreateRequest
from services.api.app.recipe_opportunities import build_recipe_opportunities


def oil_meal():
    ingredients = (
        RecipeIngredient("protein", D("0.1"), IngredientRole.MAIN_PROTEIN),
        RecipeIngredient("rice", D("0.1"), IngredientRole.STAPLE),
        RecipeIngredient("veg", D("0.1"), IngredientRole.MAIN_VEGETABLE),
        RecipeIngredient("SF120", D("0.5"), IngredientRole.COOKING_ESSENTIAL),
        RecipeIngredient("SF121", D("0.4"), IngredientRole.COOKING_ESSENTIAL),
    )
    return ReviewedRecipe(
        recipe_id="two-oils", name="Two oils", meal_type=MealType.COMPLETE_MEAL,
        base_servings=D("1"), version=1, review_status=ReviewStatus.APPROVED,
        optimizer_eligible=True, quantity_basis=QuantityBasis.RAW_EDIBLE_KG,
        ingredients=ingredients,
        steps=(CookingStep(1, "Cook.", frozenset(i.food_id for i in ingredients)),),
        max_weekly_occurrences=1,
    )


def solve(options, pantry=(), budget=D("10"), preferred=frozenset()):
    return optimize_recipe_plan(
        Household(1, 0), (oil_meal(),),
        tuple(PantryStock(fid, D("1")) for fid in ("protein", "rice", "veg")) + tuple(pantry),
        options, budget, 1, preferred_oil_food_ids=preferred,
        include_shortfall_diagnostics=False,
    )


def test_group_stock_once_and_exact_selected_purchase_cost():
    result = solve(
        (PurchaseOption("SF120", D("0.2"), D("12")), PurchaseOption("SF121", D("0.1"), D("10"))),
        (PantryStock("SF123", D("0.6")),),
    )
    assert result.status == "FULL_PLAN"
    assert sum(a.pantry_used_kg for a in result.calculation.allocations if a.food_id in {"SF120", "SF121"}) == D("0.6")
    purchased = [item for item in result.calculation.items.values() if item.purchase_units]
    assert len(purchased) == 1
    assert purchased[0].food_id == "SF121"
    assert purchased[0].purchase_units == 3
    assert result.calculation.exact_cost_rm == D("3.0")
    oil_allocations = [a for a in result.calculation.allocations if a.food_id in {"SF120", "SF121"}]
    assert all(a.pantry_source_food_ids == ("SF123",) for a in oil_allocations)
    assert oil_allocations[1].purchase_source_food_id == "SF121"


def test_preferred_unpriced_oil_does_not_silently_buy_other_oil():
    result = solve((PurchaseOption("SF120", D("0.1"), D("1")),), preferred=frozenset({"SF121"}))
    assert result.status == "SHORTFALL"
    assert result.calculation.exact_cost_rm == 0


def test_ghee_stock_not_equivalent_and_budget_is_exact():
    stock = (PantryStock("SF122", D("2")),)
    option = (PurchaseOption("SF121", D("0.1"), D("10")),)
    assert solve(option, stock, budget=D("9.00")).status == "FULL_PLAN"
    assert solve(option, stock, budget=D("8.99")).status == "SHORTFALL"
    assert oil_group("SF122") == "SF122"


@pytest.mark.parametrize(("quantity", "unit", "expected"), [
    ("1000", "ml", D("0.92")), ("1", "l", D("0.92")),
    ("1000", "g", D("1")), ("1", "kg", D("1")),
    ("1", "bottle", None),
])
def test_only_reviewed_oil_units_use_density(quantity, unit, expected):
    assert oil_raw_kg(D(quantity), unit) == expected


def test_v2_request_rejects_non_oil_and_duplicate_preferences():
    base = {"household": {"adults": 1, "children": 0}, "budget_rm": "10", "target_meals": 1}
    with pytest.raises(ValueError):
        PlannerV2CreateRequest(**base, purchase_policy={"preferred_oil_food_ids": ["SF122"]})
    with pytest.raises(ValueError):
        PlannerV2CreateRequest(**base, purchase_policy={"preferred_oil_food_ids": ["SF120", "SF120"]})


def test_excluded_equivalent_oil_stock_cannot_bypass_safety():
    catalog = PlannerV2Catalog(
        recipes=(oil_meal(),),
        purchase_options=(PurchaseOption("SF120", D("0.1"), D("10")),),
        food_safety=tuple(FoodSafety(fid, True, True, False) for fid in ("SF120", "SF121", "SF123")),
    )
    base = {
        "household": {"adults": 1, "children": 0}, "budget_rm": "5", "target_meals": 1,
        "pantry": [
            {"food_id": fid, "quantity_kg": str(amount), "status": "CONFIRMED"}
            for fid, amount in (("protein", 1), ("rice", 1), ("veg", 1), ("SF123", D("0.6")))
        ],
    }
    allowed = create_plan_v2(PlannerV2CreateRequest(**base), catalog)
    blocked = create_plan_v2(PlannerV2CreateRequest(**base, excluded_food_ids=["SF123"]), catalog)
    assert allowed.outcome.status == "FULL_PLAN"
    assert blocked.outcome.status == "SHORTFALL"


def test_opportunity_estimate_uses_one_group_shortage_and_one_oil_sku():
    opportunities = build_recipe_opportunities(
        recipes=(oil_meal(),), household=Household(1, 0),
        selected_food_ids={"protein"},
        pantry=tuple(PantryStock(fid, quantity) for fid, quantity in (
            ("rice", D("1")), ("veg", D("1")), ("SF123", D("0.6")),
        )),
        purchase_options=(PurchaseOption("SF120", D("0.1"), D("10")),),
        excluded_food_ids=frozenset(), budget_rm=D("10"),
    )
    assert len(opportunities) == 1
    assert [(item.food_id, item.quantity_kg, item.purchase_units) for item in opportunities[0].missing_ingredients] == [
        ("SF120", 0.3, 3),
    ]
