# Epic 5 household recipe portion calculation contract.

import pytest

from services.api.app.services.recipe_portions import scale_recipe_for_adults, scale_recipe_for_household


def test_recipe_scales_ingredient_quantity_for_adults_only():
    # Given a recipe serves two adult-equivalent portions and needs 300 g chicken.
    base_servings = 2
    base_chicken_quantity_g = 300
    adult_count = 4

    # When the recipe is scaled for four adults.
    result = scale_recipe_for_adults(
        base_servings=base_servings,
        base_ingredient_quantity_g=base_chicken_quantity_g,
        adult_count=adult_count,
    )

    # Then the household needs four portions and 600 g chicken.
    assert result.required_servings == 4
    assert result.required_quantity_g == 600


def test_recipe_scales_ingredient_quantity_for_adults_and_children():
    # Given a recipe serves two adult-equivalent portions and needs 300 g chicken.
    base_servings = 2
    base_chicken_quantity_g = 300
    adult_count = 2
    child_count = 2

    # When the recipe is scaled with each child counting as half an adult portion.
    result = scale_recipe_for_household(
        base_servings=base_servings,
        base_ingredient_quantity_g=base_chicken_quantity_g,
        adult_count=adult_count,
        child_count=child_count,
    )

    # Then the household needs three adult-equivalent portions and 450 g chicken.
    assert result.required_servings == 3
    assert result.required_quantity_g == 450


def test_recipe_portion_calculation_preserves_fractional_grams():
    # Given a household-scaled ingredient requirement that is not a whole gram.
    base_servings = 2
    base_chicken_quantity_g = 225

    # When the recipe is scaled for two adults and two children.
    result = scale_recipe_for_household(
        base_servings=base_servings,
        base_ingredient_quantity_g=base_chicken_quantity_g,
        adult_count=2,
        child_count=2,
    )

    # Then comparison precision retains 337.5 g instead of rounding it down.
    assert result.required_quantity_g == 337.5


def test_recipe_portion_calculation_rejects_zero_base_servings():
    # Given invalid recipe data with zero base servings.
    base_servings = 0

    # When the recipe quantity is scaled.
    # Then the calculation is rejected instead of dividing by zero.
    with pytest.raises(ValueError, match="Recipe base servings must be positive"):
        scale_recipe_for_adults(
            base_servings=base_servings,
            base_ingredient_quantity_g=300,
            adult_count=2,
        )
