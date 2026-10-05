# Controlled nutrition scoring tests: no database and no medical claims.
from decimal import Decimal as D

import pytest

from packages.optimizer.wisebasket_optimizer.v2.calculations import Household, PurchaseOption
from packages.optimizer.wisebasket_optimizer.v2.domain import (
    CookingStep,
    IngredientRole,
    MealType,
    QuantityBasis,
    RecipeIngredient,
    ReviewStatus,
    ReviewedRecipe,
)
from packages.optimizer.wisebasket_optimizer.v2.nutrition import (
    FoodNutrition,
    NutritionTargets,
    household_nutrition_targets,
)
from packages.optimizer.wisebasket_optimizer.v2.optimizer import optimize_recipe_plan


def meal(recipe_id: str, protein: str, max_occurrences: int = 2) -> ReviewedRecipe:
    ingredients = (
        RecipeIngredient(protein, D("1"), IngredientRole.MAIN_PROTEIN),
        RecipeIngredient("rice", D("0.1"), IngredientRole.STAPLE),
        RecipeIngredient("carrot", D("0.1"), IngredientRole.MAIN_VEGETABLE),
        RecipeIngredient("oil", D("0.01"), IngredientRole.COOKING_ESSENTIAL),
    )
    return ReviewedRecipe(
        recipe_id, recipe_id, MealType.COMPLETE_MEAL, D("1"), 1,
        ReviewStatus.APPROVED, True, QuantityBasis.RAW_EDIBLE_KG,
        ingredients,
        (CookingStep(1, "Cook.", frozenset(i.food_id for i in ingredients)),),
        max_occurrences,
    )


def options(**protein_prices: str) -> tuple[PurchaseOption, ...]:
    common = (
        PurchaseOption("rice", D("0.1"), D("0.01")),
        PurchaseOption("carrot", D("0.1"), D("0.01")),
        PurchaseOption("oil", D("0.01"), D("0.01")),
    )
    return common + tuple(
        PurchaseOption(food_id.replace("_", "-"), D("1"), D(price))
        for food_id, price in protein_prices.items()
    )


def test_household_reference_uses_adult_and_child_counts_not_recipe_portions():
    targets = household_nutrition_targets(Household(1, 2), meal_occasions=3)
    assert targets == NutritionTargets(D("5200"), D("120"), D("3000"))


def test_capped_linear_score_prefers_complementary_recipes():
    result = optimize_recipe_plan(
        Household(1, 0),
        (meal("energy-meal", "energy-food"), meal("protein-meal", "protein-food")),
        (),
        options(energy_food="1", protein_food="1"),
        D("10"),
        2,
        nutrition_targets=NutritionTargets(D("1000"), D("60"), D("1000")),
        food_nutrition=(
            FoodNutrition("energy-food", D("1000"), D("0"), D("0")),
            FoodNutrition("protein-food", D("0"), D("60"), D("1000")),
        ),
    )
    assert result.occurrences == {"energy-meal": 1, "protein-meal": 1}
    assert result.nutrition is not None
    assert result.nutrition.energy_coverage == D("1")
    assert result.nutrition.protein_coverage == D("1")
    assert result.nutrition.calcium_coverage == D("1")


def test_cost_breaks_tie_after_nutrition_targets_are_capped():
    result = optimize_recipe_plan(
        Household(1, 0),
        (meal("enough", "enough-food", 1), meal("excess", "excess-food", 1)),
        (),
        options(enough_food="1", excess_food="4"),
        D("10"),
        1,
        nutrition_targets=NutritionTargets(D("100"), D("10"), D("100")),
        food_nutrition=(
            FoodNutrition("enough-food", D("100"), D("10"), D("100")),
            FoodNutrition("excess-food", D("1000"), D("100"), D("1000")),
        ),
    )
    assert result.occurrences == {"enough": 1}
    assert result.calculation.exact_cost_rm < D("2")


def test_missing_nutrition_is_disclosed_without_blocking_a_complete_recipe():
    result = optimize_recipe_plan(
        Household(1, 0),
        (meal("unknown", "unknown-food", 1),),
        (),
        options(unknown_food="1"),
        D("10"),
        1,
        nutrition_targets=NutritionTargets(D("100"), D("10"), D("100")),
        food_nutrition=(),
    )
    assert result.meal_count == 1
    assert result.nutrition.missing_food_ids == ("carrot", "oil", "rice", "unknown-food")
    assert result.nutrition.energy_coverage == D("0")


@pytest.mark.parametrize("factory", [
    lambda: FoodNutrition("rice", D("-1"), D("0"), D("0")),
    lambda: FoodNutrition("rice", D("0"), D("0"), D("0")),
    lambda: NutritionTargets(D("0"), D("10"), D("100")),
    lambda: household_nutrition_targets(Household(1, 0), 0),
])
def test_invalid_nutrition_inputs_are_rejected(factory):
    with pytest.raises(ValueError):
        factory()
