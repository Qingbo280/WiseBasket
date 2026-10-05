# Epic 5 household quantity sufficiency contract.

from services.api.app.services.recipe_quantity_matching import (
    RecipeIngredientQuantity,
    match_ingredient_quantity,
    match_recipe_quantities,
)


def test_recipe_quantity_match_marks_known_sufficient_ingredient():
    # Given the household needs 450 g chicken and has 2000 g available.
    required_quantity_g = 450
    available_quantity_g = 2000

    # When recipe quantity sufficiency is evaluated.
    result = match_ingredient_quantity(
        required_quantity_g=required_quantity_g,
        available_quantity_g=available_quantity_g,
        quantity_status="KNOWN",
    )

    # Then chicken is sufficient with 1550 g remaining.
    assert result.quantity_status == "SUFFICIENT"
    assert result.is_sufficient is True
    assert result.shortfall_quantity_g == 0
    assert result.remaining_quantity_g == 1550


def test_recipe_quantity_match_returns_exact_shortfall_for_insufficient_ingredient():
    # Given the household needs 450 g chicken and has only 300 g available.
    required_quantity_g = 450
    available_quantity_g = 300

    # When recipe quantity sufficiency is evaluated.
    result = match_ingredient_quantity(
        required_quantity_g=required_quantity_g,
        available_quantity_g=available_quantity_g,
        quantity_status="KNOWN",
    )

    # Then chicken is insufficient with an exact 150 g shortfall.
    assert result.quantity_status == "INSUFFICIENT"
    assert result.is_sufficient is False
    assert result.shortfall_quantity_g == 150
    assert result.remaining_quantity_g == 0


def test_recipe_quantity_match_does_not_mark_unknown_quantity_as_sufficient():
    # Given the household needs 450 g chicken but the pantry amount is unknown.
    required_quantity_g = 450

    # When recipe quantity sufficiency is evaluated.
    result = match_ingredient_quantity(
        required_quantity_g=required_quantity_g,
        available_quantity_g=None,
        quantity_status="UNKNOWN",
    )

    # Then the ingredient is unresolved and cannot be marked sufficient.
    assert result.quantity_status == "UNKNOWN"
    assert result.is_sufficient is False
    assert result.shortfall_quantity_g is None
    assert result.remaining_quantity_g is None


def test_recipe_quantity_match_marks_recipe_sufficient_when_all_required_ingredients_are_sufficient():
    # Given every required ingredient has enough quantity and an optional item is missing.
    chicken_match = match_ingredient_quantity(450, 2000, "KNOWN")
    kangkung_match = match_ingredient_quantity(150, 300, "KNOWN")
    rice_match = match_ingredient_quantity(240, 500, "KNOWN")
    carrot_match = match_ingredient_quantity(80, 0, "KNOWN")
    ingredients = (
        RecipeIngredientQuantity(canonical_food_id="SF006", required=True, quantity_match=chicken_match),
        RecipeIngredientQuantity(canonical_food_id="SF074", required=True, quantity_match=kangkung_match),
        RecipeIngredientQuantity(canonical_food_id="SF110", required=True, quantity_match=rice_match),
        RecipeIngredientQuantity(canonical_food_id="SF077", required=False, quantity_match=carrot_match),
    )

    # When recipe quantity sufficiency is evaluated.
    result = match_recipe_quantities(ingredients=ingredients)

    # Then the optional carrot shortfall does not block cooking the recipe.
    assert result.is_quantity_sufficient is True
    assert result.required_sufficient_count == 3
    assert result.required_ingredient_count == 3


def test_recipe_quantity_match_marks_recipe_insufficient_when_a_required_ingredient_has_shortfall():
    # Given chicken is short while the other required ingredients are sufficient.
    chicken_match = match_ingredient_quantity(450, 300, "KNOWN")
    kangkung_match = match_ingredient_quantity(150, 300, "KNOWN")
    rice_match = match_ingredient_quantity(240, 500, "KNOWN")
    ingredients = (
        RecipeIngredientQuantity(canonical_food_id="SF006", required=True, quantity_match=chicken_match),
        RecipeIngredientQuantity(canonical_food_id="SF074", required=True, quantity_match=kangkung_match),
        RecipeIngredientQuantity(canonical_food_id="SF110", required=True, quantity_match=rice_match),
    )

    # When recipe quantity sufficiency is evaluated.
    result = match_recipe_quantities(ingredients=ingredients)

    # Then the recipe is not quantity sufficient and only two required items pass.
    assert result.is_quantity_sufficient is False
    assert result.required_sufficient_count == 2
    assert result.required_ingredient_count == 3
