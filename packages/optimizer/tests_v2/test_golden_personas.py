# End-to-end controlled personas through the database-free V2 service.
from decimal import Decimal as D

from packages.optimizer.tests_v2.test_optimizer import meal, options
from packages.optimizer.tests_v2.test_substitution_optimizer import chicken_rule
from packages.optimizer.wisebasket_optimizer.v2.calculations import PurchaseOption
from services.api.app.planner_v2_service import PlannerV2Catalog, create_plan_v2
from services.api.app.schemas import PlannerV2CreateRequest


def request(**changes):
    values = {
        "household": {"adults": 1, "children": 2},
        "budget_rm": D("150"),
        "target_meals": 10,
    }
    values.update(changes)
    return PlannerV2CreateRequest(**values)


def four_recipe_catalog(include_beef_price=True):
    purchase_options = list(options(chicken="10", egg="5", tofu="2"))
    if include_beef_price:
        purchase_options.append(PurchaseOption("beef", D("0.1"), D("20")))
    return PlannerV2Catalog(
        recipes=(
            meal("chicken-meal", "chicken"),
            meal("egg-meal", "egg"),
            meal("tofu-meal", "tofu"),
            meal("beef-meal", "beef"),
        ),
        purchase_options=tuple(purchase_options),
    )


def canonical_family_catalog():
    return PlannerV2Catalog(
        recipes=(
            meal("chicken-meal", "chicken"),
            meal("egg-meal", "egg"),
            meal("tofu-meal", "tofu"),
            meal("beef-meal", "beef"),
        ),
        purchase_options=options(chicken="10", egg="5", tofu="2"),
        substitution_rules=(chicken_rule(recipe_ids=frozenset({"beef-meal"})),),
    )


def canonical_family_request(**changes):
    values = {
        "pantry": [
            {"food_id": "rice", "quantity_kg": D("1.0"), "status": "CONFIRMED"},
            {"food_id": "egg", "quantity_kg": D("0.3"), "status": "CONFIRMED"},
            {"food_id": "oil", "quantity_kg": D("0.1"), "status": "CONFIRMED"},
            {"food_id": "yoghurt", "quantity_kg": D("0.5"), "status": "CONFIRMED"},
            {"food_id": "cheese", "quantity_kg": D("0.2"), "status": "CONFIRMED"},
        ],
        "preferences": [
            {"food_id": "chicken", "score": 10},
            {"food_id": "beef", "score": 9},
        ],
    }
    values.update(changes)
    return request(**values)


def item(response, food_id):
    return next(row for row in response.shopping_items if row.food_id == food_id)


def test_new_family_with_empty_pantry_receives_ten_complete_meals():
    response = create_plan_v2(request(), four_recipe_catalog())
    assert response.outcome.status == "FULL_PLAN"
    assert response.outcome.supported_meals == 10
    assert response.outcome.deferred_meals == 0
    assert sum(recipe.occurrences for recipe in response.recipes) == 10
    assert all(row.pantry_used_kg == 0 for row in response.shopping_items)
    assert response.exact_total_cost_rm <= 150


def test_confirmed_family_pantry_reduces_purchases_without_changing_portions():
    empty = create_plan_v2(request(), four_recipe_catalog())
    stocked = create_plan_v2(request(pantry=[
        {"food_id": "rice", "quantity_kg": D("1"), "status": "CONFIRMED"},
        {"food_id": "chicken", "quantity_kg": D("0.2"), "status": "CONFIRMED"},
    ]), four_recipe_catalog())
    assert item(stocked, "rice").demand_kg == item(empty, "rice").demand_kg
    assert item(stocked, "rice").pantry_used_kg == 1.0
    assert item(stocked, "rice").purchase_kg < item(empty, "rice").purchase_kg
    assert stocked.exact_total_cost_rm < empty.exact_total_cost_rm


def test_missing_beef_price_returns_food_id_and_maximum_affordable_meals():
    response = create_plan_v2(request(), four_recipe_catalog(include_beef_price=False))
    assert response.outcome.status == "SHORTFALL"
    assert response.outcome.supported_meals == 9
    assert response.outcome.error_codes == ["MISSING_PRICE"]
    assert response.outcome.missing_price_food_ids == ["beef"]
    assert response.outcome.minimum_additional_budget_rm is None


def test_edible_yield_and_bounded_top_up_surplus_are_visible_in_api_response():
    recipe = meal("yield-meal", protein_kg="0.300", max_occurrences=1)
    purchase_options = tuple(
        option for option in options(chicken="10") if option.food_id != "chicken"
    ) + (
        PurchaseOption("chicken", D("0.200"), D("10"), D("0.80")),
    )
    response = create_plan_v2(
        request(household={"adults": 2, "children": 0}, target_meals=1),
        PlannerV2Catalog(recipes=(recipe,), purchase_options=purchase_options),
    )
    chicken = item(response, "chicken")
    assert chicken.demand_kg == 0.3
    assert chicken.purchase_units == 3
    assert chicken.purchase_kg == 0.6
    assert chicken.surplus_kg == 0.18


def test_complex_family_result_is_deterministic():
    payload = request(
        pantry=[{"food_id": "rice", "quantity_kg": D("0.5"), "status": "CONFIRMED"}],
        preferences=[{"food_id": "chicken", "score": 10}],
    )
    first = create_plan_v2(payload, four_recipe_catalog())
    second = create_plan_v2(payload, four_recipe_catalog())
    assert first == second


def test_canonical_family_scenario_is_complete_measurable_and_auditable():
    payload = canonical_family_request()
    first = create_plan_v2(payload, canonical_family_catalog())
    second = create_plan_v2(payload, canonical_family_catalog())

    assert first == second
    assert first.outcome.status == "FULL_PLAN"
    assert first.outcome.supported_meals == 10
    assert sum(recipe.occurrences for recipe in first.recipes) == 10
    assert {recipe.recipe_id: recipe.occurrences for recipe in first.recipes} == {
        "beef-meal": 2,
        "chicken-meal": 2,
        "egg-meal": 3,
        "tofu-meal": 3,
    }

    assert len(first.substitutions) == 1
    substitution = first.substitutions[0]
    assert substitution.recipe_id == "beef-meal"
    assert substitution.original_food_id == "beef"
    assert substitution.substitute_food_id == "chicken"
    assert substitution.occurrences == 2

    assert item(first, "rice").purchase_kg == 0
    assert item(first, "rice").pantry_used_kg == 1.0
    assert item(first, "oil").purchase_kg == 0
    assert item(first, "egg").pantry_used_kg == 0.3
    assert all(row.purchase_kg >= row.shortage_kg for row in first.shopping_items)

    line_total = round(sum(row.estimated_cost_rm for row in first.shopping_items), 2)
    assert line_total == first.displayed_total_cost_rm
    assert first.displayed_total_cost_rm == round(first.exact_total_cost_rm, 2)
    assert first.exact_total_cost_rm <= 150


def test_canonical_family_scenario_reports_budget_shortfall_without_trimming():
    response = create_plan_v2(
        canonical_family_request(budget_rm=D("10")),
        canonical_family_catalog(),
    )

    assert response.outcome.status == "SHORTFALL"
    assert response.outcome.supported_meals < 10
    assert response.outcome.deferred_meals == 10 - response.outcome.supported_meals
    assert response.outcome.error_codes == ["INSUFFICIENT_BUDGET"]
    assert response.outcome.minimum_additional_budget_rm is not None
    assert all(recipe.occurrences == int(recipe.occurrences) for recipe in response.recipes)
