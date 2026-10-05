"""Offline quantity/metadata contracts; no provider calls or prices as weights."""
from decimal import Decimal

import pytest

from packages.receipt_purchase_rules import (
    ground_purchase_quantity, is_receipt_metadata, printed_measure,
)


@pytest.mark.parametrize("label", [
    "TOTAL", "TOTAL 25.05", "GRAND TOTAL RM25.05", "GST", "GST 6% 1.50",
    "SST TAX 0.80", "MEMBERSHIP FEE", "Paid by VISAxxxx 25.05",
    "Payment via TNG 25.05", "MYDEBIT 25.05", "isa Card 25.05",
    "Eligible: Union/FP mbr benefit 0.00", "FP Group app $ 25.05",
    "MY LOTUS'S POINTS MISSED : 17", "Discount 0.50",
    "TOTAL (GST INCL)", "GST (6%)", "GST REG NO 12345",
    "TOTAL SALES INCL SVC TAX", "WECHATCB - 77.10",
    "Item 23 SubTotal 343.41", "Saving 0.00 Rounding -0.01",
    "QUANTITY : 7 Units",
])
def test_strict_receipt_metadata_is_not_a_purchase(label):
    assert is_receipt_metadata(label)


@pytest.mark.parametrize("label", [
    "TOTAL GRAIN CEREAL 500G", "MILK TOTAL NUTRITION", "GST BRAND RICE",
    "SST CHILLI", "DISCOUNT COOKIES", "PLASTIC BAG CHARGE", "TISSUES",
])
def test_product_names_and_charged_nonfoods_survive_metadata_filter(label):
    assert not is_receipt_metadata(label)


def test_per_kg_price_never_establishes_a_weight_without_private_evidence():
    assert ground_purchase_quantity("RED CHILLI KG", 1, "KG", "1.01") == (None, None)
    assert ground_purchase_quantity("RED CHILLI KG", 1, "KG", "1000.00", []) == (None, None)
    assert ground_purchase_quantity("RED CHILLI @ 1KG", 1, "KG", "1.01") == (None, None)


def test_private_weighed_continuations_keep_distinct_chicken_purchases():
    private = [
        {"name": "ABF CHICKEN DRUMSTIC", "qty": 0.556, "unit": "kg", "price_rm": 11.40},
        {"name": "ABF CHICKEN DRUMSTIC", "qty": 0.516, "unit": "kg", "price_rm": 10.58},
    ]
    assert ground_purchase_quantity("ABF CHICKEN DRUMSTIC", 0.556, "kg", "11.40", private) == (Decimal("0.556"), "kg")
    assert ground_purchase_quantity("ABF CHICKEN DRUMSTIC", 0.516, "kg", "10.58", private) == (Decimal("0.516"), "kg")
    assert ground_purchase_quantity("ABF CHICKEN DRUMSTIC", 1, "kg", "99", private) == (None, None)
    private[1]["price_rm"] = 11.40
    assert ground_purchase_quantity("ABF CHICKEN DRUMSTIC", 1, "kg", "11.40", private) == (None, None)


@pytest.mark.parametrize("label,qty,unit,expected", [
    ("DL KANGKUNG 300G 2 pkt", 2, "pkt", (Decimal("0.600"), "kg")),
    ("NISSIN CHICKEN RAMEN 5PX425G *1", 1, None, (Decimal("0.425"), "kg")),
    ("HORLICKS32GM", 1, None, (Decimal("0.032"), "kg")),
    ("BUSTANI THINFILLED ASST500GM", 1, None, (Decimal("0.500"), "kg")),
    ("PEEL FRESH ORANGE 2L", 1, None, (Decimal("2"), "l")),
    ("JUICE250ML 2 pack", 2, "pack", (Decimal("0.500"), "l")),
    ("FARM TABLE EGG A30S", 1, None, (Decimal("30"), "pcs")),
    ("QL FRESH EGGS 30'S GRADE C", 30, "pcs", (Decimal("30"), "pcs")),
    ("KNIFE COOKING OIL 3KG", 1, None, (Decimal("3"), "kg")),
])
def test_printed_packaging_and_cartons_ground_stock_amounts(label, qty, unit, expected):
    assert ground_purchase_quantity(label, qty, unit, "999") == expected


def test_generic_multipacks_remain_unknown_and_printed_mass_is_not_multiplied_by_mass():
    assert printed_measure("OTHER NOODLES 5PX425G") is None
    assert ground_purchase_quantity("OTHER NOODLES 5PX425G", 2.125, "kg", "10") == (None, None)
    assert ground_purchase_quantity("CHICKEN 0.556KG", 0.556, "kg", "11.40") == (Decimal("0.556"), "kg")


def test_private_pack_count_and_private_mass_are_not_replaced_by_cloud_guess():
    private = [{"name": "DL KANGKUNG 3OUG", "qty": 2, "unit": "pkt", "price_rm": 9}]
    assert ground_purchase_quantity("DL KANGKUNG 300G", 1, None, 9, private) == (Decimal("0.600"), "kg")
    private = [{"name": "RED CHILLI KG", "qty": 150, "unit": "g", "price_rm": 1.01}]
    assert ground_purchase_quantity("RED CHILLI KG", 1, "kg", "1.01", private) == (Decimal("0.15"), "kg")


def test_bare_provider_integer_does_not_multiply_printed_pack_size():
    assert ground_purchase_quantity("KANGKUNG 300G", 2, None, 9) == (Decimal("0.300"), "kg")
    assert ground_purchase_quantity("KANGKUNG 300G", 2, "pkt", 9) == (Decimal("0.300"), "kg")


@pytest.mark.parametrize("count", [10, 12, 20])
def test_printed_egg_pieces_are_contents_not_an_outer_pack_multiplier(count):
    assert ground_purchase_quantity(f"EGGS {count} PCS", count, "pcs", 5, []) == (Decimal(count), "pcs")


def test_egg_outer_packs_multiply_only_the_printed_carton_contents():
    assert ground_purchase_quantity("EGGS 30 PCS 2 PACKS", 2, "pack", 5, []) == (Decimal(60), "pcs")
    private = [{"name": "EGGS 30 PCS", "qty": 2, "unit": "pkt", "price_rm": 5}]
    assert ground_purchase_quantity("EGGS 30 PCS", 2, "pack", 5, private) == (Decimal(60), "pcs")


@pytest.mark.parametrize("cloud_qty,cloud_unit", [(1, None), (2, "pkt"), (0.6, "kg"), (600, "g")])
def test_private_pack_evidence_wins_independently_of_cloud_unit(cloud_qty, cloud_unit):
    private = [{"name": "DL KANGKUNG 3OUG", "qty": 2, "unit": "pkt", "price_rm": 9}]
    assert ground_purchase_quantity("DL KANGKUNG 300G", cloud_qty, cloud_unit, 9, private) == (Decimal("0.600"), "kg")
