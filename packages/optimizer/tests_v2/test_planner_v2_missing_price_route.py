"""An unpriced accepted basket item passes through without adding to cost."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from services.api.app.planner_v2_routes import create_planner_v2_router
from services.api.app.planner_v2_service import PlannerV2Catalog


class UnpricedCatalogProvider:
    async def get_catalog(self, payload):
        return PlannerV2Catalog(recipes=(), purchase_options=())


def test_missing_latest_database_price_passes_through_without_a_cost():
    app = FastAPI()
    app.include_router(create_planner_v2_router(UnpricedCatalogProvider()))

    response = TestClient(app).post("/api/v2/plans", json={
        "household": {"adults": 2, "children": 0},
        "budget_rm": "100",
        "target_meals": 1,
        "selected_food_ids": ["SF106"],
        "minimum_purchase_quantities": [{"food_id": "SF106", "purchase_kg": "0.25"}],
    })

    assert response.status_code == 200
    assert response.json()["unpriced_food_ids"] == ["SF106"]
    assert response.json()["exact_total_cost_rm"] == 0
