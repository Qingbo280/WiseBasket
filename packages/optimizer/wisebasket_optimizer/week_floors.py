# -*- coding: utf-8 -*-
"""Curated per-food single-person weekly purchase floors (PM proposal,
user decision 2026-09-16: the table lives in CODE, not the DB - same
pattern as recommend_tags.csv; editing values = edit CSV + push, Railway
watchPatterns rebuilds automatically).

Rationale: the blanket household-size floor (250/400/1000 g by bucket)
forces unrealistic lines - one adult does not buy 1 kg of lime or 500 g of
condensed milk for a week. Every food gets a curated SOLO-adult weekly
floor; the household floor scales linearly by effective persons
(adults + 0.6 * children), matching the PM's example (beef 0.5 kg solo ->
1 kg for 2 adults, 0.8 kg for 1A1C).

Fallback: a food missing from the CSV (new catalogue entry before the CSV
is extended) falls back to the HOUSEHOLD_BASKET_RULES_TABLE floor, so the
table can never break a solve.
"""
from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path
from typing import Dict, Optional

_CSV = Path(__file__).resolve().parent / "data" / "week_floors.csv"


@lru_cache(maxsize=1)
def load_week_floors() -> Dict[str, int]:
    """food_id -> solo-adult weekly floor (g/ml). Empty dict if the CSV is
    missing (fail-open to the legacy table floor)."""
    floors: Dict[str, int] = {}
    try:
        with _CSV.open("r", encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                fid = (row.get("food_id") or "").strip()
                raw = (row.get("solo_week_floor_g") or "").strip()
                if not fid or not raw:
                    continue
                floors[fid] = int(float(raw))
    except FileNotFoundError:
        return {}
    return floors


def solo_week_floor_g(food_id: str) -> Optional[int]:
    return load_week_floors().get(food_id)
