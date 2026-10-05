from __future__ import annotations

import math
from datetime import date
from typing import Iterable

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from packages.optimizer.wisebasket_optimizer.data import Food
from packages.optimizer.wisebasket_optimizer.portions import (
    BY_WEIGHT_STEP_G,
    is_by_weight_food,
    select_pack,
)

from .representative_price import (
    fetch_current_purchase_masses_batch,
    resolve_food_prices,
)


OPTIMIZER_CANDIDATE_SQL = text(
    """
    select
        c.canonical_food_id,
        c.canonical_name,
        c.canonical_name_ms,
        c.category,
        c.energy_kcal,
        c.protein_g,
        c.fibre_g,
        c.iron_mg,
        c.calcium_mg,
        c.vitamin_a_ug,
        c.vitamin_c_mg,
        c.price_rm_per_100g_edible,
        c.observed_date,
        c.source_dataset_version,
        c.nutrition_source_dataset_version,
        c.purchase_mass_g,
        c.pack_label,
        c.price_quality_status,
        c.nutrition_quality_status,
        c.location_id,
        loc.state as location_state,
        loc.district as location_district
    from v_optimizer_food_candidate c
    left join location loc on loc.location_id = c.location_id
    order by c.canonical_food_id
    """
)


def _float_or_none(value) -> float | None:
    # None in, None out; non-finite results (NaN/inf, e.g. a 'NaN'::numeric
    # literal decoded by asyncpg) normalise to None -- the codebase's standard
    # "no data" marker -- so downstream consumers never see NaN
    # (2026-09-10: NaN nutrients crashed POST /plans with ValueError).
    if value is None:
        return None
    v = float(value)
    return v if math.isfinite(v) else None


def _int_pack_grams(value) -> int:
    if value is None:
        return 50
    pack = int(round(float(value)))
    return max(1, pack)


def _date_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def rows_to_optimizer_foods(
    rows: Iterable,
    state: str | None = None,
    district: str | None = None,
) -> list[Food]:
    """Pick one price per food, preferring the requested area.

    NOTE (SF009 price-recovery port): this function, and the
    OPTIMIZER_CANDIDATE_SQL/v_optimizer_food_candidate query it consumes, are
    no longer called by load_optimizer_candidates() below -- that function now
    resolves price via representative_price.resolve_food_price() instead (see
    that module's docstring and docs/data_food_integrity/price_recovery/ for
    why: v_optimizer_food_candidate gates on the stale, offline-computed
    price_rm_per_100g_edible column, and this function's own "cheapest
    observation in the requested tier" selection is exactly the class of bug
    the P0 price-recovery work fixed -- a real median-based selection must
    not be gameable by whichever observation happens to be lowest). Both are
    kept here, UNCHANGED, purely because tests/test_availability_guards.py
    unit-tests this exact function directly and independently of the
    database; retiring it is a separate, out-of-scope follow-up (it would
    also mean deleting or rewriting that test, which this narrow pricing-only
    change does not do). Treat this as dead code from the live serving path's
    perspective, kept alive only for its own test's sake.

    The view carries one row per (food, location). Pricing tiers per food:
    cheapest observation inside the requested district, else inside the
    requested state, else cheapest nationwide. Area-aware pricing keeps the
    plan's estimated cost achievable at stores the user can actually reach
    instead of a theoretical nationwide floor no single store can match.
    """
    state_l = state.strip().lower() if state else None
    district_l = district.strip().lower() if district else None
    best_by_food_id: dict = {}
    best_key_by_food_id: dict = {}
    # Ease-of-purchase signal: distinct stores quoting each food, bucketed by
    # the same district -> state -> nationwide scopes used for pricing, so
    # Food.availability_stores reflects the area the price actually came from.
    stores_by_food_id: dict = {}
    for row in rows:
        data = row._mapping
        price = _float_or_none(data["price_rm_per_100g_edible"])
        if price is None:
            continue
        if data["price_quality_status"] == "BLOCK" or data["nutrition_quality_status"] == "BLOCK":
            continue
        tier = 0
        row_state = (data.get("location_state") or "").strip().lower()
        row_district = (data.get("location_district") or "").strip().lower()
        if state_l and row_state == state_l:
            tier = 1
            if district_l and row_district == district_l:
                tier = 2
        location_id = data.get("location_id")
        if location_id is not None:
            scopes = stores_by_food_id.setdefault(
                data["canonical_food_id"], {0: set(), 1: set(), 2: set()}
            )
            scopes[0].add(location_id)
            if tier >= 1:
                scopes[1].add(location_id)
            if tier >= 2:
                scopes[2].add(location_id)
        # Prefer the most local tier; within a tier, the cheapest price.
        key = (-tier, price)
        if best_key_by_food_id.get(data["canonical_food_id"]) is None or key < best_key_by_food_id[data["canonical_food_id"]]:
            best_by_food_id[data["canonical_food_id"]] = data
            best_key_by_food_id[data["canonical_food_id"]] = key

    foods: list[Food] = []
    for data in sorted(best_by_food_id.values(), key=lambda item: item["canonical_food_id"]):
        price = _float_or_none(data["price_rm_per_100g_edible"])
        tier_used = -best_key_by_food_id[data["canonical_food_id"]][0]
        scopes = stores_by_food_id.get(data["canonical_food_id"])
        availability_stores = len(scopes[tier_used]) if scopes else None
        foods.append(
            Food(
                food_id=data["canonical_food_id"],
                name=data["canonical_name"],
                name_ms=data["canonical_name_ms"] or data["canonical_name"],
                category=data["category"],
                price_rm_per_100g=price,
                price_is_estimated=False,
                edible_fraction=1.0,
                nutrients={
                    "energy_kcal": _float_or_none(data["energy_kcal"]),
                    "protein_g": _float_or_none(data["protein_g"]),
                    "fibre_g": _float_or_none(data["fibre_g"]),
                    "iron_mg": _float_or_none(data["iron_mg"]),
                    "calcium_mg": _float_or_none(data["calcium_mg"]),
                    "vita_ug": _float_or_none(data["vitamin_a_ug"]),
                    "vitc_mg": _float_or_none(data["vitamin_c_mg"]),
                },
                allergen_tags=frozenset(),
                diet_tags=frozenset(),
                pack_grams=_int_pack_grams(data["purchase_mass_g"]),
                pack_label=data["pack_label"] or "",
                price_source=data["source_dataset_version"] or "",
                price_updated=_date_text(data["observed_date"]),
                nutrition_source=data["nutrition_source_dataset_version"] or "",
                nutrition_updated="",
                availability_stores=availability_stores,
            )
        )
    return foods


# ---------------------------------------------------------------------------
# SF009 price-recovery port: identity + nutrition + mapping-governance ONLY
# (deliberately no price join at all). Price is resolved separately, per
# food, via representative_price.resolve_food_prices() (batch port of the
# per-food resolve_food_price()), which reads CURRENT
# unit_conversion + food_price_observation state at query time rather than a
# stored, potentially-stale price_rm_per_100g_edible column (see that
# module's own docstring, and docs/data_food_integrity/price_recovery/ for
# the full root-cause history this design fixes: DERIVED_COLUMN_NOT_RECOMPUTED).
#
# This mirrors v_optimizer_food_candidate's own identity/nutrition/mapping
# conditions exactly (status='ACTIVE', fn.is_current, fn.quality_status in
# PASS/WARN, the same three-part mapping-approval EXISTS clause) so nothing
# about WHICH foods are identity-eligible changes -- only HOW a food's price
# is resolved changes. Also closes the same-class gap found in the mapping
# EXISTS clause (Section on source_food_mapping.source_system in the P0
# audit series): a SEED-tagged mapping row can no longer satisfy this
# eligibility check either.
# ---------------------------------------------------------------------------
CANDIDATE_IDENTITY_SQL = text(
    """
    select cf.canonical_food_id, cf.canonical_name, cf.canonical_name_ms, cf.category,
           fn.source_dataset_version as nutrition_source_dataset_version, fn.basis_g,
           fn.energy_kcal, fn.protein_g, fn.fibre_g, fn.iron_mg, fn.calcium_mg,
           fn.vitamin_a_ug, fn.vitamin_c_mg
    from canonical_food cf
    join food_nutrition fn on fn.canonical_food_id = cf.canonical_food_id
    where cf.status = 'ACTIVE'
      and cf.catalog_eligible
      and fn.is_current = true
      and fn.quality_status in ('PASS', 'WARN')
      and exists (
          select 1
          from source_food_mapping sfm
          where sfm.canonical_food_id = cf.canonical_food_id
            and sfm.mapping_status in ('EXACT', 'ACCEPTED_EQUIVALENT', 'NEEDS_CONVERSION')
            and sfm.verification_status = 'VERIFIED'
            and sfm.review_status = 'APPROVED'
            and sfm.source_system <> 'SEED'
      )
    order by cf.canonical_food_id
    """
)


async def load_optimizer_candidates(
    db: AsyncSession,
    state: str | None = None,
    district: str | None = None,
    adults: int | None = None,
    children: int | None = None,
    days: int | None = None,
) -> list[Food]:
    """Live food catalogue: identity+nutrition+mapping-eligible foods, each
    with its price resolved fresh via representative_price.resolve_food_price
    (District->State->National cascade, one-shop-one-vote median, structural
    real-source allow-list). Restricted to catalogue-eligible foods (the team's
    curated real-data list, migration f7a8b9c0d1e2). A food with no real,
    governance-eligible price
    (or no real, approved edible-yield conversion) is correctly excluded here
    -- never served with a fabricated or synthetic price.

    2026-09-11 multi-pack: when adults/children/days are supplied, the pack
    size is chosen per household via portions.select_pack (largest pack that
    fits the item consumption cap; smallest pack if none fit) instead of
    always taking the latest unit_conversion row. Without household context
    the previous latest-row behaviour stands (tests, catalog previews)."""
    identity_rows = (await db.execute(CANDIDATE_IDENTITY_SQL)).all()

    # Batch price resolution: 2 round trips for ALL foods instead of 2 per
    # food (~70 foods -> ~6 s of sequential round trips saved). The batch
    # path is row-for-row identical to the per-food resolve_food_price()
    # (same predicates, same pure resolution, same fail-closed rules); it
    # also reads one consistent snapshot, so a concurrent data write can no
    # longer produce a mixed price vector within a single plan request.
    food_ids = [row._mapping["canonical_food_id"] for row in identity_rows]
    prices_by_id = await resolve_food_prices(db, food_ids, district=district, state=state)
    purchase_masses = await fetch_current_purchase_masses_batch(db, food_ids)

    foods: list[Food] = []
    for row in identity_rows:
        data = row._mapping
        food_id = data["canonical_food_id"]
        price = prices_by_id.get(food_id)
        if price is None:
            continue  # fail-closed: no real, eligible price -> not servable, same as before
        purchase_mass = purchase_masses.get(food_id)
        if purchase_mass and adults is not None and days is not None:
            # 2026-09-11: household-appropriate pack among ALL registered sizes.
            pack_options = [( _int_pack_grams(f), lbl or "") for f, lbl in purchase_mass]
            pack_grams, pack_label = select_pack(
                pack_options, data["category"], adults, children or 0, days
            )
        elif purchase_mass:
            latest = purchase_mass[-1]  # largest = historically the latest row
            pack_grams = _int_pack_grams(latest[0])
            pack_label = latest[1] or ""
        else:
            pack_grams = _int_pack_grams(None)
            pack_label = ""
        if is_by_weight_food(food_id, data["category"],
                             data["canonical_name"]):
            # By-weight purchase (user decision 2026-09-13; extended 2026-09-15
            # to fresh seasonings and 2026-09-16 to ALL fresh produce + loose
            # dried goods, see portions.is_by_weight_food): replace the
            # registered retail pack with a fine 25 g step priced linearly at
            # price_rm_per_100g (a 1 kg pack would floor a single line at
            # 1 kg, eating a 1A household's whole category budget). The
            # unit_conversion rows stay untouched as the price source; only
            # the optimizer's purchase unit changes.
            pack_grams = BY_WEIGHT_STEP_G
            pack_label = f"{BY_WEIGHT_STEP_G} g"
            pack_options_tuple = ((BY_WEIGHT_STEP_G, pack_label),)
            by_weight = True
        else:
            pack_options_tuple = tuple(
                (_int_pack_grams(g), lbl or "")
                for g, lbl in (purchase_mass or ())
            )
            by_weight = False
        foods.append(Food(
            food_id=food_id,
            name=data["canonical_name"],
            name_ms=data["canonical_name_ms"] or data["canonical_name"],
            category=data["category"],
            price_rm_per_100g=price.price_rm_per_100g_edible,
            price_is_estimated=price.price_is_estimated,
            price_provenance=price.price_provenance,
            edible_fraction=1.0,  # unchanged from before: the edible adjustment is already
                                  # baked into price_rm_per_100g_edible above, so the solver
                                  # must not apply it a second time (matches this codebase's
                                  # existing convention, not the data-team pipeline's
                                  # purchase-basis-in-solver convention -- an intentional,
                                  # disclosed difference; see SF009_PILOT.md Section 1)
            nutrients={
                "energy_kcal": _float_or_none(data["energy_kcal"]),
                "protein_g": _float_or_none(data["protein_g"]),
                "fibre_g": _float_or_none(data["fibre_g"]),
                "iron_mg": _float_or_none(data["iron_mg"]),
                "calcium_mg": _float_or_none(data["calcium_mg"]),
                "vita_ug": _float_or_none(data["vitamin_a_ug"]),
                "vitc_mg": _float_or_none(data["vitamin_c_mg"]),
            },
            allergen_tags=frozenset(),
            diet_tags=frozenset(),
            pack_grams=pack_grams,
            pack_label=pack_label,
            # All registered retail sizes, for the habit-pick retry's
            # smallest-pack lock (see solver._ensure_habit_picks). By-weight
            # foods carry their fine step instead.
            pack_options=pack_options_tuple,
            by_weight=by_weight,
            price_source=price.price_source,
            price_updated=price.price_updated,
            nutrition_source=data["nutrition_source_dataset_version"] or "",
            nutrition_updated="",
            # Ease-of-purchase signal (pre-existing feature, preserved): how many
            # distinct, real, governance-eligible shops the served price actually
            # came from. Previously counted per-row from v_optimizer_food_candidate
            # rows in the winning geographic tier; now taken directly from
            # ResolvedFoodPrice.shop_count, which is the same concept computed by
            # the SAME tier-cascade logic that produced the price itself (D1/D2/D2-B
            # -- see representative_price.py), so it stays consistent with the price
            # by construction instead of being recomputed by a second, separate
            # counting pass. solver.py's MIN_AVAILABILITY_STORES=3 gate already
            # matches representative_price.py's own MIN_ELIGIBLE_SHOPS=3 NORMAL-
            # confidence threshold, so this mapping does not change which foods
            # clear that gate for any food resolved at NORMAL confidence; a food
            # resolved at LOW_CONFIDENCE (a sparse, <3-shop National fallback) will
            # now correctly also read as low-availability to the solver, which did
            # not have a governed, real concept of "shop count" for such foods
            # before this fix.
            availability_stores=price.shop_count,
        ))
    return foods
