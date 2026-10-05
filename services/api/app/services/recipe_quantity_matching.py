# Deterministic ingredient quantity sufficiency for Epic 5 recipes.
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IngredientQuantityMatch:
    quantity_status: str
    is_sufficient: bool
    shortfall_quantity_g: float | None
    remaining_quantity_g: float | None


@dataclass(frozen=True)
class RecipeIngredientQuantity:
    canonical_food_id: str
    required: bool
    quantity_match: IngredientQuantityMatch


@dataclass(frozen=True)
class RecipeQuantityMatch:
    is_quantity_sufficient: bool
    required_sufficient_count: int
    required_ingredient_count: int


def match_ingredient_quantity(
    required_quantity_g: float,
    available_quantity_g: float | None,
    quantity_status: str,
) -> IngredientQuantityMatch:
    if required_quantity_g <= 0:
        raise ValueError("Required ingredient quantity must be positive.")
    if quantity_status != "KNOWN" or available_quantity_g is None:
        return IngredientQuantityMatch(
            quantity_status="UNKNOWN",
            is_sufficient=False,
            shortfall_quantity_g=None,
            remaining_quantity_g=None,
        )
    if available_quantity_g >= required_quantity_g:
        return IngredientQuantityMatch(
            quantity_status="SUFFICIENT",
            is_sufficient=True,
            shortfall_quantity_g=0,
            remaining_quantity_g=available_quantity_g - required_quantity_g,
        )

    return IngredientQuantityMatch(
        quantity_status="INSUFFICIENT",
        is_sufficient=False,
        shortfall_quantity_g=required_quantity_g - available_quantity_g,
        remaining_quantity_g=0,
    )


def match_recipe_quantities(ingredients: tuple[RecipeIngredientQuantity, ...]) -> RecipeQuantityMatch:
    required_ingredients = tuple(ingredient for ingredient in ingredients if ingredient.required)
    required_sufficient_count = sum(
        ingredient.quantity_match.is_sufficient for ingredient in required_ingredients
    )
    return RecipeQuantityMatch(
        is_quantity_sufficient=required_sufficient_count == len(required_ingredients),
        required_sufficient_count=required_sufficient_count,
        required_ingredient_count=len(required_ingredients),
    )
