# Controlled HTTP boundary tests with an injected in-memory catalogue provider.
from fastapi import FastAPI
from fastapi.testclient import TestClient

from packages.optimizer.tests_v2.test_golden_personas import canonical_family_catalog
from packages.optimizer.tests_v2.test_optimizer import meal, options
from services.api.app.planner_v2_routes import (
    CatalogUnavailableError,
    create_planner_v2_router,
)
from services.api.app.planner_v2_service import PlannerV2Catalog


class ControlledCatalogProvider:
    def __init__(self, catalog=None, unavailable=False):
        self.catalog = catalog
        self.unavailable = unavailable
        self.requests = []

    async def get_catalog(self, payload):
        self.requests.append(payload)
        if self.unavailable:
            raise CatalogUnavailableError("Controlled catalogue unavailable")
        return self.catalog


def catalog():
    return PlannerV2Catalog(
        recipes=(meal("chicken-meal", max_occurrences=3),),
        purchase_options=options(chicken="10"),
    )


def client(provider):
    app = FastAPI()
    app.include_router(create_planner_v2_router(provider))
    return TestClient(app)


def payload(**changes):
    values = {
        "household": {"adults": 2, "children": 0},
        "budget_rm": "10.00",
        "target_meals": 1,
    }
    values.update(changes)
    return values


def test_http_endpoint_returns_complete_typed_plan_with_empty_pantry_default():
    provider = ControlledCatalogProvider(catalog())
    response = client(provider).post("/api/v2/plans", json=payload())
    assert response.status_code == 200
    body = response.json()
    assert body["planner_version"] == "recipe-first-v2"
    assert body["outcome"]["status"] == "FULL_PLAN"
    assert body["recipes"] == [{
        "recipe_id": "chicken-meal",
        "name": "chicken-meal",
        "occurrences": 1,
        "household_servings": 2.0,
    }]
    assert provider.requests[0].pantry == []


def test_shortfall_is_http_success_with_machine_readable_domain_error():
    provider = ControlledCatalogProvider(catalog())
    response = client(provider).post(
        "/api/v2/plans",
        json=payload(budget_rm="1.00"),
    )
    assert response.status_code == 200
    assert response.json()["outcome"]["error_codes"] == ["INSUFFICIENT_BUDGET"]


def test_request_validation_errors_remain_http_422():
    provider = ControlledCatalogProvider(catalog())
    response = client(provider).post(
        "/api/v2/plans",
        json=payload(household={"adults": 0, "children": 0}),
    )
    assert response.status_code == 422
    assert provider.requests == []


def test_client_cannot_submit_recipes_prices_or_catalogue_records():
    provider = ControlledCatalogProvider(catalog())
    response = client(provider).post(
        "/api/v2/plans",
        json=payload(recipes=[], purchase_options=[]),
    )
    assert response.status_code == 422
    assert provider.requests == []


def test_catalogue_provider_failure_has_stable_service_error_code():
    provider = ControlledCatalogProvider(unavailable=True)
    response = client(provider).post("/api/v2/plans", json=payload())
    assert response.status_code == 503
    assert response.json() == {
        "detail": {
            "code": "PLANNER_V2_CATALOG_UNAVAILABLE",
            "message": "Controlled catalogue unavailable",
        }
    }


def test_canonical_family_scenario_survives_the_http_boundary():
    provider = ControlledCatalogProvider(canonical_family_catalog())
    response = client(provider).post(
        "/api/v2/plans",
        json={
            "household": {"adults": 1, "children": 2},
            "budget_rm": "150.00",
            "target_meals": 10,
            "pantry": [
                {"food_id": "rice", "quantity_kg": "1.0", "status": "CONFIRMED"},
                {"food_id": "egg", "quantity_kg": "0.3", "status": "CONFIRMED"},
                {"food_id": "oil", "quantity_kg": "0.1", "status": "CONFIRMED"},
                {"food_id": "yoghurt", "quantity_kg": "0.5", "status": "CONFIRMED"},
                {"food_id": "cheese", "quantity_kg": "0.2", "status": "CONFIRMED"},
            ],
            "preferences": [
                {"food_id": "chicken", "score": 10},
                {"food_id": "beef", "score": 9},
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["outcome"]["status"] == "FULL_PLAN"
    assert body["outcome"]["supported_meals"] == 10
    assert sum(recipe["occurrences"] for recipe in body["recipes"]) == 10
    assert body["substitutions"] == [{
        "rule_id": "beef-to-chicken",
        "recipe_id": "beef-meal",
        "original_food_id": "beef",
        "substitute_food_id": "chicken",
        "occurrences": 2,
        "original_quantity_kg": 0.4,
        "substitute_quantity_kg": 0.48,
    }]
    assert round(sum(row["estimated_cost_rm"] for row in body["shopping_items"]), 2) == body[
        "displayed_total_cost_rm"
    ]


def test_invalid_provider_catalogue_returns_stable_http_error():
    valid = catalog()
    invalid = PlannerV2Catalog(
        recipes=(valid.recipes[0], valid.recipes[0]),
        purchase_options=valid.purchase_options,
    )
    response = client(ControlledCatalogProvider(invalid)).post(
        "/api/v2/plans",
        json=payload(),
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": {
            "code": "PLANNER_V2_CATALOG_INVALID",
            "message": "Planner catalogue failed validation",
            "issues": ["DUPLICATE_RECIPE_ID:chicken-meal"],
        }
    }


def test_empty_provider_catalogue_returns_domain_shortfall():
    response = client(ControlledCatalogProvider(PlannerV2Catalog((), ()))).post(
        "/api/v2/plans",
        json=payload(),
    )

    assert response.status_code == 200
    assert response.json()["outcome"]["error_codes"] == ["NO_ELIGIBLE_RECIPE"]


def test_wrong_provider_catalogue_type_returns_stable_http_error():
    response = client(ControlledCatalogProvider({})).post(
        "/api/v2/plans",
        json=payload(),
    )

    assert response.status_code == 503
    assert response.json()["detail"] == {
        "code": "PLANNER_V2_CATALOG_INVALID",
        "message": "Planner catalogue failed validation",
        "issues": ["INVALID_CATALOG_TYPE"],
    }
