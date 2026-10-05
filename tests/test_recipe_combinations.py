from decimal import Decimal

from packages.optimizer.wisebasket_optimizer.v2.domain import (
    CookingStep,
    IngredientRole,
    MealType,
    QuantityBasis,
    RecipeIngredient,
    ReviewedRecipe,
    ReviewStatus,
    assess_recipe,
)
from services.api.app.recipe_combinations import build_complete_meal_candidates


def recipe(recipe_id, meal_type, ingredients):
    return ReviewedRecipe(
        recipe_id=recipe_id,
        name=recipe_id.replace("-", " ").title(),
        meal_type=meal_type,
        base_servings=Decimal("2"),
        version=3,
        review_status=ReviewStatus.APPROVED,
        optimizer_eligible=meal_type is MealType.COMPLETE_MEAL,
        quantity_basis=QuantityBasis.RAW_EDIBLE_KG,
        ingredients=tuple(ingredients),
        steps=(
            CookingStep(
                1,
                "Cook and serve.",
                frozenset(item.food_id for item in ingredients if item.required),
            ),
        ),
        max_weekly_occurrences=3,
    )


def ingredient(food_id, role, quantity="0.1"):
    return RecipeIngredient(food_id, Decimal(quantity), role, True)


def test_main_dish_and_side_form_one_complete_meal_candidate():
    main = recipe(
        "fish-rice",
        MealType.MAIN_DISH,
        (
            ingredient("fish", IngredientRole.MAIN_PROTEIN, "0.2"),
            ingredient("rice", IngredientRole.STAPLE, "0.16"),
        ),
    )
    side = recipe(
        "broccoli",
        MealType.SIDE,
        (ingredient("broccoli", IngredientRole.MAIN_VEGETABLE, "0.2"),),
    )

    candidates = build_complete_meal_candidates(
        (main, side),
        (("fish-rice", "broccoli"),),
    )

    assert len(candidates) == 1
    combined = candidates[0]
    assert combined.recipe_id == "meal-set--fish-rice--broccoli"
    assert combined.name == "Fish Rice + Broccoli"
    assert {item.food_id for item in combined.ingredients} == {
        "fish", "rice", "broccoli",
    }
    assert [step.step_number for step in combined.steps] == [1, 2]
    assert assess_recipe(combined).optimizer_eligible


def test_combination_merges_shared_food_quantities():
    main = recipe(
        "fish-rice",
        MealType.MAIN_DISH,
        (
            ingredient("fish", IngredientRole.MAIN_PROTEIN, "0.2"),
            ingredient("rice", IngredientRole.STAPLE, "0.16"),
            ingredient("soy", IngredientRole.COOKING_ESSENTIAL, "0.01"),
        ),
    )
    side = recipe(
        "greens",
        MealType.SIDE,
        (
            ingredient("greens", IngredientRole.MAIN_VEGETABLE, "0.2"),
            ingredient("soy", IngredientRole.COOKING_ESSENTIAL, "0.02"),
        ),
    )

    combined = build_complete_meal_candidates(
        (main, side),
        (("fish-rice", "greens"),),
    )[0]
    soy = next(item for item in combined.ingredients if item.food_id == "soy")

    assert soy.quantity_kg == Decimal("0.03")


def test_complete_meals_remain_and_two_sides_do_not_form_a_meal():
    complete = recipe(
        "complete",
        MealType.COMPLETE_MEAL,
        (
            ingredient("egg", IngredientRole.MAIN_PROTEIN),
            ingredient("rice", IngredientRole.STAPLE),
            ingredient("tomato", IngredientRole.MAIN_VEGETABLE),
        ),
    )
    first_side = recipe(
        "first-side",
        MealType.SIDE,
        (ingredient("broccoli", IngredientRole.MAIN_VEGETABLE),),
    )
    second_side = recipe(
        "second-side",
        MealType.SIDE,
        (ingredient("cabbage", IngredientRole.MAIN_VEGETABLE),),
    )

    assert build_complete_meal_candidates((complete, first_side, second_side)) == (
        complete,
    )
