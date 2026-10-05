"""Receipt quantity estimates use a minimum, not the planner's median."""

from datetime import date

from services.api.app.services.representative_price import (
    ShopPrice,
    minimum_purchase_price,
    resolve_representative_price,
)


def _shop(location_id: int, rate: float) -> ShopPrice:
    return ShopPrice(
        location_id=location_id,
        price_rm_per_100g_purchase=rate,
        observed_date=date(2026, 9, 29),
        source_item_code="PINEAPPLE",
        source_dataset_version="PRICECATCHER_2026-09",
        district=None,
        state=None,
    )


def test_receipt_minimum_is_distinct_from_representative_median():
    rows = [_shop(1, 0.2), _shop(2, 0.4), _shop(3, 0.6)]
    assert minimum_purchase_price(rows) == 0.2
    assert resolve_representative_price(rows, district=None, state=None).price_rm_per_100g_purchase == 0.4


def test_receipt_minimum_rejects_invalid_rates():
    assert minimum_purchase_price([_shop(1, 0), _shop(2, -1), _shop(3, float("nan"))]) is None
    assert minimum_purchase_price([_shop(1, float("inf")), _shop(2, 0.25)]) == 0.25
