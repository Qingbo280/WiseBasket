"""Retailer-scoped receipt alias learning from independent purchases."""
from __future__ import annotations

from sqlalchemy import delete, func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from packages.receipt_matching import normalize_label

from ..db import Receipt, ReceiptAliasVote, ReceiptLine, ReceiptLogicalPurchase, ReceiptTrustedAlias


async def record_receipt_alias_vote(
    db: AsyncSession, receipt: Receipt, line: ReceiptLine, canonical_food_id: str
) -> None:
    """One vote per logical purchase/scope/label, never a global overwrite."""
    if not receipt.logical_fingerprint or not receipt.merchant or line.client_line_id:
        return
    scope = normalize_label(receipt.merchant)[:240]
    alias = normalize_label(line.name_raw)[:240]
    if not scope or not alias:
        return
    purchase_id = await db.scalar(
        select(ReceiptLogicalPurchase.purchase_id).where(
            ReceiptLogicalPurchase.household_id == receipt.household_id,
            ReceiptLogicalPurchase.fingerprint == receipt.logical_fingerprint,
            ReceiptLogicalPurchase.canonical_receipt_id == receipt.receipt_id,
        )
    )
    if purchase_id is None:
        return
    # Different households can vote concurrently for the same retailer/alias.
    await db.execute(
        text("select pg_advisory_xact_lock(hashtextextended(:key, 0))"),
        {"key": scope + "|" + alias},
    )
    await db.execute(
        pg_insert(ReceiptAliasVote)
        .values(
            logical_purchase_id=purchase_id, retailer_scope=scope,
            normalized_alias=alias, canonical_food_id=canonical_food_id,
        )
        .on_conflict_do_nothing()
    )
    rows = (
        await db.execute(
            select(ReceiptAliasVote.canonical_food_id, func.count())
            .where(
                ReceiptAliasVote.retailer_scope == scope,
                ReceiptAliasVote.normalized_alias == alias,
            )
            .group_by(ReceiptAliasVote.canonical_food_id)
        )
    ).all()
    ranked = sorted(rows, key=lambda row: (-row[1], row[0]))
    if not ranked:
        return
    winner_id, winner_votes = ranked[0]
    total_votes = sum(count for _, count in ranked)
    if winner_votes >= 3 and winner_votes > total_votes - winner_votes:
        await db.execute(
            pg_insert(ReceiptTrustedAlias)
            .values(retailer_scope=scope, normalized_alias=alias, canonical_food_id=winner_id)
            .on_conflict_do_update(
                index_elements=["retailer_scope", "normalized_alias"],
                set_={"canonical_food_id": winner_id},
            )
        )
    elif len(ranked) > 1 and ranked[0][1] == ranked[1][1]:
        # A tie keeps an existing mapping; no existing mapping remains absent.
        return
    else:
        await db.execute(
            delete(ReceiptTrustedAlias).where(
                ReceiptTrustedAlias.retailer_scope == scope,
                ReceiptTrustedAlias.normalized_alias == alias,
            )
        )
