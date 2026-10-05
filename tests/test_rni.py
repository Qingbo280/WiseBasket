"""Tests for RNI target expansion (children ages, pregnancy, lactation)."""
import pytest

from packages.optimizer.wisebasket_optimizer.rni import RNI_DAILY, household_targets


def test_backward_compatible_without_lifecycle_details():
    """When children_ages / pregnant / lactating are omitted, use adult/child buckets."""
    targets = household_targets(adults=2, children=1, days=7)
    expected_energy = (2 * RNI_DAILY["adult"]["energy_kcal"] + 1 * RNI_DAILY["child"]["energy_kcal"]) * 7
    assert targets["energy_kcal"] == pytest.approx(expected_energy)
    assert targets["protein_g"] == pytest.approx((2 * 55 + 1 * 25) * 7)


def test_children_ages_replaces_child_bucket():
    """Supplying ages switches from averaged child bucket to age-banded targets."""
    averaged = household_targets(adults=2, children=1, days=7)
    age_banded = household_targets(adults=2, children=1, days=7, children_ages=[5])
    # 5-year-old 4-6 band energy = 1300 (male) vs averaged child 1400
    assert age_banded["energy_kcal"] < averaged["energy_kcal"]
    assert age_banded["energy_kcal"] == pytest.approx((2 * 2000 + 1300) * 7)


def test_children_ages_partial_fallback():
    """Only the supplied ages use age bands; remaining children use the fallback bucket."""
    targets = household_targets(adults=2, children=3, days=7, children_ages=[5])
    # one 5y @ 1300 + two averaged children @ 1400
    assert targets["energy_kcal"] == pytest.approx((2 * 2000 + 1300 + 2 * 1400) * 7)


def test_pregnancy_adds_to_targets():
    targets = household_targets(adults=2, children=0, days=7, pregnant_count=1)
    base = household_targets(adults=2, children=0, days=7)
    assert targets["energy_kcal"] > base["energy_kcal"]
    assert targets["protein_g"] > base["protein_g"]


def test_lactation_adds_to_targets():
    targets = household_targets(adults=2, children=0, days=7, lactating_count=1)
    base = household_targets(adults=2, children=0, days=7)
    assert targets["energy_kcal"] > base["energy_kcal"]
    assert targets["protein_g"] > base["protein_g"]


def test_iron_bioavailability_switch():
    ten = household_targets(adults=1, children=0, days=1, iron_bioavailability="10pct")
    fifteen = household_targets(adults=1, children=0, days=1, iron_bioavailability="15pct")
    assert ten["iron_mg"] == pytest.approx(16.0)
    assert fifteen["iron_mg"] == pytest.approx(11.0)


def test_out_of_range_child_age_uses_fallback():
    targets = household_targets(adults=2, children=1, days=7, children_ages=[0])
    expected = household_targets(adults=2, children=1, days=7)
    assert targets["energy_kcal"] == pytest.approx(expected["energy_kcal"])
