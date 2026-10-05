"""Seed Malaysian home-style meal templates into meal_template tables (local dev).

Ingredient resolution is NAME-BASED and exact-match only: every recipe
ingredient (authored against the new 201-food handoff catalogue) is resolved
to a LOCAL canonical_food row by exact normalized-name equality (canonical
name or the OVERRIDES table below). Anything that does not resolve exactly is
skipped -- the seed can never create a semantically wrong mapping.

The OLD/NEW canonical ID namespaces differ between the handoff crosswalk and
the local i2-pack database, so IDs are never used for matching here.

Idempotent: re-seeding replaces all WB_<CODE> templates.

Usage (repo root, local docker PG):
    $env:DATABASE_URL='postgresql+asyncpg://wisebasket:wisebasket@localhost:5432/wisebasket'
    $env:PYTHONPATH=(Get-Location).Path
    python scripts/seed_meal_templates.py
"""
from __future__ import annotations

import asyncio
import csv
import re
import sys
from pathlib import Path

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.api.app.db import (  # noqa: E402
    MealTemplate,
    MealTemplateIngredient,
)

HANDOFF = Path(__file__).resolve().parent.parent.parent / "wisebasket_food_data_FINAL_HANDOFF"

# New-catalogue food id -> EXACT local canonical_food.canonical_name.
# None = intentionally skipped (no trustworthy local equivalent).
OVERRIDES: dict[str, str | None] = {
    "SF110": "white rice (raw)",
    "SF109": "wet yellow noodles",
    "SF108": "kuey teow",
    "SF002": "local beef thigh",
    "SF124": "red lentils",
    "SF013": "whole chicken",
    "SF035": "indian mackerel",
    "SF151": "table salt",
    "SF120": "palm cooking oil",
    "SF129": "sweet soy sauce",
    "SF058": "green chili",
    "SF102": "fresh coconut milk",
    "SF160": "bread",
    "SF195": "instant oats",
    "SF161": "instant curry noodles",
    "SF063": "round eggplant",
    "SF176": "full cream milk",
    "SF104": "grated coconut",
    "SF156": "canned sardine",
    "SF011": "wheat flour",
    # --- intentionally skipped ---
    "SF022": None,  # white prawn: not in local catalogue
    "SF031": None,  # snakehead fish: not in local catalogue
    "SF042": None,  # squid: not in local catalogue
    "SF052": None,  # dried shrimp: not in local catalogue
    "SF134": None,  # soup spices: not in local catalogue
    "SF138": None,  # fried rice seasoning: not in local catalogue
    "SF070": None,  # fresh turmeric: not in local catalogue
    "SF065": None,  # leek: not in local catalogue
    "SF172": None,  # peanut butter: not in local catalogue
}

# (code, name, meal_type, servings, [(new_catalogue_food_id, grams_per_serving)])
RECIPES: list[tuple[str, str, str, int, list[tuple[str, float]]]] = [
    ("WB_KARI_AYAM", "Kari Ayam", "DINNER", 4, [("SF006", 120), ("SF055", 80), ("SF133", 5), ("SF120", 10), ("SF110", 90)]),
    ("WB_AYAM_KUNYIT", "Ayam Goreng Berempah", "DINNER", 4, [("SF013", 130), ("SF076", 15), ("SF110", 90), ("SF058", 20)]),
    ("WB_TELUR_SAMBAL", "Telur Masak Sambal", "DINNER", 4, [("SF018", 100), ("SF058", 15), ("SF054", 15), ("SF110", 90)]),
    ("WB_IKAN_GORENG", "Ikan Kembung Goreng", "DINNER", 4, [("SF025", 120), ("SF110", 90), ("SF151", 2), ("SF083", 10)]),
    ("WB_SARDIN_SOS", "Sardin Masak Sos Tomato", "DINNER", 4, [("SF156", 100), ("SF072", 60), ("SF054", 15), ("SF110", 90)]),
    ("WB_SAYUR_CAMPUR", "Sayur Campur Goreng", "DINNER", 4, [("SF078", 80), ("SF084", 60), ("SF054", 15), ("SF120", 10), ("SF110", 90)]),
    ("WB_KANGKUNG", "Kangkung Tumis Bawang Putih", "DINNER", 4, [("SF074", 100), ("SF058", 10), ("SF069", 8), ("SF110", 90)]),
    ("WB_SUP_AYAM", "Sup Ayam", "DINNER", 4, [("SF013", 120), ("SF073", 40), ("SF056", 20), ("SF110", 90)]),
    ("WB_MEE_GORENG", "Mee Goreng", "DINNER", 4, [("SF109", 150), ("SF018", 50), ("SF076", 40), ("SF129", 10), ("SF120", 10)]),
    ("WB_NASI_GORENG", "Nasi Goreng", "DINNER", 4, [("SF110", 120), ("SF018", 50), ("SF054", 15), ("SF058", 15), ("SF120", 10)]),
    ("WB_BUBUR_NASI", "Bubur Nasi", "BREAKFAST", 4, [("SF110", 60), ("SF018", 50), ("SF056", 10), ("SF151", 2)]),
    ("WB_KARI_DHAL", "Kari Dhal", "DINNER", 4, [("SF124", 80), ("SF133", 5), ("SF110", 90), ("SF120", 8)]),
    ("WB_TEMPE_KICAP", "Tempe Goreng Kicap", "DINNER", 4, [("SF106", 100), ("SF129", 10), ("SF069", 5), ("SF110", 90)]),
    ("WB_TAUHU_GORENG", "Tauhu Goreng Taugeh", "DINNER", 4, [("SF107", 150), ("SF076", 40), ("SF129", 10), ("SF110", 90)]),
    ("WB_TUMIS_BAYAM", "Tumis Bayam Bawang Putih", "DINNER", 4, [("SF062", 100), ("SF069", 8), ("SF120", 8), ("SF110", 90)]),
    ("WB_KAILAN_IKAN", "Kailan Goreng Ikan Bilis", "DINNER", 4, [("SF078", 100), ("SF051", 15), ("SF069", 8), ("SF110", 90)]),
    ("WB_GULAI_IKAN", "Gulai Ikan", "DINNER", 4, [("SF035", 130), ("SF133", 5), ("SF072", 50), ("SF110", 90)]),
    ("WB_IKAN_BILIS_SAMBAL", "Ikan Bilis Sambal", "DINNER", 4, [("SF051", 30), ("SF058", 15), ("SF054", 15), ("SF110", 90)]),
    ("WB_TUMIS_KOBIS", "Tumis Kobis", "DINNER", 4, [("SF055", 120), ("SF054", 15), ("SF120", 8), ("SF110", 90)]),
    ("WB_TERUNG_SAMBAL", "Terung Masak Sambal", "DINNER", 4, [("SF063", 120), ("SF058", 10), ("SF110", 90)]),
    ("WB_DAGING_KENTANG", "Daging Masak Kentang", "DINNER", 4, [("SF002", 100), ("SF057", 120), ("SF129", 10), ("SF110", 90)]),
    ("WB_SAYUR_BENING", "Sayur Bening Bayam", "DINNER", 4, [("SF062", 80), ("SF056", 10), ("SF110", 90)]),
    ("WB_KACANG_PANJANG", "Tumis Kacang Panjang", "DINNER", 4, [("SF084", 100), ("SF054", 15), ("SF069", 5), ("SF110", 90)]),
    ("WB_DAGING_KICAP", "Daging Masak Kicap", "DINNER", 4, [("SF002", 100), ("SF129", 15), ("SF054", 15), ("SF110", 90)]),
    ("WB_BIHUN_GORENG", "Bihun Goreng", "DINNER", 4, [("SF159", 60), ("SF018", 50), ("SF076", 30), ("SF129", 10), ("SF120", 10)]),
    ("WB_NASI_LEMAK_EKO", "Nasi Lemak Ekonomi", "BREAKFAST", 4, [("SF110", 100), ("SF051", 10), ("SF018", 50), ("SF058", 5)]),
    ("WB_ROTI_TELUR", "Roti Telur", "BREAKFAST", 1, [("SF160", 60), ("SF018", 50), ("SF171", 5)]),
    ("WB_KUEY_TEOW", "Kuey Teow Goreng", "DINNER", 4, [("SF108", 150), ("SF076", 40), ("SF129", 10), ("SF120", 10)]),
    ("WB_SAMBAL_BENDI", "Sambal Bendi Lemak", "DINNER", 4, [("SF073", 80), ("SF058", 10), ("SF102", 40), ("SF110", 90)]),
    ("WB_BUBUR_KACANG", "Bubur Kacang Merah", "SNACK", 4, [("SF124", 60), ("SF176", 80), ("SF118", 10)]),
]


def _norm(name: str) -> str:
    name = re.sub(r"\(.*?\)", "", name.lower())
    return re.sub(r"[^a-z0-9]+", " ", name).strip()


def load_handoff_names() -> dict[str, tuple[str, str]]:
    path = HANDOFF / "canonical_food_FINAL.csv"
    out: dict[str, tuple[str, str]] = {}
    with path.open(encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            out[row["canonical_food_id"]] = (row["canonical_name"], row["canonical_name_ms"])
    return out


async def main() -> None:
    import os
    url = os.environ.get(
        'DATABASE_URL',
        'postgresql+asyncpg://wisebasket:wisebasket@localhost:5432/wisebasket')
    engine = create_async_engine(url)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    handoff_names = load_handoff_names()

    async with Session() as db:
        local_rows = (await db.execute(
            text("select canonical_food_id, canonical_name from canonical_food"))).all()
        local_ids = {r[0] for r in local_rows}
        name_to_id = {_norm(r[1]): r[0] for r in local_rows}
        candidate_ids = set((await db.execute(
            text("select distinct canonical_food_id from v_optimizer_food_candidate"))).scalars())
        local_names = dict(local_rows)

        old_ids = (await db.execute(
            select(MealTemplate.meal_template_id).where(MealTemplate.meal_name.like("WB\\_%"))
        )).scalars().all()
        if old_ids:
            await db.execute(delete(MealTemplateIngredient).where(
                MealTemplateIngredient.meal_template_id.in_(old_ids)))
            await db.execute(delete(MealTemplate).where(MealTemplate.meal_template_id.in_(old_ids)))
            print(f"cleared {len(old_ids)} previous WB_ templates")

        inserted = skipped = 0
        for code, name, meal_type, servings, ingredients in RECIPES:
            rows: list[tuple[str, float]] = []
            for new_id, grams in ingredients:
                override = OVERRIDES.get(new_id)
                keys: list[str] = []
                if override is None and new_id in OVERRIDES:
                    skipped += 1
                    continue
                # OVERRIDES point at legacy-DB names; the 201-namespace DB
                # uses handoff names -- try the override first, then the
                # handoff canonical_name / canonical_name_ms as fallback.
                if override:
                    keys.append(override)
                keys.extend(handoff_names.get(new_id, ()))
                resolved = next((name_to_id[_norm(k)] for k in keys if _norm(k) in name_to_id), None)
                if resolved is None:
                    skipped += 1
                    print(f"  skip {code}: {new_id} ({handoff_names.get(new_id, ('?',))[0]}) no exact local name match")
                    continue
                rows.append((resolved, grams))
            if len(rows) < 2:
                print(f"  DROP {code}: only {len(rows)} resolvable ingredients")
                continue
            tpl = MealTemplate(meal_name=code, meal_type=meal_type, servings=servings, active=True)
            db.add(tpl)
            await db.flush()
            for old_id, grams in rows:
                db.add(MealTemplateIngredient(
                    meal_template_id=tpl.meal_template_id,
                    canonical_food_id=old_id,
                    grams_per_serving=grams,
                ))
            n_cand = sum(1 for r, _ in rows if r in candidate_ids)
            inserted += 1
            print(f"  ok {code:<20} {len(rows)} ingredients ({n_cand} candidates): "
                  + ", ".join(local_names[r] for r, _ in rows))

        await db.commit()
    await engine.dispose()
    print(f"\nseeded {inserted} templates, skipped {skipped} ingredients")


if __name__ == "__main__":
    asyncio.run(main())
