"""Shared receipt extraction path used by inline API tasks and Celery worker."""
from __future__ import annotations

import asyncio
import base64
import logging
import time
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx
from sqlalchemy import delete, select, update

from packages.receipt_matching import (
    expand_receipt_label,
    normalize_label,
    normalize_receipt_item_label,
)
from packages.receipt_matching_policy import propose_receipt_food, verified_product_expansion
from packages.receipt_catalog_suggestions import combine_review_candidates
from packages.receipt_price_evidence import repair_barcode_paired_purchases
from packages.receipt_purchase_rules import ground_purchase_quantity, is_receipt_metadata
from ..config import get_settings
from ..db import AsyncSessionLocal, CanonicalFood, FoodAlias, Receipt, ReceiptLine, ReceiptTrustedAlias
from .receipt_cloud_contract import ReceiptExtraction, ReceiptHeader, quality_score
from .receipt_cloud_runtime import extract_cloud_receipt
from .receipt_catalog_suggestions import suggest_catalogue_foods

log = logging.getLogger("receipt_extraction")


class ReceiptCloudRequiredError(RuntimeError):
    """A test receipt must not masquerade as a DeepSeek result after fallback."""


async def _fetch_image_b64(receipt_uuid: uuid.UUID) -> str | None:
    async with AsyncSessionLocal() as db:
        receipt = await db.get(Receipt, receipt_uuid)
        if receipt is None:
            return None
        if receipt.image_bytes is None:
            return None
        return base64.b64encode(receipt.image_bytes).decode("ascii")


_RECEIPT_QTY_MAX = Decimal("999999999.999")
_RECEIPT_PRICE_MAX = Decimal("9999999999.99")


def _inference_request_timeout_s(configured: float, remaining: float) -> float:
    """Respect the CPU OCR setting without outliving the receipt deadline."""
    return min(max(1.0, configured), remaining)


def _num_or_none(value: Any, *, maximum: Decimal) -> Decimal | None:
    """Return a database-safe OCR decimal, or omit an implausible token.

    Receipt OCR can mistake a barcode, card number, or transaction reference
    for a quantity.  Do not let that one token abort the entire receipt when
    PostgreSQL enforces the receipt-line NUMERIC precision.
    """
    if value is None:
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    if not number.is_finite() or number < 0 or number > maximum:
        return None
    return number


# The inference service processes receipts under a serial lock and answers
# 429 while busy - transient, retry instead of failing the receipt.
# Generous ceiling kept as a backstop (post-PaddleOCR the lock is held seconds).
# Local development has no broker, so FastAPI BackgroundTasks starts one task
# per upload. Keep that fallback CPU-safe as well: receipts wait in FIFO-like
# task order and remain PENDING until they acquire this single processing slot.
_inline_receipt_queue = asyncio.Semaphore(1)

async def _post_with_busy_retry(
    client: httpx.AsyncClient, url: str, payload: dict, deadline: float | None = None
) -> httpx.Response:
    while True:
        resp = await client.post(url, json=payload)
        if resp.status_code != 429:
            return resp
        try:
            retry_after = float(resp.headers.get("Retry-After", ""))
        except ValueError:
            return resp
        if retry_after < 0 or deadline is None or retry_after >= deadline - time.monotonic():
            return resp
        await asyncio.sleep(retry_after)


async def _extract_local(
    client: httpx.AsyncClient, image_b64: str, deadline: float | None = None
) -> tuple[list[dict[str, Any]], ReceiptHeader | None]:
    settings = get_settings()
    resp = await _post_with_busy_retry(
        client, f"{settings.inference_url}/receipt/extract", {"image_base64": image_b64}, deadline
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("error"):
        raise RuntimeError("INFERENCE_OCR_FAILED")
    # Legacy per-line LLM calls have no cost reservation and can exceed the
    # two-call limit. The paid provider path is added only with a priced B3
    # adapter; until then the deterministic local OCR path remains available.
    identity = None
    if isinstance(data.get("identity"), dict):
        try:
            identity = ReceiptHeader.model_validate(data["identity"])
            if not all((identity.merchant, identity.date, identity.time,
                        identity.receipt_number, identity.total is not None)):
                identity = None
        except ValueError:
            # An invalid identity must not discard otherwise useful item rows.
            pass
    return [line for line in data.get("lines") or []
            if isinstance(line, dict) and not is_receipt_metadata(str(line.get("name") or ""))], identity


async def _extract_lines(
    client: httpx.AsyncClient, image_b64: str, deadline: float | None = None
) -> list[dict[str, Any]]:
    """Compatibility helper for callers that only need private OCR item rows."""
    lines, _ = await _extract_local(client, image_b64, deadline)
    return lines


async def _extract_draft(
    client: httpx.AsyncClient, receipt_uuid: uuid.UUID, image_b64: str, deadline: float,
) -> tuple[list[dict[str, Any]], ReceiptExtraction | None, ReceiptHeader | None]:
    """Take identity from private OCR; cloud can improve *item rows* only."""
    settings = get_settings()
    try:
        cloud_result = await extract_cloud_receipt(client, receipt_uuid, image_b64, deadline, settings)
        cloud = cloud_result.extraction if cloud_result is not None else None
        if cloud is not None and cloud.header.currency and cloud.header.currency.upper() not in {"MYR", "RM"}:
            raise ValueError("UNSUPPORTED_RECEIPT_CURRENCY")
        if cloud is not None and quality_score(cloud) > 0:
            repaired = repair_barcode_paired_purchases(
                [line.model_dump() for line in cloud.lines], cloud_result.private_purchase_lines)
            if repaired != [line.model_dump() for line in cloud.lines]:
                cloud = cloud.model_copy(update={"lines": [type(cloud.lines[0]).model_validate(row) for row in repaired]})
            grounded = []
            for line in cloud.lines:
                qty, unit = ground_purchase_quantity(
                    line.name_raw, line.quantity, line.unit, line.line_total,
                    cloud_result.private_purchase_lines,
                )
                grounded.append(line if (qty, unit) == (line.quantity, line.unit)
                                else line.model_copy(update={"quantity": qty, "unit": unit}))
            if any(before is not after for before, after in zip(cloud.lines, grounded)):
                cloud = cloud.model_copy(update={"lines": grounded})
            return [
                {"name": line.name_raw, "expanded_name": line.name_expanded,
                 "qty": str(line.quantity) if line.quantity is not None else None,
                 "unit": line.unit, "price_rm": str(line.line_total) if line.line_total is not None else None,
                 "confidence": str(line.confidence) if line.confidence is not None else None}
                for line in cloud.lines
            ], cloud, cloud_result.private_header
        if settings.receipt_cloud_required:
            raise ReceiptCloudRequiredError("RECEIPT_CLOUD_UNAVAILABLE")
    except Exception as exc:  # fail closed; the local OCR path is still useful
        log.warning("receipt cloud path unavailable receipt=%s type=%s", receipt_uuid, type(exc).__name__)
        if settings.receipt_cloud_required:
            raise ReceiptCloudRequiredError("RECEIPT_CLOUD_UNAVAILABLE") from exc
    # Local fallback is one original-pixel OCR pass. The successful cloud path
    # already ran that pass inside the private redactor and must not repeat it.
    local_lines, local_header = await _extract_local(client, image_b64, deadline)
    return local_lines, None, local_header


def _header_datetime(header: ReceiptHeader) -> datetime | None:
    if not header.date or not header.time:
        return None
    try:
        value = datetime.fromisoformat(f"{header.date}T{header.time}")
    except ValueError:
        return None
    # Malaysian receipts generally print local civil time without timezone.
    if value.tzinfo is None:
        from zoneinfo import ZoneInfo
        value = value.replace(tzinfo=ZoneInfo("Asia/Kuala_Lumpur"))
    return value


def _expand_label(raw_name: str, service_expanded: Any) -> str | None:
    """Display a deterministic expansion first; a model hint is only fallback."""
    expanded = expand_receipt_label(raw_name)
    if expanded:
        return expanded[:240]
    return _model_expansion(service_expanded)


def _model_expansion(value: Any) -> str | None:
    """Never coerce provider arrays/objects into a fabricated grocery label."""
    if not isinstance(value, str):
        return None
    label = value.strip()[:240]
    return label or None


async def run_extraction(receipt_id: str) -> None:
    """Queue one local receipt extraction behind the active CPU-bound OCR job."""
    settings = get_settings()
    receipt_uuid = uuid.UUID(receipt_id)
    if not settings.inference_url:
        await _mark_failed(receipt_uuid, "INFERENCE_URL is not configured.")
        return
    async with _inline_receipt_queue:
        await _run_extraction_once(receipt_id)


async def _run_extraction_once(receipt_id: str) -> None:
    """Process one receipt: OCR -> alias matching -> reviewable food candidates."""
    settings = get_settings()
    receipt_uuid = uuid.UUID(receipt_id)
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        claimed = await db.scalar(
            update(Receipt)
            .where(Receipt.receipt_id == receipt_uuid, Receipt.status == "PENDING")
            .values(
                status="PROCESSING", error=None, processing_started_at=now,
                processing_deadline_at=now + timedelta(seconds=settings.receipt_processing_deadline_s),
                attempt_count=Receipt.attempt_count + 1,
            )
            .returning(Receipt.receipt_id)
        )
        await db.commit()
        if claimed is None:
            return
    deadline = time.monotonic() + settings.receipt_processing_deadline_s
    try:
        image_b64 = await _fetch_image_b64(receipt_uuid)
        if image_b64 is None:
            await _mark_failed(receipt_uuid, "IMAGE_UNAVAILABLE")
            return
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("receipt deadline elapsed")
        # One slow CPU OCR call may legitimately take longer than 60 seconds.
        # The configured inference timeout and the whole-receipt deadline are
        # separate limits; the latter still encloses the entire draft stage.
        request_timeout = _inference_request_timeout_s(settings.inference_timeout_s, remaining)
        async with httpx.AsyncClient(timeout=request_timeout) as client:
            lines, cloud_extraction, local_header = await asyncio.wait_for(
                _extract_draft(client, receipt_uuid, image_b64, deadline), timeout=remaining
            )
        if not any(line.get("name") and line.get("price_rm") is not None for line in lines):
            raise ValueError("NO_VALID_RECEIPT_LINES")
        # Read the active catalogue before optional network I/O, then release
        # the read session. Never hold a DB transaction while awaiting a model.
        async with AsyncSessionLocal() as db:
            foods = (
                await db.scalars(select(CanonicalFood).where(CanonicalFood.status == "ACTIVE"))
            ).all()
            # Old global aliases learned from a single receipt confirmation
            # can point at the wrong food. Only curated catalogue aliases may
            # influence all users; verified receipts have their own
            # retailer-scoped, multi-purchase trust table below.
            stored_aliases = (
                await db.scalars(
                    select(FoodAlias).where(FoodAlias.source_system != "RECEIPT_CONFIRMATION")
                )
            ).all()
        canonical_names = [
            (food.canonical_food_id, name)
            for food in foods
            for name in (food.canonical_name, food.canonical_name_ms)
            if name
        ]
        active_food_ids = {food.canonical_food_id for food in foods}
        candidate_aliases = [
            (alias.canonical_food_id, alias.alias_name)
            for alias in stored_aliases
            if alias.canonical_food_id in active_food_ids
        ]
        catalog_suggestions: list[list[str]] | None = None
        if cloud_extraction is not None and cloud_extraction.provider == "deepseek":
            try:
                async with httpx.AsyncClient(trust_env=False, follow_redirects=False) as client:
                    catalog_suggestions = await suggest_catalogue_foods(
                        client, receipt_uuid, cloud_extraction, canonical_names, settings,
                        deadline - 8,
                    )
                if catalog_suggestions is not None and len(catalog_suggestions) != len(lines):
                    raise ValueError("Catalogue hint line count mismatch")
            except Exception as exc:  # optional hints never fail the receipt
                log.warning("receipt catalogue hints unavailable receipt=%s type=%s", receipt_uuid, type(exc).__name__)
        async with AsyncSessionLocal() as db:
            receipt = await db.get(Receipt, receipt_uuid, with_for_update=True)
            if receipt is None or receipt.status != "PROCESSING":
                return
            if time.monotonic() >= deadline:
                raise TimeoutError("receipt deadline elapsed")
            if local_header is not None:
                # Cloud input is item-band-v2: its header/footer is masked.
                # Never turn a provider's reconstruction into dedup identity.
                receipt.merchant = local_header.merchant
                receipt.transaction_at = _header_datetime(local_header)
                receipt.receipt_number = local_header.receipt_number
                receipt.total_rm = _num_or_none(local_header.total, maximum=_RECEIPT_PRICE_MAX)
            trusted_aliases: list[tuple[str, str]] = []
            if all((receipt.merchant, receipt.transaction_at, receipt.receipt_number, receipt.total_rm is not None)):
                scope = normalize_label(receipt.merchant)
                trusted_aliases = [
                    (alias.canonical_food_id, alias.normalized_alias)
                    for alias in (await db.scalars(
                        select(ReceiptTrustedAlias).where(ReceiptTrustedAlias.retailer_scope == scope)
                    )).all()
                    if alias.canonical_food_id in active_food_ids
                ]
            await db.execute(delete(ReceiptLine).where(ReceiptLine.receipt_id == receipt_uuid))
            for index, line in enumerate(lines):
                raw_name = str(line.get("name") or "")
                cleaned_name = normalize_receipt_item_label(raw_name)
                model_expanded = _model_expansion(line.get("expanded_name") or line.get("expanded"))
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
                verified_expansion = verified_product_expansion(raw_name)
                if verified_expansion:
                    candidate_only_labels.append(verified_expansion)
                match = propose_receipt_food(
                    labels, canonical_names, candidate_aliases, trusted_aliases,
                    candidate_only_labels=candidate_only_labels,
                )
                verified_review_ids = []
                if verified_expansion:
                    verified_review_ids = [food_id for food_id, name in canonical_names
                                           if normalize_label(name) == normalize_label(verified_expansion)]
                ranked_candidates = combine_review_candidates(
                    match.candidates,
                    catalog_suggestions[index] if catalog_suggestions is not None else [],
                    match.food_id,
                    verified_review_ids=verified_review_ids,
                    purchase_label=raw_name,
                    canonical_names=canonical_names,
                )
                confidence = _num_or_none(line.get("confidence"), maximum=Decimal("1"))
                low_confidence = confidence is not None and confidence < Decimal("0.80")
                db.add(
                    ReceiptLine(
                        receipt_id=receipt_uuid,
                        display_order=index + 1,
                        name_raw=raw_name[:240],
                        expanded_name=expanded_name[:240] if expanded_name else None,
                        qty=_num_or_none(line.get("qty"), maximum=_RECEIPT_QTY_MAX),
                        unit=(str(line.get("unit"))[:24] if line.get("unit") else None),
                        price_rm=_num_or_none(line.get("price_rm"), maximum=_RECEIPT_PRICE_MAX),
                        canonical_food_id=match.food_id,
                        match_score=match.score,
                        # The mobile logic never preselects a candidate row.
                        match_basis="CANDIDATE" if low_confidence else match.basis,
                        candidates=[
                            {"canonical_food_id": food_id_, "score": score_}
                            for food_id_, score_ in ranked_candidates
                        ],
                    )
                )
            if time.monotonic() >= deadline or receipt.status != "PROCESSING":
                raise TimeoutError("receipt deadline elapsed")
            receipt.status = "DONE"
            receipt.processed_at = datetime.now(timezone.utc)
            await db.commit()
    except Exception as exc:  # noqa: BLE001 - persisted for the user to see
        log.warning("receipt extraction failed receipt=%s type=%s", receipt_id, type(exc).__name__)
        # Never persist provider response, OCR text or the original image.
        await _mark_failed(receipt_uuid, type(exc).__name__[:80])


async def _mark_failed(receipt_uuid: uuid.UUID, message: str) -> None:
    async with AsyncSessionLocal() as db:
        receipt = await db.get(Receipt, receipt_uuid)
        if receipt is not None and receipt.status in {"PENDING", "PROCESSING"}:
            receipt.status = "FAILED"
            receipt.error = message
            receipt.processed_at = datetime.now(timezone.utc)
            await db.commit()
