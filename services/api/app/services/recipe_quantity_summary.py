# Deterministic quantity output for household-scaled Epic 5 recipes.
from __future__ import annotations

from dataclasses import dataclass

from .recipe_portions import scale_recipe_for_household
from .recipe_quantities import PantryQuantity, aggregate_available_quantity
from .recipe_quantity_matching import (
    RecipeIngredientQuantity,
    match_ingredient_quantity,
    match_recipe_quantities,
)


@dataclass(frozen=True)
class RecipeQuantityIngredientInput:
    canonical_food_id: str
    required: bool
    base_quantity_g: float | None
    pantry_quantities: tuple[PantryQuantity, ...]


@dataclass(frozen=True)
class RecipeQuantityIngredientSummary:
    canonical_food_id: str
    required: bool
    base_quantity_g: float | None
    required_quantity_g: float | None
    available_quantity_g: float | None
    quantity_status: str
    is_quantity_sufficient: bool | None
    shortfall_quantity_g: float | None
    remaining_quantity_g: float | None


@dataclass(frozen=True)
class RecipeQuantitySummary:
    base_servings: int | None
    household_servings: float
    quantity_status: str
    is_quantity_sufficient: bool | None
    required_quantity_sufficient_count: int
    required_ingredient_count: int
    ingredients: tuple[RecipeQuantityIngredientSummary, ...]


def recipe_quantity_rank(quantity_status: str) -> int:
    # A known shortfall is more actionable than an unmeasured pantry amount.
    rank_by_status = {
        "SUFFICIENT": 0,
        "INSUFFICIENT": 1,
        "UNKNOWN": 2,
        "NOT_TRACKED": 3,
    }
    return rank_by_status[quantity_status]


def summarize_recipe_quantities(
    base_servings: int | None,
    adult_count: int,
    child_count: int,
    ingredients: tuple[RecipeQuantityIngredientInput, ...],
) -> RecipeQuantitySummary:
    # The household serving count is available even while a recipe is waiting
    # for its ingredient grams to be reviewed.
    household_servings = adult_count + child_count * 0.5
    summaries = []
    matched_ingredients = []
    has_untracked_required_quantity = False

    for ingredient in ingredients:
        available = aggregate_available_quantity(ingredient.pantry_quantities)
        if base_servings is None or ingredient.base_quantity_g is None:
            summaries.append(
                RecipeQuantityIngredientSummary(
                    canonical_food_id=ingredient.canonical_food_id,
                    required=ingredient.required,
                    base_quantity_g=ingredient.base_quantity_g,
                    required_quantity_g=None,
                    available_quantity_g=available.quantity_g,
                    quantity_status="NOT_TRACKED",
                    is_quantity_sufficient=None,
                    shortfall_quantity_g=None,
                    remaining_quantity_g=None,
                )
            )
            has_untracked_required_quantity = has_untracked_required_quantity or ingredient.required
            continue

        portion = scale_recipe_for_household(
            base_servings=base_servings,
            base_ingredient_quantity_g=ingredient.base_quantity_g,
            adult_count=adult_count,
            child_count=child_count,
        )
        match = match_ingredient_quantity(
            required_quantity_g=portion.required_quantity_g,
            available_quantity_g=available.quantity_g,
            quantity_status=available.quantity_status,
        )
        summaries.append(
            RecipeQuantityIngredientSummary(
                canonical_food_id=ingredient.canonical_food_id,
                required=ingredient.required,
                base_quantity_g=ingredient.base_quantity_g,
                required_quantity_g=portion.required_quantity_g,
                available_quantity_g=available.quantity_g,
                quantity_status=match.quantity_status,
                is_quantity_sufficient=match.is_sufficient,
                shortfall_quantity_g=match.shortfall_quantity_g,
                remaining_quantity_g=match.remaining_quantity_g,
            )
        )
        matched_ingredients.append(
            RecipeIngredientQuantity(
                canonical_food_id=ingredient.canonical_food_id,
                required=ingredient.required,
                quantity_match=match,
            )
        )

    matched_result = match_recipe_quantities(tuple(matched_ingredients))
    required_ingredient_count = sum(ingredient.required for ingredient in ingredients)
    required_summaries = tuple(summary for summary in summaries if summary.required)
    if has_untracked_required_quantity:
        quantity_status = "NOT_TRACKED"
    elif all(summary.quantity_status == "SUFFICIENT" for summary in required_summaries):
        quantity_status = "SUFFICIENT"
    elif any(summary.quantity_status == "UNKNOWN" for summary in required_summaries):
        quantity_status = "UNKNOWN"
    else:
        quantity_status = "INSUFFICIENT"

    return RecipeQuantitySummary(
        base_servings=base_servings,
        household_servings=household_servings,
        quantity_status=quantity_status,
        is_quantity_sufficient=(
            None if has_untracked_required_quantity else matched_result.is_quantity_sufficient
        ),
        required_quantity_sufficient_count=matched_result.required_sufficient_count,
        required_ingredient_count=required_ingredient_count,
        ingredients=tuple(summaries),
    )
