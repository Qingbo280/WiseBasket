"""Offline, aggregate-only evaluation of receipt abbreviation expansions.

This intentionally does not call a model, database, or network service. It
scores a small hand-audited subset of abbreviation-bearing product rows, not
all receipt lines. It reads the v2 purchase-only prompt experiment; the
earlier v1 predictions are never mixed into the score. The private rubric and
predictions must remain git-ignored.

Usage (from the repository root)::

    python -m scripts.evaluate_receipt_expansions receipt_eval_private

The output contains counts and rates only, never item text, images, receipt
identifiers, or provider response bodies. Five receipts and draft gold are a
pilot, not evidence of production-level accuracy.
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from collections import Counter
from decimal import Decimal, InvalidOperation
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any


PROVIDERS = ("kimi", "deepseek", "azure")
RUNS_PER_RECEIPT = 3
EXPERIMENT_ID = "raw-and-expanded-purchases-v2"
EXPERIMENT_MANIFEST = "manifest_raw_and_expanded_v2.json"
STATUSES = ("correct_expansion", "wrong_expansion", "abstained", "missing_ocr_line", "provider_failure")
STRATA = ("food_identity", "ancillary_or_nonfood")


def _words(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return " ".join(re.findall(r"[a-z0-9]+", normalized))


def _contains_phrase(haystack: str, phrase: str) -> bool:
    needle = _words(phrase)
    return bool(needle) and f" {needle} " in f" {haystack} "


def _decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        number = Decimal(str(value))
    except (ValueError, InvalidOperation):
        return None
    return number if number.is_finite() else None


def _printed_measurements(value: Any) -> set[tuple[Decimal, str]]:
    """Normalize explicit g/kg/ml/l facts; absence in an expansion is allowed.

    An invented or altered amount is not a correct full-name expansion even if
    the food-identity words are right (for example, 32 GM becoming 326 g).
    """
    if not isinstance(value, str):
        return set()
    compact = unicodedata.normalize("NFKC", value).casefold()
    found: set[tuple[Decimal, str]] = set()
    for amount, unit in re.findall(
        r"(?<!\d)(\d+(?:\.\d+)?)\s*(kilograms?|kgs?|grams?|gms?|g|litres?|liters?|l|millilitres?|milliliters?|mls?|ml)(?![a-z])",
        compact,
    ):
        number = Decimal(amount)
        if unit.startswith("kg") or unit.startswith("kilogram"):
            found.add((number * 1000, "mass_g"))
        elif unit.startswith("g"):
            found.add((number, "mass_g"))
        elif unit in {"l", "litre", "litres", "liter", "liters"}:
            found.add((number * 1000, "volume_ml"))
        else:
            found.add((number, "volume_ml"))
    return found


def _amount_agrees(gold: dict[str, Any], prediction: dict[str, Any]) -> bool:
    # Gross and net can differ when a discount is paired to one item. Either
    # printed charged amount or printed unit/gross price is useful for pairing.
    expected = (_decimal(gold.get("line_total")), _decimal(gold.get("unit_price")))
    actual = (_decimal(prediction.get("line_total")), _decimal(prediction.get("unit_price")))
    return any(
        left is not None and right is not None and abs(left - right) <= Decimal("0.01")
        for left in expected for right in actual
    )


def _pair_score(gold: dict[str, Any], prediction: dict[str, Any]) -> float | None:
    left, right = _words(gold.get("name_raw")), _words(prediction.get("name_raw"))
    if not left or not right:
        return None
    similarity = SequenceMatcher(None, left, right).ratio()
    gold_tokens, predicted_tokens = set(left.split()), set(right.split())
    shared = len(gold_tokens & predicted_tokens) / max(1, min(len(gold_tokens), len(predicted_tokens)))
    amount_match = _amount_agrees(gold, prediction)
    # A shared price alone is never enough: two different items can cost the
    # same. Conversely, OCR may slightly change a printed abbreviation.
    if similarity < 0.68 and not (similarity >= 0.52 and amount_match and shared >= 0.34):
        return None
    return similarity * 100 + (20 if amount_match else 0) + (20 if left == right else 0)


def _validate_rubric(gold_by_image: dict[str, dict[str, Any]], rubric: dict[str, Any]) -> list[dict[str, Any]]:
    if rubric.get("version") != 1 or not isinstance(rubric.get("cases"), list):
        raise ValueError("Invalid rubric version")
    cases: list[dict[str, Any]] = rubric["cases"]
    seen: set[tuple[str, int]] = set()
    excluded = rubric.get("excluded_uncertain_examples", [])
    if not isinstance(excluded, list):
        raise ValueError("Invalid exclusion list")
    for position, case in enumerate(cases + excluded):
        if not isinstance(case, dict):
            raise ValueError("Invalid rubric case")
        image_path, index = case.get("image_path"), case.get("gold_index")
        if not isinstance(image_path, str) or not isinstance(index, int):
            raise ValueError("Invalid rubric reference")
        lines = (gold_by_image.get(image_path) or {}).get("lines") or []
        if not isinstance(lines, list) or index < 0 or index >= len(lines):
            raise ValueError("Rubric reference does not exist in draft gold")
        if position < len(cases):
            key = (image_path, index)
            if key in seen or case.get("stratum") not in STRATA:
                raise ValueError("Duplicate or invalid rubric case")
            seen.add(key)
            if _words(case.get("printed_name")) != _words(lines[index].get("name_raw")):
                raise ValueError("Rubric printed text differs from draft gold")
            groups = case.get("required_any_of")
            if not isinstance(groups, list) or not groups or any(
                not isinstance(group, list) or not group or any(not isinstance(phrase, str) for phrase in group)
                for group in groups
            ):
                raise ValueError("Invalid rubric expected-meaning groups")
    return cases


def _match_cases(
    cases: list[dict[str, Any]], gold_lines: list[dict[str, Any]], predicted_lines: list[dict[str, Any]],
) -> dict[int, dict[str, Any]]:
    """One-to-one greedy assignment, price-aware for duplicate purchases."""
    edges: list[tuple[float, int, int]] = []
    for case_index, case in enumerate(cases):
        gold = gold_lines[case["gold_index"]]
        for prediction_index, prediction in enumerate(predicted_lines):
            if not isinstance(prediction, dict):
                continue
            score = _pair_score(gold, prediction)
            if score is not None:
                # Stable tie-breakers keep duplicate-price observations
                # deterministic without pretending source_order is perfect.
                edges.append((score, case_index, prediction_index))
    edges.sort(key=lambda edge: (-edge[0], edge[1], edge[2]))
    matched: dict[int, dict[str, Any]] = {}
    used_predictions: set[int] = set()
    for _score, case_index, prediction_index in edges:
        if case_index not in matched and prediction_index not in used_predictions:
            matched[case_index] = predicted_lines[prediction_index]
            used_predictions.add(prediction_index)
    return matched


def _classify(case: dict[str, Any], gold: dict[str, Any], prediction: dict[str, Any] | None) -> str:
    if prediction is None:
        return "missing_ocr_line"
    raw = _words(prediction.get("name_raw"))
    expanded = _words(prediction.get("name_expanded"))
    if not expanded or expanded == raw:
        return "abstained"
    printed_measurements = _printed_measurements(gold.get("name_raw"))
    expanded_measurements = _printed_measurements(prediction.get("name_expanded"))
    if expanded_measurements - printed_measurements:
        return "wrong_expansion"
    if all(any(_contains_phrase(expanded, phrase) for phrase in group) for group in case["required_any_of"]):
        return "correct_expansion"
    return "wrong_expansion"


def _summary(counter: Counter[str], observations: int) -> dict[str, Any]:
    correct = counter["correct_expansion"]
    attempted = correct + counter["wrong_expansion"]
    return {
        "observations": observations,
        **{status: counter[status] for status in STATUSES},
        "correct_per_observation": round(correct / observations, 4) if observations else None,
        "precision_when_attempted": round(correct / attempted, 4) if attempted else None,
        "attempt_rate_among_seen_lines": round(
            attempted / (observations - counter["missing_ocr_line"] - counter["provider_failure"]), 4
        ) if observations > counter["missing_ocr_line"] + counter["provider_failure"] else None,
    }


def evaluate(manifest: dict[str, Any], gold: dict[str, Any], rubric: dict[str, Any]) -> dict[str, Any]:
    if manifest.get("experiment_id") != EXPERIMENT_ID:
        raise ValueError("Experiment protocol mismatch")
    receipts = manifest.get("receipts")
    gold_receipts = gold.get("receipts")
    if not isinstance(receipts, list) or not isinstance(gold_receipts, list):
        raise ValueError("Invalid private manifest or gold")
    gold_by_image = {item.get("image_path"): item.get("gold") or {} for item in gold_receipts if isinstance(item, dict)}
    if len(gold_by_image) != len(gold_receipts) or len(receipts) != len(gold_receipts):
        raise ValueError("Gold/manifest receipt count mismatch")
    cases = _validate_rubric(gold_by_image, rubric)
    cases_by_image: dict[str, list[dict[str, Any]]] = {}
    for case in cases:
        cases_by_image.setdefault(case["image_path"], []).append(case)
    if {item.get("image_path") for item in receipts} != set(gold_by_image):
        raise ValueError("Gold/manifest receipt identity mismatch")

    provider_reports: dict[str, Any] = {}
    all_complete = True
    for provider in PROVIDERS:
        by_stratum = {stratum: Counter() for stratum in STRATA}
        completed_runs = 0
        failed_runs = 0
        for receipt in receipts:
            image_path = receipt["image_path"]
            local_cases = cases_by_image.get(image_path, [])
            predictions = (receipt.get("predictions") or {}).get(provider) or []
            if not isinstance(predictions, list) or len(predictions) > RUNS_PER_RECEIPT:
                raise ValueError("Unexpected provider run count")
            completed_runs += len(predictions)
            for record in predictions:
                if not isinstance(record, dict) or record.get("provider") != provider:
                    raise ValueError("Provider prediction slot mismatch")
                if record.get("error_type"):
                    failed_runs += 1
                    for case in local_cases:
                        by_stratum[case["stratum"]]["provider_failure"] += 1
                    continue
                predicted_lines = record.get("lines") or []
                if not isinstance(predicted_lines, list):
                    raise ValueError("Invalid provider lines")
                matched = _match_cases(local_cases, gold_by_image[image_path]["lines"], predicted_lines)
                for index, case in enumerate(local_cases):
                    gold_line = gold_by_image[image_path]["lines"][case["gold_index"]]
                    by_stratum[case["stratum"]][_classify(case, gold_line, matched.get(index))] += 1
        expected_runs = len(receipts) * RUNS_PER_RECEIPT
        if completed_runs != expected_runs:
            all_complete = False
        total = sum(by_stratum.values(), Counter())
        provider_reports[provider] = {
            "completed_runs": completed_runs,
            "expected_runs": expected_runs,
            "provider_failure_runs": failed_runs,
            "all_scored_abbreviations": _summary(total, sum(total.values())),
            "food_identity_abbreviations": _summary(by_stratum["food_identity"], sum(by_stratum["food_identity"].values())),
            "ancillary_or_nonfood_abbreviations": _summary(
                by_stratum["ancillary_or_nonfood"], sum(by_stratum["ancillary_or_nonfood"].values())
            ),
        }
    return {
        "status": "five_receipt_pilot_complete_gold_review_pending" if all_complete else "incomplete_pilot",
        "protocol": EXPERIMENT_ID,
        "gold_review_status": rubric.get("review_status"),
        "receipt_count": len(receipts),
        "rubric_case_count": len(cases),
        "distinct_printed_label_count": len({(case["image_path"], _words(case["printed_name"])) for case in cases}),
        "food_identity_case_count": sum(case["stratum"] == "food_identity" for case in cases),
        "excluded_uncertain_example_count": len(rubric.get("excluded_uncertain_examples", [])),
        "primary_metric": "food_identity_abbreviations.correct_per_observation",
        "metric_limit": "Lexical check of required meanings and printed measures; unsupported nonnumeric modifiers still require human review",
        "failure_handling": "Transport, timeout, and provider-contract failures count as provider_failure, not missing_ocr_line",
        "provider_role_note": "Azure adapter is OCR-only and supplies no native name_expanded; this metric excludes shared dictionary/canonical-food matching",
        "sampling_note": "Repeated runs and separately charged duplicate product rows are correlated observations, not independent receipts or unique food types",
        "pilot_comparison_permitted": all_complete and len(receipts) >= 5,
        "formal_accuracy_claim_permitted": all_complete and rubric.get("review_status") == "independently_verified",
        "providers": provider_reports,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("private_dir", type=Path, help="Ignored receipt_eval_private directory")
    root = parser.parse_args().private_dir.resolve()
    if root.name != "receipt_eval_private":
        parser.error("Use the ignored receipt_eval_private directory")
    try:
        manifest = json.loads((root / EXPERIMENT_MANIFEST).read_text(encoding="utf-8"))
        gold = json.loads((root / "gold_lines_draft.json").read_text(encoding="utf-8"))
        rubric = json.loads((root / "abbreviation_gold_rubric_v1.json").read_text(encoding="utf-8"))
        result = evaluate(manifest, gold, rubric)
    except (OSError, ValueError, KeyError, TypeError):
        parser.exit(1, "Private evaluation input invalid; no receipt content was displayed.\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
