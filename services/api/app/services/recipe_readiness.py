"""Read-only presentation guidance; never changes recipe ranking or pantry stock."""
from __future__ import annotations

from decimal import Decimal, ROUND_CEILING
import math

from ..schemas import PantryFoodResponse, RecipeReadinessIssue, RecipeReadinessResponse
from .recipe_quantity_summary import RecipeQuantitySummary


def _kg(grams: float | None) -> float | None:
    return grams / 1000 if grams is not None and math.isfinite(grams) and grams >= 0 else None


def _shortfall_label(kg: float) -> str:
    # Copy rounds UP to a gram, never displaying a positive shortfall as zero.
    # Machine-readable amounts retain their original precision.
    grams = (Decimal(str(kg)) * 1000).quantize(Decimal("1"), rounding=ROUND_CEILING)
    return f"{grams:g} g" if grams < 1000 else f"{grams / 1000:g} kg"


def build_recipe_readiness(
    summary: RecipeQuantitySummary,
    required_foods: dict[str, PantryFoodResponse],
    present_food_ids: set[str],
    noncomparable_food_ids: frozenset[str] = frozenset(),
) -> RecipeReadinessResponse:
    """Keys are original recipe slots; food values use the actual pantry SKU.

    Only required slots participate. Missing quantity records fail closed.
    An unavailable substitute conversion must not inherit the original cut's
    grams, even if the caller accidentally supplies a known quantity summary.
    """
    quantities = {item.canonical_food_id: item for item in summary.ingredients if item.required}
    issues = []
    all_present = bool(required_foods) and required_foods.keys() <= present_food_ids
    for food_id, food in required_foods.items():
        quantity = quantities.get(food_id)
        required = _kg(quantity.required_quantity_g) if quantity else None
        available = _kg(quantity.available_quantity_g) if quantity else None
        shortfall = None
        if food_id not in present_food_ids:
            status, reason = "MISSING", "NOT_IN_PANTRY"
            message = f"{food.name}: not recorded in What You Have."
        elif food_id in noncomparable_food_ids:
            status, reason = "UNKNOWN", "SUBSTITUTION_CONVERSION_UNAVAILABLE"
            required = available = None
            message = f"{food.name}: confirm the usable amount for this recipe."
        elif quantity is None or required is None or required <= 0 or quantity.quantity_status == "NOT_TRACKED":
            status, reason = "NOT_TRACKED", "RECIPE_AMOUNT_UNREVIEWED"
            message = f"{food.name}: recipe quantity needs review."
        elif (quantity.quantity_status == "SUFFICIENT" and quantity.is_quantity_sufficient is True
              and available is not None and available >= required):
            continue
        elif (quantity.quantity_status == "INSUFFICIENT" and available is not None
              and available < required and (candidate := _kg(quantity.shortfall_quantity_g)) is not None
              and candidate > 0):
            status, reason = "INSUFFICIENT", "KNOWN_SHORTFALL"
            shortfall = candidate
            message = f"{food.name}: need {_shortfall_label(shortfall)} more."
        else:
            status, reason = "UNKNOWN", "AMOUNT_UNKNOWN"
            message = f"{food.name}: confirm how much you have."
        issues.append(RecipeReadinessIssue(
            recipe_food_id=food_id, food=food, status=status, reason=reason,
            required_quantity_kg=required, available_quantity_kg=available,
            shortfall_quantity_kg=shortfall, message_en=message,
        ))

    sufficient = all_present and not issues
    if not required_foods:
        status, message = "CHECK_QUANTITIES", "Recipe requirements need review."
    elif not all_present:
        status, message = "MISSING_INGREDIENTS", "Some required ingredients are not recorded in What You Have."
    elif any(issue.status == "INSUFFICIENT" for issue in issues):
        status, message = "INSUFFICIENT_QUANTITY", "All required ingredients are available, but some amounts are insufficient. Check quantities."
    elif issues:
        status, message = "CHECK_QUANTITIES", "All required ingredients are available. Please confirm quantities."
    else:
        status, message = "READY", "Required ingredients and recorded quantities are sufficient for your household."
    return RecipeReadinessResponse(
        status=status, all_required_ingredients_available=all_present,
        all_required_quantities_sufficient=sufficient, message_en=message, issues=issues,
    )
