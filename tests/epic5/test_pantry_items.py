# Epic 5 pantry API acceptance tests.
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from services.api.app.db import AppUser, AsyncSessionLocal, Household, PantryItem, engine
from services.api.app.main import app
from services.api.app.services.pantry_stock import upsert_pantry_stock


client = TestClient(app)
pytestmark = pytest.mark.usefixtures("curated_recipes")
run_id = uuid.uuid4().hex[:8]
test_emails: set[str] = set()

# The curated recipes are test-owned fixtures since migration o7p8q9r0s1t2
# removed them from the production catalogue (tests/epic5/conftest.py).
pytestmark = pytest.mark.usefixtures("curated_recipes")


def run_database(coroutine):
    async def runner():
        try:
            return await coroutine
        finally:
            await engine.dispose()

    return asyncio.run(runner())


def create_authenticated_household(scenario_name: str) -> tuple[dict[str, str], int]:
    email = f"epic5-pantry-{run_id}-{scenario_name}@example.com"
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
        json={"name": "Epic 5 test household", "adults": 1, "children": 0},
    )
    assert household.status_code == 200, household.text
    return headers, household.json()["id"]


@pytest.fixture(scope="module", autouse=True)
def remove_pantry_test_data():
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
            await db.commit()

    run_database(cleanup())


def test_add_manual_food_to_owned_household_pantry():
    # Given an authenticated user owns a household and a canonical food exists.
    headers, household_id = create_authenticated_household("add")

    # When the user adds rice as food manually available at home.
    created = client.post(
        f"/api/v1/households/{household_id}/pantry-items",
        headers=headers,
        json={"canonical_food_id": "SEED001"},
    )

    # Then the API creates a manual available pantry item.
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["household_id"] == household_id
    assert body["food"]["canonical_food_id"] == "SEED001"
    assert body["source"] == "MANUAL"
    assert body["status"] == "AVAILABLE"

    # And the item appears when the household pantry is listed.
    listed = client.get(
        f"/api/v1/households/{household_id}/pantry-items",
        headers=headers,
    )
    assert listed.status_code == 200, listed.text
    assert [item["pantry_item_id"] for item in listed.json()] == [body["pantry_item_id"]]


def test_basket_have_replace_replays_without_erasing_manual_or_receipt_stock():
    headers, household_id = create_authenticated_household("have-replace")
    manual = client.post(
        f"/api/v1/households/{household_id}/pantry-items", headers=headers,
        json={"canonical_food_id": "SF018", "quantity": 10, "unit": "biji"},
    )
    assert manual.status_code == 201, manual.text
    endpoint = f"/api/v1/households/{household_id}/basket-have-items"
    first = client.put(endpoint, headers=headers, json={"food_ids": ["SF018", "SF110", "SF110"]})
    assert first.status_code == 200, first.text
    rows = first.json()
    assert len(rows) == 2
    egg = next(row for row in rows if row["food"]["canonical_food_id"] == "SF018")
    rice = next(row for row in rows if row["food"]["canonical_food_id"] == "SF110")
    assert egg["pantry_item_id"] == manual.json()["pantry_item_id"]
    assert egg["basket_have_managed"] is False
    assert rice["basket_have_managed"] is True
    replay = client.put(endpoint, headers=headers, json={"food_ids": ["SF110", "SF018"]})
    assert replay.status_code == 200, replay.text
    assert [row["pantry_item_id"] for row in replay.json()] == [row["pantry_item_id"] for row in rows]
    cleared = client.put(endpoint, headers=headers, json={"food_ids": []})
    assert cleared.status_code == 200, cleared.text
    assert [row["food"]["canonical_food_id"] for row in cleared.json()] == ["SF018"]


def test_manual_edit_takes_ownership_and_invalid_replace_is_atomic():
    headers, household_id = create_authenticated_household("have-takeover")
    endpoint = f"/api/v1/households/{household_id}/basket-have-items"
    first = client.put(endpoint, headers=headers, json={"food_ids": ["SF110"]})
    assert first.status_code == 200, first.text
    item_id = first.json()[0]["pantry_item_id"]
    edited = client.patch(
        f"/api/v1/households/{household_id}/pantry-items/{item_id}",
        headers=headers, json={"canonical_food_id": "SF110", "quantity": 0.5, "unit": "kg"},
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["basket_have_managed"] is False
    invalid = client.put(endpoint, headers=headers, json={"food_ids": ["SF018", "NOT_REAL"]})
    assert invalid.status_code == 422, invalid.text
    emptied = client.put(endpoint, headers=headers, json={"food_ids": []})
    assert emptied.status_code == 200, emptied.text
    assert [(row["pantry_item_id"], row["quantity"]) for row in emptied.json()] == [(item_id, 0.5)]


def test_concurrent_have_replace_cannot_create_duplicate_managed_rows():
    headers, household_id = create_authenticated_household("have-concurrent")
    endpoint = f"/api/v1/households/{household_id}/basket-have-items"
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(
            lambda _: client.put(endpoint, headers=headers, json={"food_ids": ["SF110"]}),
            range(2),
        ))
    assert all(response.status_code == 200 for response in responses), [r.text for r in responses]
    listed = client.get(f"/api/v1/households/{household_id}/pantry-items", headers=headers)
    assert listed.status_code == 200, listed.text
    assert len([row for row in listed.json() if row["food"]["canonical_food_id"] == "SF110"]) == 1


def test_replayed_have_snapshot_does_not_invalidate_pantry_confirmation():
    headers, household_id = create_authenticated_household("have-replay-confirm")
    endpoint = f"/api/v1/households/{household_id}/basket-have-items"
    assert client.put(endpoint, headers=headers, json={"food_ids": ["SF110"]}).status_code == 200
    confirmed = client.post(f"/api/v1/households/{household_id}/pantry-confirmations", headers=headers)
    assert confirmed.status_code == 200, confirmed.text

    async def confirmation_time():
        async with AsyncSessionLocal() as db:
            return await db.scalar(select(Household.pantry_confirmed_at).where(Household.id == household_id))

    before = run_database(confirmation_time())
    assert before is not None
    assert client.put(endpoint, headers=headers, json={"food_ids": ["SF110", "SF110"]}).status_code == 200
    assert run_database(confirmation_time()) == before
    assert client.put(endpoint, headers=headers, json={"food_ids": []}).status_code == 200
    assert run_database(confirmation_time()) is None


def test_receipt_stock_write_takes_over_a_have_managed_row():
    headers, household_id = create_authenticated_household("have-receipt-takeover")
    endpoint = f"/api/v1/households/{household_id}/basket-have-items"
    assert client.put(endpoint, headers=headers, json={"food_ids": ["SF110"]}).status_code == 200

    async def receipt_write():
        async with AsyncSessionLocal() as db:
            await db.scalar(select(Household).where(Household.id == household_id).with_for_update())
            await upsert_pantry_stock(db, household_id, "SF110", None, None, "RECEIPT")
            await db.commit()

    run_database(receipt_write())
    cleared = client.put(endpoint, headers=headers, json={"food_ids": []})
    assert cleared.status_code == 200, cleared.text
    assert len(cleared.json()) == 1
    assert cleared.json()[0]["source"] == "RECEIPT"
    assert cleared.json()[0]["basket_have_managed"] is False


def test_edit_food_in_owned_household_pantry():
    # Given an authenticated user owns a household with a pantry food item.
    headers, household_id = create_authenticated_household("edit")

    created = client.post(
        f"/api/v1/households/{household_id}/pantry-items",
        headers=headers,
        json={"canonical_food_id": "SF018"},
    )
    assert created.status_code == 201, created.text
    pantry_item_id = created.json()["pantry_item_id"]

    # When the user changes the pantry item to another active canonical food.
    updated = client.patch(
        f"/api/v1/households/{household_id}/pantry-items/{pantry_item_id}",
        headers=headers,
        json={"canonical_food_id": "SF110"},
    )

    # Then the API returns the updated food and the pantry list reflects it.
    assert updated.status_code == 200, updated.text
    assert updated.json()["food"]["canonical_food_id"] == "SF110"
    listed = client.get(
        f"/api/v1/households/{household_id}/pantry-items",
        headers=headers,
    )
    updated_item = next(item for item in listed.json() if item["pantry_item_id"] == pantry_item_id)
    assert updated_item["food"]["canonical_food_id"] == "SF110"


def test_add_and_update_manual_pantry_quantity():
    # Given an authenticated household records chicken with a measured weight.
    headers, household_id = create_authenticated_household("measured-quantity")
    created = client.post(
        f"/api/v1/households/{household_id}/pantry-items",
        headers=headers,
        json={"canonical_food_id": "SF006", "quantity": 0.6, "unit": "kg"},
    )
    assert created.status_code == 201, created.text
    pantry_item_id = created.json()["pantry_item_id"]
    assert created.json()["quantity"] == 0.6
    assert created.json()["unit"] == "kg"

    # When the household corrects that amount in grams.
    updated = client.patch(
        f"/api/v1/households/{household_id}/pantry-items/{pantry_item_id}",
        headers=headers,
        json={"canonical_food_id": "SF006", "quantity": 450, "unit": "g"},
    )

    # Then the API converts the corrected gram amount to kilograms.
    assert updated.status_code == 200, updated.text
    assert updated.json()["quantity"] == 0.45
    assert updated.json()["unit"] == "kg"


def test_remove_food_from_owned_household_pantry():
    # Given an authenticated user owns a household with a pantry food item.
    headers, household_id = create_authenticated_household("remove")
    created = client.post(
        f"/api/v1/households/{household_id}/pantry-items",
        headers=headers,
        json={"canonical_food_id": "SF110"},
    )
    assert created.status_code == 201, created.text
    pantry_item_id = created.json()["pantry_item_id"]

    # When the user removes that pantry item.
    removed = client.delete(
        f"/api/v1/households/{household_id}/pantry-items/{pantry_item_id}",
        headers=headers,
    )

    # Then the item is no longer included in the available pantry list.
    assert removed.status_code == 204, removed.text
    listed = client.get(
        f"/api/v1/households/{household_id}/pantry-items",
        headers=headers,
    )
    assert listed.status_code == 200, listed.text
    assert pantry_item_id not in {item["pantry_item_id"] for item in listed.json()}


def test_confirm_current_available_food_list_before_recipe_suggestions():
    # Given an authenticated user owns a household with several available food items.
    headers, household_id = create_authenticated_household("confirm-list")
    for canonical_food_id in ("SF110", "SF018"):
        created = client.post(
            f"/api/v1/households/{household_id}/pantry-items",
            headers=headers,
            json={"canonical_food_id": canonical_food_id},
        )
        assert created.status_code == 201, created.text

    # When the user confirms the current available-food list.
    confirmed = client.post(
        f"/api/v1/households/{household_id}/pantry-confirmations",
        headers=headers,
    )

    # Then the API confirms the list and identifies the confirmed item count.
    assert confirmed.status_code == 200, confirmed.text
    body = confirmed.json()
    assert body["household_id"] == household_id
    assert body["available_item_count"] == 2
    assert body["confirmed_at"] is not None


def test_confirmed_pantry_returns_recipe_suggestions_and_recipe_details():
    # Given a household has the required ingredients for a curated recipe.
    headers, household_id = create_authenticated_household("recipe-suggestions")
    for canonical_food_id in ("SF006", "SF074", "SF110"):
        created = client.post(
            f"/api/v1/households/{household_id}/pantry-items",
            headers=headers,
            json={"canonical_food_id": canonical_food_id},
        )
        assert created.status_code == 201, created.text
    confirmed = client.post(
        f"/api/v1/households/{household_id}/pantry-confirmations",
        headers=headers,
    )
    assert confirmed.status_code == 200, confirmed.text

    # When the user requests recipe suggestions from the confirmed pantry.
    suggestions = client.get(
        f"/api/v1/households/{household_id}/recipe-suggestions",
        headers=headers,
    )

    # Then a named suggestion shows the available ingredients it uses.
    assert suggestions.status_code == 200, suggestions.text
    chicken_recipe = next(
        recipe for recipe in suggestions.json() if recipe["recipe_id"] == "chicken-kangkung-stir-fry"
    )
    assert chicken_recipe["name"] == "Chicken & Kangkung Stir-fry"
    assert chicken_recipe["required_match_count"] == 3
    assert {food["canonical_food_id"] for food in chicken_recipe["available_ingredients"]} >= {
        "SF006",
        "SF074",
        "SF110",
    }

    # And opening that suggestion shows ingredients and ordered cooking steps.
    detail = client.get(
        f"/api/v1/households/{household_id}/recipes/chicken-kangkung-stir-fry",
        headers=headers,
    )
    assert detail.status_code == 200, detail.text
    assert len(detail.json()["ingredients"]) == 5
    assert detail.json()["cooking_steps"][-1] == "Serve with rice."


def test_empty_unconfirmed_pantry_can_browse_all_recipes_and_stocked_matches_rank_first():
    """Meal ideas are browseable before a user makes a plan or adds pantry food."""
    headers, household_id = create_authenticated_household("browse-all-recipes")

    empty_pantry = client.get(
        f"/api/v1/households/{household_id}/recipe-suggestions",
        headers=headers,
    )

    assert empty_pantry.status_code == 200, empty_pantry.text
    # Never-empty fallback: with no pantry stock at all the list degrades to
    # the full eligible set (fewest-missing first); every item transparently
    # reports zero matches and basics_only.
    assert empty_pantry.json()
    assert all(recipe["required_match_count"] == 0 for recipe in empty_pantry.json())
    assert all(recipe["pantry_state"] == "basics_only" for recipe in empty_pantry.json())

    added = client.post(
        f"/api/v1/households/{household_id}/pantry-items",
        headers=headers,
        json={"canonical_food_id": "SF006"},
    )
    assert added.status_code == 201, added.text

    ranked = client.get(
        f"/api/v1/households/{household_id}/recipe-suggestions",
        headers=headers,
    )

    assert ranked.status_code == 200, ranked.text
    ranked_recipes = ranked.json()
    positive_match_indexes = [
        index for index, recipe in enumerate(ranked_recipes) if recipe["required_match_count"] > 0
    ]
    # All eligible recipes are listed again (filter retired); the ranking,
    # not a filter, keeps every main-matching recipe ahead of zero-match
    # ones.
    assert positive_match_indexes
    assert any(recipe["main_match_count"] == 0 for recipe in ranked_recipes)
    first_zero = next(
        index for index, recipe in enumerate(ranked_recipes) if recipe["main_match_count"] == 0
    )
    assert all(
        recipe["main_match_count"] > 0 for recipe in ranked_recipes[:first_zero]
    )


def test_household_recipe_api_reports_quantities_ranking_and_safe_substitution():
    # Given two adults and two children have measured recipe ingredients at home.
    headers, household_id = create_authenticated_household("quantity-recipe-flow")
    for canonical_food_id, quantity, unit in (
        ("SF006", 0.5, "kg"),
        ("SF074", 0.2, "kg"),
        ("SF110", 0.3, "kg"),
        ("SF062", 0.25, "kg"),
    ):
        created = client.post(
            f"/api/v1/households/{household_id}/pantry-items",
            headers=headers,
            json={"canonical_food_id": canonical_food_id, "quantity": quantity, "unit": unit},
        )
        assert created.status_code == 201, created.text

    # The existing test helper creates a one-adult household. Update it to the
    # approved two-adult, two-child household scenario through the database.
    async def set_household_members():
        async with AsyncSessionLocal() as db:
            household = await db.get(Household, household_id)
            household.adults = 2
            household.children = 2
            await db.commit()

    run_database(set_household_members())
    confirmed = client.post(
        f"/api/v1/households/{household_id}/pantry-confirmations",
        headers=headers,
    )
    assert confirmed.status_code == 200, confirmed.text

    # When the household requests its recipe suggestions and recipe detail.
    suggestions = client.get(
        f"/api/v1/households/{household_id}/recipe-suggestions",
        headers=headers,
    )
    detail = client.get(
        f"/api/v1/households/{household_id}/recipes/chicken-kangkung-stir-fry",
        headers=headers,
    )

    # Then the recipe is ranked as an actionable measured shortfall, ahead of
    # recipes with unknown quantities, and gives the household-scaled kilograms.
    assert suggestions.status_code == 200, suggestions.text
    recipe_ids = [recipe["recipe_id"] for recipe in suggestions.json()]
    assert recipe_ids.index("chicken-kangkung-stir-fry") < recipe_ids.index("egg-fried-rice")
    chicken_suggestion = next(
        recipe for recipe in suggestions.json() if recipe["recipe_id"] == "chicken-kangkung-stir-fry"
    )
    assert chicken_suggestion["household_servings"] == 3
    assert chicken_suggestion["quantity_status"] == "INSUFFICIENT"
    assert chicken_suggestion["required_quantity_sufficient_count"] == 2

    # And recipe detail gives the exact water-spinach shortage and only the
    # approved spinach candidate already held by the household.
    assert detail.status_code == 200, detail.text
    ingredients_by_food = {
        ingredient["food"]["canonical_food_id"]: ingredient for ingredient in detail.json()["ingredients"]
    }
    assert ingredients_by_food["SF074"]["required_quantity_kg"] == 0.3
    assert ingredients_by_food["SF074"]["available_quantity_kg"] == 0.2
    assert ingredients_by_food["SF074"]["shortfall_quantity_kg"] == 0.1
    assert detail.json()["substitution_suggestions"] == [
        {
            "rule_id": "water-spinach-to-spinach",
            "original_food": ingredients_by_food["SF074"]["food"],
            "substitute_food": {
                "canonical_food_id": "SF062",
                "name": "spinach (bayam)",
                "name_ms": "bayam",
                "category": "vegetables",
            },
            "reason": "Spinach can replace water spinach in a quick stir-fry.",
        }
    ]


def test_available_ingredients_combine_food_at_home_and_confirmed_purchase():
    # Given a household has food at home and an Epic 6 confirmed purchase.
    headers, household_id = create_authenticated_household("combined-sources")
    manual = client.post(
        f"/api/v1/households/{household_id}/pantry-items",
        headers=headers,
        json={"canonical_food_id": "SF110"},
    )
    assert manual.status_code == 201, manual.text

    async def add_confirmed_purchase():
        async with AsyncSessionLocal() as db:
            # Epic 6 will create receipt-source pantry items after purchase review.
            db.add(
                PantryItem(
                    household_id=household_id,
                    canonical_food_id="SF018",
                    source="RECEIPT",
                    status="AVAILABLE",
                )
            )
            await db.commit()

    run_database(add_confirmed_purchase())

    # When the household views its available ingredients.
    listed = client.get(
        f"/api/v1/households/{household_id}/pantry-items",
        headers=headers,
    )

    # Then both origins appear together and can be understood by source.
    assert listed.status_code == 200, listed.text
    sources_by_food_id = {item["food"]["canonical_food_id"]: item["source"] for item in listed.json()}
    assert sources_by_food_id == {"SF110": "MANUAL", "SF018": "RECEIPT"}


def test_changing_available_food_updates_suggestions_without_reconfirmation():
    # Given a household confirmed its available-food list.
    headers, household_id = create_authenticated_household("reconfirm")
    created = client.post(
        f"/api/v1/households/{household_id}/pantry-items",
        headers=headers,
        json={"canonical_food_id": "SF110"},
    )
    assert created.status_code == 201, created.text
    pantry_item_id = created.json()["pantry_item_id"]
    confirmed = client.post(
        f"/api/v1/households/{household_id}/pantry-confirmations",
        headers=headers,
    )
    assert confirmed.status_code == 200, confirmed.text

    # When the user changes an available food item.
    updated = client.patch(
        f"/api/v1/households/{household_id}/pantry-items/{pantry_item_id}",
        headers=headers,
        json={"canonical_food_id": "SF018"},
    )
    assert updated.status_code == 200, updated.text

    # Then browsing immediately reflects the current pantry instead of blocking.
    suggestions = client.get(
        f"/api/v1/households/{household_id}/recipe-suggestions",
        headers=headers,
    )
    assert suggestions.status_code == 200, suggestions.text
    assert suggestions.json()
    assert any(recipe["required_match_count"] > 0 for recipe in suggestions.json())


def test_recipe_suggestions_are_available_before_first_pantry_confirmation():
    # Given a household has available food but has not confirmed the current list.
    headers, household_id = create_authenticated_household("suggestions-unconfirmed")
    created = client.post(
        f"/api/v1/households/{household_id}/pantry-items",
        headers=headers,
        json={"canonical_food_id": "SF110"},
    )
    assert created.status_code == 201, created.text

    # When the user requests recipe suggestions without confirmation.
    suggestions = client.get(
        f"/api/v1/households/{household_id}/recipe-suggestions",
        headers=headers,
    )

    # Then the API returns recipe ideas and ranks recipes using that pantry item.
    assert suggestions.status_code == 200, suggestions.text
    assert suggestions.json()
    assert any(recipe["required_match_count"] > 0 for recipe in suggestions.json())


def test_pantry_without_recipe_match_still_returns_the_recipe_catalogue():
    # Buffalo is not used by the fixture recipes or their reviewed alternatives.
    # SF015 is now a valid chicken alternative, so it is no longer a no-match case.
    headers, household_id = create_authenticated_household("suggestions-no-match")
    created = client.post(
        f"/api/v1/households/{household_id}/pantry-items",
        headers=headers,
        json={"canonical_food_id": "SF001"},
    )
    assert created.status_code == 201, created.text
    confirmed = client.post(
        f"/api/v1/households/{household_id}/pantry-confirmations",
        headers=headers,
    )
    assert confirmed.status_code == 200, confirmed.text

    # When the user requests recipe suggestions.
    suggestions = client.get(
        f"/api/v1/households/{household_id}/recipe-suggestions",
        headers=headers,
    )

    # Then the API remains browseable; with no main match anywhere the
    # never-empty fallback returns the degraded catalogue where each recipe
    # transparently has no match and the pantry is marked basics_only.
    assert suggestions.status_code == 200, suggestions.text
    assert suggestions.json()
    assert all(recipe["required_match_count"] == 0 for recipe in suggestions.json())
    assert all(recipe["pantry_state"] == "basics_only" for recipe in suggestions.json())


def test_complete_recipe_match_ranks_before_partial_recipe_match():
    # Given a confirmed pantry completely matches one recipe and partly matches another.
    headers, household_id = create_authenticated_household("suggestions-ranking")
    for canonical_food_id in ("SF006", "SF074", "SF110", "SF018"):
        created = client.post(
            f"/api/v1/households/{household_id}/pantry-items",
            headers=headers,
            json={"canonical_food_id": canonical_food_id},
        )
        assert created.status_code == 201, created.text
    confirmed = client.post(
        f"/api/v1/households/{household_id}/pantry-confirmations",
        headers=headers,
    )
    assert confirmed.status_code == 200, confirmed.text

    # When recipe suggestions are requested.
    suggestions = client.get(
        f"/api/v1/households/{household_id}/recipe-suggestions",
        headers=headers,
    )

    # Then the full chicken recipe ranks ahead of the partly matched tofu recipe.
    assert suggestions.status_code == 200, suggestions.text
    recipe_ids = [recipe["recipe_id"] for recipe in suggestions.json()]
    assert recipe_ids.index("chicken-kangkung-stir-fry") < recipe_ids.index("tofu-kangkung-stir-fry")


def test_other_users_cannot_access_household_pantry_or_recipe_routes():
    # Given one user owns and confirms a household pantry.
    owner_headers, household_id = create_authenticated_household("owner-isolation")
    created = client.post(
        f"/api/v1/households/{household_id}/pantry-items",
        headers=owner_headers,
        json={"canonical_food_id": "SF110"},
    )
    assert created.status_code == 201, created.text
    confirmed = client.post(
        f"/api/v1/households/{household_id}/pantry-confirmations",
        headers=owner_headers,
    )
    assert confirmed.status_code == 200, confirmed.text

    # When a different authenticated user requests household-scoped resources.
    other_headers, other_household_id = create_authenticated_household("other-isolation")
    assert other_household_id != household_id
    responses = [
        client.get(f"/api/v1/households/{household_id}/pantry-items", headers=other_headers),
        client.post(f"/api/v1/households/{household_id}/pantry-confirmations", headers=other_headers),
        client.get(f"/api/v1/households/{household_id}/recipe-suggestions", headers=other_headers),
        client.get(
            f"/api/v1/households/{household_id}/recipes/chicken-kangkung-stir-fry",
            headers=other_headers,
        ),
    ]

    # Then the API does not expose another household's pantry or recipe data.
    assert [response.status_code for response in responses] == [404, 404, 404, 404]


def test_confirmed_pantry_returns_not_found_for_unknown_recipe():
    # Given a household has confirmed its available-food list.
    headers, household_id = create_authenticated_household("unknown-recipe")
    created = client.post(
        f"/api/v1/households/{household_id}/pantry-items",
        headers=headers,
        json={"canonical_food_id": "SF110"},
    )
    assert created.status_code == 201, created.text
    confirmed = client.post(
        f"/api/v1/households/{household_id}/pantry-confirmations",
        headers=headers,
    )
    assert confirmed.status_code == 200, confirmed.text

    # When the user opens a recipe that is not in the curated collection.
    detail = client.get(
        f"/api/v1/households/{household_id}/recipes/not-a-curated-recipe",
        headers=headers,
    )

    # Then the API reports that the recipe does not exist.
    assert detail.status_code == 404, detail.text
    assert detail.json()["detail"] == "Recipe not found."


def test_manual_pantry_creation_rejects_receipt_source_input():
    # Given an authenticated user owns a household.
    headers, household_id = create_authenticated_household("reject-receipt-input")

    # When the user attempts to create a receipt-origin item through the manual endpoint.
    created = client.post(
        f"/api/v1/households/{household_id}/pantry-items",
        headers=headers,
        json={"canonical_food_id": "SF110", "source": "RECEIPT"},
    )

    # Then the API rejects the Epic 6-only source field.
    assert created.status_code == 422, created.text


def test_manual_pantry_creation_rejects_unknown_food():
    # Given an authenticated user owns a household.
    headers, household_id = create_authenticated_household("reject-unknown-food")

    # When the user adds a canonical food that does not exist.
    created = client.post(
        f"/api/v1/households/{household_id}/pantry-items",
        headers=headers,
        json={"canonical_food_id": "UNKNOWN-FOOD"},
    )

    # Then the API accepts only active canonical food.
    assert created.status_code == 422, created.text
    assert created.json()["detail"] == "Active food not found."
