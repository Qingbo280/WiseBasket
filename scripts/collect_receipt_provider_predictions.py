"""Private live collector with a durable USD5 evaluation budget hard stop.

No request runs by default: it requires an ignored private directory, rotated
keys, a private inference endpoint and a verified price ceiling for every
selected provider. It never writes raw images or OCR/provider bodies to logs.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sqlite3
import sys
import time
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlparse

import httpx
from pydantic import ValidationError

from services.api.app.config import Settings
from services.api.app.services.receipt_cloud_providers import (
    ProviderConfig, _validate_endpoint, estimate_kimi_input_tokens, extract,
)
from services.api.app.services.receipt_cloud_runtime import _known_returned_model, _redact, price_ceiling_usd
from scripts.evaluate_receipt_providers import PROVIDERS, RUNS_PER_RECEIPT, evaluate


LIMIT_MICRO_USD = 5_000_000
EXPERIMENT_ID = "raw-and-expanded-purchases-v2"
EXPERIMENT_MANIFEST = "manifest_raw_and_expanded_v2.json"


def _private_inference_url(value: str) -> str:
    parsed = urlparse(value)
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in {"http", "https"} or parsed.username or parsed.password or not (
        host in {"localhost", "127.0.0.1"} or host.endswith(".railway.internal")
    ):
        raise ValueError("Inference endpoint must be localhost or Railway private DNS")
    return value.rstrip("/")


def _private_file(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError("Private receipt image path is unavailable")
    return path


def _configs(settings: Settings, selected: tuple[str, ...]) -> list[tuple[ProviderConfig, Decimal]]:
    all_configs = {
        "kimi": ProviderConfig("kimi", settings.kimi_model, settings.kimi_base_url, settings.kimi_api_key),
        "deepseek": ProviderConfig("deepseek", settings.deepseek_model, settings.deepseek_base_url, settings.deepseek_api_key),
        "azure": ProviderConfig("azure", "prebuilt-receipt", settings.azure_document_intelligence_endpoint,
                                settings.azure_document_intelligence_key),
    }
    result = []
    for name in selected:
        config = all_configs[name]
        ceiling = price_ceiling_usd(config, settings)
        if not config.api_key or ceiling is None:
            raise ValueError(f"{name} key, model, or verified price ceiling unavailable")
        _validate_endpoint(config)
        result.append((config, ceiling))
    return result


def reserve_evaluation_cost(ledger_path: Path, ceiling: Decimal) -> None:
    """SQLite BEGIN IMMEDIATE serializes even separate collector processes.

    A hold is permanent after commit, including timeout and unknown outcome.
    No reset/refund operation exists in this tool.
    """
    if not ceiling.is_finite() or ceiling <= 0:
        raise ValueError("Invalid evaluation price ceiling")
    micros = int((ceiling * Decimal(1_000_000)).to_integral_value())
    if micros <= 0:
        raise ValueError("Evaluation price ceiling is too small")
    with sqlite3.connect(ledger_path, timeout=30, isolation_level=None) as db:
        db.execute("CREATE TABLE IF NOT EXISTS reservation (id INTEGER PRIMARY KEY, micro_usd INTEGER NOT NULL CHECK(micro_usd > 0))")
        db.execute("BEGIN IMMEDIATE")
        try:
            used = db.execute("SELECT COALESCE(SUM(micro_usd), 0) FROM reservation").fetchone()[0]
            if used + micros > LIMIT_MICRO_USD:
                raise ValueError("USD5 evaluation budget exhausted")
            db.execute("INSERT INTO reservation(micro_usd) VALUES (?)", (micros,))
            db.execute("COMMIT")
        except Exception:
            db.execute("ROLLBACK")
            raise


def _atomic_manifest(path: Path, manifest: dict) -> None:
    temporary = path.with_suffix(".next")
    temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _experiment_manifest(root: Path) -> tuple[Path, dict]:
    """Keep earlier raw-only observations intact across prompt revisions."""
    path = root / EXPERIMENT_MANIFEST
    if path.is_file():
        manifest = json.loads(path.read_text(encoding="utf-8"))
        if manifest.get("experiment_id") != EXPERIMENT_ID:
            raise ValueError("Private experiment protocol mismatch")
        return path, manifest
    original = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    receipts = original.get("receipts")
    if not isinstance(receipts, list) or not receipts:
        raise ValueError("Private manifest has no receipts")
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "receipts": [
            {key: value for key, value in receipt.items() if key != "predictions"}
            for receipt in receipts
        ],
    }
    _atomic_manifest(path, manifest)
    return path, manifest


async def collect(
    root: Path, selected: tuple[str, ...], settings: Settings,
    max_new_runs: int | None = None, receipt_index: int | None = None,
    target_runs: int = RUNS_PER_RECEIPT,
) -> dict:
    if root.name != "receipt_eval_private" or not root.is_dir():
        raise ValueError("Use an existing receipt_eval_private directory")
    if not settings.receipt_cloud_keys_rotated:
        raise ValueError("Rotated-key acknowledgement is required")
    inference_url = _private_inference_url(settings.inference_url)
    configs = _configs(settings, selected)  # verify ALL before any network I/O
    manifest_path, manifest = _experiment_manifest(root)
    receipts = manifest.get("receipts")
    if not isinstance(receipts, list) or not receipts:
        raise ValueError("Private manifest has no receipts")
    ledger_path = root / "evaluation_budget.sqlite3"
    new_runs = 0
    async with httpx.AsyncClient(trust_env=False, follow_redirects=False) as client:
        for index, receipt in enumerate(receipts, start=1):
            if receipt_index is not None and index != receipt_index:
                continue
            image_path = _private_file(root, str(receipt.get("image_path") or ""))
            image = image_path.read_bytes()
            if not image or len(image) > 8 * 1024 * 1024:
                raise ValueError("Invalid private receipt image size")
            import base64
            original_b64 = base64.b64encode(image).decode("ascii")
            # One fixed mask per receipt is reused across providers and runs.
            redacted, _private_header = await _redact(
                client, original_b64, "normal", inference_url, time.monotonic() + 120,
            )
            predictions = receipt.setdefault("predictions", {})
            for config, ceiling in configs:
                records = predictions.setdefault(config.provider, [])
                while len(records) < target_runs:
                    reserve_evaluation_cost(ledger_path, ceiling)  # commit before paid I/O
                    if config.provider == "kimi":
                        await estimate_kimi_input_tokens(client, redacted, time.monotonic() + 120, config)
                    try:
                        result = await extract(client, redacted, time.monotonic() + 120, config)
                        if not _known_returned_model(result, settings):
                            raise ValueError("Unknown returned model version")
                        record = result.model_dump(mode="json")
                    except (ValueError, ValidationError, asyncio.TimeoutError, httpx.TransportError) as exc:
                        # A reserved attempt counts even when a provider returned
                        # truncated/malformed output. Keep only a safe error type;
                        # never persist the response body or extracted private text.
                        record = {
                            "provider": config.provider, "requested_model": config.model,
                            "lines": [], "error_type": type(exc).__name__,
                        }
                    record["reserved_upper_bound_usd"] = str(ceiling)
                    records.append(record)
                    _atomic_manifest(manifest_path, manifest)
                    new_runs += 1
                    if max_new_runs is not None and new_runs >= max_new_runs:
                        return evaluate(manifest)
    return evaluate(manifest)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("private_dir", type=Path)
    parser.add_argument("--providers", nargs="+", choices=PROVIDERS, default=list(PROVIDERS))
    parser.add_argument("--max-new-runs", type=int, default=None, help="Pilot a bounded number of paid runs")
    parser.add_argument("--receipt-index", type=int, default=None, help="One-based receipt index for a private pilot")
    parser.add_argument("--target-runs", type=int, default=RUNS_PER_RECEIPT,
                        help="Complete each receipt to 1, 2 or 3 runs before the next round")
    args = parser.parse_args()
    if args.max_new_runs is not None and args.max_new_runs < 1:
        parser.error("--max-new-runs must be positive")
    if args.receipt_index is not None and args.receipt_index < 1:
        parser.error("--receipt-index must be positive")
    if not 1 <= args.target_runs <= RUNS_PER_RECEIPT:
        parser.error("--target-runs must be between 1 and 3")
    # The repository-root .env is ignored by Git and is the same backend
    # settings source as the API. The rotated-key flag is still mandatory.
    settings = Settings()
    try:
        report = asyncio.run(collect(
            args.private_dir.resolve(), tuple(args.providers), settings,
            args.max_new_runs, args.receipt_index, args.target_runs,
        ))
    except ValidationError as exc:
        # Pydantic's default exception includes receipt field input values.
        # Report only schema paths and error types, never those values.
        issues = [
            {"path": ".".join(str(part) for part in issue["loc"]), "type": issue["type"]}
            for issue in exc.errors(include_input=False)[:5]
        ]
        print(f"Private evaluation stopped: ValidationError fields={json.dumps(issues)}", file=sys.stderr)
        raise SystemExit(1) from None
    except httpx.HTTPStatusError as exc:
        # Status and a short service error code are safe diagnostics; never
        # print provider messages, URLs, headers, or request/response bodies.
        try:
            code = str((exc.response.json().get("error") or {}).get("code") or "")
        except (ValueError, AttributeError, TypeError):
            code = ""
        safe_code = code if code.isascii() and code.replace("_", "").isalnum() and len(code) <= 40 else "unknown"
        print(f"Private evaluation stopped: HTTPStatusError status={exc.response.status_code} code={safe_code}", file=sys.stderr)
        raise SystemExit(1) from None
    except Exception as exc:
        # Never print exception text: provider errors can contain request data.
        print(f"Private evaluation stopped: {type(exc).__name__}", file=sys.stderr)
        raise SystemExit(1) from None
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
