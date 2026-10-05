"""Database contracts for resolving hard-exclusion codes.

These tests cover the shared catalogue boundary used by planner inputs:
active codes resolve to canonical food IDs, zero-mapping codes are safe, and
unknown or inactive codes are rejected. They do not exercise the retired V1
planner.
"""

import asyncio
import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import delete

from services.api.app.db import (
    AsyncSessionLocal,
    CanonicalFood,
    HardExclusion,
    HardExclusionFood,
    engine,
)
from services.api.app.main import _resolve_excluded_food_ids


RUN = uuid.uuid4().hex[:8].upper()
RICE_ID = f"T{RUN}R1"
EGG_ID = f"T{RUN}E1"
MILK_ID = f"T{RUN}M1"
CHICKEN_ID = f"T{RUN}C1"
FOOD_IDS = [RICE_ID, EGG_ID, MILK_ID, CHICKEN_ID]
ZERO_CODE = f"TEST_ZERO_{RUN}"
INACTIVE_CODE = f"TEST_INACTIVE_{RUN}"


def run_db(coro):
    async def runner():
        try:
            return await coro
        finally:
            await engine.dispose()

    return asyncio.run(runner())


async def cleanup_test_rows() -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(
            delete(HardExclusionFood).where(
                HardExclusionFood.canonical_food_id.in_(FOOD_IDS)
            )
        )
        await db.execute(
            delete(HardExclusion).where(
                HardExclusion.exclusion_code.in_([ZERO_CODE, INACTIVE_CODE])
            )
        )
        await db.execute(
            delete(CanonicalFood).where(CanonicalFood.canonical_food_id.in_(FOOD_IDS))
        )
        await db.commit()


async def seed_test_rows() -> None:
    async with AsyncSessionLocal() as db:
        foods = [
            (RICE_ID, "test rice", "carbohydrate"),
            (EGG_ID, "test egg", "protein"),
            (MILK_ID, "test milk", "other"),
            (CHICKEN_ID, "test chicken", "protein"),
        ]
        for food_id, name, category in foods:
            db.add(
                CanonicalFood(
                    canonical_food_id=food_id,
                    canonical_name=name,
                    category=category,
                    status="ACTIVE",
                )
            )

        db.add(HardExclusionFood(exclusion_code="EGGS", canonical_food_id=EGG_ID))
        db.add(HardExclusionFood(exclusion_code="MILK", canonical_food_id=MILK_ID))
        db.add(
            HardExclusionFood(
                exclusion_code="VEGETARIAN",
                canonical_food_id=CHICKEN_ID,
            )
        )
        db.add(
            HardExclusion(
                exclusion_code=ZERO_CODE,
                display_name="Zero-mapping test code",
                active=True,
            )
        )
        db.add(
            HardExclusion(
                exclusion_code=INACTIVE_CODE,
                display_name="Inactive test code",
                active=False,
            )
        )
        await db.commit()


@pytest.fixture(scope="module", autouse=True)
def manage_test_rows():
    run_db(cleanup_test_rows())
    run_db(seed_test_rows())
    yield
    run_db(cleanup_test_rows())


def test_resolver_maps_codes_to_canonical_food_ids():
    async def check():
        async with AsyncSessionLocal() as db:
            # The shared database also carries migration seed mappings, so
            # membership is the stable contract here.
            assert {EGG_ID} <= await _resolve_excluded_food_ids(db, ["EGGS"])
            assert {MILK_ID} <= await _resolve_excluded_food_ids(db, ["MILK"])
            assert {CHICKEN_ID} <= await _resolve_excluded_food_ids(
                db, ["VEGETARIAN"]
            )
            assert {EGG_ID, MILK_ID} <= await _resolve_excluded_food_ids(
                db, [" eggs ", "milk"]
            )

    run_db(check())


def test_zero_mapping_code_is_safe_noop():
    async def check():
        async with AsyncSessionLocal() as db:
            assert await _resolve_excluded_food_ids(db, [ZERO_CODE]) == set()
            combined = await _resolve_excluded_food_ids(db, [ZERO_CODE, "EGGS"])
            assert EGG_ID in combined

    run_db(check())


def test_unknown_code_rejected_explicitly():
    async def check():
        async with AsyncSessionLocal() as db:
            with pytest.raises(HTTPException) as exc_info:
                await _resolve_excluded_food_ids(db, [f"NOPE_{RUN}"])
            assert exc_info.value.status_code == 422
            assert f"NOPE_{RUN}" in str(exc_info.value.detail)

    run_db(check())


def test_inactive_code_rejected_explicitly():
    async def check():
        async with AsyncSessionLocal() as db:
            with pytest.raises(HTTPException) as exc_info:
                await _resolve_excluded_food_ids(db, [INACTIVE_CODE])
            assert exc_info.value.status_code == 422

    run_db(check())
