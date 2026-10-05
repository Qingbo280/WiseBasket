"""Evaluation tolerates OCR typos without treating equal prices as identity."""

from services.api.app.services.receipt_cloud_contract import ExtractedLine, ReceiptExtraction
from scripts.evaluate_receipt_providers import _line_pairs, _quantity, attach_private_gold


def _prediction(*names: str) -> ReceiptExtraction:
    return ReceiptExtraction(
        provider="deepseek", requested_model="test",
        lines=[ExtractedLine(name_raw=name, line_total="15.90") for name in names],
    )


def test_minor_ocr_typo_is_tolerant_hit_but_not_strict_hit():
    gold = [{"name_raw": "PURPLE POTATO LOAF", "line_total": "15.90"}]
    prediction = _prediction("PURPLE POTATOO LOAF")
    assert _line_pairs(gold, prediction)[1] == 0
    assert _line_pairs(gold, prediction, ocr_tolerant=True)[1] == 1


def test_count_quantity_accepts_unit_and_unspecified_packaged_goods_but_not_mass():
    assert _quantity("2", "pkt") == (2, "count")
    assert _quantity("1", None) == (1, "count")
    assert _quantity("0.556", "kg") == (556, "mass")


def test_same_price_does_not_make_unrelated_food_a_hit():
    gold = [{"name_raw": "BUTTER LOAF", "line_total": "15.90"}]
    assert _line_pairs(gold, _prediction("CHICKEN DRUMSTICK"), ocr_tolerant=True)[1] == 0


def test_duplicate_purchases_are_paired_one_to_one():
    gold = [{"name_raw": "EGG"}, {"name_raw": "EGG"}]
    assert _line_pairs(gold, _prediction("EGG"), ocr_tolerant=True)[1] == 1


def test_gold_sidecar_merges_without_overwriting_predictions():
    manifest = {"receipts": [{"image_path": "sample.jpg", "predictions": {"deepseek": [1]}}]}
    sidecar = {"receipts": [{"image_path": "sample.jpg", "gold": {"lines": [2]}}]}
    merged = attach_private_gold(manifest, sidecar)
    assert merged["receipts"][0]["gold"]["lines"] == [2]
    assert merged["receipts"][0]["predictions"]["deepseek"] == [1]
    assert "gold" not in manifest["receipts"][0]


def test_masked_total_is_not_scored_as_provider_error():
    manifest = {
        "experiment_id": "raw-and-expanded-purchases-v2",
        "receipts": [{"image_path": "sample.jpg", "gold": {"total": "12.00"}}],
    }
    sidecar = {"receipts": [{"image_path": "sample.jpg", "gold": {"lines": []}}]}
    assert attach_private_gold(manifest, sidecar)["receipts"][0]["gold"]["total_visible"] is False
