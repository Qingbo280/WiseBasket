"""Catalogue completeness classification (detail_level), kept deliberately
separate from optimizer eligibility.

A canonical food no longer needs to be fully optimizer-ready to exist in the
catalogue. This module computes, at query time, from the SAME underlying
tables/functions the optimizer gates already use (never a duplicated or
hand-maintained copy of that logic, so the two can never silently drift):

  - detail_level: FULL_DETAIL / PARTIAL_DETAIL / NO_DETAIL -- a catalogue-
    completeness classification.
  - missing_detail_fields: the deterministic list of concrete gaps, using
    this repository's own concept names (real_price, nutrition,
    purchase_conversion, edible_yield).
  - optimizer_eligible: whether this food would actually appear in
    load_optimizer_candidates() right now -- a LIVE, query-time fact,
    independent of detail_level. A FULL_DETAIL food can transiently be
    optimizer_eligible=False (e.g. every shop stopped reporting a price this
    month) without its catalogue governance state changing; nothing here
    lets a food skip the optimizer's own gates.

No field here is stored -- it is always derived fresh, so it cannot drift
from the tables that are its own source of truth.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from services.api.app.services.optimizer_candidate_service import _int_pack_grams
from services.api.app.services.representative_price import (
    fetch_current_edible_yield,
    fetch_current_purchase_mass,
    fetch_shop_latest_prices,
    resolve_food_price,
)

FULL_DETAIL = "FULL_DETAIL"
PARTIAL_DETAIL = "PARTIAL_DETAIL"
NO_DETAIL = "NO_DETAIL"

_CURRENT_NUTRITION_SQL = text(
    """
    select 1 from food_nutrition
    where canonical_food_id = :cid and is_current = true and quality_status in ('PASS', 'WARN')
    limit 1
    """
)


@dataclass(frozen=True)
class DetailInfo:
    detail_level: str
    missing_detail_fields: list[str] = field(default_factory=list)
    optimizer_eligible: bool = False
    has_real_price: bool = False
    has_nutrition: bool = False


async def compute_detail(db: AsyncSession, canonical_food_id: str) -> DetailInfo:
    has_nutrition = (
        await db.execute(_CURRENT_NUTRITION_SQL, {"cid": canonical_food_id})
    ).first() is not None

    shop_prices = await fetch_shop_latest_prices(db, canonical_food_id)
    has_real_price = len(shop_prices) > 0

    purchase_mass = await fetch_current_purchase_mass(db, canonical_food_id)
    has_purchase_conversion = purchase_mass is not None

    yield_fraction = await fetch_current_edible_yield(db, canonical_food_id)
    has_yield = yield_fraction is not None

    missing: list[str] = []
    if not has_nutrition:
        missing.append("nutrition")
    if not has_real_price:
        missing.append("real_price")
    if not has_purchase_conversion:
        missing.append("purchase_conversion")
    if not has_yield:
        missing.append("edible_yield")

    # optimizer_eligible mirrors resolve_food_price()'s ACTUAL live gates
    # exactly: nutrition + a real, currently-resolvable price + edible yield.
    # Purchase-mass conversion is deliberately NOT one of these gates: it is
    # applied once, at ingestion time, to compute food_price_observation's
    # stored price_rm_per_100g_purchase column -- resolve_food_price never
    # re-fetches unit_conversion(PURCHASE_MASS) at serve time (confirmed by
    # reading that function directly). has_purchase_conversion is still
    # reported below as a catalogue-completeness signal (a new food needs it
    # for its price observations to ever be computed correctly in the first
    # place), just not as an optimizer_eligible gate, to avoid silently
    # duplicating -- and risking drifting from -- the resolver's own logic.
    optimizer_eligible = has_nutrition and has_real_price and has_yield

    if not missing:
        detail_level = FULL_DETAIL
    elif has_nutrition or has_real_price:
        detail_level = PARTIAL_DETAIL
    else:
        detail_level = NO_DETAIL

    return DetailInfo(
        detail_level=detail_level,
        missing_detail_fields=missing,
        optimizer_eligible=optimizer_eligible,
        has_real_price=has_real_price,
        has_nutrition=has_nutrition,
    )


_ALL_ACTIVE_FOODS_SQL = text(
    """
    select canonical_food_id, canonical_name, canonical_name_ms, category
    from canonical_food
    where status = 'ACTIVE'
      and (:include_hidden or catalog_eligible)
    order by canonical_food_id
    """
)

_CURRENT_NUTRITION_ROW_SQL = text(
    """
    select energy_kcal, protein_g, fibre_g, iron_mg, calcium_mg, vitamin_a_ug, vitamin_c_mg,
           source_dataset_version
    from food_nutrition
    where canonical_food_id = :cid and is_current = true and quality_status in ('PASS', 'WARN')
    order by created_at desc
    limit 1
    """
)


@dataclass(frozen=True)
class CatalogueEntry:
    """One row for the full catalogue endpoint -- every ACTIVE canonical food,
    regardless of detail_level. Catalogue visibility (this) is deliberately
    separate from optimizer eligibility (DetailInfo.optimizer_eligible):
    a PARTIAL_DETAIL or NO_DETAIL food is never hidden just because the
    optimizer cannot currently use it."""
    food_id: str
    name: str
    name_ms: str
    category: str
    detail_level: str
    missing_detail_fields: list[str]
    optimizer_eligible: bool
    price_rm_per_100g: Optional[float]
    price_rm_per_100g_purchase: Optional[float]
    price_is_estimated: bool
    price_provenance: str
    price_source: str
    price_updated: str
    nutrients: dict
    nutrition_source: str
    pack_grams: Optional[int]
    pack_label: str


async def load_full_catalogue(
    db: AsyncSession, include_hidden: bool = False
) -> list[CatalogueEntry]:
    """ACTIVE canonical foods, FULL/PARTIAL/NO_DETAIL alike.

    By default only catalogue-eligible foods are served (the catalog_eligible
    tag hides the foods the team curated out of the PLANNING layer - see
    migration f7a8b9c0d1e2). ``include_hidden=True`` additionally serves the
    catalog_eligible=false foods for the what-you-have/pantry layer: the user
    can buy them in a real shop even though we have no trustworthy price, so
    they stay invisible to planning but must remain pickable as stock. Price
    and nutrition are populated wherever they genuinely resolve (same real,
    fail-closed resolvers the optimizer uses -- never fabricated for a
    PARTIAL/NO_DETAIL food just to look more complete)."""
    identity_rows = (
        await db.execute(
            _ALL_ACTIVE_FOODS_SQL, {"include_hidden": include_hidden}
        )
    ).all()

    entries: list[CatalogueEntry] = []
    for row in identity_rows:
        data = row._mapping
        food_id = data["canonical_food_id"]

        nutrition_row = (
            await db.execute(_CURRENT_NUTRITION_ROW_SQL, {"cid": food_id})
        ).first()
        nutrients = {
            "energy_kcal": None, "protein_g": None, "fibre_g": None, "iron_mg": None,
            "calcium_mg": None, "vita_ug": None, "vitc_mg": None,
        }
        nutrition_source = ""
        if nutrition_row is not None:
            n = nutrition_row._mapping
            nutrients = {
                "energy_kcal": _f(n["energy_kcal"]), "protein_g": _f(n["protein_g"]),
                "fibre_g": _f(n["fibre_g"]), "iron_mg": _f(n["iron_mg"]),
                "calcium_mg": _f(n["calcium_mg"]), "vita_ug": _f(n["vitamin_a_ug"]),
                "vitc_mg": _f(n["vitamin_c_mg"]),
            }
            nutrition_source = n["source_dataset_version"] or ""

        price = await resolve_food_price(db, food_id)
        purchase_mass = await fetch_current_purchase_mass(db, food_id)
        pack_grams = _int_pack_grams(purchase_mass[0]) if purchase_mass else None
        pack_label = (purchase_mass[1] or "") if purchase_mass else ""

        detail = await compute_detail(db, food_id)

        entries.append(CatalogueEntry(
            food_id=food_id,
            name=data["canonical_name"],
            name_ms=data["canonical_name_ms"] or data["canonical_name"],
            category=data["category"],
            detail_level=detail.detail_level,
            missing_detail_fields=detail.missing_detail_fields,
            optimizer_eligible=detail.optimizer_eligible,
            price_rm_per_100g=price.price_rm_per_100g_edible if price else None,
            price_rm_per_100g_purchase=price.price_rm_per_100g_purchase if price else None,
            price_is_estimated=price.price_is_estimated if price else False,
            price_provenance=price.price_provenance if price else "",
            price_source=price.price_source if price else "",
            price_updated=price.price_updated if price else "",
            nutrients=nutrients,
            nutrition_source=nutrition_source,
            pack_grams=pack_grams,
            pack_label=pack_label,
        ))
    return entries


def _f(value) -> Optional[float]:
    return float(value) if value is not None else None
