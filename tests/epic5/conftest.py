# Shared Epic 5 test fixtures.
#
# The three original curated recipes were production seed data until migration
# o7p8q9r0s1t2 removed them from the catalogue (the collected 35-recipe dataset
# superseded them). Endpoint tests that exercise suggestions / detail /
# quantities still need known recipes, so the same three recipes now live here
# as test-owned fixture data. Tests that need them declare:
#
#     pytestmark = pytest.mark.usefixtures("curated_recipes")
from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import delete

from services.api.app.db import (
    AsyncSessionLocal,
    RecipeCatalog,
    RecipeCatalogIngredient,
    RecipeCookingStep,
    engine,
)

CURATED_RECIPE_IDS = (
    "chicken-kangkung-stir-fry",
    "egg-fried-rice",
    "tofu-kangkung-stir-fry",
)

_RECIPES = (
    {"recipe_id": "chicken-kangkung-stir-fry", "name": "Chicken & Kangkung Stir-fry", "description": "A quick stir-fry that makes practical use of chicken, kangkung and rice.", "active": True, "base_servings": 2},
    {"recipe_id": "egg-fried-rice", "name": "Egg Fried Rice", "description": "A simple fried-rice meal using eggs and rice.", "active": True, "base_servings": 2},
    {"recipe_id": "tofu-kangkung-stir-fry", "name": "Tofu & Kangkung Stir-fry", "description": "A simple vegetable-forward tofu stir-fry.", "active": True, "base_servings": 2},
)

# canonical_food_id values are the current 201-namespace IDs (SF110 rice,
# SF018 chicken egg, SF074 water spinach, SF006 whole chicken, SF107 tofu,
# SF056 onion, SF069 garlic, SF077 carrot) - the old 72-space IDs collide with
# completely different foods and must never be used here.
_INGREDIENTS = (
    {"recipe_id": "chicken-kangkung-stir-fry", "canonical_food_id": "SF006", "required": True, "base_quantity_g": 300, "display_order": 1},
    {"recipe_id": "chicken-kangkung-stir-fry", "canonical_food_id": "SF074", "required": True, "base_quantity_g": 200, "display_order": 2},
    {"recipe_id": "chicken-kangkung-stir-fry", "canonical_food_id": "SF110", "required": True, "base_quantity_g": 160, "display_order": 3},
    {"recipe_id": "chicken-kangkung-stir-fry", "canonical_food_id": "SF056", "required": False, "base_quantity_g": None, "display_order": 4},
    {"recipe_id": "chicken-kangkung-stir-fry", "canonical_food_id": "SF069", "required": False, "base_quantity_g": None, "display_order": 5},
    {"recipe_id": "egg-fried-rice", "canonical_food_id": "SF018", "required": True, "base_quantity_g": 100, "display_order": 1},
    {"recipe_id": "egg-fried-rice", "canonical_food_id": "SF110", "required": True, "base_quantity_g": 160, "display_order": 2},
    {"recipe_id": "egg-fried-rice", "canonical_food_id": "SF056", "required": False, "base_quantity_g": None, "display_order": 3},
    {"recipe_id": "egg-fried-rice", "canonical_food_id": "SF077", "required": False, "base_quantity_g": None, "display_order": 4},
    {"recipe_id": "tofu-kangkung-stir-fry", "canonical_food_id": "SF107", "required": True, "base_quantity_g": 300, "display_order": 1},
    {"recipe_id": "tofu-kangkung-stir-fry", "canonical_food_id": "SF074", "required": True, "base_quantity_g": 200, "display_order": 2},
    {"recipe_id": "tofu-kangkung-stir-fry", "canonical_food_id": "SF056", "required": False, "base_quantity_g": None, "display_order": 3},
    {"recipe_id": "tofu-kangkung-stir-fry", "canonical_food_id": "SF069", "required": False, "base_quantity_g": None, "display_order": 4},
)

_STEPS = (
    {"recipe_id": "chicken-kangkung-stir-fry", "step_number": 1, "instruction": "Wash the chicken and kangkung."},
    {"recipe_id": "chicken-kangkung-stir-fry", "step_number": 2, "instruction": "Stir-fry chicken until it is cooked through."},
    {"recipe_id": "chicken-kangkung-stir-fry", "step_number": 3, "instruction": "Add kangkung and any preferred seasoning, then stir-fry for 2 to 3 minutes."},
    {"recipe_id": "chicken-kangkung-stir-fry", "step_number": 4, "instruction": "Serve with rice."},
    {"recipe_id": "egg-fried-rice", "step_number": 1, "instruction": "Scramble the eggs in a hot pan."},
    {"recipe_id": "egg-fried-rice", "step_number": 2, "instruction": "Add rice and stir-fry until heated through."},
    {"recipe_id": "egg-fried-rice", "step_number": 3, "instruction": "Add any preferred vegetables or seasoning, then serve."},
    {"recipe_id": "tofu-kangkung-stir-fry", "step_number": 1, "instruction": "Pan-fry tofu until lightly golden."},
    {"recipe_id": "tofu-kangkung-stir-fry", "step_number": 2, "instruction": "Add kangkung, then stir-fry until tender."},
    {"recipe_id": "tofu-kangkung-stir-fry", "step_number": 3, "instruction": "Add any preferred vegetables or seasoning and serve."},
)


def run_database(coroutine):
    async def runner():
        try:
            return await coroutine
        finally:
            await engine.dispose()

    return asyncio.run(runner())


async def install_curated_recipes() -> None:
    """Idempotently (re)install the three fixture recipes with full data."""
    async with AsyncSessionLocal() as db:
        # Delete parents first; FK ON DELETE CASCADE clears any stale children,
        # so the fixture works on databases that still hold the old seeds too.
        await db.execute(delete(RecipeCatalog).where(RecipeCatalog.recipe_id.in_(CURATED_RECIPE_IDS)))
        db.add_all(RecipeCatalog(**row) for row in _RECIPES)
        db.add_all(RecipeCatalogIngredient(**row) for row in _INGREDIENTS)
        db.add_all(RecipeCookingStep(**row) for row in _STEPS)
        await db.commit()


async def remove_curated_recipes() -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(delete(RecipeCatalog).where(RecipeCatalog.recipe_id.in_(CURATED_RECIPE_IDS)))
        await db.commit()


@pytest.fixture(scope="module")
def curated_recipes():
    """Module-scoped: install the three fixture recipes, remove them after."""
    run_database(install_curated_recipes())
    yield
    run_database(remove_curated_recipes())
