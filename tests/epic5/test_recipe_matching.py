# Epic 5 recipe matching contract.
# This pure unit test defines recipe matching before API or mobile work begins.

from services.api.app.services.recipe_matching import Recipe, RecipeIngredient, match_recipe


def test_recipe_match_separates_available_and_missing_required_ingredients():
    # A partly stocked pantry must yield an explainable partial recipe match.
    recipe = Recipe(
        recipe_id="chicken-kangkung-stir-fry",
        title="Chicken & Kangkung Stir-fry",
        ingredients=(
            RecipeIngredient(canonical_food_id="SF003", required=True),
            RecipeIngredient(canonical_food_id="SF010", required=True),
            RecipeIngredient(canonical_food_id="SF001", required=True),
        ),
    )

    result = match_recipe(recipe, pantry_food_ids={"SF003", "SF010"})

    assert result.recipe_id == "chicken-kangkung-stir-fry"
    assert result.available_food_ids == ("SF003", "SF010")
    assert result.missing_food_ids == ("SF001",)
    assert result.required_match_count == 2
    assert result.required_ingredient_count == 3
