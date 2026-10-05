"""Private, budgeted text-only pilot of catalogue-constrained receipt suggestions.

This experiment reuses first-run DeepSeek purchases from the five-image v2
manifest. It sends ONLY their item names and ACTIVE local catalogue names to
DeepSeek. It never sends original images, headers, receipts, or gold answers.
The separate experimental calls are reserved in the same durable USD5 ledger
as the image trials. Results stay in ignored ``receipt_eval_private``.

The pilot does not change the production matcher or declare a model winner.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path
from typing import Any

import httpx

from scripts.collect_receipt_provider_predictions import reserve_evaluation_cost
from scripts.evaluate_receipt_canonical import (
    EXPERIMENT_ID, _gold_cases, _production_match, _trusted_aliases,
    load_local_catalogue,
)
from scripts.evaluate_receipt_providers import _line_pairs
from packages.receipt_catalog_suggestions import (
    build_catalogue_suggestion_prompt, combine_review_candidates,
    parse_catalogue_suggestions,
)
from services.api.app.config import Settings
from services.api.app.services.receipt_cloud_contract import ReceiptExtraction
from services.api.app.services.receipt_cloud_providers import (
    ProviderConfig, _validate_endpoint, repair_repeated_barcode_lines,
)
from services.api.app.services.receipt_cloud_runtime import price_ceiling_usd


PILOT_VERSION = "catalog-mapping-text-only-v2"


def _aggregate(
    manifest: dict[str, Any], draft: dict[str, Any], sidecar: dict[str, Any],
    mappings: list[list[list[str]]], catalogue: tuple,
) -> dict[str, Any]:
    names, aliases, trusted_by_scope, active_ids = catalogue
    cases, _ = _gold_cases(manifest, draft, sidecar, active_ids)
    totals = {key: 0 for key in (
        "mapped_gold", "mapped_ocr_paired", "top1_hits", "top3_hits",
        "negative_gold", "negative_ocr_paired", "negative_with_candidates",
        "merged_top1_hits", "merged_top3_hits", "merged_negative_with_candidates",
    )}
    errors: list[dict[str, Any]] = []
    for receipt_index, (receipt, mapped_rows) in enumerate(
        zip(manifest["receipts"], mappings, strict=True), start=1,
    ):
        gold_lines, mapped, excluded = cases[receipt["image_path"]]
        first = ReceiptExtraction.model_validate(receipt["predictions"]["deepseek"][0])
        first.lines = repair_repeated_barcode_lines(first.lines)
        if len(mapped_rows) != len(first.lines):
            raise ValueError("Mapping count differs from first-run purchases")
        pairs, _ = _line_pairs(gold_lines, first, ocr_tolerant=True)
        by_predicted_id = {id(line): index for index, line in enumerate(first.lines)}
        by_gold_id = {id(gold): predicted for gold, predicted in pairs}
        trusted = _trusted_aliases(first, trusted_by_scope)
        totals["mapped_gold"] += len(mapped)
        totals["negative_gold"] += sum(
            reason in {"nonfood", "out_of_catalog"} for reason in excluded.values()
        )
        for index, gold in enumerate(gold_lines):
            predicted = by_gold_id.get(id(gold))
            if predicted is None:
                continue
            if index in mapped:
                target = mapped[index]
                ranked = mapped_rows[by_predicted_id[id(predicted)]]
                match = _production_match(predicted, names, aliases, trusted)
                merged = [food_id for food_id, _ in combine_review_candidates(
                    match.candidates, ranked, match.food_id,
                )]
                totals["mapped_ocr_paired"] += 1
                totals["top1_hits"] += bool(ranked) and ranked[0] == target
                totals["top3_hits"] += target in ranked
                totals["merged_top1_hits"] += bool(merged) and merged[0] == target
                totals["merged_top3_hits"] += target in merged
                if target not in ranked:
                    errors.append({"receipt": receipt_index, "gold_index": index,
                                   "kind": "miss", "target": target, "predicted": ranked})
            elif excluded.get(index) in {"nonfood", "out_of_catalog"}:
                totals["negative_ocr_paired"] += 1
                ranked = mapped_rows[by_predicted_id[id(predicted)]]
                totals["negative_with_candidates"] += bool(ranked)
                match = _production_match(predicted, names, aliases, trusted)
                merged = combine_review_candidates(match.candidates, ranked, match.food_id)
                totals["merged_negative_with_candidates"] += bool(merged)
                if ranked:
                    errors.append({"receipt": receipt_index, "gold_index": index,
                                   "kind": excluded[index], "predicted": ranked})
    totals["top1_recall"] = round(totals["top1_hits"] / totals["mapped_gold"], 4)
    totals["top3_recall"] = round(totals["top3_hits"] / totals["mapped_gold"], 4)
    totals["merged_top1_recall"] = round(totals["merged_top1_hits"] / totals["mapped_gold"], 4)
    totals["merged_top3_recall"] = round(totals["merged_top3_hits"] / totals["mapped_gold"], 4)
    totals["negative_false_candidate_rate"] = round(
        totals["negative_with_candidates"] / totals["negative_ocr_paired"], 4
    ) if totals["negative_ocr_paired"] else None
    totals["merged_negative_false_candidate_rate"] = round(
        totals["merged_negative_with_candidates"] / totals["negative_ocr_paired"], 4
    ) if totals["negative_ocr_paired"] else None
    totals["error_positions"] = errors
    return totals


async def run(private_dir: Path, settings: Settings) -> dict[str, Any]:
    root = private_dir.resolve()
    if root.name != "receipt_eval_private" or not root.is_dir():
        raise ValueError("Use the ignored private evaluation directory")
    if not settings.receipt_cloud_keys_rotated:
        raise ValueError("Rotated-key acknowledgement is required")
    config = ProviderConfig("deepseek", settings.deepseek_model,
                            settings.deepseek_base_url, settings.deepseek_api_key)
    base = _validate_endpoint(config)
    ceiling = price_ceiling_usd(config, settings)
    if ceiling is None:
        raise ValueError("Verified DeepSeek price ceiling unavailable")
    manifest = json.loads((root / "manifest_raw_and_expanded_v2.json").read_text(encoding="utf-8"))
    draft = json.loads((root / "gold_lines_draft.json").read_text(encoding="utf-8"))
    sidecar = json.loads((root / "canonical_food_gold_v1.json").read_text(encoding="utf-8"))
    if manifest.get("experiment_id") != EXPERIMENT_ID or len(manifest.get("receipts", [])) != 5:
        raise ValueError("This pilot requires exactly the five-image v2 manifest")
    catalogue = load_local_catalogue()
    names, _, _, active_ids = catalogue
    result_path = root / "catalog_mapping_pilot_v2.json"
    stored = json.loads(result_path.read_text(encoding="utf-8")) if result_path.is_file() else {
        "protocol": PILOT_VERSION, "mappings": [],
    }
    if stored.get("protocol") != PILOT_VERSION or len(stored.get("mappings", [])) > 5:
        raise ValueError("Private pilot protocol mismatch")
    mappings = stored["mappings"]
    async with httpx.AsyncClient(trust_env=False, follow_redirects=False) as client:
        for receipt in manifest["receipts"][len(mappings):]:
            first = ReceiptExtraction.model_validate(receipt["predictions"]["deepseek"][0])
            first.lines = repair_repeated_barcode_lines(first.lines)
            prompt = build_catalogue_suggestion_prompt(first.lines, names)
            reserve_evaluation_cost(root / "evaluation_budget.sqlite3", ceiling)
            start = time.monotonic()
            response = await client.post(
                f"{base}/chat/completions",
                headers={"Authorization": f"Bearer {config.api_key}"},
                json={
                    "model": config.model, "temperature": 0, "thinking": {"type": "disabled"},
                    "response_format": {"type": "json_object"}, "max_tokens": 2048,
                    "messages": [{"role": "user", "content": (
                        prompt
                    )}],
                },
                timeout=90,
            )
            response.raise_for_status()
            data = response.json()
            if data.get("model") not in {"deepseek-flash", "deepseek-v4.1-flash", "DeepSeek-V4.1-Flash"}:
                raise ValueError("Unverified returned DeepSeek model")
            choices = data.get("choices") or []
            if not choices or choices[0].get("finish_reason") == "length":
                raise ValueError("Truncated catalogue mapping response")
            mapped = parse_catalogue_suggestions(
                choices[0].get("message", {}).get("content"), len(first.lines), active_ids,
            )
            mappings.append(mapped)
            result_path.write_text(json.dumps(stored, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"Completed catalogue pilot receipt {len(mappings)}/5 in {int((time.monotonic()-start)*1000)} ms")
    return _aggregate(manifest, draft, sidecar, mappings, catalogue)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("private_dir", type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(asyncio.run(run(args.private_dir, Settings())), indent=2))
    except (OSError, ValueError, TypeError, KeyError, httpx.HTTPError) as exc:
        parser.exit(1, f"Private catalogue pilot failed ({type(exc).__name__}); no receipt content displayed.\n")


if __name__ == "__main__":
    main()
