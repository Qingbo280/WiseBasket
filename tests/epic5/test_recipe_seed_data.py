# Epic 5 recipe catalogue semantic guards and dietary-exclusion filtering tests.
#
# The guard tests pin the curated recipe fixture data to real 201-namespace
# food identities. This is a regression lock for the old-72-ID trap: the
# previous seed mapped "egg fried rice" to SF002 (beef) because the old and
# current ID spaces collide on the same SF prefixes. The recipes are test-owned
# fixtures (tests/epic5/conftest.py) since migration o7p8q9r0s1t2 removed them
# from the production catalogue.
from __future__ import annotations

import asyncio
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from services.api.app.db import (
    AppUser,
    AsyncSessionLocal,
    CanonicalFood,
    Household,
    RecipeCatalog,
    RecipeCatalogIngredient,
    RecipeCookingStep,
    engine,
)
from services.api.app.main import app


client = TestClient(app)
pytestmark = pytest.mark.usefixtures("curated_recipes")
run_id = uuid.uuid4().hex[:8]
test_emails: set[str] = set()

EXPECTED_REQUIRED_INGREDIENTS = {
    "chicken-kangkung-stir-fry": {"SF006", "SF074", "SF110"},  # whole chicken, water spinach, rice
    "egg-fried-rice": {"SF018", "SF110"},  # chicken egg, rice
    "tofu-kangkung-stir-fry": {"SF107", "SF074"},  # tofu, water spinach
}

TEMP_PORK_RECIPE_ID = f"epic5-test-pork-recipe-{run_id}"


def run_database(coroutine):
    async def runner():
        try:
            return await coroutine
        finally:
            await engine.dispose()

    return asyncio.run(runner())


def create_authenticated_household(scenario_name: str) -> tuple[dict[str, str], int]:
    email = f"epic5-recipe-{run_id}-{scenario_name}@example.com"
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
        json={"name": "Epic 5 recipe test household", "adults": 1, "children": 0},
    )
    assert household.status_code == 200, household.text
    return headers, household.json()["id"]


async def load_recipe_ingredients():
    async with AsyncSessionLocal() as db:
        recipes = (
            await db.scalars(select(RecipeCatalog).where(RecipeCatalog.active.is_(True)).order_by(RecipeCatalog.recipe_id))
        ).all()
        assert recipes, "Epic 5 recipe catalogue seed data is missing."
        data = {}
        for recipe in recipes:
            rows = (
                await db.execute(
                    select(RecipeCatalogIngredient, CanonicalFood)
                    .join(CanonicalFood, CanonicalFood.canonical_food_id == RecipeCatalogIngredient.canonical_food_id)
                    .where(RecipeCatalogIngredient.recipe_id == recipe.recipe_id)
                    .order_by(RecipeCatalogIngredient.display_order)
                )
            ).all()
            steps = (
                await db.scalars(
                    select(RecipeCookingStep.step_number)
                    .where(RecipeCookingStep.recipe_id == recipe.recipe_id)
                    .order_by(RecipeCookingStep.step_number)
                )
            ).all()
            data[recipe.recipe_id] = {"rows": rows, "steps": list(steps)}
        return data


@pytest.fixture(scope="module", autouse=True)
def seed_guard_cleanup():
    yield

    async def cleanup():
        async with AsyncSessionLocal() as db:
            users = (
                await db.execute(
                    select(AppUser).where(AppUser.email_normalized.in_(test_emails))
                )
            ).scalars().all()
            user_ids = [user.user_id for user in users]
            if user_ids:
                await db.execute(delete(Household).where(Household.owner_user_id.in_(user_ids)))
                await db.execute(delete(AppUser).where(AppUser.user_id.in_(user_ids)))
            await db.execute(delete(RecipeCookingStep).where(RecipeCookingStep.recipe_id == TEMP_PORK_RECIPE_ID))
            await db.execute(
                delete(RecipeCatalogIngredient).where(RecipeCatalogIngredient.recipe_id == TEMP_PORK_RECIPE_ID)
            )
            await db.execute(delete(RecipeCatalog).where(RecipeCatalog.recipe_id == TEMP_PORK_RECIPE_ID))
            await db.commit()

    run_database(cleanup())


def test_seeded_recipes_have_expected_required_ingredients():
    # Semantic guard: the seeded recipe ingredients must be the real foods the
    # recipe names describe, in the current 201-namespace ID space.
    data = run_database(load_recipe_ingredients())

    assert set(EXPECTED_REQUIRED_INGREDIENTS).issubset(set(data)), (
        f"Missing seeded recipes: {set(EXPECTED_REQUIRED_INGREDIENTS) - set(data)}"
    )
    for recipe_id, expected_ids in EXPECTED_REQUIRED_INGREDIENTS.items():
        required_ids = {
            ingredient.canonical_food_id
            for ingredient, _ in data[recipe_id]["rows"]
            if ingredient.required
        }
        assert required_ids == expected_ids, (
            f"{recipe_id} required ingredients {sorted(required_ids)} != expected {sorted(expected_ids)}"
        )


def test_seeded_recipe_ingredients_reference_active_foods():
    # Every seeded ingredient must resolve to an ACTIVE canonical food; a stale
    # or typo'd food id would surface here as a missing/RETIRED join row.
    data = run_database(load_recipe_ingredients())

    for recipe_id, payload in data.items():
        rows = payload["rows"]
        assert rows, f"{recipe_id} has no ingredients."
        for ingredient, food in rows:
            assert food.status == "ACTIVE", (
                f"{recipe_id} ingredient {ingredient.canonical_food_id} is not ACTIVE "
                f"(name={food.canonical_name!r}, status={food.status!r})"
            )


def test_seeded_recipes_have_sequential_steps_and_display_order():
    data = run_database(load_recipe_ingredients())

    for recipe_id, payload in data.items():
        steps = payload["steps"]
        assert steps, f"{recipe_id} has no cooking steps."
        assert steps == list(range(1, len(steps) + 1)), f"{recipe_id} step numbers are not sequential: {steps}"
        orders = [ingredient.display_order for ingredient, _ in payload["rows"]]
        assert orders == list(range(1, len(orders) + 1)), f"{recipe_id} display_order not sequential: {orders}"


async def insert_temp_pork_recipe():
    async with AsyncSessionLocal() as db:
        existing = await db.get(RecipeCatalog, TEMP_PORK_RECIPE_ID)
        if existing is not None:
            return
        db.add(
            RecipeCatalog(
                recipe_id=TEMP_PORK_RECIPE_ID,
                name="Epic5 test pork dish",
                description="Temporary recipe containing pork for exclusion-filter tests.",
                active=True,
            )
        )
        db.add(
            RecipeCatalogIngredient(
                recipe_id=TEMP_PORK_RECIPE_ID,
                canonical_food_id="SF009",  # pork (lean & fat) - mapped to NO_PORK
                required=True,
                display_order=1,
            )
        )
        db.add(
            RecipeCookingStep(
                recipe_id=TEMP_PORK_RECIPE_ID,
                step_number=1,
                instruction="Test step.",
            )
        )
        await db.commit()


def test_recipe_suggestions_filter_declared_hard_exclusions():
    run_database(insert_temp_pork_recipe())
    headers, household_id = create_authenticated_household("suggest-filter")

    # Pantry holds pork, so the temp pork recipe matches and would be suggested.
    added = client.post(
        f"/api/v1/households/{household_id}/pantry-items",
        headers=headers,
        json={"canonical_food_id": "SF009"},
    )
    assert added.status_code == 201, added.text
    confirmed = client.post(f"/api/v1/households/{household_id}/pantry-confirmations", headers=headers)
    assert confirmed.status_code == 200, confirmed.text

    unfiltered = client.get(f"/api/v1/households/{household_id}/recipe-suggestions", headers=headers)
    assert unfiltered.status_code == 200, unfiltered.text
    assert TEMP_PORK_RECIPE_ID in {r["recipe_id"] for r in unfiltered.json()}

    filtered = client.get(
        f"/api/v1/households/{household_id}/recipe-suggestions",
        headers=headers,
        params={"exclusions": "NO_PORK"},
    )
    assert filtered.status_code == 200, filtered.text
    filtered_ids = {r["recipe_id"] for r in filtered.json()}
    assert TEMP_PORK_RECIPE_ID not in filtered_ids
    # No seeded recipe contains pork, so the filtered catalogue may be empty
    # here; the assertions above and below pin the actual filter behaviour.


def test_recipe_detail_is_not_found_under_declared_hard_exclusions():
    run_database(insert_temp_pork_recipe())
    headers, household_id = create_authenticated_household("detail-filter")
    confirmed = client.post(f"/api/v1/households/{household_id}/pantry-confirmations", headers=headers)
    assert confirmed.status_code == 200, confirmed.text

    blocked = client.get(
        f"/api/v1/households/{household_id}/recipes/{TEMP_PORK_RECIPE_ID}",
        headers=headers,
        params={"exclusions": "NO_PORK"},
    )
    assert blocked.status_code == 404, blocked.text

    allowed = client.get(f"/api/v1/households/{household_id}/recipes/{TEMP_PORK_RECIPE_ID}", headers=headers)
    assert allowed.status_code == 200, allowed.text


def test_other_restriction_filters_recipe_list_and_detail_even_without_a_db_code():
    headers, household_id = create_authenticated_household("recipe-name-filter")
    listed = client.get(
        f"/api/v1/households/{household_id}/recipe-suggestions",
        headers=headers,
        params={"custom_restriction": "chicken"},
    )
    assert listed.status_code == 200, listed.text
    listed_ids = {recipe["recipe_id"] for recipe in listed.json()}
    assert "chicken-kangkung-stir-fry" not in listed_ids

    detail = client.get(
        f"/api/v1/households/{household_id}/recipes/chicken-kangkung-stir-fry",
        headers=headers,
        params={"custom_restriction": "chicken"},
    )
    assert detail.status_code == 404, detail.text
    safe_detail = client.get(
        f"/api/v1/households/{household_id}/recipes/tofu-kangkung-stir-fry",
        headers=headers,
        params={"custom_restriction": "chicken"},
    )
    assert safe_detail.status_code == 200, safe_detail.text


def test_planned_food_ids_reorder_without_claiming_food_is_in_pantry():
    headers, household_id = create_authenticated_household("recipe-plan-hint")
    # One real pantry main keeps the list non-empty; the planned chicken set
    # is only an ordering hint and never claims pantry ownership.
    created = client.post(
        f"/api/v1/households/{household_id}/pantry-items",
        headers=headers,
        json={"canonical_food_id": "SF018"},
    )
    assert created.status_code == 201, created.text
    listed = client.get(
        f"/api/v1/households/{household_id}/recipe-suggestions",
        headers=headers,
        params=[("planned_food_ids", food_id) for food_id in ("SF006", "SF074", "SF110")],
    )
    assert listed.status_code == 200, listed.text
    recipes = listed.json()
    # Planned-but-unpurchased foods never count as ownership: the planned
    # chicken recipe is listed (every eligible recipe is) but still reports
    # zero real matches, and ranks after every genuinely matched recipe.
    chicken = next(recipe for recipe in recipes if recipe["recipe_id"] == "chicken-kangkung-stir-fry")
    assert chicken["required_match_count"] == 0
    assert chicken["main_match_count"] == 0
    assert chicken["required_quantity_sufficient_count"] == 0
    chicken_index = recipes.index(chicken)
    assert all(recipe["main_match_count"] > 0 for recipe in recipes[:chicken_index])
    # The planned foods still never count as owned matches on listed recipes.
    assert all(
        food["canonical_food_id"] not in {"SF006", "SF074", "SF110"}
        for recipe in recipes
        for food in recipe["available_ingredients"]
    )


def test_recipe_endpoints_reject_unknown_exclusion_codes():
    headers, household_id = create_authenticated_household("unknown-code")
    confirmed = client.post(f"/api/v1/households/{household_id}/pantry-confirmations", headers=headers)
    assert confirmed.status_code == 200, confirmed.text

    suggestions = client.get(
        f"/api/v1/households/{household_id}/recipe-suggestions",
        headers=headers,
        params={"exclusions": "NOT_A_REAL_CODE"},
    )
    assert suggestions.status_code == 422, suggestions.text

    detail = client.get(
        f"/api/v1/households/{household_id}/recipes/egg-fried-rice",
        headers=headers,
        params={"exclusions": "NOT_A_REAL_CODE"},
    )
    assert detail.status_code == 422, detail.text
