#!/usr/bin/env python3
"""Teammate data handoff export -- DELIVERABLE ONLY, never committed.

Produces two CSVs for a teammate needing food/location data:

  teammate_food_location.csv       -- one row per (food, state, district):
      canonical_food_id, food_item_en, food_item_ms, category, detail_level,
      state, district, premise_count, latest_price_date

  teammate_food_store_location.csv -- one row per (food, store/premise):
      canonical_food_id, food_item_en, food_item_ms, premise_name,
      premise_type, district, state, latest_price, purchase_unit,
      latest_price_date, source

  teammate_food_tags.csv           -- one row per (food, evidence-backed tag):
      canonical_food_id, food_item_en, food_item_ms, tag_text, tag_category,
      evidence_source (see services/api/app/services/food_tag_service.py)

Only fields genuinely present in the schema are used -- no invented
coordinates, no fabricated distances. All three exports are derived entirely
from real food_price_observation/food_nutrition rows (source_dataset_version
matching the real PriceCatcher tag shapes, or real MyFCD-sourced nutrition),
never synthetic/seed data.

Usage:
    python scripts/export_teammate_data.py --out-dir /path/outside/the/repo

The --out-dir MUST be outside this repository's working tree (checked and
refused otherwise) -- these are teammate deliverables, not tracked data.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import sys
from pathlib import Path

from sqlalchemy import text

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from services.api.app.db import AsyncSessionLocal  # noqa: E402
from services.api.app.services.representative_price import (  # noqa: E402
    REAL_MARKET_SOURCE_SQL_REGEX,
)

FOOD_LOCATION_SQL = text(
    f"""
    select
        cf.canonical_food_id,
        cf.canonical_name,
        cf.canonical_name_ms,
        cf.category,
        loc.state,
        loc.district,
        count(distinct fpo.location_id) as premise_count,
        max(fpo.observed_date) as latest_price_date
    from canonical_food cf
    join food_price_observation fpo on fpo.canonical_food_id = cf.canonical_food_id
    join location loc on loc.location_id = fpo.location_id
    where cf.status = 'ACTIVE'
      and fpo.quality_status = 'PASS'
      and fpo.source_dataset_version ~ '{REAL_MARKET_SOURCE_SQL_REGEX}'
    group by cf.canonical_food_id, cf.canonical_name, cf.canonical_name_ms, cf.category,
             loc.state, loc.district
    order by cf.canonical_food_id, loc.state, loc.district
    """
)

FOOD_STORE_LOCATION_SQL = text(
    f"""
    select distinct on (cf.canonical_food_id, loc.location_id)
        cf.canonical_food_id,
        cf.canonical_name,
        cf.canonical_name_ms,
        loc.location_name,
        loc.premise_type,
        loc.district,
        loc.state,
        fpo.price_rm,
        fpo.original_unit,
        fpo.observed_date,
        fpo.source_dataset_version
    from canonical_food cf
    join food_price_observation fpo on fpo.canonical_food_id = cf.canonical_food_id
    join location loc on loc.location_id = fpo.location_id
    where cf.status = 'ACTIVE'
      and fpo.quality_status = 'PASS'
      and fpo.source_dataset_version ~ '{REAL_MARKET_SOURCE_SQL_REGEX}'
    order by cf.canonical_food_id, loc.location_id, fpo.observed_date desc, fpo.price_observation_id desc
    """
)


def _refuse_if_inside_repo(out_dir: Path) -> None:
    resolved = out_dir.resolve()
    if REPO_ROOT.resolve() in resolved.parents or resolved == REPO_ROOT.resolve():
        raise SystemExit(
            f"REFUSING: --out-dir {resolved} is inside the repository working tree "
            f"({REPO_ROOT.resolve()}). Teammate exports must never be committed -- "
            f"choose a path outside the repo."
        )


async def export_food_location(db, out_path: Path) -> int:
    rows = (await db.execute(FOOD_LOCATION_SQL)).all()
    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "canonical_food_id", "food_item_en", "food_item_ms", "category", "detail_level",
            "state", "district", "premise_count", "latest_price_date",
        ])
        for r in rows:
            m = r._mapping
            w.writerow([
                m["canonical_food_id"], m["canonical_name"], m["canonical_name_ms"] or m["canonical_name"],
                m["category"], "",  # detail_level filled in by caller (needs async compute_detail per food)
                m["state"] or "", m["district"] or "", m["premise_count"],
                m["latest_price_date"].isoformat() if m["latest_price_date"] else "",
            ])
    return len(rows)


async def export_food_store_location(db, out_path: Path) -> int:
    rows = (await db.execute(FOOD_STORE_LOCATION_SQL)).all()
    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "canonical_food_id", "food_item_en", "food_item_ms", "premise_name", "premise_type",
            "district", "state", "latest_price", "purchase_unit", "latest_price_date", "source",
        ])
        for r in rows:
            m = r._mapping
            w.writerow([
                m["canonical_food_id"], m["canonical_name"], m["canonical_name_ms"] or m["canonical_name"],
                m["location_name"], m["premise_type"] or "", m["district"] or "", m["state"] or "",
                m["price_rm"], m["original_unit"] or "",
                m["observed_date"].isoformat() if m["observed_date"] else "",
                m["source_dataset_version"],
            ])
    return len(rows)


async def export_food_tags(db, out_path: Path) -> int:
    """One row per (food, tag) -- only foods with at least one qualifying,
    evidence-backed tag appear. See services/api/app/services/
    food_tag_service.py for the thresholds/citations; nothing here
    re-derives or duplicates that logic."""
    from sqlalchemy import text as _text

    from services.api.app.services.food_tag_service import compute_tags

    identity_rows = (
        await db.execute(_text(
            "select canonical_food_id, canonical_name, canonical_name_ms "
            "from canonical_food where status = 'ACTIVE' order by canonical_food_id"
        ))
    ).all()

    n = 0
    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "canonical_food_id", "food_item_en", "food_item_ms",
            "tag_text", "tag_category", "evidence_source",
        ])
        for row in identity_rows:
            m = row._mapping
            tags = await compute_tags(db, m["canonical_food_id"])
            for tag in tags:
                w.writerow([
                    m["canonical_food_id"], m["canonical_name"], m["canonical_name_ms"] or m["canonical_name"],
                    tag.text, tag.category, tag.evidence_source,
                ])
                n += 1
    return n


async def _run(out_dir: Path) -> None:
    from services.api.app.services.catalogue_detail_service import compute_detail
    from sqlalchemy import text as _text

    out_dir.mkdir(parents=True, exist_ok=True)
    loc_path = out_dir / "teammate_food_location.csv"
    store_path = out_dir / "teammate_food_store_location.csv"
    tags_path = out_dir / "teammate_food_tags.csv"

    async with AsyncSessionLocal() as db:
        n_loc = await export_food_location(db, loc_path)
        n_store = await export_food_store_location(db, store_path)
        n_tags = await export_food_tags(db, tags_path)

        # Backfill detail_level per food (small number of distinct foods,
        # cheap to compute once and patch the CSV rather than complicate the
        # aggregate SQL above with per-row async calls).
        food_ids = [
            r[0] for r in (
                await db.execute(_text("select distinct canonical_food_id from canonical_food where status='ACTIVE'"))
            ).all()
        ]
        detail_by_id = {fid: (await compute_detail(db, fid)).detail_level for fid in food_ids}

    import csv as _csv
    rows = list(_csv.reader(loc_path.open(encoding="utf-8")))
    header, body = rows[0], rows[1:]
    detail_idx = header.index("detail_level")
    id_idx = header.index("canonical_food_id")
    for row in body:
        row[detail_idx] = detail_by_id.get(row[id_idx], "")
    with loc_path.open("w", newline="", encoding="utf-8") as f:
        w = _csv.writer(f)
        w.writerow(header)
        w.writerows(body)

    print(f"Wrote {n_loc} rows to {loc_path}")
    print(f"Wrote {n_store} rows to {store_path}")
    print(f"Wrote {n_tags} rows to {tags_path}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", required=True, type=Path)
    args = ap.parse_args()
    _refuse_if_inside_repo(args.out_dir)
    asyncio.run(_run(args.out_dir))
    return 0


if __name__ == "__main__":
    sys.exit(main())
