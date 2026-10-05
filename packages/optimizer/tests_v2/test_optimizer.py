# Controlled CP-SAT planner tests: synthetic inputs only.
from decimal import Decimal as D

import pytest

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
from packages.optimizer.wisebasket_optimizer.v2.optimizer import optimize_recipe_plan


def meal(
    recipe_id: str,
    protein: str = "chicken",
    protein_kg: str = "0.200",
    max_occurrences: int = 3,
    status: ReviewStatus = ReviewStatus.APPROVED,
) -> ReviewedRecipe:
    ingredients = (
        RecipeIngredient(protein, D(protein_kg), IngredientRole.MAIN_PROTEIN),
        RecipeIngredient("rice", D("0.100"), IngredientRole.STAPLE),
        RecipeIngredient("carrot", D("0.100"), IngredientRole.MAIN_VEGETABLE),
        RecipeIngredient("oil", D("0.010"), IngredientRole.COOKING_ESSENTIAL),
    )
    return ReviewedRecipe(
        recipe_id=recipe_id,
        name=recipe_id,
        meal_type=MealType.COMPLETE_MEAL,
        base_servings=D("2"),
        version=1,
        review_status=status,
        optimizer_eligible=True,
        quantity_basis=QuantityBasis.RAW_EDIBLE_KG,
        ingredients=ingredients,
        steps=(CookingStep(1, "Cook and serve.", frozenset(i.food_id for i in ingredients)),),
        max_weekly_occurrences=max_occurrences,
    )


def options(**protein_prices: str) -> tuple[PurchaseOption, ...]:
    rows = {
        "rice": ("0.1", "2"),
        "carrot": ("0.1", "1"),
        "oil": ("0.01", "5"),
        **{food: ("0.1", price) for food, price in protein_prices.items()},
    }
    return tuple(PurchaseOption(food, D(unit), D(price)) for food, (unit, price) in rows.items())


def test_exact_target_uses_caps_and_minimizes_purchase_cost():
    result = optimize_recipe_plan(
        Household(2, 0),
        (meal("cheap", "tofu", max_occurrences=2), meal("costly", "beef")),
        (),
        options(tofu="2", beef="20"),
        D("20"),
        target_meals=3,
    )
    assert result.status == "FULL_PLAN"
    assert result.meal_count == 3
    assert result.shortfall_meals == 0
    assert result.occurrences == {"cheap": 2, "costly": 1}
    assert result.calculation.within_budget


def test_weekly_floor_is_rounded_to_purchase_units_when_food_is_bought():
    result = optimize_recipe_plan(
        Household(2, 0),
        (meal("chicken-meal", protein_kg="0.200", max_occurrences=1),),
        (),
        options(chicken="10"),
        D("20"),
        target_meals=1,
        conditional_purchase_floor_kg={"chicken": D("0.55")},
    )

    assert result.status == "FULL_PLAN"
    assert result.calculation.items["chicken"].purchase_kg == D("0.6")
    assert result.calculation.exact_cost_rm <= D("20")


def test_weekly_floor_does_not_force_unselected_food_into_basket():
    result = optimize_recipe_plan(
        Household(2, 0),
        (meal("cheap", "tofu", max_occurrences=1), meal("costly", "chicken", max_occurrences=1)),
        (),
        options(tofu="2", chicken="10"),
        D("1"),
        target_meals=1,
        conditional_purchase_floor_kg={"chicken": D("0.5")},
    )

    assert result.status == "FULL_PLAN"
    assert "chicken" not in result.calculation.items
    assert result.calculation.items["tofu"].purchase_units > 0


def test_rm100_combines_all_premium_meat_under_fifteen_percent():
    result = optimize_recipe_plan(
        Household(2, 0),
        (
            meal("beef-meal", "beef", max_occurrences=1),
            meal("lamb-meal", "lamb", max_occurrences=1),
        ),
        (),
        options(beef="40", lamb="40"),
        D("100"),
        target_meals=2,
    )

    premium_cost = sum(
        result.calculation.items[food_id].exact_cost_rm
        for food_id in ("beef", "lamb")
        if food_id in result.calculation.items
    )
    assert result.meal_count == 1
    assert premium_cost <= D("15")


def test_infeasible_target_returns_maximum_whole_meals_without_trimming_portions():
    result = optimize_recipe_plan(
        Household(2, 0),
        (meal("chicken", max_occurrences=10),),
        (),
        options(chicken="10"),
        D("5.00"),
        target_meals=4,
    )
    assert result.status == "SHORTFALL"
    assert result.meal_count == 2
    assert result.shortfall_meals == 2
    assert result.occurrences == {"chicken": 2}
    assert result.calculation.total_cost_rm == D("4.70")


def test_confirmed_pantry_is_shared_across_all_occurrences():
    result = optimize_recipe_plan(
        Household(2, 0),
        (meal("chicken", max_occurrences=5),),
        (PantryStock("chicken", D("0.300")),),
        options(chicken="10"),
        D("3.00"),
        target_meals=3,
    )
    assert result.meal_count == 2
    assert result.calculation.items["chicken"].pantry_used_kg == D("0.300")
    assert result.calculation.items["chicken"].shortage_kg == D("0.100")


def test_exact_budget_prevents_display_rounding_from_hiding_overspend():
    costly = meal("fractional", protein_kg="0.001", max_occurrences=1)
    result = optimize_recipe_plan(
        Household(2, 0),
        (costly,),
        (
            PantryStock("rice", D("1")),
            PantryStock("carrot", D("1")),
            PantryStock("oil", D("1")),
        ),
        (PurchaseOption("chicken", D("0.001"), D("10.004")),),
        D("0.01"),
        target_meals=1,
    )
    assert result.meal_count == 0
    assert result.status == "SHORTFALL"
    assert result.calculation.total_cost_rm == D("0.00")


def test_unapproved_recipe_is_reported_and_never_selected():
    result = optimize_recipe_plan(
        Household(2, 0),
        (meal("draft", status=ReviewStatus.DRAFT), meal("approved", max_occurrences=1)),
        (),
        options(chicken="1"),
        D("10"),
        target_meals=2,
    )
    assert result.occurrences == {"approved": 1}
    assert result.rejected_recipes["draft"].reasons == ("NOT_APPROVED",)


def test_missing_purchase_option_can_only_use_available_pantry():
    result = optimize_recipe_plan(
        Household(2, 0),
        (meal("chicken", max_occurrences=3),),
        (
            PantryStock("chicken", D("0.200")),
            PantryStock("rice", D("1")),
            PantryStock("carrot", D("1")),
            PantryStock("oil", D("1")),
        ),
        (),
        D("10"),
        target_meals=3,
    )
    assert result.meal_count == 1
    assert result.occurrences == {"chicken": 1}


def test_canonical_household_reaches_ten_meals_deterministically_without_database():
    inputs = dict(
        household=Household(1, 2),
        recipes=(
            meal("chicken-meal", "chicken"),
            meal("egg-meal", "egg"),
            meal("tofu-meal", "tofu"),
            meal("beef-meal", "beef"),
        ),
        pantry=(
            PantryStock("chicken", D("0.300")),
            PantryStock("rice", D("1.000")),
            PantryStock("carrot", D("1.000")),
            PantryStock("oil", D("0.100")),
        ),
        purchase_options=options(chicken="10", egg="5", tofu="2", beef="20"),
        budget_rm=D("150"),
        target_meals=10,
    )
    first = optimize_recipe_plan(**inputs)
    second = optimize_recipe_plan(**inputs)
    assert first.status == "FULL_PLAN"
    assert first.meal_count == 10
    assert first.occurrences == {
        "chicken-meal": 3,
        "egg-meal": 3,
        "tofu-meal": 3,
        "beef-meal": 1,
    }
    assert first.calculation.within_budget
    assert first == second


@pytest.mark.parametrize(("budget", "target"), [(D("0"), 1), (D("10"), 0), (D("10"), 1.5)])
def test_invalid_optimizer_inputs_fail_closed(budget, target):
    with pytest.raises(ValueError):
        optimize_recipe_plan(Household(2, 0), (meal("meal"),), (), options(chicken="1"), budget, target)
