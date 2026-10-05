"""Offline barcode/name charge alignment, including actual rece4 failure."""
from decimal import Decimal
import asyncio
import time
import uuid

import httpx

from packages.receipt_price_evidence import repair_barcode_paired_purchases
from packages.receipt_purchase_rules import ground_purchase_quantity
from services.inference.app.paddle_receipt_parser import parse_receipt_lines


def receipt4_evidence():
    # Public item barcode layout; product identifiers do not establish prices.
    rows = ["1x9555897602702 EARTH AMBASSADOR PP HOVEN BAG 5.00",
            "1x2280409000902 0.90", "LEMON GRASS ( E.T )",
            "1x9556046100086 21.90", "KNIFE COOKING OIL 3KG",
            "1x9557240612285 12.30", "QL FRESH EGGS 30'S GRADE (C)",
            "1x2000043066658 3.90", "SM BAYAM RED/GREEN ORG",
            "1x2261710050077 50.07", "FRZ OX TAIL", "DISC 50%@25.04 -25.03",
            "1x2261710048371 48.37", "FRZ OX TAIL", "DISC 50%24.19 -24.18"]
    return [line.model_dump() for line in parse_receipt_lines(rows)]


def shifted_cloud():
    return [{"name_raw": name, "quantity": Decimal(1), "unit": None, "line_total": Decimal(price)}
            for name, price in [("PP WOVEN BAG", ".90"), ("LEMON GRASS ( E.T )", "21.90"),
                                ("KNIFE COOKING OIL 3KG", "12.30"), ("QL FRESH EGGS 30'S GRADE (C)", "3.90"),
                                ("SM BAYAM RED/GREEN ORG", "25.04"), ("FRZ OX TAIL", "24.19")]]


def test_receipt4_raw_pairs_restore_six_correct_net_charges_and_both_ox_tails():
    evidence = receipt4_evidence()
    assert len(evidence) == 6
    assert all(row["price_basis"] == "BARCODE_PRICE_BEFORE_NAME" for row in evidence)
    corrected = repair_barcode_paired_purchases(shifted_cloud(), evidence)
    assert [(line["name_raw"], line["line_total"]) for line in corrected] == [
        (row["name"], Decimal(str(row["price_rm"]))) for row in evidence]
    assert [row["line_total"] for row in corrected] == list(map(Decimal, [".90", "21.90", "12.30", "3.90", "25.04", "24.19"]))


def test_correct_cloud_is_unchanged_and_older_inference_without_provenance_is_unchanged():
    evidence = receipt4_evidence()
    correct = [{"name_raw": row["name"], "line_total": Decimal(str(row["price_rm"]))} for row in evidence]
    assert repair_barcode_paired_purchases(correct, evidence) is correct
    old = [dict(row, price_basis=None) for row in evidence]
    cloud = shifted_cloud()
    assert repair_barcode_paired_purchases(cloud, old) is cloud


def test_partial_evidence_repairs_known_pair_without_deleting_other_purchase():
    evidence = receipt4_evidence()[:1]
    cloud = shifted_cloud()[1:] + [{"name_raw": "NEW LEGITIMATE VEGETABLE", "line_total": Decimal("4.10")}]
    corrected = repair_barcode_paired_purchases(cloud, evidence)
    assert corrected[0]["line_total"] == Decimal(".90")
    assert corrected[1:] == cloud[1:]


def test_unrelated_private_purchase_prices_and_nonadjacent_provenance_cannot_repair():
    cloud = shifted_cloud()
    evidence = [dict(row, source_row_ids=[1, 4]) for row in receipt4_evidence()]
    assert repair_barcode_paired_purchases(cloud, evidence) is cloud
    unrelated = [{"name_raw": "PEEL FRESH ORANGE 2L", "line_total": Decimal("13.20")}]
    assert repair_barcode_paired_purchases(unrelated, receipt4_evidence()) is unrelated


def test_each_juice_variant_keeps_its_own_printed_volume_after_charge_repair():
    evidence = [
        {"name": "PEEL FRESH ORANGE 1L", "qty": 1, "unit": "pcs", "price_rm": 7,
         "price_basis": "BARCODE_PRICE_BEFORE_NAME", "source_row_ids": [1, 2]},
        {"name": "PEEL FRESH ORANGE 2L", "qty": 1, "unit": "pcs", "price_rm": 13,
         "price_basis": "BARCODE_PRICE_BEFORE_NAME", "source_row_ids": [3, 4]},
    ]
    cloud = [{"name_raw": "PEEL FRESH ORANGE 1L", "line_total": Decimal(13)},
             {"name_raw": "PEEL FRESH ORANGE 2L", "line_total": Decimal(7)}]
    repaired = repair_barcode_paired_purchases(cloud, evidence)
    assert [row["name_raw"] for row in repaired] == [row["name_raw"] for row in cloud]
    assert [ground_purchase_quantity(row["name_raw"], row["quantity"], row["unit"], row["line_total"], evidence)
            for row in repaired] == [(Decimal(1), "l"), (Decimal(2), "l")]


def test_unrelated_genuine_bag_is_not_deleted_when_two_food_prices_conflict():
    evidence = [
        {"name": "RICE", "qty": 1, "unit": "pcs", "price_rm": 7,
         "price_basis": "BARCODE_PRICE_BEFORE_NAME", "source_row_ids": [1, 2]},
        {"name": "MILK", "qty": 1, "unit": "pcs", "price_rm": 13,
         "price_basis": "BARCODE_PRICE_BEFORE_NAME", "source_row_ids": [3, 4]},
    ]
    bag = {"name_raw": "PLASTIC BAG CHARGE", "line_total": Decimal(".30")}
    cloud = [bag, {"name_raw": "RICE", "line_total": Decimal(13)}, {"name_raw": "MILK", "line_total": Decimal(7)}]
    assert repair_barcode_paired_purchases(cloud, evidence)[0] == bag


def test_missing_corresponding_cloud_variant_uses_private_printed_size_not_other_pack():
    private = [{"name": "JUICE 2L", "qty": 1, "unit": "pcs", "price_rm": 13,
                "price_basis": "BARCODE_PRICE_BEFORE_NAME", "source_row_ids": [1, 2]}]
    cloud = [{"name_raw": "JUICE 1L", "name_expanded": "One litre juice", "line_total": Decimal(7)}]
    row = repair_barcode_paired_purchases(cloud, private)[0]
    assert row["name_raw"] == "JUICE 2L" and row["name_expanded"] is None
    assert ground_purchase_quantity(row["name_raw"], row["quantity"], row["unit"], row["line_total"], private) == (Decimal(2), "l")


def test_raw_receipt4_private_pairs_reach_final_cloud_draft_with_correct_charges(monkeypatch):
    from services.api.app.services import receipt_extraction, receipt_cloud_runtime
    from services.api.app.services.receipt_cloud_contract import ReceiptExtraction

    cloud = ReceiptExtraction(provider="deepseek", requested_model="offline-fixture", lines=shifted_cloud())
    async def fake_cloud(*_args):
        return receipt_cloud_runtime.CloudReceiptResult(cloud, None, receipt4_evidence())
    async def no_extra_ocr(*_args):
        raise AssertionError("Repair reuses the private redaction evidence")
    monkeypatch.setattr(receipt_extraction, "extract_cloud_receipt", fake_cloud)
    monkeypatch.setattr(receipt_extraction, "_extract_local", no_extra_ocr)
    async def run():
        async with httpx.AsyncClient() as client:
            return await receipt_extraction._extract_draft(client, uuid.uuid4(), "private-test-only", time.monotonic() + 60)
    lines, repaired, _ = asyncio.run(run())
    assert len(lines) == 6
    assert [Decimal(row["price_rm"]) for row in lines] == list(map(Decimal, [".90", "21.90", "12.30", "3.90", "25.04", "24.19"]))
    assert [(Decimal(row["qty"]), row["unit"]) for row in lines[1:3]] == [(Decimal("3"), "kg"), (Decimal("30"), "pcs")]
    assert [row.name_raw for row in repaired.lines].count("FRZ OX TAIL") == 2
