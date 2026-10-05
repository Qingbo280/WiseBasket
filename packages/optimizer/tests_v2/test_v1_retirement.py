from fastapi.testclient import TestClient

from services.api.app.main import app


client = TestClient(app)


def test_v1_plan_endpoint_is_retired_for_legacy_payload():
    response = client.post(
        "/api/v1/plans",
        json={"budget_rm": 80, "days": 7, "adults": 2, "children": 0},
    )

    assert response.status_code == 410
    assert response.json() == {
        "detail": {
            "code": "PLANNER_V1_RETIRED",
            "message": (
                "The basket-first planner has been retired while the "
                "recipe-first planner is rebuilt."
            ),
        }
    }


def test_v1_plan_endpoint_cannot_route_persisted_payload_to_old_code():
    response = client.post(
        "/api/v1/plans",
        json={
            "household": {"adults": 1, "children": 2},
            "available_budget_rm": 150,
            "planning_days": 7,
        },
    )

    assert response.status_code == 410
    assert response.json()["detail"]["code"] == "PLANNER_V1_RETIRED"
