"""Contract tests for the V2-native basket pricing boundary.

These tests intentionally describe the API before its implementation.  The
first TDD run must therefore fail because the route is not registered yet.
They do not connect to PostgreSQL or mutate shared test data.
"""
from __future__ import annotations

import os

# Keep importing the FastAPI application isolated from the developer's local
# or Railway configuration.  This contract test only inspects OpenAPI.
os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = (
    "postgresql+asyncpg://wisebasket:wisebasket@localhost:5432/wisebasket"
)
os.environ["LLM_ENABLED"] = "false"

from services.api.app.main import _basket_store_sort_key, app
from services.api.app.schemas import BasketPriceStoreResponse


ROUTE = "/api/v2/basket-prices"


def _store(*, store_id: str, matched: int, distance: float | None, cost: float):
    return BasketPriceStoreResponse(
        store_id=store_id,
        store_name=store_id,
        matched_item_count=matched,
        basket_cost_rm=cost,
        distance_km=distance,
        latest_observed_date="2026-09-24",
        items=[],
    )


def test_basket_store_order_prioritizes_coverage_then_nearby_distance() -> None:
    stores = [
        _store(store_id="cheap-low-coverage", matched=2, distance=0.2, cost=5),
        _store(store_id="far-high-coverage", matched=4, distance=4.0, cost=20),
        _store(store_id="near-high-coverage", matched=4, distance=1.0, cost=25),
    ]

    ranked = sorted(stores, key=_basket_store_sort_key)

    assert [store.store_id for store in ranked] == [
        "near-high-coverage",
        "far-high-coverage",
        "cheap-low-coverage",
    ]


def _resolved_schema(openapi: dict, schema: dict) -> dict:
    reference = schema.get("$ref")
    if not reference:
        return schema
    component_name = reference.rsplit("/", 1)[-1]
    return openapi["components"]["schemas"][component_name]


def test_basket_price_api_declares_quantity_location_and_price_provenance() -> None:
    """The public contract must make live prices and estimates distinguishable."""
    openapi = app.openapi()

    assert ROUTE in openapi["paths"], (
        "Basket pricing must be a V2-native API instead of a dummy "
        "store_comparison field in the legacy planner response."
    )
    operation = openapi["paths"][ROUTE]["post"]

    request_schema = _resolved_schema(
        openapi,
        operation["requestBody"]["content"]["application/json"]["schema"],
    )
    assert {"location", "items"} <= set(request_schema["required"])

    location_schema = _resolved_schema(
        openapi,
        request_schema["properties"]["location"],
    )
    assert {"state", "district"} <= set(location_schema["properties"])
    assert {"latitude", "longitude"} <= set(location_schema["properties"])

    items_schema = request_schema["properties"]["items"]
    item_schema = _resolved_schema(openapi, items_schema["items"])
    assert {"food_id", "quantity_kg"} <= set(item_schema["required"])
    assert item_schema["properties"]["quantity_kg"]["exclusiveMinimum"] == 0

    response_schema = _resolved_schema(
        openapi,
        operation["responses"]["200"]["content"]["application/json"]["schema"],
    )
    assert {
        "currency",
        "pricing_scope",
        "items",
        "stores",
        "summary",
    } <= set(response_schema["required"])

    response_item_schema = _resolved_schema(
        openapi,
        response_schema["properties"]["items"]["items"],
    )
    assert {
        "food_id",
        "quantity_kg",
        "price_source",
        "matched_store_count",
        "estimated_cost_rm",
        "latest_observed_date",
    } <= set(response_item_schema["required"])

    price_source_schema = response_item_schema["properties"]["price_source"]
    if "$ref" in price_source_schema:
        price_source_schema = _resolved_schema(openapi, price_source_schema)
    assert set(price_source_schema["enum"]) == {
        "OBSERVED_STORE_PRICE",
        "CATALOGUE_ESTIMATE",
        "UNAVAILABLE",
    }

    summary_schema = _resolved_schema(
        openapi,
        response_schema["properties"]["summary"],
    )
    assert {
        "total_item_count",
        "matched_item_count",
        "estimated_item_count",
        "unavailable_item_count",
    } <= set(summary_schema["required"])
