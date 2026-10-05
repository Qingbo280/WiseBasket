from decimal import Decimal
from contextlib import asynccontextmanager

import pytest
from fastapi.testclient import TestClient

from services.api.app.db import AsyncSessionLocal
from services.api.app.main import app
from services.api.app.planner_v2_catalog_db import (
    DatabasePlannerV2CatalogProvider,
    load_planner_v2_catalog,
    load_purchase_options,
    purchase_unit_kg,
)
from services.api.app.planner_v2_service import PlannerV2Catalog, validate_planner_v2_catalog
from services.api.app.schemas import PlannerV2CreateRequest
from services.api.app.services.representative_price import ResolvedFoodPrice
from tests.db_seed import run_db
from packages.optimizer.wisebasket_optimizer.v2.oil_equivalence import OIL_FOOD_IDS
from services.api.app.weekly_baselines import BASELINE_FOOD_IDS


EXPECTED_DIRECT_RECIPE_IDS = {
    "bihun-goreng",
    "dhal-curry-with-rice",
    "egg-potato-curry-with-rice",
    "maggi-goreng",
    "malay-chicken-soup",
    "mee-goreng",
    "onion-omelette",
    "sardine-sambal-with-rice",
    "soy-sauce-mackerel-with-rice",
    "tofu-cabbage-stir-fry",
    "tomato-chicken-with-rice",
    "tomato-egg-stir-fry",
    "tomato-tofu-with-rice",
    "turmeric-chicken-with-rice",
}

EXPECTED_COMPONENT_IDS = {
    "cabbage-mamak-stir-fry", "cauliflower-stir-fry",
    "french-bean-garlic-stir-fry", "garlic-broccoli-stir-fry",
    "garlic-long-beans", "garlic-prawn-stir-fry",
    "garlic-spinach-stir-fry", "long-bean-egg-stir-fry",
    "malaysian-chicken-curry-with-rice", "mixed-vegetable-stir-fry",
    "mustard-greens-stir-fry", "okra-eggplant-stir-fry",
    "potato-onion-stir-fry", "red-tilapia-soy-with-rice",
    "sambal-eggplant-with-rice", "soy-sauce-chicken-with-rice",
    "soy-sauce-eggs-with-rice", "squid-soy-stir-fry", "steamed-egg",
    "tofu-prawn-stir-fry", "winged-bean-stir-fry",
}


def test_v2_purchase_unit_respects_fixed_pack_and_by_weight_modes():
    pack_sizes = [(Decimal("300"), "300 g"), (Decimal("1000"), "1 kg")]

    assert purchase_unit_kg("FIXED_PACK", pack_sizes) == Decimal("0.3")
    assert purchase_unit_kg("BY_WEIGHT", pack_sizes) == Decimal("0.025")


@pytest.mark.asyncio
async def test_database_provider_loads_purchase_options_for_minimum_basket_foods(monkeypatch):
    captured_food_ids = None

    async def load_catalog(db, additional_food_ids=()):
        nonlocal captured_food_ids
        captured_food_ids = set(additional_food_ids)
        return PlannerV2Catalog(recipes=(), purchase_options=())

    @asynccontextmanager
    async def session_factory():
        yield object()

    monkeypatch.setattr(
        "services.api.app.planner_v2_catalog_db.load_planner_v2_catalog",
        load_catalog,
    )
    payload = PlannerV2CreateRequest(
        household={"adults": 1, "children": 0},
        budget_rm="100",
        target_meals=5,
        selected_food_ids=["SF013"],
        minimum_purchase_quantities=[{"food_id": "SF013", "purchase_kg": "0.25"}],
    )

    await DatabasePlannerV2CatalogProvider(session_factory).get_catalog(payload)

    assert captured_food_ids == {"SF013"} | BASELINE_FOOD_IDS


def test_database_catalog_loads_direct_recipes_and_reviewed_meal_sets():
    async def load_catalog():
        async with AsyncSessionLocal() as db:
            return await load_planner_v2_catalog(db)

    catalog = run_db(load_catalog())

    direct_ids = {
        recipe.recipe_id
        for recipe in catalog.recipes
        if not recipe.recipe_id.startswith("meal-set--")
    }
    meal_sets = {
        recipe.recipe_id
        for recipe in catalog.recipes
        if recipe.recipe_id.startswith("meal-set--")
    }
    covered_components = {
        component_id
        for recipe_id in meal_sets
        for component_id in recipe_id.removeprefix("meal-set--").split("--")
    }
    assert direct_ids == EXPECTED_DIRECT_RECIPE_IDS
    assert len(meal_sets) == 12
    assert covered_components == EXPECTED_COMPONENT_IDS
    assert validate_planner_v2_catalog(catalog) is catalog
    recipe_food_ids = {
        ingredient.food_id
        for recipe in catalog.recipes
        for ingredient in recipe.ingredients
    }
    safety_ids = {record.food_id for record in catalog.food_safety}
    option_ids = {option.food_id for option in catalog.purchase_options}
    nutrition_ids = {record.food_id for record in catalog.food_nutrition}
    # Equivalent oils can be bought even when absent from this recipe slice,
    # but no unrelated food can enter the V2 catalogue.
    assert recipe_food_ids <= safety_ids <= recipe_food_ids | OIL_FOOD_IDS
    assert option_ids <= recipe_food_ids | OIL_FOOD_IDS
    assert nutrition_ids <= recipe_food_ids | OIL_FOOD_IDS


def test_main_application_mounts_live_recipe_first_endpoint():
    response = TestClient(app).post(
        "/api/v2/plans",
        json={
            "household": {"adults": 1, "children": 2},
            "budget_rm": "150.00",
            "target_meals": 10,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["planner_version"] == "recipe-first-v2"
    assert body["outcome"]["requested_meals"] == 10
    assert body["outcome"]["status"] in {"FULL_PLAN", "SHORTFALL"}


@pytest.mark.asyncio
async def test_v2_uses_labelled_purchase_weight_when_edible_yield_is_missing(monkeypatch):
    async def prices(*args, **kwargs):
        assert kwargs["default_edible_yield"] == Decimal("1")
        return {
            "SF018": ResolvedFoodPrice(
                price_rm_per_100g_edible=0.50,
                price_rm_per_100g_purchase=0.50,
                tier_used="NATIONAL",
                shop_count=3,
                confidence="NORMAL",
                price_provenance="REAL_PRICECATCHER",
                price_is_estimated=False,
                price_source="PriceCatcher",
                price_updated="2026-09-21",
                location_state=None,
                location_district=None,
            )
        }

    async def masses(*args, **kwargs):
        return {"SF018": [(Decimal("300"), "300 g")]}

    async def modes(*args, **kwargs):
        return {"SF018": "FIXED_PACK"}

    monkeypatch.setattr("services.api.app.planner_v2_catalog_db.resolve_food_prices", prices)
    monkeypatch.setattr("services.api.app.planner_v2_catalog_db.fetch_current_purchase_masses_batch", masses)
    monkeypatch.setattr("services.api.app.planner_v2_catalog_db.load_purchase_modes", modes)
    options = await load_purchase_options(object(), ["SF018"])

    assert len(options) == 1
    assert options[0].unit_kg == Decimal("0.3")
    assert options[0].edible_yield == Decimal("1")
