"""Epic 6 semantic recipe recall (BGE-M3 embeddings).

Scores each recipe by its strongest embedding "bridge" between the
household's pantry foods and the recipe's ingredients - surfacing recipes
whose ingredients are *similar* to what the user has even when the exact
canonical IDs do not match (e.g. pantry has spinach, recipe calls for kailan).

All vectors come from the food_embedding table (seeded offline), so scoring
is pure in-memory cosine at request time - no inference-service call and no
dependency on Inference-UAT being up.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.receipt_matching import best_pair_score

from ..db import FoodEmbedding

# Recipes below this bridge score (and with zero exact ingredient matches)
# stay hidden - similarity too weak to be useful.
SEMANTIC_INCLUDE_THRESHOLD = 0.55


async def semantic_scores(
    db: AsyncSession,
    pantry_food_ids: set[str],
    recipe_food_ids_by_recipe: dict[str, set[str]],
) -> dict[str, float]:
    """recipe_id -> strongest pantry<->ingredient cosine score (0.0..1.0).

    Recipes with no embeddable foods on either side score 0.0.
    """
    involved = set(pantry_food_ids)
    for food_ids in recipe_food_ids_by_recipe.values():
        involved.update(food_ids)
    if not involved:
        return {}
    rows = (
        await db.scalars(
            select(FoodEmbedding).where(FoodEmbedding.canonical_food_id.in_(involved))
        )
    ).all()
    embeddings = {row.canonical_food_id: list(row.embedding) for row in rows}
    pantry_vectors = [embeddings[f] for f in pantry_food_ids if f in embeddings]
    scores: dict[str, float] = {}
    for recipe_id, food_ids in recipe_food_ids_by_recipe.items():
        ingredient_vectors = [embeddings[f] for f in food_ids if f in embeddings]
        scores[recipe_id] = round(best_pair_score(pantry_vectors, ingredient_vectors), 4)
    return scores
