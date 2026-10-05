# Small, explicit nutrition contracts for capped planner scoring.
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable

from .calculations import Household
from .domain import ReviewedRecipe


D = Decimal
ADULT_DAILY = (D("2000"), D("60"), D("1000"))
CHILD_DAILY = (D("1600"), D("30"), D("1000"))
NUTRITION_TARGET_PRECISION = D("0.001")


def require_food_identifier(value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Food id must be a nonempty string")


def require_nonnegative_decimal(value: Decimal, label: str) -> None:
    if not isinstance(value, Decimal) or not value.is_finite() or value < 0:
        raise ValueError(f"{label} must be a nonnegative finite Decimal")


def require_positive_decimal(value: Decimal, label: str) -> None:
    require_nonnegative_decimal(value, label)
    if value == 0:
        raise ValueError(f"{label} must be positive")


@dataclass(frozen=True)
class FoodNutrition:
    # Nutrients per kg of raw edible food.

    food_id: str
    energy_kcal: Decimal
    protein_g: Decimal
    calcium_mg: Decimal

    def __post_init__(self) -> None:
        require_food_identifier(self.food_id)
        for value, label in (
            (self.energy_kcal, "Energy"),
            (self.protein_g, "Protein"),
            (self.calcium_mg, "Calcium"),
        ):
            require_nonnegative_decimal(value, label)
        if self.energy_kcal == self.protein_g == self.calcium_mg == 0:
            raise ValueError("Food nutrition must contain at least one measured nutrient")


@dataclass(frozen=True)
class NutritionTargets:
    energy_kcal: Decimal
    protein_g: Decimal
    calcium_mg: Decimal

    def __post_init__(self) -> None:
        for value, label in (
            (self.energy_kcal, "Energy target"),
            (self.protein_g, "Protein target"),
            (self.calcium_mg, "Calcium target"),
        ):
            require_positive_decimal(value, label)


@dataclass(frozen=True)
class NutritionAssessment:
    targets: NutritionTargets
    energy_kcal: Decimal
    protein_g: Decimal
    calcium_mg: Decimal
    energy_coverage: Decimal
    protein_coverage: Decimal
    calcium_coverage: Decimal
    missing_food_ids: tuple[str, ...]


def household_nutrition_targets(
    household: Household,
    meal_occasions: int,
    daily_meals: int = 3,
) -> NutritionTargets:
    # Scale approximate daily references by planned household meal occasions.
    # Adult and child references are separate from the 0.5 child recipe-portion
    # assumption. They are planning score thresholds, not clinical requirements
    # or intake ceilings.
    if type(meal_occasions) is not int or meal_occasions <= 0:
        raise ValueError("Meal occasions must be a positive integer")
    if type(daily_meals) is not int or daily_meals <= 0:
        raise ValueError("Daily meals must be a positive integer")
    factor = D(meal_occasions) / D(daily_meals)
    values = tuple(
        ((D(household.adults) * adult + D(household.children) * child) * factor).quantize(
            NUTRITION_TARGET_PRECISION,
            rounding=ROUND_HALF_UP,
        )
        for adult, child in zip(ADULT_DAILY, CHILD_DAILY)
    )
    return NutritionTargets(*values)


def assess_plan_nutrition(
    household: Household,
    recipes: dict[str, ReviewedRecipe],
    occurrences: dict[str, int],
    targets: NutritionTargets,
    food_nutrition: Iterable[FoodNutrition],
) -> NutritionAssessment:
    profiles = tuple(food_nutrition)
    if len({profile.food_id for profile in profiles}) != len(profiles):
        raise ValueError("Food nutrition records must be unique per food")
    by_food = {profile.food_id: profile for profile in profiles}
    totals = [D("0"), D("0"), D("0")]
    missing: set[str] = set()
    for recipe_id, count in occurrences.items():
        recipe = recipes[recipe_id]
        scale = household.servings / recipe.base_servings * count
        for ingredient in recipe.ingredients:
            if not ingredient.required:
                continue
            profile = by_food.get(ingredient.food_id)
            if profile is None:
                missing.add(ingredient.food_id)
                continue
            quantity = ingredient.quantity_kg * scale
            totals[0] += quantity * profile.energy_kcal
            totals[1] += quantity * profile.protein_g
            totals[2] += quantity * profile.calcium_mg
    target_values = (targets.energy_kcal, targets.protein_g, targets.calcium_mg)
    coverage = tuple(min(D("1"), total / target) for total, target in zip(totals, target_values))
    return NutritionAssessment(targets, *totals, *coverage, tuple(sorted(missing)))
