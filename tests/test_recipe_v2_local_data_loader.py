from decimal import Decimal

import pytest

from scripts.load_recipe_v2_data_to_local import (
    build_identity_transfers,
    build_safe_price_food_ids,
    parse_purchase_mass_g,
    require_local_database_url,
)


def test_loader_refuses_nonlocal_database():
    with pytest.raises(ValueError, match="only runs against a local"):
        require_local_database_url("postgresql://user:secret@example.com/database")


def test_identity_transfer_accepts_one_reviewed_identity_without_granularity_change():
    rows = [{
        "old_canonical_food_id": "OLD-RICE",
        "new_canonical_food_id": "SF110",
        "MATCH_STATUS": "EXACT_IDENTITY_MATCH",
        "CONFIDENCE": "HIGH",
        "GRANULARITY_CHANGE": "NONE",
    }]

    assert build_identity_transfers(rows, {"SF110"}) == {"SF110": rows[0]}


def test_identity_transfer_rejects_merge_and_ambiguous_matches():
    rows = [
        {
            "old_canonical_food_id": "OLD-A",
            "new_canonical_food_id": "SF110",
            "MATCH_STATUS": "EXACT_IDENTITY_MATCH",
            "CONFIDENCE": "HIGH",
            "GRANULARITY_CHANGE": "MERGE",
        },
        {
            "old_canonical_food_id": "OLD-B",
            "new_canonical_food_id": "SF124",
            "MATCH_STATUS": "AMBIGUOUS_MATCH",
            "CONFIDENCE": "AMBIGUOUS",
            "GRANULARITY_CHANGE": "UNRESOLVED_TARGET",
        },
    ]

    assert build_identity_transfers(rows, {"SF110", "SF124"}) == {}


def test_safe_price_food_requires_both_review_and_display_gates():
    rows = [
        {
            "canonical_food_id": "safe",
            "representative_price_safe": "YES",
            "app_canonical_price_display": "SHOW",
        },
        {
            "canonical_food_id": "hidden",
            "representative_price_safe": "YES",
            "app_canonical_price_display": "HIDE",
        },
    ]

    assert build_safe_price_food_ids(rows, {"safe", "hidden"}) == {"safe"}


def test_purchase_mass_parser_handles_governed_mass_piece_and_liquid_units():
    assert parse_purchase_mass_g("10 kg", "904", "SF110") == Decimal("10000")
    assert parse_purchase_mass_g("30 biji", "1109", "SF018") == Decimal("1740")
    assert parse_purchase_mass_g("500 ml", "1610", "SF102") == Decimal("500.00")
    assert parse_purchase_mass_g("10 biji", "1930", "SF018") is None
