"""W1/W2 catalogue tests (2026-09-16): B40-staple display order and the
two-layer visibility contract for GET /api/v1/foods.

W1: the catalogue exit order is curated by data/catalogue_priority.csv
    (22 pinned B40 staples first, everything else stable by food_id);
    the CSV is fail-open -- missing/empty must never break the endpoint.
W2: `include_hidden=false` (default) serves exactly the catalogue-eligible
    planning layer; `?include_hidden=true` additionally serves the
    catalog_eligible=false foods for the what-you-have/pantry layer, with
    every price/nutrition availability flag reported honestly from the
    same fail-closed resolvers (never fabricated for a hidden food).
"""
import asyncio

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from services.api.app.main import app
from services.api.app.db import AsyncSessionLocal
from packages.optimizer.wisebasket_optimizer.portions import is_by_weight_food

client = TestClient(app)

B40_PINNED_FIRST = ["SF110", "SF018", "SF013", "SF006", "SF160"]
NEWLY_UNHIDDEN_B40 = {"SF051", "SF076", "SF106", "SF107", "SF160"}
KNOWN_HIDDEN_FOOD = "SF007"  # live chicken: ACTIVE but catalog_eligible=false


def _run(coro):
    async def runner():
        return await coro

    return asyncio.run(runner())


def _active_food_ids(*, eligible_only: bool) -> set[str]:
    sql = "select canonical_food_id from canonical_food where status = 'ACTIVE'"
    if eligible_only:
        sql += " and catalog_eligible"

    async def query():
        async with AsyncSessionLocal() as db:
            rows = (await db.execute(text(sql))).all()
            return {row[0] for row in rows}

    return _run(query())


def test_default_catalogue_serves_exactly_the_planning_layer_in_pinned_order():
    if not NEWLY_UNHIDDEN_B40 <= _active_food_ids(eligible_only=True):
        # The 2026-09-16 B40 unhide is a manual data patch applied to the
        # live DBs (ns_rebuild/UAT/PROD). Fresh migration-only CI databases
        # keep the 5 staples catalog_eligible=false - the visibility
        # contract itself is DB-relative (asserted below); only the pinned
        # staple membership needs the patch.
        pytest.skip("requires the 2026-09-16 B40 unhide data patch")
    body = client.get("/api/v1/foods").json()
    ids = [entry["food_id"] for entry in body]

    # Exactly the ACTIVE + catalogue-eligible planning layer (seed rows are
    # catalogue-eligible too, so compare against the same DB predicate).
    assert set(ids) == _active_food_ids(eligible_only=True)
    # The 5 B40 staples un-hidden on 2026-09-16 are all served.
    assert NEWLY_UNHIDDEN_B40 <= set(ids)
    # W1: curated B40 staples lead the catalogue, in CSV priority order.
    assert ids[:5] == B40_PINNED_FIRST
    # Tail after the pinned staples is the stable food_id order.
    pinned = set(ids[:22])
    tail = ids[22:]
    assert pinned.isdisjoint(tail)
    assert tail == sorted(tail)


def test_include_hidden_serves_everything_for_the_what_you_have_layer():
    hidden_default_ids = _active_food_ids(eligible_only=False) - _active_food_ids(
        eligible_only=True
    )
    # The fixture world keeps at least one catalog_eligible=false food.
    assert KNOWN_HIDDEN_FOOD in hidden_default_ids

    default_body = client.get("/api/v1/foods").json()
    default_ids = {entry["food_id"] for entry in default_body}
    assert KNOWN_HIDDEN_FOOD not in default_ids

    res = client.get("/api/v1/foods", params={"include_hidden": "true"})
    assert res.status_code == 200
    body = res.json()
    ids = {entry["food_id"] for entry in body}

    # The full ACTIVE catalogue: planning layer + every hidden food.
    assert ids == _active_food_ids(eligible_only=False)
    assert hidden_default_ids <= ids
    assert len(ids) > len(default_ids)

    # Hidden foods are served with honest availability flags: the flag is
    # exactly "the real resolver found a price", never fabricated.
    by_id = {entry["food_id"]: entry for entry in body}
    for food_id in hidden_default_ids:
        entry = by_id[food_id]
        assert entry["price_available"] == (
            entry["price_rm_per_100g"] is not None
        ), f"{food_id}: price_available must mirror the resolved price"
        assert entry["nutrition_available"] == any(
            value is not None for value in entry["nutrients"].values()
        ), f"{food_id}: nutrition_available must mirror the resolved nutrients"
        assert (entry["price_rm_per_100g_purchase"] is not None) == entry["price_available"]
        assert entry["sold_by_weight"] == is_by_weight_food(
            food_id, entry["category"], entry["name"]
        )


def test_priority_ordering_fails_open_without_the_csv(monkeypatch):
    monkeypatch.setattr(
        "services.api.app.main.load_catalogue_priority", lambda: {}
    )
    body = client.get("/api/v1/foods").json()
    ids = [entry["food_id"] for entry in body]
    # No curation available -> the whole catalogue falls back to plain
    # food_id order, and the endpoint still succeeds.
    assert ids == sorted(ids)


def test_priority_loader_fails_open_when_csv_missing(monkeypatch):
    from services.api.app.services import catalogue_priority

    monkeypatch.setattr(
        catalogue_priority, "_CSV", catalogue_priority._CSV.with_name("nope.csv")
    )
    catalogue_priority.load_catalogue_priority.cache_clear()
    try:
        assert catalogue_priority.load_catalogue_priority() == {}
    finally:
        catalogue_priority.load_catalogue_priority.cache_clear()
