"""Query-time representative-price resolution for the live serving path.

Ported from the data-team pipeline's own already-validated fix for this exact
bug class: `3_data_team/implementation_v3/src/data_pipeline/export/
representative_price.py` (its own docstring cites the V22.15A.1
COST_BASIS_DEFECT and V22.16A.2 RESOLVER_BUG fixes -- confirmed live there:
"every one of SF003/SF009/SF024's ~26.5k/5.7k/20.7k real PASS rows has
price_rm_per_100g_purchase fully populated and price_rm_per_100g_edible NULL
on 100% of them"). That module was documented as "read-only, additive, and
NOT wired into services/api" -- this module ports its behavioural rules
(tier cascade, one-shop-one-vote, median-of-latest, >=3-shop confidence gate,
source exclusion) into this codebase's own SQLAlchemy-async idiom, rather
than importing across the two separate packages (different DB driver --
psycopg vs. asyncpg -- and 3_data_team/implementation_v3 is not a dependency
of this application). The pure resolution logic below (constants, tier
cascade, median) is an intentionally faithful port: same names, same order,
same statistic, same confidence gate -- not a third, independently-invented
algorithm.

Design decision (Option A, per the P0 audit series' own Section 4
recommendation): the edible-basis price is derived HERE, at query time, from
current `unit_conversion` state and current `food_price_observation` rows --
never read from the stored `food_price_observation.price_rm_per_100g_edible`
column, which is a value computed once at offline-ETL time and can go stale
whenever new yield evidence is approved after a price row was already loaded
(the exact "DERIVED_COLUMN_NOT_RECOMPUTED" root cause this module exists to
fix). This also means a food lacking real, approved edible-yield evidence
correctly yields no price here -- the same fail-closed behaviour the project
has always intended, just no longer dependent on WHEN the yield evidence was
approved relative to WHEN a price row was loaded.
"""
from __future__ import annotations

import re
import math
import statistics
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Literal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

MIN_ELIGIBLE_SHOPS = 3  # D2-B, ported from representative_price.py

TIER_DISTRICT = "DISTRICT"
TIER_STATE = "STATE"
TIER_NATIONAL = "NATIONAL"
TIER_ORDER = (TIER_DISTRICT, TIER_STATE, TIER_NATIONAL)  # D1, ported order

CONFIDENCE_NORMAL = "NORMAL"
CONFIDENCE_LOW = "LOW_CONFIDENCE"

PRICE_SELECTION_METHOD = "MEDIAN_LATEST_PER_SHOP"

# Structural synthetic-source exclusion (Section 5/8 of the P0 audit series):
# an ALLOW-list, not a deny-list -- a source_dataset_version that doesn't
# match a known real-market pattern is excluded by default (fails safe), so
# a future test/seed tag nobody thought to blocklist cannot silently slip
# through the way 'wisebasket-seed-v1' did under the old, filter-less view.
#
# Two proven-real vintage-tag SHAPES exist, each traced to a specific,
# committed, real-data ingestion path (see docs/data_food_integrity/
# price_recovery/source_tag_compatibility/
# PRICECATCHER_SOURCE_TAG_COMPATIBILITY_REPORT.md for the full evidence
# chain -- neither was added on naming plausibility alone):
#   "PriceCatcher YYYY-MM"   -- 3_data_team/implementation_v3's export path
#                               (the shape this allow-list originally shipped
#                               with in PR #78).
#   "PRICECATCHER_YYYY-MM"   -- scripts/sync_pricecatcher_daily.py (develop
#                               branch, commit 8845ec7 / PR #63): downloads
#                               real monthly Parquet files directly from
#                               https://storage.data.gov.my/pricecatcher,
#                               joins them through APPROVED PRICECATCHER
#                               source_food_mapping rows, and writes
#                               `dataset_version = f"PRICECATCHER_{month_label}"`
#                               (scripts/load_60food_data_pack_to_local.py,
#                               same commit, uses the identical convention).
#                               This is the mechanism that currently updates
#                               the live UAT database (`--uat` flag) -- it
#                               explains every PRICECATCHER_2026-06..09 tag
#                               observed there.
#
# Both shapes are kept as separate, explicit, individually-evidenced entries
# -- NOT collapsed into a case-insensitive or separator-insensitive pattern.
# Nothing else has been proven real. In particular, the sibling synthetic-data
# generator introduced in the SAME commit (scripts/generate_i2_data_pack.py)
# uses a completely distinct, honest tag ("WISEBASKET_SEED") and never
# produces anything PriceCatcher-shaped -- confirming the two real shapes
# above are not accidentally shared with any known synthetic generator.
#
# Hardening (SF009 deployment-readiness review, Section 3): a plain
# startswith("PriceCatcher") prefix check would also admit any string an
# operator or a careless script happened to prefix that way --
# "PriceCatcher-test", "PriceCatcherFake", "PriceCatcher-synthetic",
# "PRICECATCHER_2026-06_TEST". This is not hypothetical: this codebase's OWN
# test fixtures once used exactly such a variant ("PriceCatcher-TESTFIXTURE")
# to simulate real data. Fixed by requiring the full, exact SHAPE via regex
# (still forward-compatible with a new month's tag in either family, no code
# change needed) rather than any prefix/contains check.
#
# Single source of truth for BOTH the Python check below and the SQL
# predicate in _FETCH_SHOP_LATEST_PRICES_SQL, so the two provably cannot
# drift apart (see test_sql_and_python_source_filter_share_same_patterns).
REAL_MARKET_SOURCE_TAG_SHAPES: tuple[str, ...] = (
    # Plain (capturing) groups deliberately, not "(?:...)" -- the SQL layer below
    # embeds this exact string into a SQLAlchemy text() query, which treats ':' as
    # a bind-parameter sigil; "(?:" would be silently (and wrongly) parsed as a
    # bind-parameter reference named ":0" mid-pattern. Proven by this module's own
    # test_sql_and_python_source_filter_share_same_patterns, which checks the SQL
    # text's OWN regex against real/fake tags, not just the Python object.
    r"PriceCatcher \d{4}-(0[1-9]|1[0-2])",
    r"PRICECATCHER_\d{4}-(0[1-9]|1[0-2])",
)

# Governed reference estimates (team decision 2026-09-09, DATA_MIGRATION_MASTER_PLAN
# decision #2): externally researched prices (e-commerce / FAMA / ManDarah) loaded
# as WISEBASKET_REFERENCE observations + mappings, price_is_estimated=1. They are
# STRUCTURALLY admissible to the resolver (an APPROVED WISEBASKET_REFERENCE mapping
# joins exactly like a PriceCatcher one), but they are NOT real-market data and
# must stay truthfully labeled downstream (classify_price_provenance /
# ResolvedFoodPrice.price_provenance / price_is_estimated).
REFERENCE_ESTIMATE_TAG_SHAPE: str = r"REFERENCE_ESTIMATE_\d{4}-(0[1-9]|1[0-2])"
REFERENCE_ESTIMATE_PATTERN: re.Pattern[str] = re.compile(
    f"^{REFERENCE_ESTIMATE_TAG_SHAPE}$"
)

REAL_MARKET_SOURCE_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(f"^{shape}$") for shape in REAL_MARKET_SOURCE_TAG_SHAPES
)

# The exact alternation embedded into the SQL WHERE clause below -- derived,
# not retyped, from the same REAL_MARKET_SOURCE_TAG_SHAPES tuple above.
REAL_MARKET_SOURCE_SQL_REGEX = "^(" + "|".join(REAL_MARKET_SOURCE_TAG_SHAPES) + ")$"

# Resolver admissibility = real market tags + governed reference estimates. Both
# the Python checks and the SQL predicate derive from these same shape strings, so
# the two cannot drift apart (same invariant as the original single-tuple design).
# REAL_MARKET_SOURCE_SQL_REGEX stays as the real-only alternation for callers that
# genuinely need the real-market subset.
RESOLVABLE_SOURCE_TAG_SHAPES: tuple[str, ...] = (
    REAL_MARKET_SOURCE_TAG_SHAPES + (REFERENCE_ESTIMATE_TAG_SHAPE,)
)
RESOLVABLE_SOURCE_SQL_REGEX = "^(" + "|".join(RESOLVABLE_SOURCE_TAG_SHAPES) + ")$"


def is_real_market_source(source_dataset_version: str | None) -> bool:
    """True only for a source_dataset_version matching one of the proven-real
    vintage-tag shapes ("PriceCatcher YYYY-MM" or "PRICECATCHER_YYYY-MM").
    None/empty/anything else (including every synthetic/test tag seen so
    far: 'wisebasket-seed-v1', 'WISEBASKET_SEED', 'TEST', 'SEED', or a
    look-alike like 'PriceCatcher-test' or 'PRICECATCHER_2026-06_TEST') is
    NOT a real source."""
    if not source_dataset_version:
        return False
    return any(pattern.match(source_dataset_version) for pattern in REAL_MARKET_SOURCE_PATTERNS)


def classify_price_provenance(source_dataset_version: str | None) -> str:
    """Minimal, truthful provenance label for the distinctions the data
    actually supports (see Section 6/10 of the P0 audit series --
    price_is_estimated was previously a hardcoded constant).
    REFERENCE_ESTIMATE = governed external estimate (price_is_estimated=1);
    it is admissible to the resolver but must never be labeled real."""
    if not source_dataset_version:
        return "SYNTHETIC_TEST"
    if REFERENCE_ESTIMATE_PATTERN.match(source_dataset_version):
        return "REFERENCE_ESTIMATE"
    return "REAL_PRICECATCHER" if is_real_market_source(source_dataset_version) else "SYNTHETIC_TEST"


@dataclass(frozen=True)
class ShopPrice:
    location_id: int
    price_rm_per_100g_purchase: float
    observed_date: date
    source_item_code: str
    source_dataset_version: str
    district: str | None
    state: str | None


def minimum_purchase_price(shop_prices: list[ShopPrice]) -> float | None:
    """Lowest positive, finite purchase-basis rate among vetted latest shop rows."""
    rates = [row.price_rm_per_100g_purchase for row in shop_prices
             if math.isfinite(row.price_rm_per_100g_purchase) and row.price_rm_per_100g_purchase > 0]
    return min(rates) if rates else None


@dataclass(frozen=True)
class RepresentativePrice:
    price_rm_per_100g_purchase: float
    tier_used: str
    shop_count: int
    confidence: str
    contributing_dates: list[str] = field(default_factory=list)
    contributing_source_item_codes: list[str] = field(default_factory=list)
    price_selection_method: str = PRICE_SELECTION_METHOD


def _one_row_per_shop(shop_prices: list[ShopPrice]) -> list[ShopPrice]:
    """Defensive "one shop, one vote" enforcement -- ported from
    representative_price.py's own function of the same name/contract. The
    SQL below already guarantees this via ROW_NUMBER(), but this function's
    own contract does not trust the caller for it, exactly as the reference
    implementation does not."""
    best: dict[int, ShopPrice] = {}
    for row in shop_prices:
        current = best.get(row.location_id)
        if current is None or row.observed_date >= current.observed_date:
            best[row.location_id] = row
    return list(best.values())


def _median_result(rows: list[ShopPrice], tier: str, confidence: str) -> RepresentativePrice:
    """Ported from representative_price.py::_median_result. PURCHASE-basis
    price, median (never mean, never cheapest) -- see that module's own
    V22.15A.1 COST_BASIS_DEFECT note for why purchase-basis, not edible."""
    values = sorted(r.price_rm_per_100g_purchase for r in rows)
    return RepresentativePrice(
        price_rm_per_100g_purchase=statistics.median(values),
        tier_used=tier,
        shop_count=len(rows),
        confidence=confidence,
        contributing_dates=sorted({r.observed_date.isoformat() for r in rows}),
        contributing_source_item_codes=sorted({r.source_item_code for r in rows}),
    )


def resolve_representative_price(
    shop_prices: list[ShopPrice], *, district: str | None, state: str | None
) -> RepresentativePrice | None:
    """Pure D1+D2+D2-B resolution -- no DB access, ported from
    representative_price.py::resolve_representative_price with the exact
    same tier order, minimum-shop gate, and confidence rule.

    Returns None only when there is not a single eligible observation
    anywhere (the National tier itself is empty) -- the caller must treat
    that as "unavailable price", never invent one.
    """
    national = _one_row_per_shop(shop_prices)
    tiers = {
        TIER_DISTRICT: [r for r in national if district and r.district == district],
        TIER_STATE: [r for r in national if state and r.state == state],
        TIER_NATIONAL: national,
    }
    for tier_name in TIER_ORDER:
        rows = tiers[tier_name]
        if len(rows) >= MIN_ELIGIBLE_SHOPS:
            return _median_result(rows, tier_name, CONFIDENCE_NORMAL)
    final_rows = tiers[TIER_NATIONAL]
    if not final_rows:
        return None
    confidence = CONFIDENCE_NORMAL if len(final_rows) >= MIN_ELIGIBLE_SHOPS else CONFIDENCE_LOW
    return _median_result(final_rows, TIER_NATIONAL, confidence)


# ---------------------------------------------------------------------------
# Async data access (SQLAlchemy/asyncpg port of representative_price.py's
# psycopg-based fetch_shop_latest_prices()). Same query shape: PASS-only,
# purchase-basis gating (not edible-basis -- the whole point of this port),
# structural real-source allow-list, per-item mapping-governance join,
# one-row-per-shop via ROW_NUMBER.
# ---------------------------------------------------------------------------

_FETCH_SHOP_LATEST_PRICES_SQL = text(
    """
    select latest.location_id, latest.price_rm_per_100g_purchase, latest.observed_date,
           latest.source_item_code, latest.source_dataset_version, loc.district, loc.state
    from (
        select fpo.*,
               row_number() over (
                   partition by fpo.canonical_food_id, fpo.location_id
                   order by fpo.observed_date desc, fpo.price_observation_id desc
               ) as rn
        from food_price_observation fpo
        left join source_food_mapping sfm
          on sfm.canonical_food_id = fpo.canonical_food_id
         and upper(sfm.source_system) in ('PRICECATCHER', 'WISEBASKET_REFERENCE')
         and sfm.source_food_id = fpo.source_item_code
        where fpo.canonical_food_id = :cid
          and fpo.quality_status = 'PASS'
          and fpo.price_rm_per_100g_purchase is not null
          and fpo.source_dataset_version ~ '""" + RESOLVABLE_SOURCE_SQL_REGEX + """'
          and sfm.mapping_status in ('EXACT', 'ACCEPTED_EQUIVALENT', 'NEEDS_CONVERSION')
          and sfm.verification_status = 'VERIFIED'
          and sfm.review_status = 'APPROVED'
          and upper(sfm.source_system) <> 'SEED'
    ) latest
    join location loc on loc.location_id = latest.location_id
    where latest.rn = 1
    """
)


async def fetch_shop_latest_prices(db: AsyncSession, canonical_food_id: str) -> list[ShopPrice]:
    result = await db.execute(_FETCH_SHOP_LATEST_PRICES_SQL, {"cid": canonical_food_id})
    rows = []
    for r in result.all():
        m = r._mapping
        rows.append(ShopPrice(
            location_id=m["location_id"],
            price_rm_per_100g_purchase=float(m["price_rm_per_100g_purchase"]),
            observed_date=m["observed_date"],
            source_item_code=m["source_item_code"],
            source_dataset_version=m["source_dataset_version"],
            district=m["district"],
            state=m["state"],
        ))
    return rows


# ---------------------------------------------------------------------------
# Batch variants (N foods in 3 round trips instead of 3N). The per-row SQL
# predicates are BYTE-IDENTICAL to the single-food queries above -- only the
# food filter becomes `= any(:cids)` and the latest-row window partitions by
# (food, location) exactly as before, so every food's row set is the same as
# the per-food query would return. Resolution itself stays in the same pure
# functions (resolve_representative_price), so prices cannot drift between
# the two paths. The batched form reduces ~70 foods x 3 queries from roughly
# 6 s of round trips to ~0.5 s. The single-food functions above remain for
# catalogue detail endpoints and their tests.
# ---------------------------------------------------------------------------

# The real-source filter is evaluated ONCE per distinct source_dataset_version
# (~hundred rows) instead of once per observation row: the POSIX regex costs
# ~50us per row, i.e. ~3.6 s over a 70k-row table -- that regex evaluation was
# the measured candidate-price bottleneck, rather than the round trips
# (2026-09-10: with-regex 3615 ms vs without 35 ms over
# the same scan). `versions` materializes the distinct set so the regex cannot
# be pushed back down into a per-row filter, and the outer IN is a hashed
# semi-join probe (~70 ms). Semantics are IDENTICAL to the per-row regex: every
# fpo.source_dataset_version is by definition a member of `versions`, so
# `in (select v from versions where v ~ <regex>)` is exactly `~ <regex>` on the
# row's own value (NULLs excluded in both formulations). The regex text is
# still REAL_MARKET_SOURCE_SQL_REGEX -- same single source of truth as the
# per-food query and the Python check.
_FETCH_SHOP_LATEST_PRICES_BATCH_SQL = text(
    """
    with versions as materialized (
        select distinct source_dataset_version as v from food_price_observation
    )
    select latest.canonical_food_id, latest.location_id, latest.price_rm_per_100g_purchase,
           latest.observed_date, latest.source_item_code, latest.source_dataset_version,
           loc.district, loc.state
    from (
        select fpo.*,
               row_number() over (
                   partition by fpo.canonical_food_id, fpo.location_id
                   order by fpo.observed_date desc, fpo.price_observation_id desc
               ) as rn
        from food_price_observation fpo
        left join source_food_mapping sfm
          on sfm.canonical_food_id = fpo.canonical_food_id
         and upper(sfm.source_system) in ('PRICECATCHER', 'WISEBASKET_REFERENCE')
         and sfm.source_food_id = fpo.source_item_code
        where fpo.canonical_food_id = any(:cids)
          and fpo.quality_status = 'PASS'
          and fpo.price_rm_per_100g_purchase is not null
          and fpo.source_dataset_version in (
              select v from versions where v ~ '""" + RESOLVABLE_SOURCE_SQL_REGEX + """'
          )
          and sfm.mapping_status in ('EXACT', 'ACCEPTED_EQUIVALENT', 'NEEDS_CONVERSION')
          and sfm.verification_status = 'VERIFIED'
          and sfm.review_status = 'APPROVED'
          and upper(sfm.source_system) <> 'SEED'
    ) latest
    join location loc on loc.location_id = latest.location_id
    where latest.rn = 1
    """
)


async def fetch_shop_latest_prices_batch(
    db: AsyncSession, canonical_food_ids: list[str]
) -> dict[str, list[ShopPrice]]:
    """All foods' one-row-per-shop latest prices in ONE query, grouped by
    food_id. Identical row set per food as fetch_shop_latest_prices()."""
    if not canonical_food_ids:
        return {}
    result = await db.execute(
        _FETCH_SHOP_LATEST_PRICES_BATCH_SQL, {"cids": list(canonical_food_ids)}
    )
    grouped: dict[str, list[ShopPrice]] = {}
    for r in result.all():
        m = r._mapping
        grouped.setdefault(m["canonical_food_id"], []).append(ShopPrice(
            location_id=m["location_id"],
            price_rm_per_100g_purchase=float(m["price_rm_per_100g_purchase"]),
            observed_date=m["observed_date"],
            source_item_code=m["source_item_code"],
            source_dataset_version=m["source_dataset_version"],
            district=m["district"],
            state=m["state"],
        ))
    return grouped


# Same "latest created_at wins" semantics as the single-food queries, with an
# added unit_conversion_id desc tiebreak so per-food and batch paths (and
# repeated runs) pick the SAME row even on equal created_at timestamps -- the
# single-food queries had no tiebreak and were silently arbitrary in that
# corner (behaviour change only where the old answer was already undefined).
_FETCH_EDIBLE_YIELDS_BATCH_SQL = text(
    """
    select distinct on (canonical_food_id) canonical_food_id, edible_yield_fraction
    from unit_conversion
    where canonical_food_id = any(:cids)
      and conversion_type = 'EDIBLE_YIELD'
      and production_eligible = true
      and edible_yield_fraction is not null
    order by canonical_food_id, created_at desc, unit_conversion_id desc
    """
)

_FETCH_PURCHASE_MASSES_BATCH_SQL = text(
    """
    select canonical_food_id, factor, source_unit
    from unit_conversion
    where canonical_food_id = any(:cids)
      and conversion_type = 'PURCHASE_MASS'
      and production_eligible = true
      and factor is not null
    order by canonical_food_id, factor
    """
)


async def fetch_current_edible_yields_batch(
    db: AsyncSession, canonical_food_ids: list[str]
) -> dict[str, Decimal]:
    if not canonical_food_ids:
        return {}
    result = await db.execute(
        _FETCH_EDIBLE_YIELDS_BATCH_SQL, {"cids": list(canonical_food_ids)}
    )
    return {row[0]: row[1] for row in result.all()}


async def fetch_current_purchase_masses_batch(
    db: AsyncSession, canonical_food_ids: list[str]
) -> dict[str, list[tuple[Decimal, str | None]]]:
    """ALL production-eligible PURCHASE_MASS rows per food, ascending by mass.

    2026-09-11: was `distinct on (canonical_food_id)` (latest row only), which
    silently discarded every alternative pack size (eggs 10/20/30-piece trays,
    milk powder tins). The planner now picks a household-appropriate pack via
    portions.select_pack at candidate-load time (single-pack solver model is
    unchanged). Foods with one row behave exactly as before."""
    if not canonical_food_ids:
        return {}
    result = await db.execute(
        _FETCH_PURCHASE_MASSES_BATCH_SQL, {"cids": list(canonical_food_ids)}
    )
    masses: dict[str, list[tuple[Decimal, str | None]]] = {}
    for cid, factor, source_unit in result.all():
        masses.setdefault(cid, []).append((factor, source_unit))
    return masses


async def resolve_food_prices(
    db: AsyncSession,
    canonical_food_ids: list[str],
    *,
    district: str | None = None,
    state: str | None = None,
    default_edible_yield: Decimal | None = None,
) -> dict[str, ResolvedFoodPrice]:
    """Batch equivalent of resolve_food_price() over many foods: 2 round
    trips total instead of 2 per food. Callers may explicitly provide
    ``default_edible_yield`` when their quantity contract treats labelled
    purchase weight as usable recipe weight. Other callers retain the
    established fail-closed behaviour. Returns {food_id: ResolvedFoodPrice}."""
    if not canonical_food_ids:
        return {}
    shop_grouped = await fetch_shop_latest_prices_batch(db, canonical_food_ids)
    yield_by_id = await fetch_current_edible_yields_batch(db, canonical_food_ids)
    resolved: dict[str, ResolvedFoodPrice] = {}
    for food_id, shop_prices in shop_grouped.items():
        representative = resolve_representative_price(
            shop_prices, district=district, state=state
        )
        if representative is None:
            continue
        yield_fraction = yield_by_id.get(food_id, default_edible_yield)
        if yield_fraction is None:
            continue
        edible_price = float(representative.price_rm_per_100g_purchase) / float(yield_fraction)
        provenance, is_estimated, source = resolved_price_source_fields(shop_prices)
        resolved[food_id] = ResolvedFoodPrice(
            price_rm_per_100g_edible=round(edible_price, 4),
            price_rm_per_100g_purchase=representative.price_rm_per_100g_purchase,
            tier_used=representative.tier_used,
            shop_count=representative.shop_count,
            confidence=representative.confidence,
            price_provenance=provenance,
            price_is_estimated=is_estimated,
            price_source=source,
            price_updated=max(representative.contributing_dates) if representative.contributing_dates else "",
            location_state=state, location_district=district,
        )
    return resolved


_FETCH_EDIBLE_YIELD_SQL = text(
    """
    select edible_yield_fraction
    from unit_conversion
    where canonical_food_id = :cid
      and conversion_type = 'EDIBLE_YIELD'
      and production_eligible = true
      and edible_yield_fraction is not null
    order by created_at desc, unit_conversion_id desc
    limit 1
    """
)


_FETCH_PURCHASE_MASS_SQL = text(
    """
    select factor, source_unit
    from unit_conversion
    where canonical_food_id = :cid
      and conversion_type = 'PURCHASE_MASS'
      and production_eligible = true
      and factor is not null
    order by created_at desc, unit_conversion_id desc
    limit 1
    """
)


async def fetch_current_purchase_mass(db: AsyncSession, canonical_food_id: str) -> tuple[Decimal, str | None] | None:
    """Live PURCHASE_MASS lookup, unchanged in spirit from the prior
    implementation's `uc.source_unit as pack_label` join -- kept as its own
    function (not folded into resolve_food_price) since pack_label/pack_grams
    is a display concern, not a price-eligibility one; a food can have a
    resolved price without a known pack label (falls back to defaults)."""
    result = await db.execute(_FETCH_PURCHASE_MASS_SQL, {"cid": canonical_food_id})
    row = result.first()
    return (row[0], row[1]) if row is not None else None


async def fetch_current_edible_yield(db: AsyncSession, canonical_food_id: str) -> Decimal | None:
    """Reads the CURRENT unit_conversion state, live, every call -- this is
    the fix for DERIVED_COLUMN_NOT_RECOMPUTED: a food whose yield evidence
    was approved after its price rows were loaded is picked up immediately,
    with no backfill/migration required."""
    result = await db.execute(_FETCH_EDIBLE_YIELD_SQL, {"cid": canonical_food_id})
    row = result.first()
    return row[0] if row is not None else None


@dataclass(frozen=True)
class ResolvedFoodPrice:
    price_rm_per_100g_edible: float
    price_rm_per_100g_purchase: float
    tier_used: str
    shop_count: int
    confidence: str
    price_provenance: str
    price_is_estimated: bool
    price_source: str
    price_updated: str
    location_state: str | None
    location_district: str | None


def resolved_price_source_fields(
    shop_prices: list[ShopPrice],
) -> tuple[str, bool, str]:
    contributing_versions = {row.source_dataset_version for row in shop_prices}
    is_reference_estimate = bool(contributing_versions) and all(
        bool(version) and REFERENCE_ESTIMATE_PATTERN.match(version)
        for version in contributing_versions
    )
    if is_reference_estimate:
        return "REFERENCE_ESTIMATE", True, "WiseBasket reference"
    return "REAL_PRICECATCHER", False, "PriceCatcher"


async def resolve_food_price(
    db: AsyncSession, canonical_food_id: str, *, district: str | None = None, state: str | None = None
) -> ResolvedFoodPrice | None:
    """The one entry point services/api should call. Returns None -- never a
    fabricated value -- when no real, governance-eligible price observation
    exists, OR when no real, approved edible-yield conversion exists for
    this food (fail-closed, matching the project's own established
    convention; SF003/SF005-style foods correctly stay excluded here, not
    silently defaulted to yield=1.0)."""
    shop_prices = await fetch_shop_latest_prices(db, canonical_food_id)
    if not shop_prices:
        return None
    representative = resolve_representative_price(shop_prices, district=district, state=state)
    if representative is None:
        return None
    yield_fraction = await fetch_current_edible_yield(db, canonical_food_id)
    if yield_fraction is None:
        return None
    edible_price = float(representative.price_rm_per_100g_purchase) / float(yield_fraction)
    # Truthful labeling: the SQL allow-list now admits governed WISEBASKET_REFERENCE
    # estimates alongside real PriceCatcher rows. Only when EVERY contributing shop
    # price is a reference estimate is the result labeled REFERENCE_ESTIMATE /
    # price_is_estimated=True / non-PriceCatcher source; any real row in the mix
    # keeps the real-market labels (real observations dominate the median).
    provenance, is_reference_estimate, source = resolved_price_source_fields(shop_prices)
    return ResolvedFoodPrice(
        price_rm_per_100g_edible=round(edible_price, 4),
        price_rm_per_100g_purchase=representative.price_rm_per_100g_purchase,
        tier_used=representative.tier_used,
        shop_count=representative.shop_count,
        confidence=representative.confidence,
        price_provenance=provenance,
        price_is_estimated=is_reference_estimate,
        price_source=source,
        price_updated=max(representative.contributing_dates) if representative.contributing_dates else "",
        location_state=state, location_district=district,
    )
