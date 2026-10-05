"""Pilot food data loader (I1 stand-in for the Epic 2 data pipeline).

Production: rows come from the PostgreSQL `optimiser_input` table produced by
the PriceCatcher + MyFCD + mapping-table pipeline.
I1: reads the packaged pilot_foods.csv, whose columns mirror that table.

DATA SWAP NOTE: when the Data Engineer's real dataset lands, only this file
and the CSV/loader contract should need changes - the solver consumes the
`Food` dataclass below and does not care where rows come from.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Set

DATA_FILE = Path(__file__).resolve().parent / "data" / "pilot_foods.csv"


def _opt_float(value: Optional[str]) -> Optional[float]:
    """Empty cell -> None (AC 2.0.3 / 2.0.7: missing data stays missing and is
    disclosed as 'unavailable'; it is never silently filled with a value)."""
    v = (value or "").strip()
    return float(v) if v else None

# nutrient key -> CSV column (per 100g edible portion)
_NUTRIENT_COLUMNS = {
    "energy_kcal": "kcal_100g",
    "protein_g": "protein_g_100g",
    "fibre_g": "fibre_g_100g",
    "iron_mg": "iron_mg_100g",
    "calcium_mg": "calcium_mg_100g",
    "vita_ug": "vita_ug_100g",
    "vitc_mg": "vitc_mg_100g",
}

CATEGORIES = ["protein", "vegetables", "fruit", "carbohydrate", "other"]


@dataclass(frozen=True)
class Food:
    food_id: str
    name: str
    name_ms: str
    category: str
    # None = no approved price mapped -> "Price unavailable" (AC 2.0.3).
    # Foods without a price are excluded from the optimiser candidate set.
    price_rm_per_100g: Optional[float]
    price_is_estimated: bool
    edible_fraction: float
    nutrients: dict          # nutrient_key -> Optional[float] per 100g edible
                             # portion; None = "Nutrition unavailable" (AC 2.0.7).
                             # The solver treats a missing nutrient as 0 contribution
                             # (conservative, never fabricates a value).
    allergen_tags: frozenset = field(default_factory=frozenset)
    # Dietary-pattern tags retained for candidate safety filtering.
    diet_tags: frozenset = field(default_factory=frozenset)
    # Retail purchase pack (mirrors the planned Unit_Conversion.csv): the
    # solver buys whole packs, and the UI shows pack_label to the user.
    pack_grams: int = 50
    pack_label: str = ""
    # All registered retail sizes [(grams, label), ...] when the food has
    # multi-size packs (e.g. rice 2 kg/10 kg, eggs 10/30 biji); empty when
    # only one size is known. The candidate loader picks pack_grams via
    # select_pack; the habit-pick retry uses the smallest option to lock a
    # missing pick at a household-sized portion.
    pack_options: tuple = ()
    # Provenance metadata (AC 2.0.2 / 2.0.8); populated by the Epic 2 pipeline.
    price_source: str = ""
    price_updated: str = ""
    nutrition_source: str = ""
    nutrition_updated: str = ""
    # Ease-of-purchase signal: how many stores in the pricing area have a
    # latest price quote for this food. Populated by the DB-backed candidate
    # service; None = unknown (the CSV fixture carries no such column).
    availability_stores: Optional[int] = None
    # Minimal, truthful provenance label (P0 price-recovery fix): one of
    # "REAL_PRICECATCHER" / "SYNTHETIC_TEST" / "" (unknown/not resolved via
    # the new representative_price path yet). Additive field -- does not
    # replace price_is_estimated, which stays for backward compatibility.
    price_provenance: str = ""
    # By-weight purchase (2026-09-13 user decision): sold by weight (wet
    # market/butcher), purchasable in fine BY_WEIGHT_STEP_G steps priced
    # linearly at price_rm_per_100g. Set by the DB candidate service for the
    # curated portions.BY_WEIGHT_FOOD_IDS; False for every CSV-fixture/test
    # food, which keep whole-pack purchase semantics.
    by_weight: bool = False


def load_foods(path: Optional[Path] = None) -> List[Food]:
    path = path or DATA_FILE
    foods: List[Food] = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(
            row for row in f if not row.lstrip().startswith("#") and row.strip()
        )
        for row in reader:
            nutrients = {k: _opt_float(row.get(col)) for k, col in _NUTRIENT_COLUMNS.items()}
            tags: Set[str] = {
                t.strip() for t in (row.get("allergen_tags") or "").split(";") if t.strip()
            }
            diet_tags: Set[str] = {
                t.strip() for t in (row.get("diet_tags") or "").split(";") if t.strip()
            }
            pack_grams_raw = (row.get("pack_grams") or "").strip()
            pack_grams = int(float(pack_grams_raw)) if pack_grams_raw else 50
            foods.append(
                Food(
                    food_id=row["standard_food_id"].strip(),
                    name=row["name"].strip(),
                    name_ms=row["name_ms"].strip(),
                    category=row["category"].strip(),
                    price_rm_per_100g=_opt_float(row.get("price_rm_per_100g")),
                    price_is_estimated=(row.get("price_is_estimated") or "").strip() == "1",
                    edible_fraction=float(row["edible_fraction"]),
                    nutrients=nutrients,
                    allergen_tags=frozenset(tags),
                    diet_tags=frozenset(diet_tags),
                    pack_grams=pack_grams,
                    pack_label=(row.get("pack_label") or "").strip(),
                    price_source=(row.get("price_source") or "").strip(),
                    price_updated=(row.get("price_updated") or "").strip(),
                    nutrition_source=(row.get("nutrition_source") or "").strip(),
                    nutrition_updated=(row.get("nutrition_updated") or "").strip(),
                )
            )
    return foods
