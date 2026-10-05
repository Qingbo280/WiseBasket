"""Synthetic-only evaluator tests; no original images, private gold, or API calls."""

from scripts.evaluate_receipt_providers import evaluate


def _prediction(provider: str, *, price: int = 2, unit: str = "g", quantity: int = 500):
    return {
        "provider": provider, "requested_model": "mock", "returned_model": "mock",
        "header": {"total": 2},
        "lines": [{"name_raw": "SYNTHETIC RICE", "quantity": quantity, "unit": unit,
                   "unit_price": price, "line_total": price}],
        "latency_ms": 200, "cost_usd": "0.01",
    }


def _receipt(index: int):
    return {
        "retailer": f"synthetic-retailer-{index % 3}",
        "gold": {"total": "2.00", "lines": [{
            "name_raw": "SYNTHETIC RICE", "quantity": "0.5", "unit": "kg",
            "qty_tolerance": "1", "unit_price": "2.00", "line_total": "2.00",
        }]},
        "predictions": {provider: [_prediction(provider) for _ in range(3)]
                        for provider in ("kimi", "deepseek", "azure")},
    }


def test_incomplete_private_matrix_never_declares_winner_or_leaks_names():
    report = evaluate({"receipts": [_receipt(0)]})
    assert report["status"] == "insufficient_gold_or_predictions"
    assert report["winner"] is None
    assert "SYNTHETIC RICE" not in str(report)


def test_complete_equal_matrix_prefers_azure_within_two_points():
    report = evaluate({"receipts": [_receipt(index) for index in range(5)]})
    assert report["status"] == "complete"
    assert report["receipt_count"] == 5
    assert report["winner"] == "azure"
    assert report["providers"]["azure"]["line_f1"] == 1
    assert report["providers"]["azure"]["numeric_accuracy"] == 1


def test_missing_values_count_wrong_and_unit_dimensions_do_not_cross_match():
    receipts = [_receipt(index) for index in range(10)]
    for receipt in receipts:
        for prediction in receipt["predictions"]["kimi"]:
            prediction["lines"][0]["unit"] = "ml"  # 500 ml != 0.5 kg
            prediction["lines"][0]["unit_price"] = None
            prediction["header"]["total"] = None
    report = evaluate({"receipts": receipts})
    assert report["providers"]["kimi"]["numeric_accuracy"] == 0.25
    assert report["providers"]["kimi"]["total_accuracy"] == 0
    assert report["winner"] == "azure"
