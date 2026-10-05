from decimal import Decimal

from services.api.app.services.pantry_units import combine_quantities, normalize_quantity_unit
from services.api.app.services.pantry_stock import combine_food_quantities


def test_standardizes_weight_liquid_and_count_units():
    assert normalize_quantity_unit(Decimal("500"), "g") == (Decimal("0.5"), "kg")
    assert normalize_quantity_unit(Decimal("750"), "ml") == (Decimal("0.75"), "l")
    assert normalize_quantity_unit(Decimal("12"), "biji") == (Decimal("12"), "pcs")


def test_merges_same_dimension_and_marks_mixed_dimensions_unknown():
    assert combine_quantities(Decimal("1"), "kg", Decimal("500"), "g") == (Decimal("1.5"), "kg")
    assert combine_quantities(Decimal("1"), "kg", Decimal("2"), "pcs") == (None, None)


def test_reviewed_oil_merges_weight_and_volume_without_losing_known_stock():
    expected = (Decimal("1.92"), "kg")
    assert combine_food_quantities("SF120", Decimal("1"), "kg", Decimal("1"), "l") == expected
    assert combine_food_quantities("SF120", Decimal("1"), "l", Decimal("1"), "kg") == expected
    assert combine_food_quantities("SF121", Decimal("500"), "g", Decimal("500"), "ml") == (
        Decimal("0.96000"), "kg"
    )
    assert combine_food_quantities("SF120", Decimal("1"), "pack", Decimal("1"), "l") == (None, None)
    assert combine_food_quantities("SF120", Decimal("1"), "pack", Decimal("2"), "pack") == (
        Decimal("3"), "pack"
    )
    assert combine_food_quantities("SF006", Decimal("1"), "kg", Decimal("1"), "l") == (None, None)
