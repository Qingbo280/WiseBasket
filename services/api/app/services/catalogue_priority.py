"""Curated B40-staple display order for GET /api/v1/foods (2026-09-16 W1).

Code-layer curation table, same pattern as week_floors.csv /
recommend_tags.csv: editing the order = edit the CSV + push, Railway
watchPatterns rebuilds automatically; no migration, no DB column.

Only the first screenful of the catalogue is curated (the 22 B40 staples
below); every other food keeps its stable canonical_food_id order right
after them. Fail-open by design: a missing/empty CSV or a row with an
unknown food_id changes nothing and can never break the catalogue --
foods absent from the table simply sort by food_id as before.
"""
from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path

_CSV = Path(__file__).resolve().parent.parent / "data" / "catalogue_priority.csv"


@lru_cache(maxsize=1)
def load_catalogue_priority() -> dict[str, int]:
    """food_id -> ascending display priority (lower = shown first).

    Empty dict when the CSV is missing (fail-open to plain food_id order)."""
    priority: dict[str, int] = {}
    try:
        with _CSV.open("r", encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                food_id = (row.get("food_id") or "").strip()
                raw = (row.get("priority") or "").strip()
                if not food_id or not raw:
                    continue
                priority[food_id] = int(float(raw))
    except FileNotFoundError:
        return {}
    return priority


def catalogue_priority_or_fallback(priority: dict[str, int], food_id: str) -> int:
    """Sort key head: curated rank, or a large sentinel (stable food_id tail)."""
    return priority.get(food_id, 1_000_000)
