"""Offline, privacy-preserving receipt-provider evaluation.

The input manifest is private and must never be committed. This script makes
NO model/API/database calls. The separate live collector can produce the same
ReceiptExtraction JSON records only after rotated keys and gold data exist.
Only aggregate metrics are printed; no images, item names or receipt IDs.
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from rapidfuzz import fuzz

from packages.receipt_matching import normalize_receipt_item_label, normalize_label
from services.api.app.services.receipt_cloud_contract import ReceiptExtraction
from services.api.app.services.receipt_cloud_providers import repair_repeated_barcode_lines


PROVIDERS = ("kimi", "deepseek", "azure")
RUNS_PER_RECEIPT = 3
MIN_PILOT_RECEIPTS = 5


def _decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        result = Decimal(str(value))
    except (ValueError, InvalidOperation):
        return None
    return result if result.is_finite() and result >= 0 else None


def _name(value: str) -> str:
    # Printed `*1`, a surrounding price and OCR punctuation are receipt
    # metadata, not a different purchased product identity.
    return normalize_label(normalize_receipt_item_label(value))


def attach_private_gold(manifest: dict[str, Any], sidecar: dict[str, Any]) -> dict[str, Any]:
    """Merge a separately reviewed gold file in memory, never into predictions."""
    gold_by_image = {
        item["image_path"]: item.get("gold") or {}
        for item in sidecar.get("receipts") or []
    }
    merged = {**manifest, "receipts": []}
    for receipt in manifest.get("receipts") or []:
        image_path = receipt.get("image_path")
        if image_path not in gold_by_image:
            raise ValueError("Gold sidecar does not cover every evaluated receipt")
        gold = {**(receipt.get("gold") or {}), **gold_by_image[image_path]}
        if manifest.get("experiment_id") in {
            "raw-and-expanded-v1", "raw-and-expanded-purchases-v2",
        }:
            # item-band-v2 intentionally masks totals. A provider cannot be
            # penalised for a value absent from the image it was allowed to see.
            gold["total_visible"] = False
        merged["receipts"].append({**receipt, "gold": gold})
    return merged


def _quantity(value: Any, unit: Any) -> tuple[Decimal, str] | None:
    number = _decimal(value)
    if number is None:
        return None
    normalized = str(unit or "").casefold().strip()
    if normalized in {"kg", "kilogram", "kilograms"}:
        return number * 1000, "mass"
    if normalized in {"g", "gram", "grams"}:
        return number, "mass"
    if normalized in {"l", "litre", "liter"}:
        return number * 1000, "volume"
    if normalized in {"ml", "millilitre", "milliliter"}:
        return number, "volume"
    if normalized in {"", "pcs", "pc", "piece", "pieces", "biji", "unit", "units",
                      "pkt", "packet", "pack", "packs"}:
        return number, "count"
    return None


def _same_quantity(gold: dict, prediction: Any) -> bool:
    expected = _quantity(gold.get("quantity"), gold.get("unit"))
    actual = _quantity(prediction.quantity, prediction.unit)
    tolerance = _decimal(gold.get("qty_tolerance")) or Decimal(0)
    return (expected is not None and actual is not None and expected[1] == actual[1]
            and abs(expected[0] - actual[0]) <= tolerance)


def _same_money(expected: Any, actual: Any) -> bool:
    left, right = _decimal(expected), _decimal(actual)
    return left is not None and right is not None and abs(left - right) <= Decimal("0.01")


def _line_pairs(
    gold_lines: list[dict], predicted: ReceiptExtraction, *, ocr_tolerant: bool = False,
) -> tuple[list[tuple[dict, Any]], int]:
    """One-to-one product-name pairing; optional minor OCR-typo tolerance.

    Amounts break equal-name-score ties but never turn a wrong name into a hit.
    This is still lexical identity, not a semantic or canonical-food judgment.
    """
    used_gold: set[int] = set()
    used_predicted: set[int] = set()
    matches: list[tuple[int, int]] = []
    # Exact printed-name matches are reserved first, including duplicates.
    for gold_index, gold in enumerate(gold_lines):
        name = _name(str(gold.get("name_raw") or ""))
        for predicted_index, line in enumerate(predicted.lines):
            if predicted_index not in used_predicted and name and name == _name(line.name_raw):
                matches.append((gold_index, predicted_index))
                used_gold.add(gold_index)
                used_predicted.add(predicted_index)
                break
    if ocr_tolerant:
        possibilities = []
        for gold_index, gold in enumerate(gold_lines):
            if gold_index in used_gold:
                continue
            gold_name = _name(str(gold.get("name_raw") or ""))
            for predicted_index, line in enumerate(predicted.lines):
                if predicted_index in used_predicted:
                    continue
                predicted_name = _name(line.name_raw)
                similarity = max(
                    fuzz.ratio(gold_name, predicted_name),
                    fuzz.token_sort_ratio(gold_name, predicted_name),
                ) / 100 if gold_name and predicted_name else 0.0
                if similarity >= 0.82:
                    possibilities.append((
                        -similarity, -int(_same_money(gold.get("line_total"), line.line_total)),
                        abs(gold_index - predicted_index), gold_index, predicted_index,
                    ))
        for _, _, _, gold_index, predicted_index in sorted(possibilities):
            if gold_index not in used_gold and predicted_index not in used_predicted:
                matches.append((gold_index, predicted_index))
                used_gold.add(gold_index)
                used_predicted.add(predicted_index)
    return [(gold_lines[g], predicted.lines[p]) for g, p in matches], len(matches)


def _percentile(values: list[int], fraction: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int((len(ordered) - 1) * fraction + 0.999999)))
    return ordered[index]


def evaluate(manifest: dict[str, Any]) -> dict[str, Any]:
    receipts = manifest.get("receipts")
    if not isinstance(receipts, list):
        raise ValueError("Manifest must contain a receipts array")
    retailers = {str(item.get("retailer") or "").strip() for item in receipts}
    # The project has five available real receipts. This is enough for its
    # bounded pilot decision, not a population-level accuracy claim.
    complete = len(receipts) >= MIN_PILOT_RECEIPTS and len(retailers - {""}) >= 3
    metrics: dict[str, Any] = {}
    for provider in PROVIDERS:
        tp = strict_tp = predicted_count = gold_count = 0
        numeric_correct = numeric_expected = 0
        field_correct = Counter()
        field_expected = Counter()
        total_correct = total_expected = 0
        latencies: list[int] = []
        costs: list[Decimal] = []
        reserved_costs: list[Decimal] = []
        zero_line_runs = 0
        completed_runs = 0
        for receipt in receipts:
            gold = receipt.get("gold") or {}
            gold_lines = gold.get("lines") or []
            if not isinstance(gold_lines, list):
                raise ValueError("Gold lines must be an array")
            if not gold_lines or (gold.get("total_visible", True) and gold.get("total") is None):
                complete = False
            predictions = (receipt.get("predictions") or {}).get(provider) or []
            if len(predictions) != RUNS_PER_RECEIPT:
                complete = False
            for record in predictions[:RUNS_PER_RECEIPT]:
                try:
                    result = ReceiptExtraction.model_validate(record)
                except Exception:
                    raise ValueError("Invalid private prediction contract") from None
                if result.provider != provider:
                    raise ValueError("Prediction provider does not match manifest slot")
                if provider in {"deepseek", "kimi"}:
                    # Historical private JSON stores provider-parsed rows. The
                    # production adapter now applies this deterministic repair.
                    result.lines = repair_repeated_barcode_lines(result.lines)
                completed_runs += 1
                zero_line_runs += not bool(result.lines)
                _, strict_matched = _line_pairs(gold_lines, result)
                strict_tp += strict_matched
                pairs, matched = _line_pairs(gold_lines, result, ocr_tolerant=True)
                tp += matched
                predicted_count += len(result.lines)
                gold_count += len(gold_lines)
                for gold_line, prediction in pairs:
                    for field, same in (
                        ("quantity", _same_quantity(gold_line, prediction)),
                        ("unit_price", _same_money(gold_line.get("unit_price"), prediction.unit_price)),
                        ("line_total", _same_money(gold_line.get("line_total"), prediction.line_total)),
                    ):
                        if gold_line.get(field) is not None:
                            numeric_expected += 1
                            numeric_correct += same
                            field_expected[field] += 1
                            field_correct[field] += same
                # Missing item matches count as incorrect numerical fields.
                unmatched = Counter(_name(str(line.get("name_raw") or "")) for line in gold_lines)
                unmatched.subtract(Counter(_name(str(line.get("name_raw") or "")) for line, _ in pairs))
                for line in gold_lines:
                    name = _name(str(line.get("name_raw") or ""))
                    if unmatched[name] > 0:
                        for field in ("quantity", "unit_price", "line_total"):
                            if line.get(field) is not None:
                                numeric_expected += 1
                                field_expected[field] += 1
                        unmatched[name] -= 1
                if gold.get("total_visible", True) and gold.get("total") is not None:
                    total_expected += 1
                    correct = _same_money(gold["total"], result.header.total)
                    total_correct += correct
                    numeric_expected += 1
                    numeric_correct += correct
                if result.latency_ms is not None:
                    latencies.append(result.latency_ms)
                cost = _decimal(record.get("cost_usd"))
                if cost is not None:
                    costs.append(cost)
                reserved_cost = _decimal(record.get("reserved_upper_bound_usd"))
                if reserved_cost is not None:
                    reserved_costs.append(reserved_cost)
        precision = tp / predicted_count if predicted_count else 0.0
        recall = tp / gold_count if gold_count else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        strict_precision = strict_tp / predicted_count if predicted_count else 0.0
        strict_recall = strict_tp / gold_count if gold_count else 0.0
        strict_f1 = (2 * strict_precision * strict_recall / (strict_precision + strict_recall)
                     if strict_precision + strict_recall else 0.0)
        numeric_accuracy = numeric_correct / numeric_expected if numeric_expected else 0.0
        total_accuracy = total_correct / total_expected if total_expected else None
        metrics[provider] = {
            "completed_runs": completed_runs, "expected_runs": len(receipts) * RUNS_PER_RECEIPT,
            "line_precision": round(precision, 4), "line_recall": round(recall, 4),
            "line_f1": round(f1, 4), "numeric_accuracy": round(numeric_accuracy, 4),
            "numeric_field_accuracy": {
                field: round(field_correct[field] / field_expected[field], 4)
                if field_expected[field] else None
                for field in ("quantity", "unit_price", "line_total")
            },
            "strict_printed_name_f1": round(strict_f1, 4),
            "total_accuracy": round(total_accuracy, 4) if total_accuracy is not None else None,
            "zero_line_rate": round(zero_line_runs / completed_runs, 4) if completed_runs else None,
            "p50_latency_ms": int(statistics.median(latencies)) if latencies else None,
            "p95_latency_ms": _percentile(latencies, 0.95),
            "observed_cost_usd": str(sum(costs, Decimal(0))) if costs else None,
            "reserved_upper_bound_usd": str(sum(reserved_costs, Decimal(0))) if reserved_costs else None,
        }
    return {
        "status": "complete" if complete else "insufficient_gold_or_predictions",
        "receipt_count": len(receipts), "retailer_count": len(retailers - {""}),
        "providers": metrics,
        "winner": _winner(metrics) if complete else None,
    }


def _winner(metrics: dict[str, dict]) -> str:
    qualified = [provider for provider, row in metrics.items()
                 if row["line_precision"] >= 0.95 and row["line_recall"] >= 0.95
                 and row["numeric_accuracy"] >= 0.98]
    candidates = qualified or list(PROVIDERS)
    top_f1 = max(metrics[name]["line_f1"] for name in candidates)
    if qualified and "azure" in candidates and top_f1 - metrics["azure"]["line_f1"] < 0.02:
        return "azure"
    return max(candidates, key=lambda name: (
        metrics[name]["line_f1"], metrics[name]["numeric_accuracy"],
        -metrics[name]["zero_line_rate"] if metrics[name]["zero_line_rate"] is not None else -1,
        -metrics[name]["p95_latency_ms"] if metrics[name]["p95_latency_ms"] is not None else -10**9,
        -(float(metrics[name]["observed_cost_usd"] or metrics[name]["reserved_upper_bound_usd"]))
        if (metrics[name]["observed_cost_usd"] or metrics[name]["reserved_upper_bound_usd"]) is not None else -10**9,
    ))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path, help="Private gold + prediction JSON; never commit it")
    parser.add_argument("--gold-sidecar", type=Path, help="Private reviewed item-line gold JSON")
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    if args.gold_sidecar is not None:
        manifest = attach_private_gold(manifest, json.loads(args.gold_sidecar.read_text(encoding="utf-8")))
    report = evaluate(manifest)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
