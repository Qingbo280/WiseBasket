"""The USD5 evaluation budget is durable and concurrent, not an in-memory counter."""

from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import pytest

from scripts.collect_receipt_provider_predictions import (
    _private_inference_url, reserve_evaluation_cost,
)


def test_durable_budget_hard_stops_at_usd5(tmp_path):
    ledger = tmp_path / "budget.sqlite3"
    for _ in range(250):
        reserve_evaluation_cost(ledger, Decimal("0.02"))
    with pytest.raises(ValueError, match="exhausted"):
        reserve_evaluation_cost(ledger, Decimal("0.02"))


def test_ten_receipts_three_runs_three_providers_fit_hard_cap(tmp_path):
    ledger = tmp_path / "budget.sqlite3"
    for _ in range(10 * 3):
        for ceiling in (Decimal("0.12"), Decimal("0.02"), Decimal("0.02")):
            reserve_evaluation_cost(ledger, ceiling)
    with pytest.raises(ValueError, match="exhausted"):
        reserve_evaluation_cost(ledger, Decimal("0.21"))


def test_concurrent_collectors_cannot_overspend(tmp_path):
    ledger = tmp_path / "budget.sqlite3"

    def attempt(_):
        try:
            reserve_evaluation_cost(ledger, Decimal("0.50"))
            return True
        except ValueError:
            return False

    with ThreadPoolExecutor(max_workers=8) as pool:
        allowed = list(pool.map(attempt, range(16)))
    assert sum(allowed) == 10


def test_raw_image_endpoint_must_be_private():
    assert _private_inference_url("http://localhost:8080/") == "http://localhost:8080"
    assert _private_inference_url("http://inference.railway.internal:8080")
    with pytest.raises(ValueError):
        _private_inference_url("https://public-example.com/receipt/redact")
    with pytest.raises(ValueError):
        _private_inference_url("http://inference.railway.internal.evil.com")
