"""Celery wrappers for the single API/worker receipt extraction pipeline."""
from __future__ import annotations

import asyncio
import logging
import os
import uuid

import asyncpg

from scripts.daily_pricecatcher_update import celery_app
from services.api.app.config import get_settings
from services.api.app.db import database_url as app_database_url, engine
from services.api.app.services.receipt_extraction import (
    _RECEIPT_PRICE_MAX,
    _RECEIPT_QTY_MAX,
    _num_or_none,
    run_extraction,
)

TASK_NAME = "scripts.receipt_tasks.extract_receipt_task"
log = logging.getLogger(__name__)


def _database_url() -> str:
    url = os.environ.get("DATABASE_URL", "").strip().strip('"').strip("'")
    if url.startswith("postgresql+asyncpg://"):
        url = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    if not url:
        raise RuntimeError("DATABASE_URL is not set.")
    return url


async def process_receipt(receipt_id: str) -> None:
    """Worker and inline API use the same claim, matching and write path."""
    await run_extraction(receipt_id)


async def _fail_crashed_receipt(receipt_id: str, error_type: str) -> None:
    """Make a pre-claim worker crash visible immediately, not after 240 s."""
    # Use the same resolved target as the ORM engine. Reading DATABASE_URL
    # again can diverge after app startup (or test collection mutates env).
    conn = await asyncpg.connect(app_database_url.replace("postgresql+asyncpg://", "postgresql://", 1))
    try:
        await conn.execute(
            """
            update receipt
            set status = 'FAILED', error = $2, processed_at = now()
            where receipt_id = $1 and status in ('PENDING', 'PROCESSING')
            """,
            uuid.UUID(receipt_id),
            f"WORKER_{error_type}"[:80],
        )
    finally:
        await conn.close()


def process_receipt_sync(receipt_id: str) -> None:
    async def run_and_release_connections() -> None:
        try:
            await process_receipt(receipt_id)
        except Exception as exc:
            # The extraction service marks ordinary OCR/provider failures. A
            # crash while claiming the row happens before that handler and
            # otherwise leaves PENDING until the deadline job runs.
            try:
                await _fail_crashed_receipt(receipt_id, type(exc).__name__)
            except Exception:
                log.exception("could not mark crashed receipt as failed receipt=%s", receipt_id)
            raise
        finally:
            # Celery's prefork process handles each task with a new asyncio.run()
            # loop. A pooled asyncpg connection belongs to its original loop;
            # leaving it in the module-global engine makes the next receipt
            # fail before it can be claimed ("Future attached to a different
            # loop"). Dispose while this loop is still alive, even on error.
            await engine.dispose()

    asyncio.run(run_and_release_connections())


async def purge_expired_receipt_images() -> int:
    conn = await asyncpg.connect(_database_url())
    try:
        result = await conn.execute(
            """
            update receipt
            set image_bytes = null,
                status = case when status = 'PENDING' then 'FAILED' else status end,
                error = case when status = 'PENDING' then 'IMAGE_EXPIRED' else error end,
                processed_at = case when status = 'PENDING' then now() else processed_at end
            where image_bytes is not null and image_expires_at <= now()
            """
        )
        return int(result.rsplit(" ", 1)[-1])
    finally:
        await conn.close()


async def fail_expired_receipts() -> int:
    """Persist expired queue/processing states even when no phone is polling."""
    conn = await asyncpg.connect(_database_url())
    try:
        result = await conn.execute(
            """
            update receipt
            set status = 'FAILED', error = 'PROCESSING_DEADLINE_EXCEEDED',
                processed_at = now()
            where status in ('PENDING', 'PROCESSING')
              and coalesce(processing_deadline_at,
                           created_at + make_interval(secs => $1)) <= now()
            """,
            get_settings().receipt_processing_deadline_s,
        )
        return int(result.rsplit(" ", 1)[-1])
    finally:
        await conn.close()


if celery_app is not None:

    @celery_app.task
    def extract_receipt_task(receipt_id: str) -> None:
        process_receipt_sync(receipt_id)

    @celery_app.task
    def purge_expired_receipt_images_task() -> int:
        return asyncio.run(purge_expired_receipt_images())

    @celery_app.task
    def fail_expired_receipts_task() -> int:
        return asyncio.run(fail_expired_receipts())

else:
    extract_receipt_task = None  # type: ignore[assignment]
    purge_expired_receipt_images_task = None  # type: ignore[assignment]
    fail_expired_receipts_task = None  # type: ignore[assignment]
