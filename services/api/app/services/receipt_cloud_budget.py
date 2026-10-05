"""Transactional hard stop for optional paid receipt extraction calls."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import Receipt, ReceiptCloudCall, ReceiptCloudMonth


class CloudBudgetUnavailable(Exception):
    pass


async def reserve_receipt_cloud_call(
    db: AsyncSession,
    receipt_id: uuid.UUID,
    provider: str,
    model: str,
    max_cost_usd: Decimal | None,
    monthly_limit_usd: Decimal = Decimal("10.00"),
) -> int:
    """Reserve worst-case cost before I/O; never refund uncertain outcomes.

    The provider adapter supplies a verified price-derived upper bound. An
    unknown model/version has no bound and therefore cannot make a paid call.
    Caller commits this transaction before sending any request to a provider.
    """
    if max_cost_usd is None or not max_cost_usd.is_finite() or max_cost_usd <= 0:
        raise CloudBudgetUnavailable("Unknown or invalid provider price ceiling")
    if not monthly_limit_usd.is_finite() or monthly_limit_usd <= 0:
        raise CloudBudgetUnavailable("Monthly budget is unavailable")
    receipt = await db.scalar(select(Receipt).where(Receipt.receipt_id == receipt_id).with_for_update())
    if receipt is None or receipt.status != "PROCESSING":
        raise CloudBudgetUnavailable("Receipt is not processing")
    month = datetime.now(UTC).strftime("%Y-%m")
    await db.execute(
        pg_insert(ReceiptCloudMonth)
        .values(utc_month=month, reserved_usd=Decimal("0"), call_count=0)
        .on_conflict_do_nothing(index_elements=["utc_month"])
    )
    ledger = await db.scalar(
        select(ReceiptCloudMonth).where(ReceiptCloudMonth.utc_month == month).with_for_update()
    )
    call_count = await db.scalar(
        select(func.count()).select_from(ReceiptCloudCall).where(ReceiptCloudCall.receipt_id == receipt_id)
    )
    if call_count >= 2:
        raise CloudBudgetUnavailable("Per-receipt cloud call limit reached")
    if ledger.reserved_usd + max_cost_usd > monthly_limit_usd:
        raise CloudBudgetUnavailable("Monthly cloud budget reached")
    attempt_no = call_count + 1
    ledger.reserved_usd += max_cost_usd
    ledger.call_count += 1
    db.add(ReceiptCloudCall(
        receipt_id=receipt_id, attempt_no=attempt_no, utc_month=month,
        provider=provider[:32], model=model[:120], reserved_usd=max_cost_usd,
    ))
    await db.flush()
    return attempt_no
