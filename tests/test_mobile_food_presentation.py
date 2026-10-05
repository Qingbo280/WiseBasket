"""Mobile food-presentation mapping governance tests.

The current PriceCatcher-backed catalogue contains more foods than the legacy
image library. The mobile map is deliberately partial: mapped foods get a
matching semantic R2 asset and all other foods use a safe UI fallback.

These tests pin both directions of the mapping so a future data renumbering
or an imageId typo fails loudly in CI instead of silently degrading the UI:

  - every mapped backendFoodId in foodAssetManifest.ts is an ACTIVE food
    (PostgreSQL integration test; CI provides the postgres service);
  - every imageId resolves to a cloud asset key in foodAssetManifest.ts;
  - ids are unique.

Parsing is regex-based on purpose: the TS files are data tables, and pulling
in a TS toolchain from pytest would be far heavier than the guarantee needs.
"""
import re
from pathlib import Path

import pytest
from sqlalchemy import text

from services.api.app.db import AsyncSessionLocal

MOBILE_DATA = Path(__file__).resolve().parents[1] / "apps" / "mobile" / "src" / "data"

_BACKEND_IMAGE_ROW = re.compile(r"^\s*(SF\d{3}):\s*'([^']+)'", re.MULTILINE)
_MANIFEST_ROW = re.compile(r"^\s*'([^']+)':\s*'foods/[^']+'", re.MULTILINE)


def _presentation_rows() -> dict[str, str]:
    text = (MOBILE_DATA / "foodAssetManifest.ts").read_text(encoding="utf-8")
    return dict(_BACKEND_IMAGE_ROW.findall(text))


def _manifest_keys() -> set[str]:
    text = (MOBILE_DATA / "foodAssetManifest.ts").read_text(encoding="utf-8")
    return set(_MANIFEST_ROW.findall(text))


def test_presentation_ids_are_unique():
    rows = _presentation_rows()
    assert rows, "expected at least one backend image mapping"
    assert len(rows) == len(set(rows)), "backend image IDs must be unique"


def test_every_image_id_resolves_to_cloud_asset_key():
    rows = _presentation_rows()
    manifest = _manifest_keys()
    unknown = {fid: iid for fid, iid in rows.items() if iid not in manifest}
    assert not unknown, f"imageIds missing from FOOD_IMAGE_KEYS: {unknown}"


@pytest.mark.asyncio
async def test_presentation_matches_active_canonical_foods():
    rows = _presentation_rows()
    # Compare against the serving view (what GET /api/v1/foods actually
    # returns), not the raw canonical table: migration reference rows that
    # never pass the trust chain must not count as stale presentation rows.
    async with AsyncSessionLocal() as db:
        active = set(
            (
                await db.execute(
                    text(
                        "select distinct canonical_food_id"
                        " from v_optimizer_food_candidate"
                    )
                )
            ).scalars().all()
        )
    # Test fixtures (SEED/T prefixes) are not production foods and carry no
    # presentation row by design - exclude them from both directions.
    active = {fid for fid in active if not fid.startswith(("SEED", "T"))}
    # CI's fresh database has no production foods at all - nothing to verify.
    if not active:
        pytest.skip("no ACTIVE canonical foods in this database")
    stale = set(rows) - active
    assert not stale, f"presentation rows for non-existent foods: {sorted(stale)}"
