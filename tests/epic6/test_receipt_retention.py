"""Database-free contract for 24-hour receipt-image cleanup."""
from __future__ import annotations

import asyncio

from scripts import receipt_tasks


def test_expired_receipt_cleanup_removes_only_original_image_bytes(monkeypatch):
    queries: list[str] = []

    class FakeConnection:
        async def execute(self, query: str) -> str:
            queries.append(query)
            return "UPDATE 2"

        async def close(self) -> None:
            return None

    async def fake_connect(_url: str) -> FakeConnection:
        return FakeConnection()

    monkeypatch.setenv("DATABASE_URL", "postgresql://test")
    monkeypatch.setattr(receipt_tasks.asyncpg, "connect", fake_connect)

    assert asyncio.run(receipt_tasks.purge_expired_receipt_images()) == 2
    assert "set image_bytes = null" in queries[0]
    assert "image_expires_at <= now()" in queries[0]
    assert "status = 'PENDING' then 'FAILED'" in queries[0]
