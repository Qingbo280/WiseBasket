"""Receipt OCR queue contracts that do not require a database."""
from __future__ import annotations

import asyncio
from decimal import Decimal
from types import SimpleNamespace

from scripts import receipt_tasks
from services.api.app.services import receipt_extraction


def test_inline_receipts_are_processed_one_at_a_time(monkeypatch):
    active = 0
    peak_active = 0

    async def fake_once(receipt_id: str) -> None:
        nonlocal active, peak_active
        active += 1
        peak_active = max(peak_active, active)
        await asyncio.sleep(0.01)
        active -= 1

    monkeypatch.setattr(receipt_extraction, "_run_extraction_once", fake_once)
    monkeypatch.setattr(receipt_extraction, "get_settings", lambda: SimpleNamespace(inference_url="http://test"))

    async def run_pair() -> None:
        await asyncio.gather(
            receipt_extraction.run_extraction("00000000-0000-0000-0000-000000000001"),
            receipt_extraction.run_extraction("00000000-0000-0000-0000-000000000002"),
        )

    asyncio.run(run_pair())

    assert peak_active == 1


def test_worker_releases_asyncpg_pool_before_closing_each_task_loop(monkeypatch):
    seen: list[tuple[str, asyncio.AbstractEventLoop]] = []

    async def fake_process(receipt_id: str) -> None:
        seen.append((receipt_id, asyncio.get_running_loop()))

    class FakeEngine:
        async def dispose(self) -> None:
            seen.append(("dispose", asyncio.get_running_loop()))

    monkeypatch.setattr(receipt_tasks, "process_receipt", fake_process)
    monkeypatch.setattr(receipt_tasks, "engine", FakeEngine())

    receipt_tasks.process_receipt_sync("first")
    receipt_tasks.process_receipt_sync("second")

    assert [event for event, _ in seen] == ["first", "dispose", "second", "dispose"]
    assert seen[0][1] is seen[1][1]
    assert seen[2][1] is seen[3][1]
    assert seen[0][1] is not seen[2][1]


def test_worker_releases_asyncpg_pool_even_when_receipt_raises(monkeypatch):
    disposed = []
    failed = []

    async def fail(_receipt_id: str) -> None:
        raise RuntimeError("claim failed")

    class FakeEngine:
        async def dispose(self) -> None:
            disposed.append(asyncio.get_running_loop())

    monkeypatch.setattr(receipt_tasks, "process_receipt", fail)
    monkeypatch.setattr(receipt_tasks, "engine", FakeEngine())
    async def record_failure(receipt_id: str, error_type: str) -> None:
        failed.append((receipt_id, error_type))
    monkeypatch.setattr(receipt_tasks, "_fail_crashed_receipt", record_failure)

    try:
        receipt_tasks.process_receipt_sync("failed")
    except RuntimeError as exc:
        assert str(exc) == "claim failed"
    else:
        raise AssertionError("task exception was suppressed")
    assert len(disposed) == 1
    assert failed == [("failed", "RuntimeError")]


def test_ocr_numbers_outside_receipt_column_precision_are_ignored():
    """A barcode must not become a receipt quantity and fail the whole scan."""
    for module in (receipt_extraction, receipt_tasks):
        assert module._num_or_none("999999999.999", maximum=module._RECEIPT_QTY_MAX) == Decimal("999999999.999")
        assert module._num_or_none("1000000000", maximum=module._RECEIPT_QTY_MAX) is None
        assert module._num_or_none("10000000000", maximum=module._RECEIPT_PRICE_MAX) is None
