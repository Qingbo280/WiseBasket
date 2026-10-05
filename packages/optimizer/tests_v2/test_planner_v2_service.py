# Controlled V2 application-service tests with no database or HTTP server.
from decimal import Decimal as D

import pytest
from pydantic import ValidationError

from packages.optimizer.tests_v2.test_optimizer import meal, options
from packages.optimizer.wisebasket_optimizer.v2.calculations import (
    Household,
    PantryStock,
    PurchaseOption,
)
from packages.optimizer.wisebasket_optimizer.v2.domain import (
    CookingStep,
    IngredientRole,
    MealType,
    QuantityBasis,
    RecipeIngredient,
    ReviewStatus,
    ReviewedRecipe,
)
from services.api.app.planner_v2_service import PlannerV2Catalog, create_plan_v2
from services.api.app.recipe_opportunities import (
    build_recipe_opportunities,
    ingredient_purchase_priority,
)
from services.api.app.schemas import PlannerV2CreateRequest


def catalog():
    return PlannerV2Catalog(
        recipes=(meal("chicken-meal", max_occurrences=3),),
        purchase_options=options(chicken="10"),
    )


def request(**changes):
    values = {
        "household": {"adults": 2, "children": 0},
        "budget_rm": D("10"),
        "target_meals": 1,
    }
    values.update(changes)
    return PlannerV2CreateRequest(**values)


def shopping_item(response, food_id):
    return next(item for item in response.shopping_items if item.food_id == food_id)


def test_accepted_food_without_database_price_stays_unpriced_and_out_of_total():
    priced = create_plan_v2(request(selected_food_ids=["chicken"]), catalog())
    with_unpriced = create_plan_v2(
        request(
            selected_food_ids=["chicken", "SF106"],
            minimum_purchase_quantities=[{"food_id": "SF106", "purchase_kg": D("0.25")}],
        ),
        catalog(),
    )

    assert with_unpriced.unpriced_food_ids == ["SF106"]
    assert with_unpriced.exact_total_cost_rm == priced.exact_total_cost_rm
    assert all(item.food_id != "SF106" for item in with_unpriced.shopping_items)
    assert create_plan_v2(
        request(selected_food_ids=["chicken", "SF106"]), catalog()
    ).unpriced_food_ids == ["SF106"]


def opportunity_recipe(recipe_id, ingredients, max_occurrences=3):
    rows = tuple(
        RecipeIngredient(food_id, D(quantity), role)
        for food_id, quantity, role in ingredients
    )
    return ReviewedRecipe(
        recipe_id=recipe_id,
        name=recipe_id.replace("-", " ").title(),
        meal_type=MealType.COMPLETE_MEAL,
        base_servings=D("2"),
        version=1,
        review_status=ReviewStatus.APPROVED,
        optimizer_eligible=True,
        quantity_basis=QuantityBasis.RAW_EDIBLE_KG,
        ingredients=rows,
        steps=(CookingStep(1, "Cook and serve.", frozenset(row.food_id for row in rows)),),
        max_weekly_occurrences=max_occurrences,
    )


def purchase_options(*food_ids):
    return tuple(PurchaseOption(food_id, D("0.1"), D("10")) for food_id in food_ids)


def test_opportunity_role_priority_is_protein_then_staple_then_vegetable():
    assert ingredient_purchase_priority(IngredientRole.MAIN_PROTEIN) < ingredient_purchase_priority(IngredientRole.STAPLE)
    assert ingredient_purchase_priority(IngredientRole.STAPLE) < ingredient_purchase_priority(IngredientRole.MAIN_VEGETABLE)


def test_opportunities_reuse_remaining_basket_stock_before_pricing_addons():
    roles = IngredientRole
    planned = opportunity_recipe("planned", (
        ("egg", "0.2", roles.MAIN_PROTEIN),
        ("rice", "0.1", roles.STAPLE),
    ))
    add_on = opportunity_recipe("add-on", (
        ("egg", "0.2", roles.MAIN_PROTEIN),
        ("rice", "0.1", roles.STAPLE),
        ("carrot", "0.1", roles.MAIN_VEGETABLE),
    ))

    opportunities = build_recipe_opportunities(
        recipes=(planned, add_on),
        household=Household(adults=2, children=0),
        selected_food_ids={"egg"},
        anchor_food_ids={"egg", "rice"},
        pantry=(PantryStock("rice", D("0.1"), "CONFIRMED"),),
        purchase_options=purchase_options("egg", "rice", "carrot"),
        excluded_food_ids=frozenset(),
        budget_rm=D("20"),
    )

    assert [item.recipe_id for item in opportunities] == ["add-on"]
    assert opportunities[0].additional_meals == 1
    assert [item.food_id for item in opportunities[0].missing_ingredients] == ["carrot"]


def test_an_existing_recipe_can_be_suggested_for_another_incremental_meal():
    recipe = opportunity_recipe("planned", (
        ("egg", "0.2", IngredientRole.MAIN_PROTEIN),
        ("rice", "0.1", IngredientRole.STAPLE),
    ))

    opportunities = build_recipe_opportunities(
        recipes=(recipe,),
        household=Household(adults=2, children=0),
        selected_food_ids={"egg"},
        anchor_food_ids={"egg", "rice"},
        pantry=(PantryStock("rice", D("0.05"), "CONFIRMED"),),
        purchase_options=purchase_options("egg", "rice"),
        excluded_food_ids=frozenset(),
        budget_rm=D("20"),
    )

    assert [item.recipe_id for item in opportunities] == ["planned"]
    assert opportunities[0].additional_meals == 1
    assert [item.food_id for item in opportunities[0].missing_ingredients] == ["rice"]


def test_backend_returns_at_most_three_opportunities_priced_for_one_meal_each():
    roles = IngredientRole
    recipes = tuple(
        opportunity_recipe(f"option-{index}", (
            ("egg", "0.2", roles.MAIN_PROTEIN),
            (f"vegetable-{index}", "0.1", roles.MAIN_VEGETABLE),
        ))
        for index in range(4)
    )
    opportunities = build_recipe_opportunities(
        recipes=recipes,
        household=Household(adults=2, children=0),
        selected_food_ids={"egg"},
        anchor_food_ids={"egg"},
        pantry=(),
        purchase_options=purchase_options(
            "egg", *(f"vegetable-{index}" for index in range(4))
        ),
        excluded_food_ids=frozenset(),
        budget_rm=D("20"),
    )

    assert len(opportunities) == 3
    assert all(item.additional_meals == 1 for item in opportunities)


def test_new_user_defaults_to_an_empty_pantry_and_buys_everything():
    payload = request()
    assert payload.pantry == []
    response = create_plan_v2(payload, catalog())
    chicken = shopping_item(response, "chicken")
    assert chicken.demand_kg == 0.2
    assert chicken.pantry_used_kg == 0.0
    assert chicken.purchase_kg == 0.4


def test_selected_unknown_pantry_food_does_not_reduce_purchases():
    response = create_plan_v2(request(pantry=[
        {"food_id": "chicken", "status": "UNKNOWN"},
    ]), catalog())
    chicken = shopping_item(response, "chicken")
    assert chicken.pantry_used_kg == 0.0
    assert chicken.purchase_kg == 0.4


def test_estimated_quantity_does_not_reduce_purchases():
    response = create_plan_v2(request(pantry=[
        {"food_id": "chicken", "quantity_kg": D("0.2"), "status": "ESTIMATED"},
    ]), catalog())
    assert shopping_item(response, "chicken").purchase_kg == 0.4


def test_confirmed_quantity_reduces_only_the_current_plan_request():
    with_pantry = create_plan_v2(request(pantry=[
        {"food_id": "chicken", "quantity_kg": D("0.1"), "status": "CONFIRMED"},
    ]), catalog())
    after_removal = create_plan_v2(request(pantry=[]), catalog())
    assert shopping_item(with_pantry, "chicken").pantry_used_kg == 0.1
    assert shopping_item(with_pantry, "chicken").purchase_kg == 0.2
    assert shopping_item(after_removal, "chicken").pantry_used_kg == 0.0
    assert shopping_item(after_removal, "chicken").purchase_kg == 0.4


def test_food_preference_never_becomes_pantry_stock():
    response = create_plan_v2(request(preferences=[
        {"food_id": "chicken", "score": 10},
    ]), catalog())
    chicken = shopping_item(response, "chicken")
    assert chicken.pantry_used_kg == 0.0
    assert chicken.purchase_kg == 0.4


def test_selected_foods_limit_planning_to_connected_recipes():
    connected_catalog = PlannerV2Catalog(
        recipes=(meal("chicken-meal"), meal("tofu-meal", protein="tofu")),
        purchase_options=options(chicken="10", tofu="1"),
    )
    response = create_plan_v2(
        request(selected_food_ids=["chicken"]),
        connected_catalog,
    )
    assert [recipe.recipe_id for recipe in response.recipes] == ["chicken-meal"]


def test_affordable_weekly_choice_wins_over_a_cheaper_complete_recipe():
    choices = PlannerV2Catalog(
        recipes=(meal("chicken-meal", protein="chicken"), meal("tofu-meal", protein="tofu")),
        purchase_options=options(chicken="10", tofu="1"),
    )
    chosen = create_plan_v2(
        request(budget_rm=D("20"), selected_food_ids=["rice", "chicken"]),
        choices,
    )
    assert chosen.outcome.status == "FULL_PLAN"
    # Rice connects both recipes, so the weekly chicken choice breaks the
    # otherwise cheaper tofu route while the basket remains affordable.
    assert [recipe.recipe_id for recipe in chosen.recipes] == ["chicken-meal"]


def test_unselected_plan_still_prefers_the_cheapest_complete_recipe():
    choices = PlannerV2Catalog(
        recipes=(meal("chicken-meal", protein="chicken"), meal("tofu-meal", protein="tofu")),
        purchase_options=options(chicken="10", tofu="1"),
    )
    unselected = create_plan_v2(request(budget_rm=D("20")), choices)
    assert [recipe.recipe_id for recipe in unselected.recipes] == ["tofu-meal"]


def test_non_baseline_week_plan_uses_household_weekly_floor_for_purchased_meat():
    response = create_plan_v2(
        request(budget_rm=D("100"), selected_food_ids=["SF002"]),
        PlannerV2Catalog(
            recipes=(meal("beef-meal", protein="SF002", max_occurrences=1),),
            purchase_options=options(SF002="10"),
        ),
    )

    assert response.baseline_id is None
    assert response.outcome.status == "FULL_PLAN"
    assert shopping_item(response, "SF002").purchase_kg == 1.0


def test_no_choice_plan_rotates_safe_reviewed_food_anchors_between_weeks():
    roles = IngredientRole
    first = opportunity_recipe("prawn-noodles", (
        ("SF022", "0.1", roles.MAIN_PROTEIN),
        ("SF109", "0.1", roles.STAPLE),
        ("SF055", "0.1", roles.MAIN_VEGETABLE),
    ))
    second = opportunity_recipe("egg-potato", (
        ("SF018", "0.1", roles.MAIN_PROTEIN),
        ("SF057", "0.1", roles.STAPLE),
        ("SF062", "0.1", roles.MAIN_VEGETABLE),
    ))
    from packages.optimizer.wisebasket_optimizer.v2.safety import FoodSafety
    food_ids = ("SF022", "SF109", "SF055", "SF018", "SF057", "SF062")
    approved_catalog = PlannerV2Catalog(
        recipes=(first, second),
        purchase_options=purchase_options(*food_ids),
        food_safety=tuple(FoodSafety(food_id, True, True, False, frozenset()) for food_id in food_ids),
    )

    week_one = create_plan_v2(request(budget_rm=D("100")), approved_catalog, planning_week=1)
    week_two = create_plan_v2(request(budget_rm=D("100")), approved_catalog, planning_week=2)
    assert [recipe.recipe_id for recipe in week_one.recipes] == ["prawn-noodles"]
    assert [recipe.recipe_id for recipe in week_two.recipes] == ["egg-potato"]


def test_week_plan_uses_at_most_sixty_percent_of_the_submitted_budget():
    response = create_plan_v2(
        request(
            budget_rm=D("10"), target_meals=4,
            selected_food_ids=[f"usual-{index}" for index in range(35)],
        ),
        PlannerV2Catalog(
            recipes=(meal("chicken-meal", max_occurrences=4),),
            purchase_options=options(chicken="10"),
        ),
    )

    assert response.exact_total_cost_rm <= 6
    assert response.remaining_budget_rm >= 4
    assert response.quality.purchased_food_count < 30


def test_replan_never_reduces_an_accepted_purchase_quantity():
    response = create_plan_v2(
        request(
            selected_food_ids=["chicken"],
            minimum_purchase_quantities=[
                {"food_id": "chicken", "purchase_kg": D("0.3")},
            ],
        ),
        catalog(),
    )

    assert shopping_item(response, "chicken").purchase_kg >= 0.3


def test_accepted_quantity_may_use_the_safety_buffer_but_not_exceed_the_hard_budget():
    response = create_plan_v2(
        request(
            budget_rm=D("10"),
            selected_food_ids=["chicken"],
            minimum_purchase_quantities=[
                {"food_id": "chicken", "purchase_kg": D("0.9")},
            ],
        ),
        catalog(),
    )

    assert response.outcome.status == "FULL_PLAN"
    assert shopping_item(response, "chicken").purchase_kg >= 0.9
    assert 8.5 < response.exact_total_cost_rm <= 10


def test_accepted_premium_protein_above_discretionary_cap_still_replans():
    response = create_plan_v2(
        request(
            budget_rm=D("100"),
            selected_food_ids=["beef"],
            minimum_purchase_quantities=[
                {"food_id": "beef", "purchase_kg": D("0.5")},
            ],
        ),
        PlannerV2Catalog(
            recipes=(meal("beef-meal", protein="beef"),),
            purchase_options=options(beef="40"),
        ),
    )

    assert shopping_item(response, "beef").purchase_kg >= 0.5
    assert response.exact_total_cost_rm <= 100


def test_accepted_purchase_above_budget_returns_cost_instead_of_crashing():
    response = create_plan_v2(
        request(
            budget_rm=D("10"),
            selected_food_ids=["chicken"],
            minimum_purchase_quantities=[
                {"food_id": "chicken", "purchase_kg": D("1.2")},
            ],
        ),
        catalog(),
    )

    assert shopping_item(response, "chicken").purchase_kg >= 1.2
    assert response.displayed_total_cost_rm > 10
    assert response.remaining_budget_rm == 0


def test_spare_planning_budget_tops_up_existing_core_foods_not_cooking_essentials():
    response = create_plan_v2(
        request(budget_rm=D("10"), target_meals=1),
        catalog(),
    )

    assert shopping_item(response, "chicken").purchase_kg == 0.4
    assert shopping_item(response, "rice").purchase_kg == 0.2
    assert shopping_item(response, "carrot").purchase_kg == 0.2
    assert shopping_item(response, "oil").purchase_kg == 0.01
    assert response.exact_total_cost_rm <= 8.5


def test_top_up_keeps_premium_protein_inside_its_combined_guardrail():
    response = create_plan_v2(
        request(budget_rm=D("100"), target_meals=1),
        PlannerV2Catalog(
            recipes=(meal("beef-meal", protein="beef", max_occurrences=1),),
            purchase_options=options(beef="40"),
        ),
    )

    assert shopping_item(response, "beef").estimated_cost_rm <= 12.75


def test_recipe_opportunities_are_complete_bundles_outside_the_week_plan():
    egg_curry = opportunity_recipe("egg-curry", (
        ("egg", "0.2", IngredientRole.MAIN_PROTEIN),
        ("rice", "0.1", IngredientRole.STAPLE),
        ("potato", "0.1", IngredientRole.MAIN_VEGETABLE),
        ("coconut-milk", "0.1", IngredientRole.COOKING_ESSENTIAL),
    ))
    priced_foods = ("egg", "rice", "potato", "coconut-milk")
    opportunities = build_recipe_opportunities(
        recipes=(egg_curry,),
        household=Household(adults=2, children=0),
        selected_food_ids={"egg", "rice"},
        pantry=(),
        purchase_options=tuple(
            PurchaseOption(food_id, D("0.1"), D("10"))
            for food_id in priced_foods
        ),
        excluded_food_ids=frozenset(),
        budget_rm=D("100"),
    )

    assert len(opportunities) == 1
    opportunity = opportunities[0]
    assert opportunity.recipe_id == "egg-curry"
    assert opportunity.additional_meals == 1
    assert [item.food_id for item in opportunity.missing_ingredients] == [
        "potato",
        "coconut-milk",
    ]
    assert [item.purchase_priority for item in opportunity.missing_ingredients] == [2, 3]
    assert all(item.food_id not in {"egg", "rice"} for item in opportunity.missing_ingredients)
    assert opportunity.estimated_cost_rm == 2.0
    assert all(item.price_is_estimated is False for item in opportunity.missing_ingredients)


def test_recipe_opportunity_can_use_the_unspent_weekly_buffer():
    planned = opportunity_recipe("egg-rice", (
        ("egg", "0.2", IngredientRole.MAIN_PROTEIN),
        ("rice", "0.1", IngredientRole.STAPLE),
        ("cabbage", "0.1", IngredientRole.MAIN_VEGETABLE),
    ), max_occurrences=1)
    with_carrot = opportunity_recipe("egg-rice-carrot", (
        ("egg", "0.2", IngredientRole.MAIN_PROTEIN),
        ("rice", "0.1", IngredientRole.STAPLE),
        ("cabbage", "0.1", IngredientRole.MAIN_VEGETABLE),
        ("carrot", "0.1", IngredientRole.SUPPORTING_VEGETABLE),
    ), max_occurrences=1)
    response = create_plan_v2(
        request(
            budget_rm=D("10"),
            selected_food_ids=["egg", "rice", "cabbage"],
        ),
        PlannerV2Catalog(
            recipes=(planned, with_carrot),
            purchase_options=(
                PurchaseOption("egg", D("0.1"), D("10")),
                PurchaseOption("rice", D("0.1"), D("10")),
                PurchaseOption("cabbage", D("0.1"), D("10")),
                PurchaseOption("carrot", D("0.1"), D("10")),
            ),
        ),
    )

    assert response.exact_total_cost_rm <= 6.0
    assert [item.recipe_id for item in response.recipe_opportunities] == ["egg-rice-carrot"]
    assert response.recipe_opportunities[0].estimated_cost_rm == 1.0


def test_visible_recipe_suggestions_fit_within_their_combined_budget_share():
    recipes = tuple(opportunity_recipe(f"meal-{food}", (
        ("egg", "0.1", IngredientRole.MAIN_PROTEIN),
        (food, "0.1", IngredientRole.MAIN_VEGETABLE),
    )) for food in ("carrot", "cabbage", "potato"))
    opportunities = build_recipe_opportunities(
        recipes=recipes,
        household=Household(adults=2, children=0),
        selected_food_ids={"egg"},
        pantry=(),
        purchase_options=purchase_options("egg", "carrot", "cabbage", "potato"),
        excluded_food_ids=frozenset(),
        budget_rm=D("2"),
    )

    assert len(opportunities) == 2
    assert sum(D(str(item.estimated_cost_rm)) for item in opportunities) <= D("2")


def test_recipe_opportunities_rank_reusable_ingredients_and_recipe_bundles():
    roles = IngredientRole
    potato_curry = opportunity_recipe("potato-curry", (
        ("egg", "0.2", roles.MAIN_PROTEIN),
        ("rice", "0.1", roles.STAPLE),
        ("potato", "0.1", roles.MAIN_VEGETABLE),
        ("curry", "0.01", roles.SEASONING),
    ))
    potato_soup = opportunity_recipe("potato-soup", (
        ("chicken", "0.2", roles.MAIN_PROTEIN),
        ("rice", "0.1", roles.STAPLE),
        ("potato", "0.1", roles.MAIN_VEGETABLE),
        ("spice", "0.01", roles.SEASONING),
    ))
    carrot_meal = opportunity_recipe("carrot-meal", (
        ("egg", "0.2", roles.MAIN_PROTEIN),
        ("rice", "0.1", roles.STAPLE),
        ("carrot", "0.1", roles.MAIN_VEGETABLE),
        ("oil", "0.01", roles.COOKING_ESSENTIAL),
    ))
    unpriced_potato_meal = opportunity_recipe("unpriced-potato-meal", (
        ("egg", "0.2", roles.MAIN_PROTEIN),
        ("rice", "0.1", roles.STAPLE),
        ("potato", "0.1", roles.MAIN_VEGETABLE),
        ("unpriced-sauce", "0.01", roles.COOKING_ESSENTIAL),
    ))
    opportunities = build_recipe_opportunities(
        recipes=(carrot_meal, potato_curry, potato_soup, unpriced_potato_meal),
        household=Household(adults=2, children=0),
        selected_food_ids={"egg", "rice", "chicken"},
        pantry=(),
        purchase_options=purchase_options(
            "egg", "rice", "chicken", "potato", "curry", "spice", "carrot", "oil",
        ),
        excluded_food_ids=frozenset(),
        budget_rm=D("100"),
    )

    potato_items = [
        item
        for opportunity in opportunities
        for item in opportunity.missing_ingredients
        if item.food_id == "potato"
    ]
    assert len(potato_items) == 2
    assert all(item.recipe_reuse_count == 3 for item in potato_items)
    assert opportunities[0].recipe_id == "potato-curry"
    assert [
        item.food_id for item in opportunities[0].missing_ingredients
    ] == ["potato", "curry"]


def test_recipe_opportunities_fail_closed_for_skipped_or_unpriced_bundles():
    roles = IngredientRole
    skipped = opportunity_recipe("skipped", (
        ("egg", "0.2", roles.MAIN_PROTEIN),
        ("rice", "0.1", roles.STAPLE),
        ("potato", "0.1", roles.MAIN_VEGETABLE),
        ("milk", "0.1", roles.COOKING_ESSENTIAL),
    ))
    unpriced = opportunity_recipe("unpriced", (
        ("egg", "0.2", roles.MAIN_PROTEIN),
        ("rice", "0.1", roles.STAPLE),
        ("onion", "0.1", roles.MAIN_VEGETABLE),
        ("oil", "0.01", roles.COOKING_ESSENTIAL),
    ))
    response = create_plan_v2(
        request(selected_food_ids=["egg", "rice"], excluded_food_ids=["milk"]),
        PlannerV2Catalog(
            recipes=(skipped, unpriced),
            purchase_options=purchase_options("egg", "rice", "potato", "milk", "oil"),
        ),
    )

    assert response.recipe_opportunities == []


def test_recipe_opportunities_require_observed_prices_and_rank_one_missing_item_first():
    roles = IngredientRole
    one_missing = opportunity_recipe("one-missing", (
        ("egg", "0.2", roles.MAIN_PROTEIN),
        ("rice", "0.1", roles.STAPLE),
        ("carrot", "0.1", roles.MAIN_VEGETABLE),
    ), max_occurrences=1)
    two_missing = opportunity_recipe("two-missing", (
        ("egg", "0.2", roles.MAIN_PROTEIN),
        ("rice", "0.1", roles.STAPLE),
        ("potato", "0.1", roles.MAIN_VEGETABLE),
        ("curry", "0.01", roles.SEASONING),
    ), max_occurrences=5)
    estimated = opportunity_recipe("estimated", (
        ("egg", "0.2", roles.MAIN_PROTEIN),
        ("rice", "0.1", roles.STAPLE),
        ("spinach", "0.1", roles.MAIN_VEGETABLE),
    ))
    response = create_plan_v2(
        request(budget_rm=D("100"), selected_food_ids=["egg", "rice"]),
        PlannerV2Catalog(
            recipes=(two_missing, estimated, one_missing),
            purchase_options=(
                *purchase_options("egg", "rice", "carrot", "potato", "curry"),
                PurchaseOption("spinach", D("0.1"), D("10"), price_is_estimated=True),
            ),
        ),
    )

    assert [item.recipe_id for item in response.recipe_opportunities] == [
        "one-missing",
        "two-missing",
    ]


@pytest.mark.parametrize("pantry", [
    [{"food_id": "rice", "status": "CONFIRMED"}],
    [{"food_id": "rice", "status": "ESTIMATED"}],
    [{"food_id": "rice", "quantity_kg": D("0.1"), "status": "UNKNOWN"}],
])
def test_invalid_pantry_state_and_quantity_combinations_are_rejected(pantry):
    with pytest.raises(ValidationError):
        request(pantry=pantry)


def test_service_returns_versioned_recipe_shopping_and_assumption_contracts():
    response = create_plan_v2(request(), catalog())
    assert response.planner_version == "recipe-first-v2"
    assert response.portion_policy_version == "adult-1-child-0.5-v1"
    assert response.child_portion_factor == 0.5
    assert response.quantity_basis == "RAW_EDIBLE_KG"
    assert response.outcome.status == "FULL_PLAN"
    assert response.outcome.error_codes == []
    assert response.recipes[0].recipe_id == "chicken-meal"
    assert response.recipes[0].occurrences == 1
