# Epic 5 curated recipe quantity fixture-data contract.
# The recipes are test-owned fixtures (tests/epic5/conftest.py) since migration
# o7p8q9r0s1t2 removed them from the production catalogue.
from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import select

from services.api.app.db import AsyncSessionLocal, RecipeCatalog, RecipeCatalogIngredient, engine


pytestmark = pytest.mark.usefixtures("curated_recipes")


EXPECTED_RECIPE_QUANTITIES = {
    "chicken-kangkung-stir-fry": {"SF006": 300, "SF074": 200, "SF110": 160},
    "egg-fried-rice": {"SF018": 100, "SF110": 160},
    "tofu-kangkung-stir-fry": {"SF107": 300, "SF074": 200},
}


def run_database(coroutine):
    async def runner():
        try:
            return await coroutine
        finally:
            await engine.dispose()

    return asyncio.run(runner())


async def load_curated_recipe_quantities():
    async with AsyncSessionLocal() as db:
        recipes = (
            await db.scalars(
                select(RecipeCatalog).where(RecipeCatalog.recipe_id.in_(EXPECTED_RECIPE_QUANTITIES))
            )
        ).all()
        quantities = {}
        for recipe in recipes:
            rows = (
                await db.scalars(
                    select(RecipeCatalogIngredient).where(
                        RecipeCatalogIngredient.recipe_id == recipe.recipe_id,
                        RecipeCatalogIngredient.required.is_(True),
                    )
                )
            ).all()
            quantities[recipe.recipe_id] = {
                "base_servings": recipe.base_servings,
                "ingredients": {row.canonical_food_id: float(row.base_quantity_g) for row in rows},
            }
        return quantities


def test_curated_recipes_have_approved_base_servings_and_required_gram_quantities():
    # Given the approved initial quantities for the three curated recipes.
    quantities = run_database(load_curated_recipe_quantities())

    # When seeded recipe data is loaded.
    # Then every recipe serves two and required ingredients match the approved grams.
    assert set(quantities) == set(EXPECTED_RECIPE_QUANTITIES)
    for recipe_id, expected_ingredients in EXPECTED_RECIPE_QUANTITIES.items():
        assert quantities[recipe_id]["base_servings"] == 2
        assert quantities[recipe_id]["ingredients"] == expected_ingredients
