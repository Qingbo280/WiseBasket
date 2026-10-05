"""Reviewed cooking-oil equivalence, in raw edible kilograms."""
from decimal import Decimal

OIL_FOOD_IDS = frozenset({"SF120", "SF121", "SF123"})
OIL_GROUP = "OIL_EQUIVALENT"
OIL_DENSITY_G_PER_ML = Decimal("0.92")


def oil_group(food_id: str) -> str:
    return OIL_GROUP if food_id in OIL_FOOD_IDS else food_id


def oil_raw_kg(quantity: Decimal | None, unit: str | None) -> Decimal | None:
    if quantity is None or unit is None or not quantity.is_finite() or quantity <= 0:
        return None
    unit = unit.strip().casefold()
    if unit in {"kg", "kilogram", "kilograms"}:
        return quantity
    if unit in {"g", "gram", "grams"}:
        return quantity / Decimal("1000")
    if unit in {"ml", "millilitre", "milliliter", "millilitres", "milliliters"}:
        return quantity * OIL_DENSITY_G_PER_ML / Decimal("1000")
    if unit in {"l", "litre", "liter", "litres", "liters"}:
        return quantity * OIL_DENSITY_G_PER_ML
    return None
