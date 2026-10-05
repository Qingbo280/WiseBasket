# Controlled shortfall diagnostics and API response codes.
from decimal import Decimal as D

from packages.optimizer.tests_v2.test_optimizer import meal, options
from packages.optimizer.wisebasket_optimizer.v2.calculations import (
    Household,
    PantryStock,
    PurchaseOption,
)
from packages.optimizer.wisebasket_optimizer.v2.optimizer import optimize_recipe_plan
from services.api.app.planner_v2_response import build_plan_v2_outcome


def test_budget_shortfall_returns_api_code_and_minimum_additional_budget():
    result = optimize_recipe_plan(
        Household(2, 0), (meal("chicken", max_occurrences=10),), (),
        options(chicken="10"), D("5.00"), 4,
    )
    response = build_plan_v2_outcome(result)
    assert result.reason_codes == ("INSUFFICIENT_BUDGET",)
    assert result.minimum_additional_budget_rm == D("4.40")
    assert response.model_dump() == {
        "status": "SHORTFALL",
        "requested_meals": 4,
        "supported_meals": 2,
        "deferred_meals": 2,
        "error_codes": ["INSUFFICIENT_BUDGET"],
        "minimum_additional_budget_rm": 4.4,
        "estimated_total_cost_rm": 4.7,
        "missing_price_food_ids": [],
    }


def test_recipe_cap_is_structural_and_has_no_budget_amount():
    result = optimize_recipe_plan(
        Household(2, 0), (meal("chicken", max_occurrences=2),), (),
        options(chicken="10"), D("100"), 3,
    )
    assert result.reason_codes == ("RECIPE_LIMIT_REACHED",)
    assert result.minimum_additional_budget_rm is None


def test_missing_price_is_reported_as_machine_readable_code():
    pantry = tuple(PantryStock(food, D("1")) for food in ("rice", "carrot", "oil"))
    result = optimize_recipe_plan(
        Household(2, 0), (meal("chicken"),), pantry, (), D("100"), 1,
    )
    assert result.reason_codes == ("MISSING_PRICE",)


def test_exclusions_that_remove_all_recipes_are_reported():
    result = optimize_recipe_plan(
        Household(2, 0), (meal("chicken"),), (), options(chicken="10"), D("100"), 1,
        excluded_food_ids={"chicken"},
    )
    assert result.reason_codes == ("RESTRICTIONS_TOO_LIMITING",)


def test_full_plan_has_no_error_code_or_additional_budget():
    result = optimize_recipe_plan(
        Household(2, 0), (meal("chicken"),), (), options(chicken="10"), D("10"), 1,
    )
    response = build_plan_v2_outcome(result)
    assert response.status == "FULL_PLAN"
    assert response.error_codes == []
    assert response.minimum_additional_budget_rm is None


def test_additional_budget_is_rounded_up_to_a_cent():
    tiny = meal("tiny", protein_kg="0.001", max_occurrences=1)
    pantry = tuple(PantryStock(food, D("1")) for food in ("rice", "carrot", "oil"))
    result = optimize_recipe_plan(
        Household(2, 0), (tiny,), pantry,
        (PurchaseOption("chicken", D("0.001"), D("11")),), D("0.01"), 1,
    )
    assert result.minimum_additional_budget_rm == D("0.01")
