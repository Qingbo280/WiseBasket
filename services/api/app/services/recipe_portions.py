# Deterministic household portion calculations for Epic 5 recipes.
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RecipePortionScale:
    required_servings: float
    required_quantity_g: float


def scale_recipe_for_adults(
    base_servings: int,
    base_ingredient_quantity_g: float,
    adult_count: int,
) -> RecipePortionScale:
    # This first TDD slice deliberately supports adults only. Child serving
    # policy will be added in the next approved slice.
    if base_servings <= 0:
        raise ValueError("Recipe base servings must be positive.")
    if base_ingredient_quantity_g <= 0:
        raise ValueError("Recipe ingredient quantity must be positive.")
    if adult_count <= 0:
        raise ValueError("Adult count must be positive.")

    required_quantity_g = base_ingredient_quantity_g * adult_count / base_servings
    return RecipePortionScale(
        required_servings=adult_count,
        required_quantity_g=required_quantity_g,
    )


def scale_recipe_for_household(
    base_servings: int,
    base_ingredient_quantity_g: float,
    adult_count: int,
    child_count: int,
    child_serving_factor: float = 0.5,
) -> RecipePortionScale:
    # Initial product policy: one child counts as half an adult-equivalent
    # serving. A future profile feature can make this age-aware.
    if base_servings <= 0:
        raise ValueError("Recipe base servings must be positive.")
    if base_ingredient_quantity_g <= 0:
        raise ValueError("Recipe ingredient quantity must be positive.")
    if adult_count < 0 or child_count < 0:
        raise ValueError("Household member counts cannot be negative.")
    if adult_count + child_count <= 0:
        raise ValueError("Household must have at least one member.")
    if child_serving_factor <= 0:
        raise ValueError("Child serving factor must be positive.")

    required_servings = adult_count + child_count * child_serving_factor
    required_quantity_g = base_ingredient_quantity_g * required_servings / base_servings
    return RecipePortionScale(
        required_servings=required_servings,
        required_quantity_g=required_quantity_g,
    )
