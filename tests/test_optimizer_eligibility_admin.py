from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, date, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select, text

from services.api.app.db import (
    AppUser,
    AsyncSessionLocal,
    CanonicalFood,
    FoodNutrition,
    FoodPriceObservation,
    Location,
    SourceFoodMapping,
    UnitConversion,
    engine,
)
from services.api.app.main import app
from services.api.app.security import create_access_token, hash_password
from services.api.app.services.optimizer_eligibility_service import list_optimizer_eligibility


client = TestClient(app)
RUN = uuid.uuid4().hex[:8].upper()
ELIGIBLE_ID = f"E{RUN}OK"
REJECTED_ID = f"E{RUN}RJ"
BLOCKED_NUTRITION_ID = f"E{RUN}NB"
MISSING_PRICE_ID = f"E{RUN}MP"
FOOD_IDS = [ELIGIBLE_ID, REJECTED_ID, BLOCKED_NUTRITION_ID, MISSING_PRICE_ID]


def _run_db(coro):
    async def runner():
        try:
            return await coro
        finally:
            await engine.dispose()

    return asyncio.run(runner())


async def _cleanup() -> None:
    async with AsyncSessionLocal() as db:
        location_ids = (
            await db.execute(select(Location.location_id).where(Location.source_premise_code == f"ELIG-{RUN}"))
        ).scalars().all()
        if location_ids:
            await db.execute(delete(FoodPriceObservation).where(FoodPriceObservation.location_id.in_(location_ids)))
        await db.execute(delete(UnitConversion).where(UnitConversion.canonical_food_id.in_(FOOD_IDS)))
        await db.execute(delete(SourceFoodMapping).where(SourceFoodMapping.canonical_food_id.in_(FOOD_IDS)))
        await db.execute(delete(FoodNutrition).where(FoodNutrition.canonical_food_id.in_(FOOD_IDS)))
        await db.execute(delete(CanonicalFood).where(CanonicalFood.canonical_food_id.in_(FOOD_IDS)))
        await db.execute(delete(AppUser).where(AppUser.email.like(f"%{RUN.lower()}%@example.com")))
        if location_ids:
            await db.execute(delete(Location).where(Location.location_id.in_(location_ids)))
        await db.commit()


async def _seed() -> tuple[str, str]:
    async with AsyncSessionLocal() as db:
        admin = AppUser(
            email=f"admin-{RUN.lower()}@example.com",
            email_normalized=f"admin-{RUN.lower()}@example.com",
            password_hash=hash_password("CorrectHorse123!"),
            role="ADMIN",
            status="ACTIVE",
            email_verified=True,
        )
        user = AppUser(
            email=f"user-{RUN.lower()}@example.com",
            email_normalized=f"user-{RUN.lower()}@example.com",
            password_hash=hash_password("CorrectHorse123!"),
            role="USER",
            status="ACTIVE",
            email_verified=True,
        )
        db.add_all([admin, user])
        await db.flush()
        location = Location(source_premise_code=f"ELIG-{RUN}", location_name="Eligibility Store", active=True)
        db.add(location)
        await db.flush()

        cases = [
            (ELIGIBLE_ID, "eligible test", "APPROVED", "VERIFIED", "EXACT", "PASS", True),
            (REJECTED_ID, "rejected mapping test", "REJECTED", "REJECTED", "EXCLUDED", "PASS", True),
            (BLOCKED_NUTRITION_ID, "blocked nutrition test", "APPROVED", "VERIFIED", "EXACT", "BLOCK", True),
            (MISSING_PRICE_ID, "missing price test", "APPROVED", "VERIFIED", "EXACT", "PASS", False),
        ]
        for food_id, name, review, verification, mapping, nutrition_quality, has_price in cases:
            db.add(CanonicalFood(canonical_food_id=food_id, canonical_name=name, category="test", status="ACTIVE"))
            db.add(
                SourceFoodMapping(
                    source_system="TEST",
                    source_dataset_version=f"elig-map-{RUN}",
                    source_food_id=f"src-{food_id}",
                    source_food_name=name,
                    canonical_food_id=food_id,
                    mapping_status=mapping,
                    verification_status=verification,
                    review_status=review,
                    reviewed_by=admin.user_id if review == "APPROVED" else None,
                    reviewed_at=datetime.now(UTC) if review == "APPROVED" else None,
                )
            )
            db.add(
                FoodNutrition(
                    canonical_food_id=food_id,
                    source_dataset_version=f"elig-nut-{RUN}",
                    source_record_id=f"nut-{food_id}",
                    basis_g=100,
                    energy_kcal=300,
                    protein_g=10,
                    quality_status=nutrition_quality,
                    is_current=True,
                )
            )
            db.add(
                UnitConversion(
                    canonical_food_id=food_id,
                    conversion_type="PURCHASE_MASS",
                    source_unit="100 g",
                    target_unit="g",
                    factor=100,
                    production_eligible=True,
                )
            )
            if has_price:
                db.add(
                    FoodPriceObservation(
                        canonical_food_id=food_id,
                        source_item_code=f"elig-{RUN}-{food_id}",
                        source_food_name=name,
                        source_premise_code=location.source_premise_code,
                        location_id=location.location_id,
                        observed_date=date(2026, 8, 28),
                        price_rm=1,
                        original_unit="100g",
                        purchase_mass_g=100,
                        price_rm_per_100g_edible=1,
                        source_dataset_version=f"elig-price-{RUN}",
                        quality_status="PASS",
                    )
                )
        await db.commit()
        return create_access_token(admin), create_access_token(user)


@pytest.fixture(scope="module")
def seeded_tokens():
    _run_db(_cleanup())
    tokens = _run_db(_seed())
    yield tokens
    _run_db(_cleanup())


def test_user_cannot_access_optimizer_eligibility(seeded_tokens):
    _, user_token = seeded_tokens
    response = client.get("/api/v1/admin/optimizer-eligibility", headers={"Authorization": f"Bearer {user_token}"})
    _run_db(engine.dispose())
    assert response.status_code == 403


def test_admin_can_access_optimizer_eligibility(seeded_tokens):
    admin_token, _ = seeded_tokens
    response = client.get("/api/v1/admin/optimizer-eligibility", headers={"Authorization": f"Bearer {admin_token}"})
    _run_db(engine.dispose())
    assert response.status_code == 200


def test_optimizer_eligibility_checks_and_view_match(seeded_tokens):
    async def check():
        async with AsyncSessionLocal() as db:
            diagnostics = {
                item["canonical_food_id"]: item
                for item in await list_optimizer_eligibility(db, category="test", search=RUN)
            }
            view_ids = {
                row[0]
                for row in (
                    await db.execute(text("select distinct canonical_food_id from v_optimizer_food_candidate where canonical_food_id = any(:ids)"), {"ids": FOOD_IDS})
                ).all()
            }
            return diagnostics, view_ids

    diagnostics, view_ids = _run_db(check())
    assert diagnostics[ELIGIBLE_ID]["eligible"] is True
    assert diagnostics[REJECTED_ID]["eligible"] is False
    assert "SOURCE_MAPPING_REJECTED" in diagnostics[REJECTED_ID]["reasons"]
    assert diagnostics[BLOCKED_NUTRITION_ID]["eligible"] is False
    assert "NUTRITION_BLOCKED" in diagnostics[BLOCKED_NUTRITION_ID]["reasons"]
    assert diagnostics[MISSING_PRICE_ID]["eligible"] is False
    assert "PRICE_MISSING" in diagnostics[MISSING_PRICE_ID]["reasons"]
    assert {food_id for food_id, item in diagnostics.items() if item["eligible"]} == view_ids == {ELIGIBLE_ID}
