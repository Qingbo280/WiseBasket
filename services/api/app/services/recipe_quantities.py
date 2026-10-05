# Deterministic quantity normalization for Epic 5 recipe matching.
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PantryQuantity:
    quantity_status: str
    quantity_g: float | None
    source: str | None = None


@dataclass(frozen=True)
class AvailableQuantity:
    quantity_status: str
    quantity_g: float | None
    sources: tuple[str, ...]


def normalize_pantry_quantity(quantity: float, unit: str) -> PantryQuantity:
    normalized_unit = unit.strip().lower()
    if quantity <= 0:
        raise ValueError("Quantity must be positive.")
    if normalized_unit == "kg":
        return PantryQuantity(quantity_status="KNOWN", quantity_g=quantity * 1000)
    if normalized_unit == "g":
        return PantryQuantity(quantity_status="KNOWN", quantity_g=quantity)
    return PantryQuantity(quantity_status="UNKNOWN", quantity_g=None)


def normalize_quantity_to_grams(quantity: float, unit: str) -> float:
    result = normalize_pantry_quantity(quantity=quantity, unit=unit)
    if result.quantity_g is None:
        raise ValueError(f"Unsupported quantity unit: {unit}")
    return result.quantity_g


def aggregate_available_quantity(quantities: tuple[PantryQuantity, ...]) -> AvailableQuantity:
    known_quantities = tuple(quantity for quantity in quantities if quantity.quantity_status == "KNOWN")
    unknown_quantity_exists = any(quantity.quantity_status == "UNKNOWN" for quantity in quantities)
    sources = tuple(quantity.source for quantity in quantities if quantity.source is not None)

    if not known_quantities:
        return AvailableQuantity(
            quantity_status="UNKNOWN" if unknown_quantity_exists else "UNAVAILABLE",
            quantity_g=None,
            sources=sources,
        )

    return AvailableQuantity(
        quantity_status="PARTIALLY_KNOWN" if unknown_quantity_exists else "KNOWN",
        quantity_g=sum(quantity.quantity_g or 0 for quantity in known_quantities),
        sources=sources,
    )
