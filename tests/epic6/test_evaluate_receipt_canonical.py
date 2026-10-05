"""Pure tests for the private, read-only canonical-food pilot evaluator."""

import json

import pytest

from scripts.evaluate_receipt_canonical import EXPERIMENT_ID, evaluate


def _inputs(lines):
    names = [
        {"name_raw": "BANANA", "line_total": "1.00"},
        {"name_raw": "PLASTIC BAG CHARGE", "line_total": "0.20"},
        {"name_raw": "UNKNOWN PURCHASE", "line_total": "2.00"},
    ]
    manifest = {"experiment_id": EXPERIMENT_ID, "receipts": [{
        "image_path": "private-test.jpeg",
        "predictions": {"deepseek": [{"provider": "deepseek", "requested_model": "test", "lines": lines}]},
    }]}
    gold = {"receipts": [{"image_path": "private-test.jpeg", "gold": {"lines": names}}]}
    sidecar = {"version": 1, "review_status": "agent_visual_reviewed_pending_independent_confirmation",
               "receipts": [{"image_path": "private-test.jpeg", "line_count": 3,
                             "mapped": [{"gold_index": 0, "canonical_food_id": "SF090"}],
                             "excluded": [{"gold_index": 1, "reason": "nonfood"},
                                          {"gold_index": 2, "reason": "out_of_catalog"}]}]}
    catalogue = ([('SF090', 'banana')], [], {}, {'SF090'})
    return manifest, gold, sidecar, catalogue


def test_one_to_one_recall_false_option_and_low_confidence_gate():
    inputs = _inputs([
        {"name_raw": "BANANA", "line_total": "1.00", "confidence": "0.50"},
        {"name_raw": "PLASTIC BAG CHARGE", "line_total": "0.20"},
        # A wrong model expansion can still create a candidate, but never an
        # automatic preselection; the negative-risk metric must expose it.
        {"name_raw": "UNKNOWN PURCHASE", "name_expanded": "banana", "line_total": "2.00"},
    ])
    report = evaluate(*inputs)
    row = report["providers"]["deepseek"]["by_run"]["1"]
    assert (row["mapped_gold"], row["mapped_ocr_paired"]) == (1, 1)
    assert (row["top1_hits"], row["top3_hits"]) == (1, 1)
    assert row["top1_recall"] == row["top3_recall"] == 1.0
    # Sanity floor (2026-10-02): the charge row's character noise is dropped;
    # only the wrong model expansion still creates a negative candidate.
    assert (row["negative_ocr_paired"], row["negative_with_candidates"]) == (2, 1)
    assert row["negative_false_candidate_rate"] == 0.5
    assert row["low_confidence_exact_suppressed"] == 1
    assert row["low_confidence_effective_preselect"] == 0
    assert row["effective_negative_preselect"] == 0
    # Public output contains only aggregate fields, never private item labels.
    serialized = json.dumps(report)
    assert "BANANA" not in serialized
    assert "PLASTIC BAG" not in serialized
    assert "private-test.jpeg" not in serialized


def test_missing_ocr_purchase_remains_in_recall_denominator():
    inputs = _inputs([
        {"name_raw": "PLASTIC BAG CHARGE", "line_total": "0.20"},
        {"name_raw": "UNKNOWN PURCHASE", "line_total": "2.00"},
    ])
    row = evaluate(*inputs)["providers"]["deepseek"]["by_run"]["1"]
    assert row["mapped_gold"] == 1
    assert row["mapped_ocr_paired"] == 0
    assert row["top1_recall"] == row["top3_recall"] == 0.0


def test_gold_must_cover_each_purchase_and_use_active_food_id():
    inputs = _inputs([])
    inputs[2]["receipts"][0]["excluded"].pop()
    with pytest.raises(ValueError, match="Every gold purchase line"):
        evaluate(*inputs)

    inputs = _inputs([])
    inputs[2]["receipts"][0]["mapped"][0]["canonical_food_id"] = "NOT_ACTIVE"
    with pytest.raises(ValueError, match="Invalid or duplicate"):
        evaluate(*inputs)
