# Deterministic recipe matching for the Epic 5 curated recipe catalogue.
from __future__ import annotations

from dataclasses import dataclass


def main_ingredient_priority(
    ingredients: tuple[tuple[str, bool, float | None], ...], pantry_food_ids: set[str]
) -> tuple[float, int]:
    # The catalogue has no ingredient-role field. Use the larger required
    # portions as a proxy, keeping small amounts of garlic/sauce from driving
    # recommendations. Pantry quantity is deliberately irrelevant here.
    required = tuple(ingredient for ingredient in ingredients if ingredient[1])
    largest = max((quantity or 0 for _, _, quantity in required), default=0)
    main_ids = {
        food_id for food_id, _, quantity in required
        if largest == 0 or quantity is None or quantity >= largest * 0.25
    }
    count = len(main_ids & pantry_food_ids)
    return count / max(len(main_ids), 1), count


@dataclass(frozen=True)
class RecipeIngredient:
    canonical_food_id: str
    required: bool = True


@dataclass(frozen=True)
class Recipe:
    recipe_id: str
    title: str
    ingredients: tuple[RecipeIngredient, ...]


@dataclass(frozen=True)
class RecipeMatch:
    recipe_id: str
    available_food_ids: tuple[str, ...]
    missing_food_ids: tuple[str, ...]
    required_match_count: int
    required_ingredient_count: int


def match_recipe(recipe: Recipe, pantry_food_ids: set[str]) -> RecipeMatch:
    # Preserve the curated recipe ingredient order for a stable frontend response.
    available_food_ids = tuple(
        ingredient.canonical_food_id
        for ingredient in recipe.ingredients
        if ingredient.canonical_food_id in pantry_food_ids
    )
    missing_food_ids = tuple(
        ingredient.canonical_food_id
        for ingredient in recipe.ingredients
        if ingredient.required and ingredient.canonical_food_id not in pantry_food_ids
    )
    required_ingredient_count = sum(ingredient.required for ingredient in recipe.ingredients)
    required_match_count = required_ingredient_count - len(missing_food_ids)

    return RecipeMatch(
        recipe_id=recipe.recipe_id,
        available_food_ids=available_food_ids,
        missing_food_ids=missing_food_ids,
        required_match_count=required_match_count,
        required_ingredient_count=required_ingredient_count,
    )
