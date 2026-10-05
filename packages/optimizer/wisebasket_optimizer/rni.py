"""RNI Malaysia 2017 rule table - nutrient targets scaled by household composition.

Note: RNI lists adult iron under two bioavailability assumptions (10% / 15%).
I1 keeps BOTH scenarios, selected via the `iron_bioavailability` request
parameter, defaulting to the more conservative "10pct".
Values here are I1 engineering estimates and must be calibrated against the
official RNI reference table once the data pipeline is live.
"""
from __future__ import annotations

from typing import Dict

# Per-person daily targets: adult / child (approx. 4-9 y average)
RNI_DAILY: Dict[str, Dict[str, float]] = {
    "adult": {
        "energy_kcal": 2000.0,
        "protein_g": 55.0,
        "fibre_g": 25.0,
        "iron_mg_10pct": 16.0,   # 10% bioavailability assumption
        "iron_mg_15pct": 11.0,   # 15% bioavailability assumption
        "calcium_mg": 1000.0,
        "vita_ug": 600.0,
        "vitc_mg": 70.0,
    },
    "child": {
        "energy_kcal": 1400.0,
        "protein_g": 25.0,
        "fibre_g": 15.0,
        "iron_mg_10pct": 9.0,
        "iron_mg_15pct": 6.0,
        "calcium_mg": 700.0,
        "vita_ug": 400.0,
        "vitc_mg": 35.0,
    },
}

# Age-banded child targets (Malaysia RNI 2017, approximate mid-points).
# Ages outside these bands fall back to the averaged "child" bucket above.
RNI_DAILY_CHILD_AGE_BANDS: Dict[tuple[int, int], Dict[str, float]] = {
    (1, 3): {
        "energy_kcal": 1000.0, "protein_g": 16.0, "fibre_g": 15.0,
        "iron_mg_10pct": 7.0, "iron_mg_15pct": 5.0,
        "calcium_mg": 700.0, "vita_ug": 400.0, "vitc_mg": 35.0,
    },
    (4, 6): {
        "energy_kcal": 1300.0, "protein_g": 20.0, "fibre_g": 18.0,
        "iron_mg_10pct": 9.0, "iron_mg_15pct": 6.0,
        "calcium_mg": 800.0, "vita_ug": 450.0, "vitc_mg": 45.0,
    },
    (7, 9): {
        "energy_kcal": 1700.0, "protein_g": 28.0, "fibre_g": 22.0,
        "iron_mg_10pct": 10.0, "iron_mg_15pct": 7.0,
        "calcium_mg": 900.0, "vita_ug": 500.0, "vitc_mg": 45.0,
    },
    (10, 12): {
        "energy_kcal": 1900.0, "protein_g": 37.0, "fibre_g": 25.0,
        "iron_mg_10pct": 13.0, "iron_mg_15pct": 9.0,
        "calcium_mg": 1000.0, "vita_ug": 550.0, "vitc_mg": 50.0,
    },
    (13, 15): {
        "energy_kcal": 2100.0, "protein_g": 47.0, "fibre_g": 28.0,
        "iron_mg_10pct": 16.0, "iron_mg_15pct": 11.0,
        "calcium_mg": 1200.0, "vita_ug": 600.0, "vitc_mg": 60.0,
    },
    (16, 18): {
        "energy_kcal": 2100.0, "protein_g": 50.0, "fibre_g": 30.0,
        "iron_mg_10pct": 16.0, "iron_mg_15pct": 11.0,
        "calcium_mg": 1000.0, "vita_ug": 600.0, "vitc_mg": 70.0,
    },
}

# Additional daily requirements for pregnancy and lactation (RNI 2017).
RNI_DAILY_PREGNANCY: Dict[str, float] = {
    "energy_kcal": 280.0, "protein_g": 25.0, "fibre_g": 5.0,
    "iron_mg_10pct": 7.0, "iron_mg_15pct": 5.0,
    "calcium_mg": 200.0, "vita_ug": 100.0, "vitc_mg": 20.0,
}
RNI_DAILY_LACTATION: Dict[str, float] = {
    "energy_kcal": 500.0, "protein_g": 25.0, "fibre_g": 5.0,
    "iron_mg_10pct": 4.0, "iron_mg_15pct": 3.0,
    "calcium_mg": 550.0, "vita_ug": 350.0, "vitc_mg": 50.0,
}

# Nutrient display metadata
NUTRIENT_META: Dict[str, Dict[str, str]] = {
    "energy_kcal": {"label": "Energy", "unit": "kcal"},
    "protein_g": {"label": "Protein", "unit": "g"},
    "fibre_g": {"label": "Dietary fibre", "unit": "g"},
    "iron_mg": {"label": "Iron", "unit": "mg"},
    "calcium_mg": {"label": "Calcium", "unit": "mg"},
    "vita_ug": {"label": "Vitamin A", "unit": "ug"},
    "vitc_mg": {"label": "Vitamin C", "unit": "mg"},
}

# Nutrient keys tracked by the solver (MVP also tracks 2 diversity metrics)
NUTRIENT_KEYS = ["energy_kcal", "protein_g", "fibre_g", "iron_mg", "calcium_mg", "vita_ug", "vitc_mg"]

# Coverage >= this threshold counts as achieved (below -> reported as a TIGHT gap)
ACHIEVED_THRESHOLD = 0.95


def _child_daily_targets(age: int, iron_key: str) -> Dict[str, float]:
    """Return age-banded child targets, or the averaged child bucket if the
    age is outside the supported bands."""
    for (min_age, max_age), band in RNI_DAILY_CHILD_AGE_BANDS.items():
        if min_age <= age <= max_age:
            return {k: band.get(k if k != "iron_mg" else iron_key, 0.0) for k in NUTRIENT_KEYS}
    # Out-of-range age: fall back to the averaged child bucket.
    return {k: RNI_DAILY["child"].get(k if k != "iron_mg" else iron_key, 0.0) for k in NUTRIENT_KEYS}


# 2026-09-17 (C1, real-device feedback): the onboarding meals-at-home
# bucket scales the weekly targets - a household cooking 3-5 meals a week
# must not be planned as if all 21 meals were at home (the basket over-bought
# processed carbs / protein; conversely a 10-14-meals household was judged
# against an unreachable full-week target). Fractions are the initial PM
# calibration - tune the table, nothing else. None/unknown = 1.0 (legacy
# full-week behaviour, byte-identical to before).
MEALS_AT_HOME_FRACTION = {
    "most_days_multiple": 0.8,   # 10-14 meals/week at home
    "once_daily": 0.6,           # 6-9
    "few_times_week": 0.45,      # 3-5
    "weekends_only": 0.3,
}


def meals_at_home_fraction(meals_at_home) -> float:
    """Onboarding bucket -> weekly-target scale factor (1.0 when absent)."""
    if not meals_at_home:
        return 1.0
    return MEALS_AT_HOME_FRACTION.get(str(meals_at_home), 1.0)


def household_targets(
    adults: int,
    children: int,
    days: int,
    iron_bioavailability: str = "10pct",
    children_ages: list[int] | None = None,
    pregnant_count: int = 0,
    lactating_count: int = 0,
    meals_at_home=None,
) -> Dict[str, float]:
    """Scale RNI daily targets by household composition and plan length.

    Args:
        children_ages: Optional ages for the first N children (N <= children).
            Supplied ages use banded targets; remaining children use the
            averaged child bucket.
        pregnant_count: Number of pregnant adults; adds pregnancy increment.
        lactating_count: Number of lactating adults; adds lactation increment.
        meals_at_home: Onboarding bucket (C1) - scales every target by
            meals_at_home_fraction(); None keeps the full-week legacy
            targets.
    """
    iron_key = "iron_mg_10pct" if iron_bioavailability == "10pct" else "iron_mg_15pct"
    targets: Dict[str, float] = {}

    # Resolve child targets: use ages where provided, bucket for the rest.
    child_targets: Dict[str, float] = {key: 0.0 for key in NUTRIENT_KEYS}
    ages = list(children_ages or [])[:children]
    for age in ages:
        band = _child_daily_targets(age, iron_key)
        for key in NUTRIENT_KEYS:
            child_targets[key] += band[key]
    remaining = children - len(ages)
    if remaining > 0:
        for key in NUTRIENT_KEYS:
            child_targets[key] += remaining * RNI_DAILY["child"].get(
                key if key != "iron_mg" else iron_key, 0.0
            )

    for key in NUTRIENT_KEYS:
        per_day = adults * RNI_DAILY["adult"].get(
            key if key != "iron_mg" else iron_key, 0.0
        ) + child_targets[key]
        per_day += pregnant_count * RNI_DAILY_PREGNANCY.get(
            key if key != "iron_mg" else iron_key, 0.0
        )
        per_day += lactating_count * RNI_DAILY_LACTATION.get(
            key if key != "iron_mg" else iron_key, 0.0
        )
        targets[key] = per_day * days
    # C1: the at-home meal fraction scales the WHOLE weekly target (energy,
    # macros and micros alike) - coverage is reported against the scaled
    # target, so a basket covering the at-home portion still reads ~100 %.
    _f = meals_at_home_fraction(meals_at_home)
    if _f != 1.0:
        targets = {key: value * _f for key, value in targets.items()}
    return targets
