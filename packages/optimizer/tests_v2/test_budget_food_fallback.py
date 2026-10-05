from decimal import Decimal as D

import pytest

from packages.optimizer.wisebasket_optimizer.v2.calculations import PurchaseOption
from packages.optimizer.wisebasket_optimizer.v2.safety import FoodSafety
from packages.optimizer.tests_v2.test_optimizer import meal, options
from services.api.app.budget_food_fallback import (
    FOOD_FALLBACK_ROWS,
    build_budget_food_fallback,
    rotated_food_rows,
    rotating_week_plan_priorities,
)
from services.api.app.planner_v2_service import PlannerV2Catalog, create_plan_v2
from services.api.app.schemas import PlannerV2CreateRequest


def safe(food_id: str, *, allergens=frozenset()) -> FoodSafety:
    return FoodSafety(food_id, True, True, False, allergens)


def fallback(**changes):
    values = dict(
        budget_rm=D("100"),
        basket_cost_rm=D("50"),
        purchase_options=(
            PurchaseOption("SF022", D("1"), D("33.50")),
            PurchaseOption("SF018", D("1"), D("14.70")),
            PurchaseOption("SF124", D("1"), D("4.80")),
            PurchaseOption("SF055", D("1"), D("4.15")),
            PurchaseOption("SF062", D("1"), D("6")),
            PurchaseOption("SF077", D("1"), D("3.94")),
            PurchaseOption("SF109", D("0.45"), D("1.88") / D("0.45")),
            PurchaseOption("SF057", D("1"), D("3.30")),
            PurchaseOption("SF159", D("0.4"), D("3.90") / D("0.4")),
        ),
        food_safety=tuple(safe(food_id) for food_id in (
            "SF022", "SF018", "SF124", "SF055", "SF062", "SF077",
            "SF109", "SF057", "SF159",
        )),
        dietary_patterns=[],
        allergens=[],
        excluded_food_ids=[],
        basket_food_ids=set(),
        selected_food_ids=set(),
        week=1,
    )
    values.update(changes)
    return build_budget_food_fallback(**values)


@pytest.mark.parametrize("budget,week,expected", [
    (100, 4, ("SF018", "SF072", "SF110")),
    (100, 5, ("SF006", "SF057", "SF110")),
    (200, 4, ("SF018", "SF084", "SF110")),
    (200, 5, ("SF035", "SF079", "SF110")),
    (300, 4, ("SF006", "SF072", "SF110")),
    (300, 5, ("SF022", "SF082", "SF110")),
])
def test_two_more_practical_meal_trios_rotate_into_each_budget_band(budget, week, expected):
    assert len(FOOD_FALLBACK_ROWS[budget]) == 5
    assert rotated_food_rows(D(budget), week)[0] == expected
    prices = {
        "SF006": D("9.80"), "SF018": D("8.42"),
        "SF022": D("35"), "SF035": D("17.69"),
        "SF057": D("3.15"), "SF072": D("6.99"),
        "SF079": D("8"), "SF082": D("11"),
        "SF084": D("8.90"), "SF110": D("3.499"),
    }
    unit_kg = {"SF018": D("0.58"), "SF110": D("2")}
    unit_kg.update({food_id: D("0.025") for food_id in ("SF006", "SF022", "SF035")})
    options = tuple(
        PurchaseOption(food_id, unit_kg.get(food_id, D("1")), prices[food_id])
        for food_id in expected
    )
    reviewed = tuple(safe(food_id) for food_id in expected)
    assert rotating_week_plan_priorities(
        budget_rm=D(budget), purchase_options=options, food_safety=reviewed,
        excluded_food_ids=frozenset(), recipe_food_ids=set(expected), week=week,
    ) == frozenset(expected)
    suggestions = build_budget_food_fallback(
        budget_rm=D(budget), basket_cost_rm=D("0"),
        purchase_options=options, food_safety=reviewed,
        dietary_patterns=[], allergens=[], excluded_food_ids=[],
        basket_food_ids=set(), selected_food_ids=set(),
        purchase_floor_persons=D("1"), week=week,
    )
    assert tuple(item.food_id for item in suggestions) == expected
    assert sum(D(str(item.estimated_cost_rm)) for item in suggestions) <= D(budget)
    assert all(not item.requires_swap for item in suggestions)


def test_recipe_fallback_uses_rotating_groups_and_affordable_purchase_units():
    first = fallback(purchase_floor_persons=D("3"))
    assert [item.food_id for item in first] == ["SF022", "SF055", "SF109"]
    assert first[-1].purchase_kg == 1.35
    assert sum(D(str(item.estimated_cost_rm)) for item in first) <= D("50")
    second = fallback(week=2)
    assert [item.food_id for item in second] == ["SF018", "SF062", "SF057"]


def test_fallback_skips_unreviewed_allergenic_unpriced_and_over_budget_foods():
    result = fallback(
        basket_cost_rm=D("90"),
        food_safety=(
            safe("SF022", allergens=frozenset({"SHELLFISH"})),
            safe("SF018"), safe("SF124"), safe("SF055"), safe("SF062"),
            safe("SF077"), safe("SF109"), safe("SF057"), safe("SF159"),
        ),
        allergens=["SHELLFISH"],
        excluded_food_ids=["SF055"],
        selected_food_ids={"SF018"},
        purchase_options=(
            PurchaseOption("SF022", D("1"), D("33.50")),
            PurchaseOption("SF018", D("1"), D("14.70")),
            PurchaseOption("SF124", D("1"), D("4.80")),
            PurchaseOption("SF055", D("1"), D("4.15")),
            PurchaseOption("SF062", D("1"), D("6"), price_is_estimated=True),
            PurchaseOption("SF077", D("1"), D("3.94")),
            PurchaseOption("SF109", D("0.45"), D("1.88") / D("0.45")),
            PurchaseOption("SF057", D("1"), D("3.30")),
            PurchaseOption("SF159", D("0.4"), D("3.90") / D("0.4")),
        ),
    )
    assert [item.food_id for item in result] == ["SF124", "SF077"]
    assert all(not item.requires_swap for item in result)
    assert sum(D(str(item.estimated_cost_rm)) for item in result) <= D("10")


def test_full_basket_has_no_food_ideas_that_exceed_budget():
    result = fallback(basket_cost_rm=D("100"), purchase_floor_persons=D("3.2"))
    assert result == []


def test_beef_requires_approved_safety_even_in_higher_budget_bands():
    result = fallback(
        budget_rm=D("200"),
        basket_cost_rm=D("120"),
        purchase_options=(
            PurchaseOption("SF002", D("1"), D("40")),
            PurchaseOption("SF035", D("1"), D("17.90")),
            PurchaseOption("SF084", D("1"), D("9.20")),
            PurchaseOption("SF110", D("10"), D("3.35")),
        ),
        food_safety=(safe("SF035"), safe("SF084"), safe("SF110")),
    )
    assert "SF002" not in [item.food_id for item in result]
    assert result[0].food_id == "SF035"


def test_new_item_quantity_uses_only_the_money_left_after_current_basket():
    values = dict(
        budget_rm=D("200"),
        purchase_options=(PurchaseOption("SF002", D("0.025"), D("40")),),
        food_safety=(safe("SF002"),),
        purchase_floor_persons=D("3.2"),
        week=1,
    )
    affordable = fallback(basket_cost_rm=D("190"), **values)
    assert affordable[0].food_id == "SF002"
    assert affordable[0].purchase_kg == 0.25
    assert affordable[0].estimated_cost_rm == 10
    assert affordable[0].requires_swap is False

    no_room = fallback(basket_cost_rm=D("190.01"), **values)
    assert no_room == []


def test_fallback_suggestions_fit_together_within_remaining_budget():
    result = fallback(
        budget_rm=D("100"), basket_cost_rm=D("80"),
        purchase_floor_persons=D("1"),
        purchase_options=(
            PurchaseOption("SF022", D("1"), D("9")),
            PurchaseOption("SF055", D("1"), D("8")),
            PurchaseOption("SF109", D("0.45"), D("6")),
            PurchaseOption("SF018", D("1"), D("9")),
            PurchaseOption("SF062", D("1"), D("8")),
            PurchaseOption("SF057", D("1"), D("6")),
        ),
        food_safety=tuple(safe(food_id) for food_id in (
            "SF022", "SF055", "SF109", "SF018", "SF062", "SF057",
        )),
    )
    assert result
    assert sum(D(str(item.estimated_cost_rm)) for item in result) <= D("20")
    assert all(not item.requires_swap for item in result)


def test_fallback_respects_the_twenty_percent_worth_considering_share():
    result = fallback(suggestion_budget_rm=D("20"))
    assert sum(D(str(item.estimated_cost_rm)) for item in result) <= D("20")


def test_planner_returns_food_fallback_when_no_recipe_can_match():
    response = create_plan_v2(
        PlannerV2CreateRequest(
            household={"adults": 2, "children": 2}, budget_rm=D("100"), target_meals=1,
        ),
        PlannerV2Catalog(
            recipes=(),
            purchase_options=(PurchaseOption("SF022", D("1"), D("33.50")),),
            food_safety=(safe("SF022"),),
        ),
    )
    assert response.recipe_opportunities == []
    # This protein pack costs 33.50, above the 20% suggestion cap (RM20).
    assert response.food_fallback_suggestions == []


def test_accepting_food_idea_keeps_every_existing_purchase_quantity_fixed():
    fixed = [
        {"food_id": "chicken", "purchase_kg": D("0.4")},
        {"food_id": "rice", "purchase_kg": D("0.2")},
        {"food_id": "carrot", "purchase_kg": D("0.2")},
        {"food_id": "oil", "purchase_kg": D("0.02")},
        {"food_id": "SF022", "purchase_kg": D("1")},
    ]
    response = create_plan_v2(
        PlannerV2CreateRequest(
            household={"adults": 2, "children": 0},
            budget_rm=D("100"), target_meals=3,
            selected_food_ids=[row["food_id"] for row in fixed],
            minimum_purchase_quantities=fixed,
            fixed_purchase_quantities=fixed,
        ),
        PlannerV2Catalog(
            recipes=(meal("chicken-meal", max_occurrences=3),),
            purchase_options=(*options(chicken="10"), PurchaseOption("SF022", D("1"), D("33.50"))),
            food_safety=(safe("SF022"),),
        ),
    )
    purchased = {item.food_id: item.purchase_kg for item in response.shopping_items if item.purchase_units > 0}
    assert purchased == {row["food_id"]: float(row["purchase_kg"]) for row in fixed}
    assert response.exact_total_cost_rm <= 100
