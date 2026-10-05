# Shared W9 (I2 Phase 1) recipe-catalog test fixtures.
#
# B1/B3 changed the plan soft objective and the plan-exit preview to read the
# Epic 5 recipe_catalog instead of the retired meal_template seeds. These
# helpers install a small synthetic catalogue (w9c-* ids, real 201-namespace
# food ids) into the test database and remove it afterwards. The ids never
# collide with the production seeds (chicken-kangkung-stir-fry et al.) or the
# PR #184 epic5 fixtures, so installing/removing them cannot disturb other
# test modules.
#
# Recipe set (all base_servings=2):
#   w9c-chicken-rice  required SF006 300 g + SF074 200 g + SF110 160 g, optional SF077
#   w9c-egg-rice      required SF018 100 g + SF110 160 g
#   w9c-solo-green    required SF074 200 g          (single member: >=2 gate)
#   w9c-boost-b       required SF110 160 g + SF056 50 g
#   w9c-boost-c       required SF110 160 g + SF069 20 g
#   w9c-untracked     required SF056 (grams NULL) + SF110 160 g
#   w9c-inactive      required SF006 300 g + SF110 160 g, active=False
from __future__ import annotations

import asyncio

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from services.api.app.db import (
    AsyncSessionLocal,
    RecipeCatalog,
    RecipeCatalogIngredient,
    RecipeCookingStep,
    engine,
)

W9_RECIPE_IDS = tuple(
    recipe_id
    for recipe_id, _name, _active in (
        ("w9c-chicken-rice", "W9 Chicken Rice", True),
        ("w9c-egg-rice", "W9 Egg Rice", True),
        ("w9c-solo-green", "W9 Solo Green", True),
        ("w9c-boost-b", "W9 Boost B", True),
        ("w9c-boost-c", "W9 Boost C", True),
        ("w9c-untracked", "W9 Untracked", True),
        ("w9c-inactive", "W9 Inactive", False),
    )
)

_RECIPE_ROWS = [
    {"recipe_id": "w9c-chicken-rice", "name": "W9 Chicken Rice", "description": "w9 fixture", "active": True, "base_servings": 2},
    {"recipe_id": "w9c-egg-rice", "name": "W9 Egg Rice", "description": "w9 fixture", "active": True, "base_servings": 2},
    {"recipe_id": "w9c-solo-green", "name": "W9 Solo Green", "description": "w9 fixture", "active": True, "base_servings": 2},
    {"recipe_id": "w9c-boost-b", "name": "W9 Boost B", "description": "w9 fixture", "active": True, "base_servings": 2},
    {"recipe_id": "w9c-boost-c", "name": "W9 Boost C", "description": "w9 fixture", "active": True, "base_servings": 2},
    {"recipe_id": "w9c-untracked", "name": "W9 Untracked", "description": "w9 fixture", "active": True, "base_servings": 2},
    {"recipe_id": "w9c-inactive", "name": "W9 Inactive", "description": "w9 fixture", "active": False, "base_servings": 2},
]

# (recipe_id, canonical_food_id, required, display_order, base_quantity_g)
_INGREDIENT_ROWS = [
    ("w9c-chicken-rice", "SF006", True, 1, 300),
    ("w9c-chicken-rice", "SF074", True, 2, 200),
    ("w9c-chicken-rice", "SF110", True, 3, 160),
    ("w9c-chicken-rice", "SF077", False, 4, None),
    ("w9c-egg-rice", "SF018", True, 1, 100),
    ("w9c-egg-rice", "SF110", True, 2, 160),
    ("w9c-solo-green", "SF074", True, 1, 200),
    ("w9c-boost-b", "SF110", True, 1, 160),
    ("w9c-boost-b", "SF056", True, 2, 50),
    ("w9c-boost-c", "SF110", True, 1, 160),
    ("w9c-boost-c", "SF069", True, 2, 20),
    ("w9c-untracked", "SF056", True, 1, None),
    ("w9c-untracked", "SF110", True, 2, 160),
    ("w9c-inactive", "SF006", True, 1, 300),
    ("w9c-inactive", "SF018", True, 2, 100),
]

_STEPS = [
    {"recipe_id": recipe_id, "step_number": 1, "instruction": "w9 fixture step."}
    for recipe_id in W9_RECIPE_IDS
]


def run_db(coroutine):
    async def runner():
        try:
            return await coroutine
        finally:
            await engine.dispose()

    return asyncio.run(runner())


async def install_w9_recipes() -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(delete(RecipeCatalog).where(RecipeCatalog.recipe_id.in_(W9_RECIPE_IDS)))
        db.add_all(RecipeCatalog(**row) for row in _RECIPE_ROWS)
        db.add_all(
            RecipeCatalogIngredient(
                recipe_id=recipe_id,
                canonical_food_id=food_id,
                required=required,
                base_quantity_g=grams,
                display_order=order,
            )
            for recipe_id, food_id, required, order, grams in _INGREDIENT_ROWS
        )
        db.add_all(RecipeCookingStep(**row) for row in _STEPS)
        await db.commit()


async def remove_w9_recipes() -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(delete(RecipeCatalog).where(RecipeCatalog.recipe_id.in_(W9_RECIPE_IDS)))
        await db.commit()


async def snapshot_all_recipes(db: AsyncSession):
    """Capture every catalogue row as plain dicts (for the empty-catalog test)."""
    recipes = (
        await db.scalars(select(RecipeCatalog).order_by(RecipeCatalog.recipe_id))
    ).all()
    ingredients = (
        await db.scalars(select(RecipeCatalogIngredient))
    ).all()
    steps = (await db.scalars(select(RecipeCookingStep))).all()
    snapshot = {
        "recipes": [
            {
                "recipe_id": r.recipe_id,
                "name": r.name,
                "description": r.description,
                "active": r.active,
                "base_servings": r.base_servings,
            }
            for r in recipes
        ],
        "ingredients": [
            {
                "recipe_id": i.recipe_id,
                "canonical_food_id": i.canonical_food_id,
                "required": i.required,
                "base_quantity_g": float(i.base_quantity_g) if i.base_quantity_g is not None else None,
                "display_order": i.display_order,
            }
            for i in ingredients
        ],
        "steps": [
            {"recipe_id": s.recipe_id, "step_number": s.step_number, "instruction": s.instruction}
            for s in steps
        ],
    }
    return snapshot


async def delete_all_recipes(db: AsyncSession) -> None:
    # Children first (no reliance on ORM cascade for a bulk wipe).
    await db.execute(delete(RecipeCookingStep))
    await db.execute(delete(RecipeCatalogIngredient))
    await db.execute(delete(RecipeCatalog))
    await db.commit()


async def restore_recipes(db: AsyncSession, snapshot: dict) -> None:
    db.add_all(RecipeCatalog(**row) for row in snapshot["recipes"])
    db.add_all(RecipeCatalogIngredient(**row) for row in snapshot["ingredients"])
    db.add_all(RecipeCookingStep(**row) for row in snapshot["steps"])
    await db.commit()
