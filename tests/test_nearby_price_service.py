from datetime import date
from types import SimpleNamespace

import pytest

from services.api.app.services.nearby_price_service import (
    DEFAULT_RADIUS_KM,
    find_nearby_food_prices,
)


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _Session:
    def __init__(self, rows):
        self._rows = rows

    async def execute(self, _query, _params):
        return _Result(self._rows)


def _row(location_id, name, latitude, longitude, estimated_price_per_100g):
    return SimpleNamespace(
        _mapping={
            "price_observation_id": location_id,
            "location_id": location_id,
            "price_rm": estimated_price_per_100g,
            "original_unit": "1 kg",
            "price_rm_per_100g_purchase": estimated_price_per_100g,
            "observed_date": date(2026, 9, 1),
            "source_dataset_version": "PRICECATCHER_2026-09",
            "location_name": name,
            "premise_type": "SUPERMARKET",
            "state": "Selangor",
            "district": "Petaling",
            "address": name,
            "latitude": latitude,
            "longitude": longitude,
        }
    )


@pytest.mark.asyncio
async def test_gps_results_never_expand_beyond_five_km():
    session = _Session(
        [
            _row(1, "Inside radius", 3.149, 101.687, 2.0),
            _row(2, "Cheaper but too far", 3.199, 101.687, 1.0),
        ]
    )

    result = await find_nearby_food_prices(
        session,
        "SF110",
        latitude=3.139,
        longitude=101.687,
        quantity_g=1000,
    )

    assert result.radius_km == DEFAULT_RADIUS_KM
    assert result.radius_expanded is False
    assert [quote.store_name for quote in result.quotes] == ["Inside radius"]
    assert all(quote.distance_km <= DEFAULT_RADIUS_KM for quote in result.quotes)


@pytest.mark.asyncio
async def test_gps_returns_empty_instead_of_using_a_distant_store():
    session = _Session([_row(1, "Outside radius", 3.199, 101.687, 1.0)])

    result = await find_nearby_food_prices(
        session,
        "SF110",
        latitude=3.139,
        longitude=101.687,
        quantity_g=1000,
    )

    assert result.status == "NO_PRICE_IN_RADIUS"
    assert result.quotes == []


@pytest.mark.asyncio
async def test_gps_keeps_cheapest_first_within_the_radius():
    session = _Session(
        [
            _row(1, "Nearer but dearer", 3.140, 101.687, 2.0),
            _row(2, "Farther but cheaper", 3.159, 101.687, 1.0),
        ]
    )

    result = await find_nearby_food_prices(
        session,
        "SF110",
        latitude=3.139,
        longitude=101.687,
        quantity_g=1000,
    )

    assert [quote.store_name for quote in result.quotes] == [
        "Farther but cheaper",
        "Nearer but dearer",
    ]
