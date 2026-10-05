"""Shared pantry mutations. Callers lock the owning household first."""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.optimizer.wisebasket_optimizer.v2.oil_equivalence import OIL_FOOD_IDS, oil_raw_kg

from ..db import CanonicalFood, Household, PantryItem
from .pantry_units import combine_quantities


def combine_food_quantities(
    food_id: str,
    current_quantity: Decimal | None,
    current_unit: str | None,
    incoming_quantity: Decimal | None,
    incoming_unit: str | None,
) -> tuple[Decimal | None, str | None]:
    """Merge reviewed oils by mass; keep generic mixed-unit stock conservative."""
    if food_id not in OIL_FOOD_IDS:
        return combine_quantities(current_quantity, current_unit, incoming_quantity, incoming_unit)
    current_kg = oil_raw_kg(current_quantity, current_unit)
    incoming_kg = oil_raw_kg(incoming_quantity, incoming_unit)
    if current_kg is None or incoming_kg is None:
        # An opaque pack/pcs amount cannot be treated as zero oil. Preserve
        # the generic merge policy (including unknown mixed units) instead.
        return combine_quantities(current_quantity, current_unit, incoming_quantity, incoming_unit)
    return current_kg + incoming_kg, "kg"


async def upsert_pantry_stock(
    db: AsyncSession,
    household_id: int,
    canonical_food_id: str,
    quantity: Decimal | None,
    unit: str | None,
    source: str,
) -> PantryItem:
    """Merge safe quantities; a manual/receipt write owns the resulting row."""
    existing = (
        await db.scalars(
            select(PantryItem)
            .where(
                PantryItem.household_id == household_id,
                PantryItem.canonical_food_id == canonical_food_id,
                PantryItem.status == "AVAILABLE",
            )
            .order_by(PantryItem.pantry_item_id)
            .with_for_update()
        )
    ).all()
    if not existing:
        item = PantryItem(
            household_id=household_id,
            canonical_food_id=canonical_food_id,
            source=source,
            status="AVAILABLE",
            quantity=quantity,
            unit=unit,
            basket_have_managed=False,
        )
        db.add(item)
        return item

    keeper, *duplicates = existing
    combined_quantity, combined_unit = keeper.quantity, keeper.unit
    for duplicate in duplicates:
        combined_quantity, combined_unit = combine_food_quantities(
            canonical_food_id, combined_quantity, combined_unit, duplicate.quantity, duplicate.unit
        )
        duplicate.status = "REMOVED"
        duplicate.basket_have_managed = False
    combined_quantity, combined_unit = combine_food_quantities(
        canonical_food_id, combined_quantity, combined_unit, quantity, unit
    )
    keeper.quantity = combined_quantity
    keeper.unit = combined_unit
    keeper.source = source
    keeper.basket_have_managed = False
    return keeper


async def sync_basket_have_items(
    db: AsyncSession,
    household: Household,
    desired_ids: list[str],
) -> None:
    """Replace only basket-owned existence rows; preserve all other stock."""
    desired = set(desired_ids)
    existing = (
        await db.scalars(
            select(PantryItem)
            .where(PantryItem.household_id == household.id, PantryItem.status == "AVAILABLE")
            .order_by(PantryItem.pantry_item_id)
            .with_for_update()
        )
    ).all()
    available_ids = {item.canonical_food_id for item in existing}
    changed = False
    for food_id in desired_ids:
        if food_id in available_ids:
            continue
        db.add(PantryItem(
            household_id=household.id,
            canonical_food_id=food_id,
            source="MANUAL",
            status="AVAILABLE",
            quantity=None,
            unit=None,
            basket_have_managed=True,
        ))
        changed = True
    for item in existing:
        if item.basket_have_managed and item.canonical_food_id not in desired:
            item.status = "REMOVED"
            item.basket_have_managed = False
            changed = True
    if changed:
        household.pantry_confirmed_at = None
    await db.flush()


async def available_pantry_rows(
    db: AsyncSession, household_id: int
) -> list[tuple[PantryItem, CanonicalFood]]:
    rows = await db.execute(
        select(PantryItem, CanonicalFood)
        .join(CanonicalFood, CanonicalFood.canonical_food_id == PantryItem.canonical_food_id)
        .where(PantryItem.household_id == household_id, PantryItem.status == "AVAILABLE")
        .order_by(PantryItem.pantry_item_id)
    )
    return list(rows.all())
