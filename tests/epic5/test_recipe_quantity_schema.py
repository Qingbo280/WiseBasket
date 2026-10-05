# Epic 5 recipe quantity persistence contract.

from services.api.app.db import RecipeCatalog, RecipeCatalogIngredient


def test_recipe_models_store_base_servings_and_base_ingredient_grams():
    # Given the recipe catalogue models.
    recipe_columns = RecipeCatalog.__table__.c
    ingredient_columns = RecipeCatalogIngredient.__table__.c

    # When quantitative recipe matching is introduced.
    # Then recipes can store base servings and ingredients can store base grams.
    assert "base_servings" in recipe_columns
    assert "base_quantity_g" in ingredient_columns
    assert recipe_columns.base_servings.nullable is True
    assert ingredient_columns.base_quantity_g.nullable is True
