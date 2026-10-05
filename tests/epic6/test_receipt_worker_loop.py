"""Regression for consecutive Celery receipts in one prefork process."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from scripts import receipt_tasks
from services.api.app.db import database_url


def test_consecutive_worker_tasks_do_not_reuse_a_closed_loop_connection(monkeypatch):
    # Deliberately use a pooled engine. The normal pytest app engine uses
    # NullPool, which would hide the production-only asyncpg loop failure.
    pooled_engine = create_async_engine(database_url)
    queried = []

    async def query_database(receipt_id: str) -> None:
        async with pooled_engine.connect() as conn:
            assert await conn.scalar(text("select 1")) == 1
        queried.append(receipt_id)

    monkeypatch.setattr(receipt_tasks, "engine", pooled_engine)
    monkeypatch.setattr(receipt_tasks, "run_extraction", query_database)

    receipt_tasks.process_receipt_sync("first")
    receipt_tasks.process_receipt_sync("second")

    assert queried == ["first", "second"]
