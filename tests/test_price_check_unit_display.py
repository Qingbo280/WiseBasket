"""Price-check display-unit selection stays data-driven and non-arithmetic."""

from services.api.app.main import _price_unit_display_size


def test_orders_common_source_unit_labels_by_package_magnitude():
    assert _price_unit_display_size("1kg") == 1000
    assert _price_unit_display_size("500 g") == 500
    assert _price_unit_display_size("5 X 79g") == 395
    assert _price_unit_display_size("1 liter") == 1000


def test_approximate_source_unit_can_be_ordered_without_becoming_a_conversion():
    assert _price_unit_display_size("+- 500g") == 500

