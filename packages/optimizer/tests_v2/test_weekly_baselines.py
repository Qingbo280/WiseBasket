"""Acceptance checks for the four provisional hardcoded B40 profiles."""

from dataclasses import replace
from decimal import Decimal as D

import pytest

from packages.optimizer.wisebasket_optimizer.v2.calculations import PurchaseOption
from packages.optimizer.wisebasket_optimizer.v2.domain import assess_recipe
from packages.optimizer.wisebasket_optimizer.v2.safety import FoodSafety
from services.api.app.planner_v2_service import PlannerV2Catalog, create_plan_v2, selection_is_overloaded
from services.api.app.schemas import PlannerV2CreateRequest
from services.api.app.weekly_baselines import PILOT_MEALS


PRICES = {
    "SF006": ("0.025", "9.8"), "SF018": ("0.58", "8.42"),
    "SF055": ("1", "4.49"), "SF057": ("1", "3.15"),
    "SF062": ("1", "5"), "SF072": ("1", "6.99"),
    "SF077": ("1", "3.99"), "SF110": ("2", "3.499"),
}


def catalog(*, missing=(), estimated=()):
    return PlannerV2Catalog(
        recipes=(),
        purchase_options=tuple(
            PurchaseOption(food_id, D(unit), D(price), price_is_estimated=food_id in estimated)
            for food_id, (unit, price) in PRICES.items() if food_id not in missing
        ),
        food_safety=tuple(
            FoodSafety(food_id, food_id != "SF006", food_id not in {"SF006", "SF018"},
                       False, frozenset({"EGG"}) if food_id == "SF018" else frozenset())
            for food_id in PRICES if food_id not in missing
        ),
    )


@pytest.mark.parametrize("adults,children,budget,meals,scenario", [
    (1, 0, 100, 5, "solo"),
    (1, 2, 100, 10, "single-parent"),
    (2, 1, 150, 9, "small-family"),
    (2, 3, 200, 14, "larger-family"),
])
def test_four_baselines_cover_meals_with_priced_carbs_protein_and_vegetables(
    adults, children, budget, meals, scenario,
):
    response = create_plan_v2(PlannerV2CreateRequest(
        household={"adults": adults, "children": children},
        budget_rm=D(budget), target_meals=meals,
    ), catalog(), planning_week=40)
    purchased = {item.food_id: item for item in response.shopping_items if item.purchase_units}
    used = {allocation.food_id for allocation in response.allocations}
    assert response.baseline_id == scenario
    assert response.baseline_version == "b40-pilot-v1"
    assert response.baseline_status == "PILOT"
    assert response.outcome.status == "FULL_PLAN"
    assert response.outcome.supported_meals == meals
    assert response.exact_total_cost_rm <= budget
    assert "SF110" in purchased and {"SF006", "SF018"} <= purchased.keys()
    vegetables = {"SF077"} if scenario == "solo" else {"SF055", "SF077"}
    assert vegetables <= purchased.keys()
    assert vegetables <= used
    assert "SF069" not in purchased and "SF071" not in purchased
    assert purchased["SF018"].purchase_kg in {0.58, 1.16, 1.74, 2.32}
    assert all(not item.price_is_estimated for item in purchased.values())


def test_rotating_vegetable_changes_without_changing_the_screen_contract():
    request = PlannerV2CreateRequest(
        household={"adults": 1, "children": 2}, budget_rm=D("100"), target_meals=10,
    )
    first = create_plan_v2(request, catalog(), planning_week=40)
    second = create_plan_v2(request, catalog(), planning_week=41)
    first_ids = {item.food_id for item in first.shopping_items if item.purchase_units}
    second_ids = {item.food_id for item in second.shopping_items if item.purchase_units}
    assert "SF077" in first_ids and "SF057" in second_ids
    assert first.baseline_id == second.baseline_id == "single-parent"


def test_ten_meal_family_baseline_avoids_buying_two_extra_vegetable_packs():
    request = PlannerV2CreateRequest(
        household={"adults": 2, "children": 1},
        budget_rm=D("100"), target_meals=10,
        selected_food_ids=["SF110", "SF006", "SF018", "SF055"],
    )
    response = create_plan_v2(request, catalog(), planning_week=40)
    shorter = create_plan_v2(request.model_copy(update={"target_meals": 6}),
                            catalog(), planning_week=40)
    vegetables = {item.food_id: item for item in response.shopping_items
                  if item.food_id in {"SF055", "SF077"} and item.purchase_units}
    shorter_vegetables = {item.food_id: item for item in shorter.shopping_items
                          if item.food_id in {"SF055", "SF077"} and item.purchase_units}
    assert response.outcome.status == "FULL_PLAN"
    assert shorter.outcome.status == "FULL_PLAN"
    assert set(vegetables) == {"SF055", "SF077"}
    assert sum(item.purchase_kg for item in vegetables.values()) == D("3")
    assert sum(item.purchase_kg for item in shorter_vegetables.values()) == D("2")
    assert response.exact_total_cost_rm <= D("100")


def test_three_meal_family_uses_a_small_baseline_instead_of_a_large_recipe_basket():
    response = create_plan_v2(PlannerV2CreateRequest(
        household={"adults": 2, "children": 0},
        budget_rm=D("200"), target_meals=3,
        selected_food_ids=["SF110", "SF006", "SF018", "SF055"],
    ), catalog(), planning_week=40)
    purchased = {item.food_id: item for item in response.shopping_items if item.purchase_units}
    assert response.baseline_id == "small-family"
    assert response.outcome.status == "FULL_PLAN"
    assert response.outcome.supported_meals == 3
    assert set(purchased) == {"SF110", "SF006", "SF018", "SF055", "SF077"}
    assert purchased["SF006"].purchase_kg <= D("0.5")


def test_too_many_usual_foods_do_not_become_solver_purchase_priorities():
    assert not selection_is_overloaded({"SF110", "SF006", "SF018", "SF055"}, PILOT_MEALS, 3)
    assert selection_is_overloaded({"SF110", "SF006", "SF018", "SF055", "SF057", "SF062", "SF072", "SF077"}, PILOT_MEALS, 3)
    assert selection_is_overloaded({f"usual-{index}" for index in range(20)}, PILOT_MEALS, 10)


def test_egg_allergy_removes_egg_from_plan_and_menu():
    response = create_plan_v2(PlannerV2CreateRequest(
        household={"adults": 1, "children": 2}, budget_rm=D("100"),
        target_meals=6, allergens=["EGG"],
    ), catalog(), planning_week=40)
    assert response.baseline_id == "single-parent"
    assert all(item.food_id != "SF018" or item.purchase_units == 0
               for item in response.shopping_items)
    assert all("egg" not in recipe.recipe_id for recipe in response.recipes)


def test_missing_or_estimated_core_price_does_not_activate_a_pilot_baseline():
    request = PlannerV2CreateRequest(
        household={"adults": 1, "children": 0}, budget_rm=D("100"), target_meals=5,
    )
    for unavailable in (catalog(missing={"SF110"}), catalog(estimated={"SF110"})):
        response = create_plan_v2(request, unavailable, planning_week=40)
        assert response.baseline_id is None
        assert response.baseline_status is None
        assert response.outcome.status == "SHORTFALL"


def test_tight_budget_returns_a_result_instead_of_an_unsolved_rotation_model():
    response = create_plan_v2(PlannerV2CreateRequest(
        household={"adults": 2, "children": 3},
        budget_rm=D("75"), target_meals=14,
    ), catalog(), planning_week=40)
    assert response.baseline_id == "larger-family"
    assert response.exact_total_cost_rm <= 75
    assert response.outcome.status in {"FULL_PLAN", "SHORTFALL"}


def test_protected_purchases_survive_when_baseline_exceeds_sixty_percent():
    live_like = catalog()
    live_like = replace(live_like, purchase_options=live_like.purchase_options + (
        PurchaseOption("SF002", D("0.025"), D("38")),
        PurchaseOption("SF089", D("1"), D("3.49")),
    ))
    response = create_plan_v2(PlannerV2CreateRequest(
        household={"adults": 2, "children": 2},
        budget_rm=D("50"), target_meals=9,
        selected_food_ids=["SF002", "SF089"],
        minimum_purchase_quantities=[
            {"food_id": "SF002", "purchase_kg": D("0.25")},
            {"food_id": "SF089", "purchase_kg": D("1")},
        ],
    ), live_like, planning_week=40)
    purchased = {item.food_id: item for item in response.shopping_items if item.purchase_units}
    # The pilot baseline essentials exceed 60% of this budget, so the planner
    # must use the regular solver instead of forcing the more expensive basket.
    assert response.baseline_id is None
    assert response.outcome.status == "SHORTFALL"
    assert response.exact_total_cost_rm <= 30
    assert purchased["SF002"].purchase_kg >= 0.25
    assert purchased["SF089"].purchase_kg >= 1


def test_pilot_recipes_remain_unapproved_outside_explicit_baseline_path():
    assert PILOT_MEALS
    assert all(not assess_recipe(recipe).optimizer_eligible for recipe in PILOT_MEALS)
    assert all(assess_recipe(recipe, allow_pilot=True).optimizer_eligible for recipe in PILOT_MEALS)
