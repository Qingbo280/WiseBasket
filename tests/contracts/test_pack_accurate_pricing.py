"""TDD contracts for checkout-accurate fixed-pack and by-weight prices."""
from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from services.api.app.services.nearby_price_service import (
    FETCH_NEARBY_PRICE_ROWS_SQL,
    find_nearby_food_prices,
)


def test_latest_price_query_has_no_hard_age_cutoff() -> None:
    sql = str(FETCH_NEARBY_PRICE_ROWS_SQL)

    assert "max_age_days" not in sql
    assert "observed_date >=" not in sql


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


def _row(
    observation_id: int,
    *,
    location_id: int = 1,
    original_unit: str,
    purchase_mass_g: float,
    price_rm: float,
) -> SimpleNamespace:
    return SimpleNamespace(
        _mapping={
            "price_observation_id": observation_id,
            "location_id": location_id,
            "price_rm": price_rm,
            "original_unit": original_unit,
            "purchase_mass_g": purchase_mass_g,
            "price_rm_per_100g_purchase": price_rm / purchase_mass_g * 100,
            "observed_date": date(2026, 9, 20),
            "source_dataset_version": "PRICECATCHER_2026-09",
            "location_name": "Test Store",
            "premise_type": "SUPERMARKET",
            "state": "Selangor",
            "district": "Petaling",
            "address": "Test address",
            "latitude": 3.1,
            "longitude": 101.6,
        }
    )


@pytest.mark.asyncio
async def test_fixed_pack_prefers_an_exact_registered_pack() -> None:
    result = await find_nearby_food_prices(
        _Session([
            _row(1, original_unit="10 kg", purchase_mass_g=10_000, price_rm=25.90),
            _row(2, original_unit="2 kg", purchase_mass_g=2_000, price_rm=8.40),
        ]),
        "SF110",
        state="Selangor",
        district="Petaling",
        quantity_g=2_000,
        purchase_mode="FIXED_PACK",
    )

    quote = result.quotes[0]
    assert quote.original_unit == "2 kg"
    assert quote.purchase_units == 1
    assert quote.minimum_purchase_cost_rm == 8.40
    assert quote.pricing_method == "EXACT_PACK"


@pytest.mark.asyncio
async def test_fixed_pack_multiplies_whole_bottles() -> None:
    result = await find_nearby_food_prices(
        _Session([
            _row(1, original_unit="1 L bottle", purchase_mass_g=1_000, price_rm=3.20),
        ]),
        "MILK",
        state="Selangor",
        district="Petaling",
        quantity_g=2_000,
        purchase_mode="FIXED_PACK",
    )

    quote = result.quotes[0]
    assert quote.purchase_units == 2
    assert quote.minimum_purchase_cost_rm == 6.40
    assert quote.pricing_method == "MULTIPLE_PACKS"


@pytest.mark.asyncio
async def test_fixed_pack_never_prorates_a_larger_egg_tray() -> None:
    result = await find_nearby_food_prices(
        _Session([
            _row(1, original_unit="30 biji", purchase_mass_g=1_740, price_rm=10.10),
        ]),
        "SF018",
        state="Selangor",
        district="Petaling",
        quantity_g=580,
        purchase_mode="FIXED_PACK",
    )

    quote = result.quotes[0]
    assert quote.purchase_units == 1
    assert quote.minimum_purchase_cost_rm == 10.10
    assert quote.pricing_method == "LARGER_PACK"


@pytest.mark.asyncio
async def test_by_weight_food_keeps_linear_pricing() -> None:
    result = await find_nearby_food_prices(
        _Session([
            _row(1, original_unit="1 kg", purchase_mass_g=1_000, price_rm=12.00),
        ]),
        "SF006",
        state="Selangor",
        district="Petaling",
        quantity_g=250,
        purchase_mode="BY_WEIGHT",
    )

    quote = result.quotes[0]
    assert quote.purchase_units is None
    assert quote.minimum_purchase_cost_rm == 3.00
    assert quote.pricing_method == "BY_WEIGHT"


@pytest.mark.asyncio
async def test_fixed_pack_without_purchase_mass_is_not_prorated() -> None:
    row = _row(1, original_unit="tray", purchase_mass_g=1_000, price_rm=10.00)
    row._mapping["purchase_mass_g"] = None

    result = await find_nearby_food_prices(
        _Session([row]),
        "FIXED",
        state="Selangor",
        district="Petaling",
        quantity_g=250,
        purchase_mode="FIXED_PACK",
    )

    assert result.quotes == []


@pytest.mark.asyncio
async def test_by_weight_returns_one_quote_per_store_across_pack_variants() -> None:
    result = await find_nearby_food_prices(
        _Session([
            _row(1, original_unit="500 g", purchase_mass_g=500, price_rm=6.50),
            _row(2, original_unit="1 kg", purchase_mass_g=1_000, price_rm=12.00),
        ]),
        "SF006",
        state="Selangor",
        district="Petaling",
        quantity_g=250,
        purchase_mode="BY_WEIGHT",
    )

    assert len(result.quotes) == 1
    assert result.quotes[0].minimum_purchase_cost_rm == 3.00
