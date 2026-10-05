import httpx
import pytest
from fastapi.testclient import TestClient

from services.api.app.config import Settings
from services.api.app.main import app
from services.api.app.schemas import LocationSearchSuggestion
from services.api.app.services import location_search
from services.api.app.services.location_search import (
    map_geoapify_suggestions,
    search_geoapify_locations,
)


client = TestClient(app)


def test_map_geoapify_suggestions_returns_ui_contract():
    suggestions = map_geoapify_suggestions(
        {
            "results": [
                {
                    "place_id": "51f5d2b3",
                    "name": "Sunway Geo Avenue",
                    "address_line1": "Sunway Geo Avenue",
                    "address_line2": "Bandar Sunway, Selangor, Malaysia",
                    "formatted": "Sunway Geo Avenue, Bandar Sunway, Selangor, Malaysia",
                    "lat": 3.0647651,
                    "lon": 101.6088508,
                    "state": "Selangor",
                    "county": "Petaling",
                    "district": "Sunway City",
                },
                {"formatted": "Broken row", "lat": None, "lon": 101.0},
            ]
        }
    )

    assert suggestions == [
        LocationSearchSuggestion(
            id="geoapify:51f5d2b3",
            label="Sunway Geo Avenue",
            address="Sunway Geo Avenue, Bandar Sunway, Selangor, Malaysia",
            latitude=3.0647651,
            longitude=101.6088508,
            state="Selangor",
            district="Petaling",
        )
    ]


def test_map_geoapify_suggestions_deduplicates_place_ids():
    row = {
        "place_id": "same-place",
        "address_line1": "Bangsar South",
        "formatted": "Bangsar South, Kuala Lumpur, Malaysia",
        "lat": 3.1129733,
        "lon": 101.6667294,
    }

    suggestions = map_geoapify_suggestions({"results": [row, row]})

    assert len(suggestions) == 1


@pytest.mark.asyncio
async def test_geoapify_search_uses_autocomplete_with_malaysia_filter(monkeypatch):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"results": []})

    transport = httpx.MockTransport(handler)
    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        location_search.httpx,
        "AsyncClient",
        lambda **kwargs: real_client(transport=transport, **kwargs),
    )

    results = await search_geoapify_locations(
        "sunway geo",
        Settings(geoapify_api_key="test-key"),
        limit=3,
    )

    assert results == []
    assert len(requests) == 1
    assert requests[0].url.params["text"] == "sunway geo"
    assert requests[0].url.params["filter"] == "countrycode:my"
    assert requests[0].url.params["limit"] == "3"
    assert requests[0].url.params["apiKey"] == "test-key"


def test_location_search_rejects_short_query():
    response = client.get("/api/v1/locations/search?q=kl")

    assert response.status_code == 422


def test_location_search_endpoint_returns_suggestions(monkeypatch):
    async def fake_search(query, settings, limit):
        assert query == "bangsar"
        assert limit == 3
        return [
            LocationSearchSuggestion(
                id="geoapify:bangsar",
                label="Bangsar",
                address="Bangsar, Kuala Lumpur, Malaysia",
                latitude=3.1291,
                longitude=101.6791,
                state="Kuala Lumpur",
                district="Lembah Pantai",
            )
        ]

    monkeypatch.setattr("services.api.app.main.search_geoapify_locations", fake_search)

    response = client.get("/api/v1/locations/search?q=bangsar&limit=3")

    assert response.status_code == 200
    assert response.json() == {
        "results": [
            {
                "id": "geoapify:bangsar",
                "label": "Bangsar",
                "address": "Bangsar, Kuala Lumpur, Malaysia",
                "latitude": 3.1291,
                "longitude": 101.6791,
                "state": "Kuala Lumpur",
                "district": "Lembah Pantai",
            }
        ]
    }


def test_location_search_endpoint_returns_empty_results(monkeypatch):
    async def fake_search(query, settings, limit):
        return []

    monkeypatch.setattr("services.api.app.main.search_geoapify_locations", fake_search)

    response = client.get("/api/v1/locations/search?q=no-match")

    assert response.status_code == 200
    assert response.json() == {"results": []}


def test_location_search_endpoint_hides_missing_key(monkeypatch):
    monkeypatch.setattr("services.api.app.main.settings.geoapify_api_key", "")

    response = client.get("/api/v1/locations/search?q=bangsar")

    assert response.status_code == 503
    assert response.json()["detail"] == "Location search is temporarily unavailable."


def test_location_search_endpoint_hides_provider_failure(monkeypatch):
    async def fake_search(query, settings, limit):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr("services.api.app.main.search_geoapify_locations", fake_search)

    response = client.get("/api/v1/locations/search?q=bangsar")

    assert response.status_code == 503
    assert response.json()["detail"] == "Location search is temporarily unavailable."
