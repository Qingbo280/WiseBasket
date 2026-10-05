"""Read-only local pilot: receipt OCR -> ranked canonical_food suggestions.

Uses the private v2 model predictions, visually reviewed food-ID sidecar, and
ACTIVE names/aliases from the *local Docker PostgreSQL container*. No model,
UAT, production, or paid API is contacted. Output is aggregate counts only;
neither product labels nor personal/receipt identifiers are printed.

Run from repository root::

    python -m scripts.evaluate_receipt_canonical receipt_eval_private

The five-receipt set is a pilot. Its food-ID gold is agent-reviewed but awaits
independent confirmation; no production winner should be declared from it.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import subprocess
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from packages.receipt_matching import normalize_label, normalize_receipt_item_label
from packages.receipt_matching_policy import propose_receipt_food
from services.api.app.services.receipt_cloud_contract import ReceiptExtraction
from services.api.app.services.receipt_cloud_providers import repair_repeated_barcode_lines
from services.api.app.services.receipt_extraction import _expand_label, _model_expansion

from .evaluate_receipt_providers import _line_pairs


EXPERIMENT_ID = "raw-and-expanded-purchases-v2"
PROVIDERS = ("kimi", "deepseek", "azure")
RUNS_PER_RECEIPT = 3
LOCAL_DB_CONTAINER = "wisebasket_batch1-postgres-1"
NEGATIVE_REASONS = frozenset({"nonfood", "out_of_catalog"})
AMBIGUOUS_REASONS = frozenset({"ambiguous_identity", "ambiguous_catalog_granularity"})


def _local_select(container: str, query: str) -> list[list[str]]:
    """Run one SELECT through the container's Unix socket in read-only mode."""
    command = [
        "docker", "exec", "-e", "PGOPTIONS=-c default_transaction_read_only=on",
        container, "psql", "-X", "-q", "-v", "ON_ERROR_STOP=1",
        "-h", "/var/run/postgresql", "-U", "wisebasket", "-d", "wisebasket",
        "-c", f"COPY ({query}) TO STDOUT WITH CSV",
    ]
    completed = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
    if completed.returncode:
        # stderr can carry environmental details; never echo it to a report.
        raise RuntimeError("Local read-only Docker catalogue query failed")
    return list(csv.reader(io.StringIO(completed.stdout)))


def load_local_catalogue(container: str = LOCAL_DB_CONTAINER) -> tuple[
    list[tuple[str, str]], list[tuple[str, str]], dict[str, list[tuple[str, str]]], set[str]
]:
    """The same 202 ACTIVE canonical names and active aliases used by API."""
    foods = _local_select(container,
        "SELECT canonical_food_id, canonical_name, COALESCE(canonical_name_ms, '') "
        "FROM canonical_food WHERE status = 'ACTIVE' ORDER BY canonical_food_id")
    aliases = _local_select(container,
        "SELECT fa.canonical_food_id, fa.alias_name FROM food_alias fa "
        "JOIN canonical_food cf ON cf.canonical_food_id = fa.canonical_food_id "
        "WHERE cf.status = 'ACTIVE' ORDER BY fa.food_alias_id")
    trusted = _local_select(container,
        "SELECT rta.retailer_scope, rta.canonical_food_id, rta.normalized_alias "
        "FROM receipt_trusted_alias rta JOIN canonical_food cf "
        "ON cf.canonical_food_id = rta.canonical_food_id "
        "WHERE cf.status = 'ACTIVE' ORDER BY rta.retailer_scope, rta.canonical_food_id")
    if any(len(row) != 3 for row in foods + trusted) or any(len(row) != 2 for row in aliases):
        raise ValueError("Invalid local catalogue query result")
    canonical_names = [
        (food_id, name) for food_id, english, malay in foods
        for name in (english, malay) if name
    ]
    trusted_by_scope: dict[str, list[tuple[str, str]]] = {}
    for scope, food_id, alias in trusted:
        trusted_by_scope.setdefault(scope, []).append((food_id, alias))
    return canonical_names, [(food_id, alias) for food_id, alias in aliases], trusted_by_scope, {
        row[0] for row in foods
    }


def _gold_cases(
    manifest: dict[str, Any], draft: dict[str, Any], sidecar: dict[str, Any], active_ids: set[str],
) -> tuple[dict[str, tuple[list[dict[str, Any]], dict[int, str], dict[int, str]]], Counter[str]]:
    if manifest.get("experiment_id") != EXPERIMENT_ID or sidecar.get("version") != 1:
        raise ValueError("Private experiment or food-ID gold version mismatch")
    receipts = manifest.get("receipts")
    gold_receipts = draft.get("receipts")
    reviewed_receipts = sidecar.get("receipts")
    if not all(isinstance(items, list) for items in (receipts, gold_receipts, reviewed_receipts)):
        raise ValueError("Missing private receipt array")
    images = [item.get("image_path") for item in receipts]
    gold_by_image = {item.get("image_path"): item.get("gold", {}).get("lines") for item in gold_receipts}
    review_by_image = {item.get("image_path"): item for item in reviewed_receipts}
    if (len(set(images)) != len(images) or len(gold_by_image) != len(gold_receipts)
            or len(review_by_image) != len(reviewed_receipts)
            or set(images) != set(gold_by_image) or set(images) != set(review_by_image)):
        raise ValueError("Private receipt identities do not align")
    cases: dict[str, tuple[list[dict[str, Any]], dict[int, str], dict[int, str]]] = {}
    totals: Counter[str] = Counter()
    for image in images:
        lines = gold_by_image[image]
        review = review_by_image[image]
        if not isinstance(lines, list) or len(lines) != review.get("line_count"):
            raise ValueError("Food-ID gold line count differs from draft OCR gold")
        mapped: dict[int, str] = {}
        excluded: dict[int, str] = {}
        for entry in review.get("mapped", []):
            index, food_id = entry.get("gold_index"), entry.get("canonical_food_id")
            if type(index) is not int or food_id not in active_ids or index in mapped:
                raise ValueError("Invalid or duplicate canonical-food gold")
            mapped[index] = food_id
        for entry in review.get("excluded", []):
            index, reason = entry.get("gold_index"), entry.get("reason")
            if (type(index) is not int or reason not in NEGATIVE_REASONS | AMBIGUOUS_REASONS
                    or index in excluded or index in mapped):
                raise ValueError("Invalid or duplicate gold exclusion")
            excluded[index] = reason
        if set(mapped) | set(excluded) != set(range(len(lines))):
            raise ValueError("Every gold purchase line needs exactly one review decision")
        totals["mapped"] += len(mapped)
        for reason in excluded.values():
            totals[reason] += 1
        cases[image] = (lines, mapped, excluded)
    return cases, totals


def _trusted_aliases(
    result: ReceiptExtraction, trusted_by_scope: dict[str, list[tuple[str, str]]],
) -> list[tuple[str, str]]:
    header = result.header
    if not (header.merchant and header.date and header.time
            and header.receipt_number and header.total is not None):
        return []
    try:
        datetime.fromisoformat(f"{header.date}T{header.time}")
    except ValueError:
        return []
    return trusted_by_scope.get(normalize_label(header.merchant), [])


def _production_match(
    line: Any, canonical_names: list[tuple[str, str]], aliases: list[tuple[str, str]],
    trusted: list[tuple[str, str]],
):
    """Mirror receipt_extraction's label construction; call production policy."""
    raw_name = line.name_raw
    cleaned_name = normalize_receipt_item_label(raw_name)
    model_expanded = _model_expansion(line.name_expanded)
    expanded_name = _expand_label(cleaned_name or raw_name, model_expanded)
    labels = [raw_name]
    if cleaned_name and cleaned_name.casefold() != raw_name.casefold():
        labels.append(cleaned_name)
    candidate_only_labels = []
    if expanded_name and expanded_name.casefold() != raw_name.casefold():
        candidate_only_labels.append(expanded_name)
    if model_expanded and model_expanded.casefold() not in {
        label.casefold() for label in labels + candidate_only_labels
    }:
        candidate_only_labels.append(model_expanded)
    return propose_receipt_food(
        labels, canonical_names, aliases, trusted,
        candidate_only_labels=candidate_only_labels,
    )


def _empty_counts() -> Counter[str]:
    return Counter({
        "completed_receipts": 0, "mapped_gold": 0, "mapped_ocr_paired": 0,
        "top1_hits": 0, "top3_hits": 0, "mapped_with_candidates": 0,
        "wrong_leading_candidate": 0, "effective_wrong_preselect": 0,
        "negative_gold": 0, "negative_ocr_paired": 0,
        "negative_with_candidates": 0, "effective_negative_preselect": 0,
        "ambiguous_gold": 0, "low_confidence_exact_suppressed": 0,
        "low_confidence_effective_preselect": 0, "unpaired_predictions": 0,
        "unpaired_predictions_with_candidates": 0,
    })


def _summarize(counts: Counter[str]) -> dict[str, Any]:
    output: dict[str, Any] = dict(counts)
    for key, numerator, denominator in (
        ("top1_recall", "top1_hits", "mapped_gold"),
        ("top3_recall", "top3_hits", "mapped_gold"),
        ("negative_false_candidate_rate", "negative_with_candidates", "negative_ocr_paired"),
    ):
        output[key] = round(counts[numerator] / counts[denominator], 4) if counts[denominator] else None
    return output


def evaluate(
    manifest: dict[str, Any], draft: dict[str, Any], sidecar: dict[str, Any],
    catalog: tuple[list[tuple[str, str]], list[tuple[str, str]], dict[str, list[tuple[str, str]]], set[str]],
) -> dict[str, Any]:
    canonical_names, aliases, trusted_by_scope, active_ids = catalog
    cases, totals = _gold_cases(manifest, draft, sidecar, active_ids)
    receipts = manifest["receipts"]
    providers: dict[str, Any] = {}
    complete = len(receipts) >= 10
    for provider in PROVIDERS:
        per_run = {index: _empty_counts() for index in range(1, RUNS_PER_RECEIPT + 1)}
        aggregate = _empty_counts()
        for receipt in receipts:
            image = receipt["image_path"]
            gold_lines, mapped, excluded = cases[image]
            predictions = (receipt.get("predictions") or {}).get(provider) or []
            if not isinstance(predictions, list) or len(predictions) > RUNS_PER_RECEIPT:
                raise ValueError("Invalid private provider run count")
            if len(predictions) != RUNS_PER_RECEIPT:
                complete = False
            for run_index, record in enumerate(predictions, start=1):
                if not isinstance(record, dict) or record.get("provider") != provider:
                    raise ValueError("Private provider slot mismatch")
                result = ReceiptExtraction.model_validate(record)
                if provider in {"kimi", "deepseek"}:
                    result.lines = repair_repeated_barcode_lines(result.lines)
                pairs, _ = _line_pairs(gold_lines, result, ocr_tolerant=True)
                prediction_by_gold_id = {id(gold): predicted for gold, predicted in pairs}
                paired_prediction_ids = {id(predicted) for _, predicted in pairs}
                trusted = _trusted_aliases(result, trusted_by_scope)
                counts = per_run[run_index]
                counts["completed_receipts"] += 1
                counts["mapped_gold"] += len(mapped)
                counts["negative_gold"] += sum(reason in NEGATIVE_REASONS for reason in excluded.values())
                counts["ambiguous_gold"] += sum(reason in AMBIGUOUS_REASONS for reason in excluded.values())
                for gold_index, gold in enumerate(gold_lines):
                    predicted = prediction_by_gold_id.get(id(gold))
                    if predicted is None:
                        continue
                    if gold_index in excluded and excluded[gold_index] in AMBIGUOUS_REASONS:
                        continue
                    match = _production_match(predicted, canonical_names, aliases, trusted)
                    candidates = [food_id for food_id, _ in match.candidates]
                    low_confidence = predicted.confidence is not None and predicted.confidence < 0.80
                    effective_preselect = match.food_id if not low_confidence else None
                    if low_confidence and match.food_id is not None:
                        counts["low_confidence_exact_suppressed"] += 1
                    if low_confidence and effective_preselect is not None:
                        counts["low_confidence_effective_preselect"] += 1
                    if gold_index in mapped:
                        target = mapped[gold_index]
                        counts["mapped_ocr_paired"] += 1
                        counts["mapped_with_candidates"] += bool(candidates)
                        counts["top1_hits"] += bool(candidates) and candidates[0] == target
                        counts["top3_hits"] += target in candidates
                        counts["wrong_leading_candidate"] += bool(candidates) and candidates[0] != target
                        counts["effective_wrong_preselect"] += (
                            effective_preselect is not None and effective_preselect != target
                        )
                    else:
                        counts["negative_ocr_paired"] += 1
                        counts["negative_with_candidates"] += bool(candidates)
                        counts["effective_negative_preselect"] += effective_preselect is not None
                for predicted in result.lines:
                    if id(predicted) in paired_prediction_ids:
                        continue
                    counts["unpaired_predictions"] += 1
                    match = _production_match(predicted, canonical_names, aliases, trusted)
                    counts["unpaired_predictions_with_candidates"] += bool(match.candidates)
        for counts in per_run.values():
            aggregate.update(counts)
        providers[provider] = {
            "completed_runs": aggregate["completed_receipts"],
            "expected_runs": len(receipts) * RUNS_PER_RECEIPT,
            "aggregate": _summarize(aggregate),
            "by_run": {str(index): _summarize(per_run[index]) for index in per_run},
        }
    return {
        "status": "pilot_complete_but_not_independently_verified" if complete else "incomplete_pilot",
        "protocol": EXPERIMENT_ID,
        "gold_review_status": sidecar.get("review_status"),
        "receipt_count": len(receipts),
        "active_catalog_food_count": len(active_ids),
        "gold_mapped_line_count": totals["mapped"],
        "gold_definite_negative_count": sum(totals[reason] for reason in NEGATIVE_REASONS),
        "gold_ambiguous_excluded_count": sum(totals[reason] for reason in AMBIGUOUS_REASONS),
        "risk_definition": "false candidate = any suggestion on a paired definite nonfood/out-of-catalog line; ambiguous lines are unscored",
        "sample_limit": "five receipts, correlated repeat purchases, agent-reviewed gold; do not use as production accuracy claim",
        "providers": providers,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("private_dir", type=Path, help="Ignored receipt_eval_private directory")
    args = parser.parse_args()
    root = args.private_dir.resolve()
    if root.name != "receipt_eval_private":
        parser.error("Use the ignored receipt_eval_private directory")
    try:
        manifest = json.loads((root / "manifest_raw_and_expanded_v2.json").read_text(encoding="utf-8"))
        draft = json.loads((root / "gold_lines_draft.json").read_text(encoding="utf-8"))
        sidecar = json.loads((root / "canonical_food_gold_v1.json").read_text(encoding="utf-8"))
        report = evaluate(manifest, draft, sidecar, load_local_catalogue())
    except (OSError, ValueError, TypeError, KeyError, RuntimeError, subprocess.SubprocessError):
        parser.exit(1, "Private canonical-food evaluation input invalid; no receipt content was displayed.\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
