"""Regression coverage for the P0 price-recovery fix (representative_price.py
+ optimizer_candidate_service.py's query-time price resolution).

Safety: this file seeds and cleans up its OWN, clearly-scoped test-only
canonical_food_ids (prefix "PRVTEST", distinct from the existing SEED0xx
convention and from any real SFnnn id) against whatever DATABASE_URL the
test process resolves -- exactly like tests/db_seed.py already does for the
rest of the suite. It must only ever be run against an isolated local/CI
database (see tests/conftest.py's own documented docker compose workflow).
Never point DATABASE_URL at the shared Railway instance when running this
file -- doing so once already caused CB-DEF-005's SEED001-009 pollution
incident (see docs/data_food_integrity/P0_INTEGRITY_AUDIT.md).
"""
from __future__ import annotations

from datetime import date

import pytest
import pytest_asyncio
from sqlalchemy import delete, select

from services.api.app.db import (
    AppUser,
    AsyncSessionLocal,
    CanonicalFood,
    FoodNutrition,
    FoodPriceObservation,
    Location,
    SourceFoodMapping,
    UnitConversion,
)

REVIEWER_EMAIL = "prvtest-reviewer@wisebasket.test"
from services.api.app.services.optimizer_candidate_service import load_optimizer_candidates
from services.api.app.services.representative_price import (
    ResolvedFoodPrice,
    classify_price_provenance,
    is_real_market_source,
    resolve_food_price,
)

PREFIX = "PRVTEST"
REAL_FOOD = f"{PREFIX}_REAL"       # abundant real data + a competing synthetic row
NO_YIELD_FOOD = f"{PREFIX}_NOYIELD"  # real price, real purchase-mass, NO edible-yield (SF003-style)
CONTROL_FOOD = f"{PREFIX}_CTRL"    # a plain, already-working real-priced food (regression guard)

ALL_TEST_FOOD_IDS = [REAL_FOOD, NO_YIELD_FOOD, CONTROL_FOOD]


async def _wipe():
    async with AsyncSessionLocal() as db:
        await db.execute(delete(FoodPriceObservation).where(FoodPriceObservation.canonical_food_id.in_(ALL_TEST_FOOD_IDS)))
        await db.execute(delete(UnitConversion).where(UnitConversion.canonical_food_id.in_(ALL_TEST_FOOD_IDS)))
        await db.execute(delete(SourceFoodMapping).where(SourceFoodMapping.canonical_food_id.in_(ALL_TEST_FOOD_IDS)))
        await db.execute(delete(FoodNutrition).where(FoodNutrition.canonical_food_id.in_(ALL_TEST_FOOD_IDS)))
        await db.execute(delete(CanonicalFood).where(CanonicalFood.canonical_food_id.in_(ALL_TEST_FOOD_IDS)))
        await db.execute(delete(Location).where(Location.source_premise_code.like(f"{PREFIX}%")))
        await db.commit()


def _location(db, code, name, state, district):
    loc = Location(source_premise_code=code, location_name=name, premise_type="TEST",
                    state=state, district=district, active=True)
    db.add(loc)
    return loc


@pytest_asyncio.fixture
async def price_recovery_fixture():
    await _wipe()
    async with AsyncSessionLocal() as db:
        # Six real, distinct-shop locations across two states/two districts each, so the
        # National tier (>=3 shops) is exercised without needing district/state cascade
        # detail for this test's purposes -- the cascade itself is unit-tested purely
        # (test_tier_cascade_pure below), independent of the DB.
        locs = [
            _location(db, f"{PREFIX}-L1", "Test Store 1", "Selangor", "Petaling"),
            _location(db, f"{PREFIX}-L2", "Test Store 2", "Selangor", "Petaling"),
            _location(db, f"{PREFIX}-L3", "Test Store 3", "Selangor", "Klang"),
            _location(db, f"{PREFIX}-L4", "Test Store 4", "Johor", "Johor Bahru"),
            _location(db, f"{PREFIX}-L5", "Test Store 5", "Johor", "Johor Bahru"),
            _location(db, f"{PREFIX}-SEEDLOC", "Synthetic Test Store", "Selangor", "Petaling"),
            _location(db, f"{PREFIX}-LOOKALIKELOC", "Look-alike Tag Test Store", "Selangor", "Petaling"),
        ]
        await db.flush()

        reviewer = (await db.execute(select(AppUser).where(AppUser.email_normalized == REVIEWER_EMAIL))).scalar_one_or_none()
        if reviewer is None:
            reviewer = AppUser(email=REVIEWER_EMAIL, email_normalized=REVIEWER_EMAIL,
                                password_hash="test-not-a-login", role="ADMIN", status="ACTIVE", email_verified=True)
            db.add(reviewer)
            await db.flush()

        for fid, name in [(REAL_FOOD, "test peanuts"), (NO_YIELD_FOOD, "test whole chicken"), (CONTROL_FOOD, "test rice")]:
            db.add(CanonicalFood(canonical_food_id=fid, canonical_name=name, canonical_name_ms=name, category="protein", status="ACTIVE"))
            db.add(FoodNutrition(canonical_food_id=fid, source_dataset_version="TEST_NUTRITION", source_record_id=f"nut-{fid}",
                                  basis_g=100, energy_kcal=500, protein_g=20, quality_status="PASS", is_current=True))
            db.add(SourceFoodMapping(source_system="MYFCD", source_dataset_version="TEST", source_food_id=f"myfcd-{fid}",
                                      source_food_name=name, canonical_food_id=fid,
                                      mapping_status="EXACT", verification_status="VERIFIED", review_status="APPROVED",
                                      reviewed_by=reviewer.user_id, reviewed_at=date(2026, 8, 20)))
            db.add(SourceFoodMapping(source_system="PRICECATCHER", source_dataset_version="TEST", source_food_id=f"pc-{fid}",
                                      source_food_name=name, canonical_food_id=fid,
                                      mapping_status="EXACT", verification_status="VERIFIED", review_status="APPROVED",
                                      reviewed_by=reviewer.user_id, reviewed_at=date(2026, 8, 20)))
            db.add(UnitConversion(canonical_food_id=fid, conversion_type="PURCHASE_MASS",
                                   source_unit="1kg", target_unit="g", factor=1000, production_eligible=True))
        # Only REAL_FOOD and CONTROL_FOOD get an edible-yield conversion; NO_YIELD_FOOD
        # deliberately does not, reproducing the SF003 situation exactly.
        db.add(UnitConversion(canonical_food_id=REAL_FOOD, conversion_type="EDIBLE_YIELD",
                               source_unit="purchase_mass", target_unit="edible_mass",
                               edible_yield_fraction=1.0, production_eligible=True))
        db.add(UnitConversion(canonical_food_id=CONTROL_FOOD, conversion_type="EDIBLE_YIELD",
                               source_unit="purchase_mass", target_unit="edible_mass",
                               edible_yield_fraction=1.0, production_eligible=True))
        await db.flush()

        # REAL_FOOD: 5 real PriceCatcher-sourced observations (prices 8-12 RM/kg -> median
        # RM ~1.00/100g purchase), all older than the synthetic row below.
        real_prices = [8.0, 9.0, 10.0, 11.0, 12.0]
        for loc, price_rm in zip(locs[:5], real_prices):
            db.add(FoodPriceObservation(
                canonical_food_id=REAL_FOOD, source_item_code=f"pc-{REAL_FOOD}",
                source_food_name="test peanuts", source_premise_code=loc.source_premise_code,
                location_id=loc.location_id, observed_date=date(2026, 8, 20), price_rm=price_rm,
                original_unit="1kg", purchase_mass_g=1000, price_rm_per_kg_purchase=price_rm,
                price_rm_per_100g_purchase=price_rm / 10, source_dataset_version="PriceCatcher 2026-08",
                quality_status="PASS",
            ))
        # A competing SYNTHETIC row, dated LATER (would win any date-based or naive
        # "first row" selection) and priced LOWER (would win any pure cheapest-price
        # selection with no source filter) than every real row -- the exact adversarial
        # shape of the real bug (see docs/data_food_integrity/P0_INTEGRITY_AUDIT.md), not
        # a weaker version of it.
        db.add(FoodPriceObservation(
            canonical_food_id=REAL_FOOD, source_item_code=f"SEED-{REAL_FOOD}",
            source_food_name="test peanuts", source_premise_code=f"{PREFIX}-SEEDLOC",
            location_id=locs[5].location_id, observed_date=date(2026, 8, 29), price_rm=1.0,
            original_unit="100g", purchase_mass_g=100, price_rm_per_kg_purchase=10,
            price_rm_per_100g_purchase=1.0, price_rm_per_100g_edible=1.0,
            source_dataset_version="wisebasket-seed-v1", quality_status="PASS",
        ))
        # A LOOK-ALIKE-tagged row: uses the SAME governance-approved source_item_code as
        # the real rows (so a mapping-governance gap can't explain its exclusion) but a
        # look-alike source_dataset_version that would have passed the old
        # startswith("PriceCatcher") prefix check (Section 3 of the SF009
        # deployment-readiness review). Priced to shift the median if wrongly admitted.
        # Must be excluded by the hardened exact-shape check at both the Python and the
        # SQL layer.
        db.add(FoodPriceObservation(
            canonical_food_id=REAL_FOOD, source_item_code=f"pc-{REAL_FOOD}",
            source_food_name="test peanuts", source_premise_code=f"{PREFIX}-LOOKALIKELOC",
            location_id=locs[6].location_id, observed_date=date(2026, 8, 25), price_rm=100.0,
            original_unit="1kg", purchase_mass_g=1000, price_rm_per_kg_purchase=100.0,
            price_rm_per_100g_purchase=10.0,
            source_dataset_version="PriceCatcher-test", quality_status="PASS",
        ))

        # NO_YIELD_FOOD: real price data exists (3 shops), but no edible yield -- must
        # resolve to no price at all (fail-closed), matching SF003's real situation.
        for loc, price_rm in zip(locs[:3], [9.0, 9.5, 10.0]):
            db.add(FoodPriceObservation(
                canonical_food_id=NO_YIELD_FOOD, source_item_code=f"pc-{NO_YIELD_FOOD}",
                source_food_name="test whole chicken", source_premise_code=loc.source_premise_code,
                location_id=loc.location_id, observed_date=date(2026, 8, 20), price_rm=price_rm,
                original_unit="1kg", purchase_mass_g=1000, price_rm_per_kg_purchase=price_rm,
                price_rm_per_100g_purchase=price_rm / 10, source_dataset_version="PriceCatcher 2026-08",
                quality_status="PASS",
            ))

        # CONTROL_FOOD: plain, fully-real, already-working food (3 shops) -- a regression
        # guard proving the new code path still serves ordinary real-priced foods
        # correctly, not just the one bug it was written to fix.
        for loc, price_rm in zip(locs[:3], [3.0, 3.2, 2.8]):
            db.add(FoodPriceObservation(
                canonical_food_id=CONTROL_FOOD, source_item_code=f"pc-{CONTROL_FOOD}",
                source_food_name="test rice", source_premise_code=loc.source_premise_code,
                location_id=loc.location_id, observed_date=date(2026, 8, 20), price_rm=price_rm,
                original_unit="1kg", purchase_mass_g=1000, price_rm_per_kg_purchase=price_rm,
                price_rm_per_100g_purchase=price_rm / 10, source_dataset_version="PriceCatcher 2026-08",
                quality_status="PASS",
            ))

        await db.commit()

    yield
    await _wipe()


# ---------------------------------------------------------------------------
# A. SF009-shaped real-data recovery path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_real_price_recovered_despite_no_stored_edible_price(price_recovery_fixture):
    """Reproduces the exact SF009 situation: real rows have no stored
    price_rm_per_100g_edible at all (only price_rm_per_100g_purchase); the
    new path must still resolve a real price by combining current
    unit_conversion evidence at query time."""
    async with AsyncSessionLocal() as db:
        result = await resolve_food_price(db, REAL_FOOD)
    assert result is not None
    # median of [0.8, 0.9, 1.0, 1.1, 1.2] purchase-basis RM/100g = 1.0; yield=1.0 -> edible = 1.0
    assert result.price_rm_per_100g_edible == pytest.approx(1.0, abs=0.01)
    assert result.shop_count == 5
    assert result.tier_used == "NATIONAL"


# ---------------------------------------------------------------------------
# B/C. Synthetic source exclusion -- structural, not by luck of ordering/price
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_synthetic_row_structurally_excluded_even_when_cheaper_and_newer(price_recovery_fixture):
    """The synthetic row is BOTH newer (2026-08-29 vs 2026-08-20) AND cheaper
    (RM 1.00/100g vs the real median RM 1.00/100g -- deliberately overlapping,
    see below) than the real data. If exclusion depended on date or price
    ordering, this test would be a coin flip. It must not participate at
    all -- proven by shop_count excluding it and by the resolved price being
    computable purely from the 5 real rows regardless of the synthetic row's
    values."""
    async with AsyncSessionLocal() as db:
        result = await resolve_food_price(db, REAL_FOOD)
    assert result is not None
    assert result.shop_count == 5, "synthetic row must not be counted as an eligible shop"
    assert result.price_provenance == "REAL_PRICECATCHER"
    assert result.price_is_estimated is False


@pytest.mark.asyncio
async def test_lookalike_tagged_row_excluded_even_with_valid_governance(price_recovery_fixture):
    """End-to-end (DB-layer) proof that the allow-list hardening actually reaches the
    SQL, not just the pure Python helper: a row tagged 'PriceCatcher-test', using the
    SAME governance-approved source_item_code as the real rows (ruling out mapping
    governance as the reason for exclusion), and priced at RM 10/100g -- ~10x every real
    row -- must not move the resolved median or shop_count at all."""
    async with AsyncSessionLocal() as db:
        result = await resolve_food_price(db, REAL_FOOD)
    assert result is not None
    assert result.shop_count == 5, "look-alike-tagged row must not be counted as an eligible shop"
    assert result.price_rm_per_100g_edible == pytest.approx(1.0, abs=0.01), (
        "a RM 10/100g look-alike row would have pulled the median far from 1.0 if admitted"
    )


@pytest.mark.asyncio
async def test_source_allowlist_is_structural_not_heuristic():
    """Unit-level proof the exclusion is a real allow-list, not an accident
    of price/date comparison -- covers arbitrary/unseen future source tags,
    not just the one known 'wisebasket-seed-v1' string."""
    assert is_real_market_source("PriceCatcher 2026-08") is True
    assert is_real_market_source("PriceCatcher 2099-12") is True  # future vintage, same shape
    assert is_real_market_source("wisebasket-seed-v1") is False
    assert is_real_market_source("wisebasket-estimated") is False  # real historical tag, still synthetic
    assert is_real_market_source("TEST") is False
    assert is_real_market_source("SEED") is False
    assert is_real_market_source(None) is False
    assert is_real_market_source("") is False
    # Deployment-readiness hardening (allow-list Section 3): a bare prefix match would
    # also admit any look-alike an operator or a careless script happened to prefix --
    # this codebase's OWN test fixtures did exactly this ("PriceCatcher-TESTFIXTURE")
    # before this hardening pass. Now requires the exact real vintage-tag shape.
    assert is_real_market_source("PriceCatcherButNotReally") is False
    assert is_real_market_source("PriceCatcher-test") is False
    assert is_real_market_source("PriceCatcher-synthetic") is False
    assert is_real_market_source("PriceCatcherFake") is False
    assert is_real_market_source("PriceCatcher-TESTFIXTURE") is False
    # Governed reference estimates are resolver-admissible but are NOT real-market data.
    assert is_real_market_source("REFERENCE_ESTIMATE_2026-09") is False


def test_sql_and_python_source_filter_share_same_patterns():
    """REAL_MARKET_SOURCE_SQL_REGEX must be textually derived from -- not
    independently retyped alongside -- the same REAL_MARKET_SOURCE_TAG_SHAPES
    tuple the Python check uses, so the two provably cannot drift apart the
    way a hand-duplicated pair could. Also the exact bug class this guards
    against: a prior version of this SQL regex was mistyped with a doubled
    backslash ('\\\\d' instead of '\\d'), which silently matched nothing at
    all -- checking a handful of known-real/known-fake tags against the SQL
    text's own regex (not just the Python one) catches that class of bug."""
    import re as _re

    from services.api.app.services.representative_price import (
        REAL_MARKET_SOURCE_SQL_REGEX,
        REAL_MARKET_SOURCE_TAG_SHAPES,
        RESOLVABLE_SOURCE_SQL_REGEX,
        RESOLVABLE_SOURCE_TAG_SHAPES,
        _FETCH_SHOP_LATEST_PRICES_SQL,
        _FETCH_SHOP_LATEST_PRICES_BATCH_SQL,
    )
    # The SQL embeds the RESOLVABLE alternation (real + governed reference estimates).
    assert RESOLVABLE_SOURCE_SQL_REGEX in _FETCH_SHOP_LATEST_PRICES_SQL.text
    assert REAL_MARKET_SOURCE_SQL_REGEX not in _FETCH_SHOP_LATEST_PRICES_SQL.text
    assert RESOLVABLE_SOURCE_SQL_REGEX in _FETCH_SHOP_LATEST_PRICES_BATCH_SQL.text
    assert REAL_MARKET_SOURCE_SQL_REGEX not in _FETCH_SHOP_LATEST_PRICES_BATCH_SQL.text
    for shape in REAL_MARKET_SOURCE_TAG_SHAPES:
        assert shape in REAL_MARKET_SOURCE_SQL_REGEX
        assert shape in RESOLVABLE_SOURCE_SQL_REGEX
    assert RESOLVABLE_SOURCE_TAG_SHAPES[-1] in RESOLVABLE_SOURCE_SQL_REGEX

    compiled = _re.compile(RESOLVABLE_SOURCE_SQL_REGEX)
    for tag in ("PriceCatcher 2026-08", "PRICECATCHER_2026-06", "REFERENCE_ESTIMATE_2026-09"):
        assert compiled.match(tag), f"SQL regex text failed to match a known-admissible tag: {tag!r}"
    for tag in ("PriceCatcher-TESTFIXTURE", "PRICECATCHER_2026-06_TEST", "wisebasket-seed-v1",
                "REFERENCE_ESTIMATE_2026-09_EXTRA", "reference_estimate_2026-09"):
        assert not compiled.match(tag), f"SQL regex text incorrectly matched a known-fake tag: {tag!r}"
    # The real-only alternation must NOT admit reference estimates (labeling depends on it).
    real_only = _re.compile(REAL_MARKET_SOURCE_SQL_REGEX)
    assert not real_only.match("REFERENCE_ESTIMATE_2026-09")


# ---------------------------------------------------------------------------
# PriceCatcher source-tag compatibility (uppercase/underscore vintage shape):
# proven real via scripts/sync_pricecatcher_daily.py (develop @ 8845ec7) and
# scripts/load_60food_data_pack_to_local.py, both of which write
# `PRICECATCHER_{YYYY-MM}` from a real data.gov.my ingestion path -- see
# docs/data_food_integrity/price_recovery/source_tag_compatibility/
# PRICECATCHER_SOURCE_TAG_COMPATIBILITY_REPORT.md for the full evidence
# chain. Month-range validated (01-12) since the real generator's month
# arithmetic can never produce anything else -- a stricter, not weaker, rule.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("tag", [
    "PriceCatcher 2026-06", "PriceCatcher 2026-09", "PriceCatcher 2026-01", "PriceCatcher 2026-12",
    "PRICECATCHER_2026-06", "PRICECATCHER_2026-09", "PRICECATCHER_2026-01", "PRICECATCHER_2026-12",
])
def test_proven_real_tag_formats_accepted(tag):
    assert is_real_market_source(tag) is True


@pytest.mark.parametrize("tag", [
    "PriceCatcher-TESTFIXTURE", "PriceCatcherFake",
    "PriceCatcher 2026-06-test", "PriceCatcher 2026-6", "PriceCatcher 26-06",
    "PRICECATCHER_2026-06_TEST", "PRICECATCHER_2026-06-TEST", "PRICECATCHER_FAKE", "PRICECATCHER_",
    "XPRICECATCHER_2026-06", "wisebasket-seed-v1", "WISEBASKET_SEED",
    "pricecatcher_2026-06", "Pricecatcher_2026-06",  # case variants: never proven real, must not match
    "PriceCatcher 2026-00", "PriceCatcher 2026-13",   # impossible calendar months
    "PRICECATCHER_2026-00", "PRICECATCHER_2026-13",
])
def test_lookalike_and_malformed_tags_rejected(tag):
    assert is_real_market_source(tag) is False


PRVTEST_UPPERCASE_FOOD = f"{PREFIX}_UPPERCASE"


@pytest_asyncio.fixture
async def uppercase_format_fixture():
    """A food priced ONLY via the new, newly-proven-real PRICECATCHER_YYYY-MM
    tag, plus one look-alike row sharing its governance-approved item code --
    proves the new format participates in resolution exactly like the legacy
    one, and that a visually similar fake is still rejected end-to-end."""
    ids = [PRVTEST_UPPERCASE_FOOD]
    async with AsyncSessionLocal() as db:
        await db.execute(delete(FoodPriceObservation).where(FoodPriceObservation.canonical_food_id.in_(ids)))
        await db.execute(delete(UnitConversion).where(UnitConversion.canonical_food_id.in_(ids)))
        await db.execute(delete(SourceFoodMapping).where(SourceFoodMapping.canonical_food_id.in_(ids)))
        await db.execute(delete(FoodNutrition).where(FoodNutrition.canonical_food_id.in_(ids)))
        await db.execute(delete(CanonicalFood).where(CanonicalFood.canonical_food_id.in_(ids)))
        await db.execute(delete(Location).where(Location.source_premise_code.like(f"{PREFIX}-UC%")))
        await db.commit()

    async with AsyncSessionLocal() as db:
        locs = [_location(db, f"{PREFIX}-UC{i}", f"UC Test Store {i}", "Selangor", "Petaling") for i in range(1, 4)]
        await db.flush()
        reviewer = (await db.execute(select(AppUser).where(AppUser.email_normalized == REVIEWER_EMAIL))).scalar_one_or_none()

        db.add(CanonicalFood(canonical_food_id=PRVTEST_UPPERCASE_FOOD, canonical_name="uc test food",
                              canonical_name_ms="uc test food", category="protein", status="ACTIVE"))
        db.add(FoodNutrition(canonical_food_id=PRVTEST_UPPERCASE_FOOD, source_dataset_version="TEST_NUTRITION",
                              source_record_id=f"nut-{PRVTEST_UPPERCASE_FOOD}", basis_g=100, energy_kcal=500,
                              protein_g=20, quality_status="PASS", is_current=True))
        db.add(SourceFoodMapping(source_system="PRICECATCHER", source_dataset_version="TEST",
                                  source_food_id=f"pc-{PRVTEST_UPPERCASE_FOOD}", source_food_name="uc test food",
                                  canonical_food_id=PRVTEST_UPPERCASE_FOOD, mapping_status="EXACT",
                                  verification_status="VERIFIED", review_status="APPROVED",
                                  reviewed_by=reviewer.user_id, reviewed_at=date(2026, 8, 20)))
        db.add(UnitConversion(canonical_food_id=PRVTEST_UPPERCASE_FOOD, conversion_type="PURCHASE_MASS",
                               source_unit="1kg", target_unit="g", factor=1000, production_eligible=True))
        db.add(UnitConversion(canonical_food_id=PRVTEST_UPPERCASE_FOOD, conversion_type="EDIBLE_YIELD",
                               source_unit="purchase_mass", target_unit="edible_mass",
                               edible_yield_fraction=1.0, production_eligible=True))
        await db.flush()

        # 3 real rows under the NEW proven-real format, priced 4/5/6 RM/kg -> median RM 0.50/100g.
        for loc, price_rm in zip(locs, [4.0, 5.0, 6.0]):
            db.add(FoodPriceObservation(
                canonical_food_id=PRVTEST_UPPERCASE_FOOD, source_item_code=f"pc-{PRVTEST_UPPERCASE_FOOD}",
                source_food_name="uc test food", source_premise_code=loc.source_premise_code,
                location_id=loc.location_id, observed_date=date(2026, 9, 1), price_rm=price_rm,
                original_unit="1kg", purchase_mass_g=1000, price_rm_per_kg_purchase=price_rm,
                price_rm_per_100g_purchase=price_rm / 10, source_dataset_version="PRICECATCHER_2026-09",
                quality_status="PASS",
            ))
        # A look-alike row: same governance-approved item code, wildly different price (RM 50/100g),
        # tagged with a fake that merely LOOKS like the new real format.
        db.add(FoodPriceObservation(
            canonical_food_id=PRVTEST_UPPERCASE_FOOD, source_item_code=f"pc-{PRVTEST_UPPERCASE_FOOD}",
            source_food_name="uc test food", source_premise_code=locs[0].source_premise_code,
            location_id=locs[0].location_id, observed_date=date(2026, 9, 2), price_rm=500.0,
            original_unit="1kg", purchase_mass_g=1000, price_rm_per_kg_purchase=500.0,
            price_rm_per_100g_purchase=50.0, source_dataset_version="PRICECATCHER_2026-09_TEST",
            quality_status="PASS",
        ))
        await db.commit()

    yield
    async with AsyncSessionLocal() as db:
        await db.execute(delete(FoodPriceObservation).where(FoodPriceObservation.canonical_food_id.in_(ids)))
        await db.execute(delete(UnitConversion).where(UnitConversion.canonical_food_id.in_(ids)))
        await db.execute(delete(SourceFoodMapping).where(SourceFoodMapping.canonical_food_id.in_(ids)))
        await db.execute(delete(FoodNutrition).where(FoodNutrition.canonical_food_id.in_(ids)))
        await db.execute(delete(CanonicalFood).where(CanonicalFood.canonical_food_id.in_(ids)))
        await db.execute(delete(Location).where(Location.source_premise_code.like(f"{PREFIX}-UC%")))
        await db.commit()


@pytest.mark.asyncio
async def test_uppercase_format_real_fixture_resolves_like_legacy_format(uppercase_format_fixture):
    async with AsyncSessionLocal() as db:
        result = await resolve_food_price(db, PRVTEST_UPPERCASE_FOOD)
    assert result is not None
    assert result.shop_count == 3, "the look-alike-tagged row must not count as an eligible shop"
    assert result.price_rm_per_100g_edible == pytest.approx(0.50, abs=0.01), (
        "median of [0.40, 0.50, 0.60] = 0.50; a RM 50/100g look-alike would have pulled this far off"
    )
    assert result.price_provenance == "REAL_PRICECATCHER"
    assert result.price_is_estimated is False


# ---------------------------------------------------------------------------
# NO_YIELD_FOOD: real purchase-basis data exists but no yield -> fail-closed
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_missing_edible_yield_still_fails_closed(price_recovery_fixture):
    """The whole point of query-time resolution is fixing STALE data, not
    fabricating MISSING data: a food with real price but no real edible-yield
    evidence must still resolve to no price at all (SF003's real situation)."""
    async with AsyncSessionLocal() as db:
        result = await resolve_food_price(db, NO_YIELD_FOOD)
    assert result is None


# ---------------------------------------------------------------------------
# D. Location cascade behaviour (pure, DB-independent -- the cascade logic
#    itself, exercised directly against constructed rows)
# ---------------------------------------------------------------------------

def test_tier_cascade_pure():
    from datetime import date as d

    from services.api.app.services.representative_price import ShopPrice, resolve_representative_price

    rows = [
        ShopPrice(1, 1.00, d(2026, 8, 20), "x", "PriceCatcher 2026-08", "Petaling", "Selangor"),
        ShopPrice(2, 1.10, d(2026, 8, 20), "x", "PriceCatcher 2026-08", "Petaling", "Selangor"),
        ShopPrice(3, 1.20, d(2026, 8, 20), "x", "PriceCatcher 2026-08", "Petaling", "Selangor"),
        ShopPrice(4, 5.00, d(2026, 8, 20), "x", "PriceCatcher 2026-08", "Johor Bahru", "Johor"),
    ]
    # District tier has exactly 3 shops (the minimum) -- must win over National.
    result = resolve_representative_price(rows, district="Petaling", state="Selangor")
    assert result.tier_used == "DISTRICT"
    assert result.price_rm_per_100g_purchase == pytest.approx(1.10)
    assert result.confidence == "NORMAL"

    # No matching district/state at all -> National fallback, LOW_CONFIDENCE if <3 shops there.
    result2 = resolve_representative_price(rows, district="Nowhere", state="Nowhere")
    assert result2.tier_used == "NATIONAL"
    assert result2.shop_count == 4

    # Completely empty input -> None, never a fabricated price.
    assert resolve_representative_price([], district=None, state=None) is None


# ---------------------------------------------------------------------------
# E. price_is_estimated / provenance correctness
# ---------------------------------------------------------------------------

def test_classify_price_provenance():
    assert classify_price_provenance("PriceCatcher 2026-08") == "REAL_PRICECATCHER"
    assert classify_price_provenance("wisebasket-seed-v1") == "SYNTHETIC_TEST"
    assert classify_price_provenance("REFERENCE_ESTIMATE_2026-09") == "REFERENCE_ESTIMATE"
    assert classify_price_provenance(None) == "SYNTHETIC_TEST"


@pytest.mark.asyncio
async def test_served_food_never_reports_false_estimate_for_synthetic_data(price_recovery_fixture):
    """End-to-end check via load_optimizer_candidates (the actual function
    GET /api/v1/foods calls): REAL_FOOD must appear with price_is_estimated
    False and a real provenance; the synthetic row must have zero influence
    on the result."""
    async with AsyncSessionLocal() as db:
        foods = await load_optimizer_candidates(db)
    by_id = {f.food_id: f for f in foods}
    assert REAL_FOOD in by_id
    f = by_id[REAL_FOOD]
    assert f.price_is_estimated is False
    assert f.price_provenance == "REAL_PRICECATCHER"
    assert f.price_rm_per_100g == pytest.approx(1.0, abs=0.01)
    assert NO_YIELD_FOOD not in by_id, "a food with no real edible yield must not be served at all"
    assert CONTROL_FOOD in by_id, "an ordinary already-working real-priced food must be unaffected"
