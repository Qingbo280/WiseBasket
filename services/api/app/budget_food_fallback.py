"""Reviewed, priced food ideas when no complete recipe add-on fits."""
from datetime import date
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR

from packages.optimizer.wisebasket_optimizer.v2.calculations import PurchaseOption
from packages.optimizer.wisebasket_optimizer.v2.safety import FoodSafety, resolve_safety_exclusions
from packages.optimizer.wisebasket_optimizer.week_floors import solo_week_floor_g
from services.api.app.schemas import PlannerV2FoodFallbackResponse


# Rotating candidates by budget band. These are catalogue IDs, not fixed prices.
FOOD_FALLBACK_ROWS = {
    100: (
        ("SF022", "SF055", "SF109"),  # prawn, cabbage, noodles
        ("SF018", "SF062", "SF057"),  # eggs, spinach, potato
        ("SF124", "SF077", "SF159"),  # dhal, carrot, vermicelli
        ("SF018", "SF072", "SF110"),  # tomato egg stir-fry with rice
        ("SF006", "SF057", "SF110"),  # chicken and potato with rice
    ),
    200: (
        ("SF002", "SF084", "SF110"),  # beef, long beans, rice
        ("SF035", "SF079", "SF109"),  # tilapia, cauliflower, noodles
        ("SF006", "SF062", "SF057"),  # chicken, spinach, potato
        ("SF018", "SF084", "SF110"),  # long-bean egg stir-fry with rice
        ("SF035", "SF079", "SF110"),  # tilapia and cauliflower with rice
    ),
    300: (
        ("SF002", "SF082", "SF159"),  # beef, broccoli, vermicelli
        ("SF022", "SF079", "SF109"),  # prawn, cauliflower, noodles
        ("SF035", "SF084", "SF110"),  # tilapia, long beans, rice
        ("SF006", "SF072", "SF110"),  # tomato chicken with rice
        ("SF022", "SF082", "SF110"),  # prawn and broccoli with rice
    ),
}
FOOD_FALLBACK_IDS = frozenset(
    food_id for rows in FOOD_FALLBACK_ROWS.values() for row in rows for food_id in row
)
FOOD_FALLBACK_GROUPS = ("protein", "vegetables", "carbohydrate")


def rotated_food_rows(budget_rm: Decimal, week: int | None = None) -> tuple[tuple[str, ...], ...]:
    band = 100 if budget_rm <= 100 else 200 if budget_rm <= 200 else 300
    rows = FOOD_FALLBACK_ROWS[band]
    offset = ((date.today().isocalendar().week if week is None else week) - 1) % len(rows)
    return rows[offset:] + rows[:offset]


def rotating_week_plan_priorities(
    *,
    budget_rm: Decimal,
    purchase_options: tuple[PurchaseOption, ...],
    food_safety: tuple[FoodSafety, ...],
    excluded_food_ids: frozenset[str],
    recipe_food_ids: set[str],
    week: int | None = None,
) -> frozenset[str]:
    """Prefer one eligible rotating food trio when the user chose nothing.

    These reviewed food ideas are anchors for the approved recipe solver; they
    are never treated as a complete basket or given invented quantities.
    """
    priced_ids = {option.food_id for option in purchase_options if not option.price_is_estimated}
    reviewed_ids = {record.food_id for record in food_safety}
    for row in rotated_food_rows(budget_rm, week):
        if all(food_id in priced_ids
               and food_id in reviewed_ids
               and food_id in recipe_food_ids
               and food_id not in excluded_food_ids
               for food_id in row):
            return frozenset(row)
    return frozenset()


def build_budget_food_fallback(
    *,
    budget_rm: Decimal,
    basket_cost_rm: Decimal,
    purchase_options: tuple[PurchaseOption, ...],
    food_safety: tuple[FoodSafety, ...],
    dietary_patterns: list[str],
    allergens: list[str],
    excluded_food_ids: list[str],
    basket_food_ids: set[str],
    selected_food_ids: set[str],
    purchase_floor_persons: Decimal = Decimal("1"),
    suggestion_budget_rm: Decimal | None = None,
    week: int | None = None,
) -> list[PlannerV2FoodFallbackResponse]:
    if budget_rm <= 0:
        return []
    rotated_rows = rotated_food_rows(budget_rm, week)
    options = {option.food_id: option for option in purchase_options}
    reviewed_ids = {record.food_id for record in food_safety}
    safety = resolve_safety_exclusions(
        FOOD_FALLBACK_IDS, food_safety, dietary_patterns, allergens, excluded_food_ids,
    )
    blocked = safety.excluded_food_ids | basket_food_ids | selected_food_ids
    remaining = budget_rm - basket_cost_rm
    default_floor_kg = (
        Decimal("0.25") if purchase_floor_persons <= Decimal("1.25")
        else Decimal("0.4") if purchase_floor_persons <= Decimal("1.75")
        else Decimal("1")
    )
    suggestions = []
    available_rm = max(
        Decimal("0"),
        min(remaining, suggestion_budget_rm) if suggestion_budget_rm is not None else remaining,
    )
    for group_index, group in enumerate(FOOD_FALLBACK_GROUPS):
        for row in rotated_rows:
            food_id = row[group_index]
            option = options.get(food_id)
            if food_id in blocked or food_id not in reviewed_ids or option is None:
                continue
            if option.price_is_estimated:
                continue
            # Match the app's curated weekly floor before quoting cost.
            solo_floor_g = solo_week_floor_g(food_id)
            purchase_floor_kg = (
                Decimal(solo_floor_g) * purchase_floor_persons / Decimal("1000")
                if solo_floor_g is not None else default_floor_kg
            )
            target_units = max(1, int((purchase_floor_kg / option.unit_kg).to_integral_value(rounding=ROUND_CEILING)))
            # Loose foods can be added as a 250 g side; packs need one whole
            # registered pack. Never suggest an item that needs a swap to fit.
            minimum_units = max(1, int((Decimal("0.25") / option.unit_kg).to_integral_value(rounding=ROUND_CEILING))) if option.unit_kg < Decimal("0.25") else 1
            unit_cost = option.unit_kg * option.price_rm_per_kg
            if unit_cost * minimum_units > available_rm:
                continue
            affordable_units = int((available_rm / unit_cost).to_integral_value(rounding=ROUND_FLOOR))
            units = min(target_units, affordable_units)
            purchase_kg = option.unit_kg * units
            cost = purchase_kg * option.price_rm_per_kg
            suggestions.append(PlannerV2FoodFallbackResponse(
                food_id=food_id,
                group=group,
                purchase_units=units,
                purchase_kg=float(purchase_kg),
                estimated_cost_rm=float(cost),
                requires_swap=False,
            ))
            available_rm -= cost
            break
    return suggestions
