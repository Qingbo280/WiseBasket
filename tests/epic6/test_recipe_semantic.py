# Epic 6 semantic recipe recall tests (use_semantic query param).
from __future__ import annotations

import asyncio
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from services.api.app.db import (
    AppUser,
    AsyncSessionLocal,
    FoodEmbedding,
    Household,
    RecipeCatalog,
    RecipeCatalogIngredient,
    RecipeCookingStep,
    engine,
)
from services.api.app.main import app


client = TestClient(app)
run_id = uuid.uuid4().hex[:8]
test_emails: set[str] = set()
TEST_RECIPE_IDS = ["TSEM-1", "TSEM-2"]
TEST_FOOD_IDS = ["SEED001", "SEED002", "SEED003"]


def run_database(coroutine):
    async def runner():
        try:
            return await coroutine
        finally:
            await engine.dispose()

    return asyncio.run(runner())


def create_authenticated_household(scenario_name: str) -> tuple[dict[str, str], int]:
    email = f"epic6-semantic-{run_id}-{scenario_name}@example.com"
    test_emails.add(email)
    registration = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "CorrectHorse123!"},
    )
    assert registration.status_code == 200, registration.text
    headers = {"Authorization": f"Bearer {registration.json()['access_token']}"}
    household = client.post(
        "/api/v1/households",
        headers=headers,
        json={"name": "Epic 6 semantic household", "adults": 1, "children": 0},
    )
    assert household.status_code == 200, household.text
    return headers, household.json()["id"]


@pytest.fixture(scope="module", autouse=True)
def remove_semantic_test_data():
    yield

    async def cleanup():
        async with AsyncSessionLocal() as db:
            users = (
                await db.execute(select(AppUser).where(AppUser.email_normalized.in_(test_emails)))
            ).scalars().all()
            user_ids = [user.user_id for user in users]
            if user_ids:
                await db.execute(delete(Household).where(Household.owner_user_id.in_(user_ids)))
                await db.execute(delete(AppUser).where(AppUser.user_id.in_(user_ids)))
            await db.execute(
                delete(RecipeCookingStep).where(RecipeCookingStep.recipe_id.in_(TEST_RECIPE_IDS))
            )
            await db.execute(
                delete(RecipeCatalogIngredient).where(
                    RecipeCatalogIngredient.recipe_id.in_(TEST_RECIPE_IDS)
                )
            )
            await db.execute(delete(RecipeCatalog).where(RecipeCatalog.recipe_id.in_(TEST_RECIPE_IDS)))
            await db.execute(
                delete(FoodEmbedding).where(FoodEmbedding.canonical_food_id.in_(TEST_FOOD_IDS))
            )
            await db.commit()

    run_database(cleanup())


@pytest.fixture(scope="module", autouse=True)
def seed_embeddings_and_recipes():
    """Pantry food SEED001; ingredient SEED002 is its near-twin, SEED003 orthogonal."""

    async def seed():
        async with AsyncSessionLocal() as db:
            for food_id, vector in (
                ("SEED001", [1.0] * 8),            # pantry item
                ("SEED002", [1.0] * 8),            # cos == 1.0 with SEED001
                ("SEED003", [1.0, 0, 0, 0, 0, 0, 0, 0]),  # cos ~0.35 with SEED001
            ):
                db.add(FoodEmbedding(canonical_food_id=food_id, embedding=vector, model="test", dim=8))
            db.add(RecipeCatalog(recipe_id="TSEM-1", name="Test Semantic Twin", active=True))
            # The pantry food itself is also an ingredient so the recipe keeps
            # a real main-ingredient match: the zero-main product filter hides
            # recipes whose only pantry link is a semantic twin.
            db.add(
                RecipeCatalogIngredient(
                    recipe_id="TSEM-1", canonical_food_id="SEED001", required=True, display_order=1
                )
            )
            db.add(
                RecipeCatalogIngredient(
                    recipe_id="TSEM-1", canonical_food_id="SEED002", required=True, display_order=2
                )
            )
            db.add(RecipeCatalog(recipe_id="TSEM-2", name="Test Semantic Orthogonal", active=True))
            db.add(
                RecipeCatalogIngredient(
                    recipe_id="TSEM-2", canonical_food_id="SEED003", required=True, display_order=1
                )
            )
            await db.commit()

    run_database(seed())


def setup_confirmed_pantry(scenario_name: str) -> tuple[dict[str, str], int]:
    headers, household_id = create_authenticated_household(scenario_name)
    added = client.post(
        f"/api/v1/households/{household_id}/pantry-items",
        headers=headers,
        json={"canonical_food_id": "SEED001"},
    )
    assert added.status_code == 201, added.text
    confirmed = client.post(
        f"/api/v1/households/{household_id}/pantry-confirmations", headers=headers
    )
    assert confirmed.status_code == 200, confirmed.text
    return headers, household_id


def suggestion_map(headers, household_id, use_semantic):
    params = {"use_semantic": "true"} if use_semantic else {}
    response = client.get(
        f"/api/v1/households/{household_id}/recipe-suggestions",
        headers=headers,
        params=params,
    )
    assert response.status_code == 200, response.text
    return {item["recipe_id"]: item for item in response.json()}


def test_semantic_recall_surfaces_similar_ingredient_recipe():
    headers, household_id = setup_confirmed_pantry("similar")

    with_semantics = suggestion_map(headers, household_id, use_semantic=True)
    assert "TSEM-1" in with_semantics
    assert with_semantics["TSEM-1"]["semantic_score"] is not None
    assert with_semantics["TSEM-1"]["semantic_score"] >= 0.55
    # All-visible rule: every eligible recipe is listed again (the #264
    # zero-main filter was removed). Semantic recall only affects scoring —
    # an orthogonal ingredient still must not qualify as a recall bridge.
    assert "TSEM-2" in with_semantics
    assert with_semantics["TSEM-2"]["semantic_score"] is None or (
        with_semantics["TSEM-2"]["semantic_score"] < 0.55
    )

    without_semantics = suggestion_map(headers, household_id, use_semantic=False)
    assert "TSEM-1" in without_semantics
    assert without_semantics["TSEM-1"]["semantic_score"] is None


def test_semantic_score_absent_when_not_requested():
    headers, household_id = setup_confirmed_pantry("absent")
    suggestions = suggestion_map(headers, household_id, use_semantic=False)
    for suggestion in suggestions.values():
        assert suggestion["semantic_score"] is None
