# Controlled staged-objective tests using synthetic recipes and prices.
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
from packages.optimizer.wisebasket_optimizer.v2.optimizer import (
    FoodPreference,
    optimize_recipe_plan,
)


def meal(recipe_id, protein="chicken", vegetable="carrot", staple="rice", protein_kg="0.1", cap=2):
    ingredients = (
        RecipeIngredient(protein, D(protein_kg), IngredientRole.MAIN_PROTEIN),
        RecipeIngredient(staple, D("0.1"), IngredientRole.STAPLE),
        RecipeIngredient(vegetable, D("0.1"), IngredientRole.MAIN_VEGETABLE),
        RecipeIngredient("oil", D("0.01"), IngredientRole.COOKING_ESSENTIAL),
    )
    return ReviewedRecipe(
        recipe_id, recipe_id, MealType.COMPLETE_MEAL, D("1"), 1,
        ReviewStatus.APPROVED, True, QuantityBasis.RAW_EDIBLE_KG,
        ingredients,
        (CookingStep(1, "Cook.", frozenset(i.food_id for i in ingredients)),),
        cap,
    )


def option(food_id, unit="0.1", price="1"):
    return PurchaseOption(food_id, D(unit), D(price))


def common_options(*proteins):
    return tuple(option(food) for food in (*proteins, "rice", "carrot", "oil"))


def test_familiar_food_preference_breaks_an_equal_feasibility_tie():
    result = optimize_recipe_plan(
        Household(1, 0),
        (meal("chicken-meal"), meal("tofu-meal", "tofu")),
        (), common_options("chicken", "tofu"), D("10"), 1,
        food_preferences=(FoodPreference("chicken", 5),),
    )
    assert result.occurrences == {"chicken-meal": 1}
    assert result.quality.preference_score == 5


def test_preference_never_overrides_meal_coverage_or_budget():
    options = common_options("tofu") + (option("beef", price="100"),)
    result = optimize_recipe_plan(
        Household(1, 0),
        (meal("preferred", "beef"), meal("affordable", "tofu")),
        (), options, D("1"), 1,
        food_preferences=(FoodPreference("beef", 100),),
    )
    assert result.status == "FULL_PLAN"
    assert result.occurrences == {"affordable": 1}


def test_rm100_affordability_beats_an_expensive_food_preference():
    options = common_options("tofu") + (option("beef", price="40"),)
    result = optimize_recipe_plan(
        Household(1, 0),
        (meal("preferred-beef", "beef"), meal("affordable-tofu", "tofu")),
        (), options, D("100"), 1,
        food_preferences=(FoodPreference("beef", 100),),
    )

    assert result.status == "FULL_PLAN"
    assert result.occurrences == {"affordable-tofu": 1}


def test_equal_cost_plans_prefer_less_purchase_surplus():
    pantry = tuple(PantryStock(food, D("1")) for food in ("rice", "carrot", "oil"))
    result = optimize_recipe_plan(
        Household(1, 0),
        (meal("more-surplus", "food-a", protein_kg="0.10", cap=1),
         meal("less-surplus", "food-b", protein_kg="0.15", cap=1)),
        pantry,
        (option("food-a", unit="0.2", price="10"),
         option("food-b", unit="0.2", price="10")),
        D("10"), 1,
    )
    assert result.occurrences == {"less-surplus": 1}
    assert result.quality.purchase_surplus_kg == D("0.05")


def test_shared_ingredients_win_before_variety_when_cost_is_equal():
    recipes = (
        meal("shared-one", "chicken", "carrot", "rice", cap=1),
        meal("shared-two", "chicken", "carrot", "rice", cap=1),
        meal("different-one", "tofu", "cabbage", "noodles", cap=1),
        meal("different-two", "egg", "spinach", "bread", cap=1),
    )
    foods = {ingredient.food_id for recipe in recipes for ingredient in recipe.ingredients}
    result = optimize_recipe_plan(
        Household(1, 0), recipes, (), tuple(option(food) for food in foods), D("10"), 2,
    )
    assert result.occurrences == {"shared-one": 1, "shared-two": 1}
    assert result.quality.purchased_food_count == 4
    assert result.quality.recipe_variety == 2


def test_variety_breaks_a_tie_after_higher_priority_objectives():
    result = optimize_recipe_plan(
        Household(1, 0),
        (meal("same-one", cap=2), meal("same-two", cap=2)),
        (), common_options("chicken"), D("10"), 2,
    )
    assert result.occurrences == {"same-one": 1, "same-two": 1}
    assert result.quality.recipe_variety == 2


@pytest.mark.parametrize("score", [0, 1.5, 101, -101])
def test_invalid_preference_scores_are_rejected(score):
    with pytest.raises(ValueError):
        FoodPreference("chicken", score)
