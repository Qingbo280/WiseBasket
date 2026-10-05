"""Canonical quantity units shared by pantry and receipt confirmation."""
from __future__ import annotations

from decimal import Decimal


UNIT_ALIASES = {
    "g": "kg", "gram": "kg", "grams": "kg",
    "kg": "kg", "kilogram": "kg", "kilograms": "kg",
    "ml": "l", "millilitre": "l", "milliliter": "l",
    "l": "l", "litre": "l", "liter": "l",
    "pc": "pcs", "pcs": "pcs", "piece": "pcs", "pieces": "pcs",
    "biji": "pcs", "unit": "pcs",
    "pack": "pack", "packet": "pack", "pkt": "pack",
}


def normalize_quantity_unit(quantity: Decimal | None, unit: str | None) -> tuple[Decimal | None, str | None]:
    """Return a safe canonical unit, converting only trusted dimensions."""
    if quantity is None and unit is None:
        return None, None
    if quantity is None or unit is None or quantity <= 0:
        raise ValueError("quantity and unit must be provided together and quantity must be positive")
    raw_unit = unit.strip().casefold()
    canonical = UNIT_ALIASES.get(raw_unit)
    if canonical is None:
        raise ValueError(f"Unsupported unit: {unit}")
    if raw_unit in {"g", "gram", "grams"}:
        quantity /= Decimal("1000")
    elif raw_unit in {"ml", "millilitre", "milliliter"}:
        quantity /= Decimal("1000")
    return quantity, canonical


def combine_quantities(
    current_quantity: Decimal | None,
    current_unit: str | None,
    incoming_quantity: Decimal | None,
    incoming_unit: str | None,
) -> tuple[Decimal | None, str | None]:
    """Merge equivalent stock without inventing conversions for unlike units."""
    current_quantity, current_unit = normalize_quantity_unit(current_quantity, current_unit)
    incoming_quantity, incoming_unit = normalize_quantity_unit(incoming_quantity, incoming_unit)
    if current_quantity is None:
        return incoming_quantity, incoming_unit
    if incoming_quantity is None:
        return current_quantity, current_unit
    if current_unit != incoming_unit:
        return None, None
    return current_quantity + incoming_quantity, current_unit
