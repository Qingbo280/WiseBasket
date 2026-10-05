"""Shared standard candidate seed for API-level tests (monorepo).

The serving paths read foods live from PostgreSQL, so API tests need a
trusted candidate set in the view `v_optimizer_food_candidate`. This module
seeds a fixed, idempotent set (SEED001-SEED012) with the full trust chain
(canonical_food -> nutrition PASS/current -> APPROVED+VERIFIED mapping ->
PURCHASE_MASS unit conversion -> PASS price observation at a test location)
plus hard-exclusion mappings for the restriction tests:

  SEED002 egg     -> EGGS
  SEED003 chicken -> VEGETARIAN
  SEED007 milk    -> MILK
  SEED008 peanuts -> PEANUTS

cleanup-then-insert by the fixed SEED prefix makes reseeding idempotent.
"""
from __future__ import annotations

import asyncio
from datetime import date

from sqlalchemy import delete, select, update

from services.api.app.db import (
    AppUser,
    AsyncSessionLocal,
    CanonicalFood,
    FoodAlias,
    FoodNutrition,
    FoodPriceObservation,
    GeneratedPlan,
    GeneratedPlanItem,
    HardExclusionFood,
    Location,
    PantryItem,
    PlanStoreItem,
    PlanStoreOption,
    SourceFoodMapping,
    UnitConversion,
    engine,
)

SEED_LOCATION_CODE = "SEEDLOC1"
SEED_LOCATION_CODE_2 = "SEEDLOC2"
SEED_REVIEWER_EMAIL = "seed-reviewer@wisebasket.test"

# (food_id, name, name_ms, category, pack_g, kcal, protein, fibre, iron,
#  calcium, vitA, vitC, price_rm_per_100g)
SEED_FOODS = [
    ("SEED001", "seed rice", "beras benih", "carbohydrate", 1000, 360, 7, 1, 1, 10, 0, 0, 0.30),
    ("SEED002", "seed egg", "telur benih", "protein", 550, 155, 13, 0, 2, 56, 160, 0, 0.85),
    ("SEED003", "seed chicken", "ayam benih", "protein", 1200, 215, 19, 0, 1, 12, 41, 0, 0.90),
    ("SEED004", "seed lentils", "dhal benih", "protein", 500, 352, 25, 11, 8, 51, 0, 2, 0.75),
    ("SEED005", "seed spinach", "bayam benih", "vegetables", 250, 23, 3, 2, 3, 99, 469, 28, 0.70),
    ("SEED006", "seed banana", "pisang benih", "fruit", 600, 89, 1, 3, 0, 5, 3, 9, 0.55),
    ("SEED007", "seed milk", "susu benih", "other", 1000, 61, 3, 0, 0, 113, 46, 0, 0.70),
    ("SEED008", "seed peanuts", "kacang benih", "protein", 500, 567, 26, 9, 5, 92, 0, 0, 1.50),
    ("SEED009", "seed oil", "minyak benih", "other", 1000, 884, 0, 0, 0, 0, 0, 0, 0.30),
    # Option A consumption caps (2026-09-04): the seed world above is
    # calorie-poor (realistic densities), so no household can reach the
    # energy target within the H5 category budgets. Energy-dense, realistic
    # additions keep the fixture solvable: SEED010/SEED011 cover 1A/7d, and
    # SEED012 (fruit category, which has headroom left) covers the larger
    # personas used by the API tests (2A3C/4d needs ~32,800 kcal).
    ("SEED010", "seed instant noodles", "mee segera benih", "carbohydrate", 100, 470, 8, 1, 1, 20, 0, 0, 0.45),
    ("SEED011", "seed milk powder", "susu tepung benih", "other", 250, 500, 26, 0, 1, 950, 300, 6, 1.10),
    ("SEED012", "seed raisins", "kismis benih", "fruit", 250, 299, 3, 3, 2, 59, 0, 3, 0.80),
    # 2026-09-11 realism guards (other-headroom 1.2 + 20% empty-calorie cap)
    # removed the seed oil calorie crutch; SEED013 restores energy headroom in
    # the carbohydrate category (bread ~280 kcal/100 g, realistic density).
    ("SEED013", "seed bread", "roti benih", "carbohydrate", 400, 280, 9, 2, 1, 60, 0, 0, 0.60),
]

SEED_EXCLUSION_MAPPINGS = {
    "EGGS": "SEED002",
    "VEGETARIAN": "SEED003",
    "MILK": "SEED007",
    "PEANUTS": "SEED008",
}


def run_db(coro):
    async def runner():
        try:
            return await coro
        finally:
            await engine.dispose()

    return asyncio.run(runner())


async def _delete_seed_rows(db) -> None:
    """Wipe any previous seed (cascades nothing outside SEED ids).

    Historical persisted plans may reference seed foods/prices
    (plan_store_item.price_observation_id and both item tables'
    canonical_food_id FKs have no cascade) - unlink them first.
    """
    seed_ids = [row[0] for row in SEED_FOODS]
    await db.execute(
        delete(GeneratedPlanItem).where(
            GeneratedPlanItem.canonical_food_id.in_(seed_ids)
        )
    )
    await db.execute(
        delete(PlanStoreItem).where(PlanStoreItem.canonical_food_id.in_(seed_ids))
    )
    location_ids = (
        await db.execute(
            delete(FoodPriceObservation)
            .where(FoodPriceObservation.canonical_food_id.in_(seed_ids))
            .returning(FoodPriceObservation.location_id)
        )
    ).scalars().all()
    await db.execute(
        delete(HardExclusionFood).where(
            HardExclusionFood.canonical_food_id.in_(seed_ids)
        )
    )
    # Epic 5 pantry rows have no ON DELETE CASCADE (see migration note):
    # unlink them before the canonical_food delete or reseeding errors with
    # a pantry_item FK violation after any pantry test ran in the session.
    await db.execute(
        delete(PantryItem).where(PantryItem.canonical_food_id.in_(seed_ids))
    )
    await db.execute(
        delete(UnitConversion).where(UnitConversion.canonical_food_id.in_(seed_ids))
    )
    await db.execute(
        delete(SourceFoodMapping).where(
            SourceFoodMapping.canonical_food_id.in_(seed_ids)
        )
    )
    await db.execute(
        delete(FoodNutrition).where(FoodNutrition.canonical_food_id.in_(seed_ids))
    )
    await db.execute(
        delete(FoodAlias).where(FoodAlias.canonical_food_id.in_(seed_ids))
    )
    await db.execute(
        delete(CanonicalFood).where(CanonicalFood.canonical_food_id.in_(seed_ids))
    )
    # Options from previous reseeds still reference seed locations
    # (cascades to their items) - unlink before deleting any location.
    # 2026-09-14: generated_plan.selected_store_option_id has an FK with no
    # cascade into the plan table - plans that picked one of these options
    # (any FEASIBLE persisted plan) must be unlinked first, same pattern as
    # test_db_backed_planner_integration._cleanup. Latent until the
    # universal 1000 g floor reshaped a persona into actually selecting a
    # seed store option.
    seed_loc_ids = select(Location.location_id).where(
        Location.source_premise_code.like("SEEDLOC%")
    )
    await db.execute(
        update(GeneratedPlan)
        .where(
            GeneratedPlan.selected_store_option_id.in_(
                select(PlanStoreOption.plan_store_option_id).where(
                    PlanStoreOption.location_id.in_(seed_loc_ids)
                )
            )
        )
        .values(selected_store_option_id=None)
    )
    await db.execute(
        delete(PlanStoreOption).where(
            PlanStoreOption.location_id.in_(seed_loc_ids)
        )
    )
    if location_ids:
        await db.execute(
            delete(PlanStoreOption).where(
                PlanStoreOption.location_id.in_(location_ids)
            )
        )
        await db.execute(delete(Location).where(Location.location_id.in_(location_ids)))
    await db.execute(
        delete(Location).where(Location.source_premise_code.like("SEEDLOC%"))
    )


async def seed_standard_candidates() -> None:
    async with AsyncSessionLocal() as db:
        # Idempotent: cleanup-then-insert by the fixed SEED prefix.
        await _delete_seed_rows(db)

        reviewer = (
            await db.execute(
                select(AppUser).where(AppUser.email_normalized == SEED_REVIEWER_EMAIL)
            )
        ).scalar_one_or_none()
        if reviewer is None:
            reviewer = AppUser(
                email=SEED_REVIEWER_EMAIL,
                email_normalized=SEED_REVIEWER_EMAIL,
                password_hash="seed-not-a-login",
                role="ADMIN",
                status="ACTIVE",
                email_verified=True,
            )
            db.add(reviewer)
            await db.flush()

        location = Location(
            source_premise_code=SEED_LOCATION_CODE,
            location_name="Seed premise",
            premise_type="TEST",
            state="Selangor",
            district="Petaling",
            latitude=3.1391,
            longitude=101.6870,
            active=True,
        )
        db.add(location)
        await db.flush()

        for (fid, name, name_ms, category, pack_g, kcal, protein, fibre,
             iron, calcium, vita, vitc, price) in SEED_FOODS:
            db.add(CanonicalFood(
                canonical_food_id=fid, canonical_name=name,
                canonical_name_ms=name_ms, category=category, status="ACTIVE",
            ))
            db.add(FoodNutrition(
                canonical_food_id=fid,
                source_dataset_version="seed-nutrition",
                source_record_id=f"nut-{fid}",
                basis_g=100,
                energy_kcal=kcal, protein_g=protein, fibre_g=fibre,
                iron_mg=iron, calcium_mg=calcium,
                vitamin_a_ug=vita, vitamin_c_mg=vitc,
                quality_status="PASS", is_current=True,
            ))
            db.add(SourceFoodMapping(
                source_system="TEST",
                source_dataset_version="seed-mapping",
                source_food_id=f"src-{fid}",
                source_food_name=name,
                canonical_food_id=fid,
                mapping_status="EXACT",
                verification_status="VERIFIED",
                review_status="APPROVED",
                reviewed_by=reviewer.user_id,
                reviewed_at=date(2026, 8, 20),
            ))
            # PRICECATCHER-system mapping rows, one per price-observation source_item_code
            # (SEED-L1-*/SEED-L2-*) -- representative_price.py's fetch_shop_latest_prices()
            # joins food_price_observation.source_item_code against exactly this
            # (source_system='PRICECATCHER', source_food_id) pair for per-item governance,
            # matching the real production join shape (see that module's own docstring).
            db.add(SourceFoodMapping(
                source_system="PRICECATCHER",
                source_dataset_version="seed-mapping",
                source_food_id=f"SEED-L1-{fid}",
                source_food_name=name,
                canonical_food_id=fid,
                mapping_status="EXACT",
                verification_status="VERIFIED",
                review_status="APPROVED",
                reviewed_by=reviewer.user_id,
                reviewed_at=date(2026, 8, 20),
            ))
            if fid in ("SEED001", "SEED004", "SEED009"):
                db.add(SourceFoodMapping(
                    source_system="PRICECATCHER",
                    source_dataset_version="seed-mapping",
                    source_food_id=f"SEED-L2-{fid}",
                    source_food_name=name,
                    canonical_food_id=fid,
                    mapping_status="EXACT",
                    verification_status="VERIFIED",
                    review_status="APPROVED",
                    reviewed_by=reviewer.user_id,
                    reviewed_at=date(2026, 8, 20),
                ))
            db.add(UnitConversion(
                canonical_food_id=fid,
                conversion_type="PURCHASE_MASS",
                source_unit=f"{pack_g} g seed pack",
                target_unit="g",
                factor=pack_g,
                production_eligible=True,
            ))
            # EDIBLE_YIELD=1.0: this fixture models a "fully trusted, real-shaped" food for
            # tests that are not themselves about edible-yield/price-recovery behaviour (see
            # tests/test_representative_price_recovery.py for tests of that behaviour itself,
            # which use their own dedicated PRVTEST fixture instead of this shared one).
            db.add(UnitConversion(
                canonical_food_id=fid,
                conversion_type="EDIBLE_YIELD",
                source_unit="purchase_mass",
                target_unit="edible_mass",
                edible_yield_fraction=1.0,
                production_eligible=True,
            ))
            db.add(FoodPriceObservation(
                canonical_food_id=fid,
                source_item_code=f"SEED-L1-{fid}",
                source_food_name=name,
                source_premise_code=SEED_LOCATION_CODE,
                location_id=location.location_id,
                observed_date=date(2026, 8, 20),
                price_rm=price * 10,
                original_unit="100g",
                purchase_mass_g=pack_g,
                price_rm_per_100g_purchase=price,
                price_rm_per_100g_edible=price,
                # "PriceCatcher"-prefixed so this fixture's price is recognised as real,
                # governance-eligible market data by representative_price.py's structural
                # allow-list -- see that module's own docstring and
                # docs/data_food_integrity/price_recovery/ for why a generic "seed-prices"
                # tag is (correctly) no longer eligible for the live serving path.
                source_dataset_version="PriceCatcher 2026-08",
                quality_status="PASS",
            ))

        for code, fid in SEED_EXCLUSION_MAPPINGS.items():
            db.add(HardExclusionFood(exclusion_code=code, canonical_food_id=fid))

        # Second seed store with PARTIAL coverage (cheaper where priced) so
        # store-comparison tests can check coverage ranking honestly.
        location2 = Location(
            source_premise_code=SEED_LOCATION_CODE_2,
            location_name="Seed premise 2",
            premise_type="TEST",
            state="Selangor",
            district="Petaling",
            latitude=3.1500,
            longitude=101.7000,
            active=True,
        )
        db.add(location2)
        await db.flush()
        partial_prices = {"SEED001": 0.28, "SEED004": 0.70, "SEED009": 0.28}
        for (fid, name, name_ms, category, pack_g, kcal, protein, fibre,
             iron, calcium, vita, vitc, price) in SEED_FOODS:
            if fid not in partial_prices:
                continue
            db.add(FoodPriceObservation(
                canonical_food_id=fid,
                source_item_code=f"SEED-L2-{fid}",
                source_food_name=name,
                source_premise_code=SEED_LOCATION_CODE_2,
                location_id=location2.location_id,
                observed_date=date(2026, 8, 21),
                price_rm=partial_prices[fid] * 10,
                original_unit="100g",
                purchase_mass_g=pack_g,
                price_rm_per_100g_purchase=partial_prices[fid],
                price_rm_per_100g_edible=partial_prices[fid],
                source_dataset_version="PriceCatcher 2026-08",
                quality_status="PASS",
            ))

        await db.commit()


async def cleanup_standard_candidates() -> None:
    """Remove every seed row (session teardown).

    The local docker PostgreSQL doubles as the manual web-testing database;
    leaving SEED foods/locations behind would surface fake "Seed premise"
    stores and seed foods in the served API. Tests re-seed at session start,
    so tearing down here is always safe.
    """
    async with AsyncSessionLocal() as db:
        await _delete_seed_rows(db)
        # NOTE: the seed reviewer user is deliberately left in place. Older
        # reference-data rows can reference it via source_food_mapping.reviewed_by;
        # deleting the user would violate that FK. It is an internal ADMIN row
        # that never surfaces in the served API, so leaving it is harmless.
        await db.commit()
