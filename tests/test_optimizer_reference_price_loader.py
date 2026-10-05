from decimal import Decimal

from scripts.load_optimizer_reference_prices_to_local import (
    REFERENCE_PRICES,
    ReferencePrice,
)


def reference(food_id: str) -> ReferencePrice:
    return next(row for row in REFERENCE_PRICES if row.food_id == food_id)


def test_reference_prices_cover_the_approved_recipe_price_gaps():
    assert {row.food_id for row in REFERENCE_PRICES} == {
        "SF006",
        "SF056",
        "SF077",
        "SF124",
    }


def test_reference_price_normalizes_package_price_to_purchase_basis():
    onion = reference("SF056")
    assert onion.package_mass_g == Decimal("2000")
    assert onion.package_price_rm == Decimal("4.30")
    assert onion.price_rm_per_kg == Decimal("2.15")
    assert onion.price_rm_per_100g == Decimal("0.215")


def test_reference_records_remain_truthfully_labelled_and_traceable():
    for row in REFERENCE_PRICES:
        assert row.dataset_version == "REFERENCE_ESTIMATE_2026-09"
        assert row.source_url.startswith("https://www.lotuss.com.my/")
        assert row.mapping_status in {"EXACT", "ACCEPTED_EQUIVALENT"}
