# Epic 6 receipt API tests: upload -> extraction dispatch -> review -> confirm.
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from services.api.app import main
from services.api.app.config import Settings
from services.api.app.db import (
    AppUser,
    AsyncSessionLocal,
    GeneratedPlan,
    GeneratedPlanItem,
    FoodAlias,
    Household,
    PlanningRequest,
    Receipt,
    ReceiptLine,
    ReceiptLineEffect,
    ReceiptTrustedAlias,
    engine,
)
from services.api.app.main import app
from services.api.app.services.receipt_cloud_budget import CloudBudgetUnavailable, reserve_receipt_cloud_call
from services.api.app.services.receipt_cloud_contract import ExtractedLine, ReceiptExtraction
from services.api.app.services import receipt_extraction
from scripts import receipt_tasks


client = TestClient(app)
run_id = uuid.uuid4().hex[:8]
FAKE_JPEG = b"\xff\xd8\xff\xe0fake-jpeg-bytes\xff\xd9"


def run_database(coroutine):
    async def runner():
        try:
            return await coroutine
        finally:
            await engine.dispose()

    return asyncio.run(runner())


def create_authenticated_household(scenario_name: str) -> tuple[dict[str, str], int]:
    email = f"epic6-receipt-{run_id}-{scenario_name}@example.com"
    registration = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "CorrectHorse123!"},
    )
    assert registration.status_code == 200, registration.text
    headers = {"Authorization": f"Bearer {registration.json()['access_token']}"}
    household = client.post(
        "/api/v1/households",
        headers=headers,
        json={"name": "Epic 6 test household", "adults": 1, "children": 0},
    )
    assert household.status_code == 200, household.text
    return headers, household.json()["id"]


@pytest.fixture(scope="module", autouse=True)
def remove_receipt_test_data():
    yield

    async def cleanup():
        async with AsyncSessionLocal() as db:
            users = (
                await db.execute(select(AppUser).where(
                    AppUser.email_normalized.like(f"epic6-receipt-{run_id}-%@example.com")
                ))
            ).scalars().all()
            user_ids = [user.user_id for user in users]
            if user_ids:
                # planning_request / generated_plan have no ON DELETE CASCADE in
                # the migrated schema, so tear them down before the household.
                household_ids = select(Household.id).where(Household.owner_user_id.in_(user_ids))
                request_ids = select(PlanningRequest.planning_request_id).where(
                    PlanningRequest.household_id.in_(household_ids)
                )
                plan_ids = select(GeneratedPlan.plan_id).where(
                    GeneratedPlan.planning_request_id.in_(request_ids)
                )
                await db.execute(
                    delete(GeneratedPlanItem).where(GeneratedPlanItem.plan_id.in_(plan_ids))
                )
                await db.execute(
                    delete(GeneratedPlan).where(GeneratedPlan.planning_request_id.in_(request_ids))
                )
                await db.execute(
                    delete(PlanningRequest).where(PlanningRequest.household_id.in_(household_ids))
                )
                await db.execute(
                    delete(Household).where(Household.owner_user_id.in_(user_ids))
                )
                await db.execute(delete(AppUser).where(AppUser.user_id.in_(user_ids)))
            await db.commit()

    run_database(cleanup())


def fake_ocr_result(receipt_id: str):
    """Stand-in for the extraction pipeline: two lines, one matched food."""

    async def write_lines():
        async with AsyncSessionLocal() as db:
            receipt = await db.get(Receipt, receipt_id)
            assert receipt is not None
            db.add(
                ReceiptLine(
                    receipt_id=receipt.receipt_id,
                    display_order=1,
                    name_raw="BERAS 5KG",
                    expanded_name="Beras 5kg",
                    qty=5,
                    unit="kg",
                    price_rm=13.90,
                    canonical_food_id="SEED001",
                    match_score=0.91,
                    candidates=[
                        {"canonical_food_id": "SEED001", "score": 0.91},
                        {"canonical_food_id": "SEED002", "score": 0.42},
                    ],
                )
            )
            db.add(
                ReceiptLine(
                    receipt_id=receipt.receipt_id,
                    display_order=2,
                    name_raw="UNKNOWN THING",
                    expanded_name=None,
                    qty=None,
                    unit=None,
                    price_rm=None,
                    canonical_food_id=None,
                    match_score=None,
                    candidates=[{"canonical_food_id": "SEED002", "score": 0.3}],
                )
            )
            receipt.status = "DONE"
            receipt.processed_at = datetime.now(timezone.utc)
            await db.commit()

    run_database(write_lines())


def upload(headers, household_id, content, content_type="image/jpeg"):
    return client.post(
        f"/api/v1/households/{household_id}/receipts",
        headers=headers,
        files={"file": ("receipt.jpg", content, content_type)},
    )


def test_upload_receipt_rejects_non_image():
    headers, household_id = create_authenticated_household("badtype")
    response = upload(headers, household_id, b"plain text", content_type="text/plain")
    assert response.status_code == 422, response.text


def test_upload_receipt_rejects_oversized_image():
    headers, household_id = create_authenticated_household("oversize")
    response = upload(headers, household_id, b"x" * (8 * 1024 * 1024 + 1))
    assert response.status_code == 422, response.text


def test_upload_receipt_dispatches_extraction_in_background(monkeypatch):
    headers, household_id = create_authenticated_household("dispatch")
    calls: list[str] = []
    monkeypatch.setattr(main, "run_receipt_extraction", lambda rid: calls.append(rid))

    response = upload(headers, household_id, FAKE_JPEG)

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "PENDING"
    assert body["lines"] == []
    assert calls == [str(body["receipt_id"])]


def test_uploading_the_same_receipt_again_reuses_the_existing_receipt(monkeypatch):
    headers, household_id = create_authenticated_household("duplicate-upload")
    calls: list[str] = []
    monkeypatch.setattr(main, "run_receipt_extraction", lambda rid: calls.append(rid))

    first = upload(headers, household_id, FAKE_JPEG)
    second = upload(headers, household_id, FAKE_JPEG)

    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert second.json()["receipt_id"] == first.json()["receipt_id"]
    assert calls == [first.json()["receipt_id"]]


def test_uat_default_reuses_done_and_active_images_without_another_analysis(monkeypatch):
    headers, household_id = create_authenticated_household("uat-reprocess")
    calls: list[str] = []
    uat = Settings(_env_file=None, app_env="uat", database_url=main.settings.database_url,
                   jwt_secret="x" * 32, cors_origins="https://wisebasket.example")
    monkeypatch.setattr(main.settings, "receipt_reprocess_done_uploads", uat.receipt_reprocess_done_uploads)
    monkeypatch.setattr(main.settings, "receipt_allow_repeat_purchases", uat.receipt_allow_repeat_purchases)
    monkeypatch.setattr(main, "run_receipt_extraction", lambda rid: calls.append(rid))

    first = upload(headers, household_id, FAKE_JPEG)
    active_replay = upload(headers, household_id, FAKE_JPEG)
    assert first.status_code == active_replay.status_code == 201
    assert first.json()["receipt_id"] == active_replay.json()["receipt_id"]
    assert calls == [first.json()["receipt_id"]]

    async def set_first_status(status):
        async with AsyncSessionLocal() as db:
            receipt = await db.get(Receipt, uuid.UUID(first.json()["receipt_id"]))
            receipt.status = status
            await db.commit()

    run_database(set_first_status("PROCESSING"))
    processing_replay = upload(headers, household_id, FAKE_JPEG)
    assert processing_replay.json()["receipt_id"] == first.json()["receipt_id"]
    assert calls == [first.json()["receipt_id"]]
    run_database(set_first_status("DONE"))
    again = upload(headers, household_id, FAKE_JPEG)
    assert again.status_code == 201, again.text
    assert again.json()["receipt_id"] == first.json()["receipt_id"]
    assert calls == [first.json()["receipt_id"]]


@pytest.mark.parametrize("legacy_without_effect", [False, True])
def test_qa_cached_repeat_purchase_keeps_confirmation_idempotent(monkeypatch, legacy_without_effect):
    headers, household_id = create_authenticated_household(f"cached-repeat-{legacy_without_effect}")
    monkeypatch.setattr(main.settings, "receipt_allow_repeat_purchases", True)
    monkeypatch.setattr(main.settings, "receipt_reprocess_done_uploads", False)
    monkeypatch.setattr(main.settings, "receipt_uploads_per_day", 1)
    calls = []
    def extract(rid):
        calls.append(rid)
        fake_ocr_result(rid)
    monkeypatch.setattr(main, "run_receipt_extraction", extract)
    first_id = upload(headers, household_id, FAKE_JPEG).json()["receipt_id"]
    async def add_purchase_identity():
        async with AsyncSessionLocal() as db:
            receipt = await db.get(Receipt, uuid.UUID(first_id))
            receipt.merchant = "QA SHOP"
            receipt.transaction_at = datetime(2026, 9, 29, tzinfo=timezone.utc)
            receipt.receipt_number = "QA-REPEAT-1"
            receipt.total_rm = Decimal("13.90")
            await db.commit()
    run_database(add_purchase_identity())
    base = f"/api/v1/households/{household_id}/receipts/"
    first = client.get(base + first_id, headers=headers).json()
    first_line = first["lines"][0]
    first_payload = {"lines": [{"line_id": first_line["line_id"], "canonical_food_id": "SEED001"}],
                     "added_lines": [{"client_line_id": str(uuid.uuid4()), "name_raw": "MANUAL",
                                      "canonical_food_id": "SEED002", "qty": 1, "unit": "kg"}]}
    assert client.post(base + first_id + "/confirm", headers=headers, json=first_payload).status_code == 200
    async def expire_source():
        async with AsyncSessionLocal() as db:
            receipt = await db.get(Receipt, uuid.UUID(first_id))
            receipt.image_bytes = None  # Cache survives short-lived photo retention.
            if legacy_without_effect:
                await db.execute(delete(ReceiptLineEffect).where(ReceiptLineEffect.receipt_id == receipt.receipt_id))
            await db.commit()
    run_database(expire_source())

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: upload(headers, household_id, FAKE_JPEG), range(2)))
    assert all(r.status_code == 201 for r in responses)
    cached = responses[0].json()
    assert cached["receipt_id"] == responses[1].json()["receipt_id"] != first_id
    assert cached["status"] == "DONE" and len(cached["lines"]) == 2  # no manual-addition replay
    assert all(line["status"] == "PROPOSED" for line in cached["lines"])
    line = cached["lines"][0]
    assert line["line_id"] != first_line["line_id"]
    for field in ("name_raw", "expanded_name", "qty", "unit", "price_rm", "candidates", "match_score", "match_basis"):
        assert line[field] == first_line[field]
    assert cached["duplicate_of_receipt_id"] is None
    async def verify_cache_metadata():
        async with AsyncSessionLocal() as db:
            receipt = await db.get(Receipt, uuid.UUID(cached["receipt_id"]))
            assert receipt.image_bytes is None and receipt.attempt_count == 0
            assert receipt.merchant == "QA SHOP" and receipt.receipt_number == "QA-REPEAT-1"
            assert receipt.total_rm == Decimal("13.90")
    run_database(verify_cache_metadata())
    payload = {"lines": [{"line_id": line["line_id"], "canonical_food_id": "SEED001"}]}
    confirm_url = base + cached["receipt_id"] + "/confirm"
    with ThreadPoolExecutor(max_workers=2) as pool:
        confirmed = list(pool.map(lambda _: client.post(confirm_url, headers=headers, json=payload), range(2)))
    assert all(r.status_code == 200 for r in confirmed)
    pantry = client.get(f"/api/v1/households/{household_id}/pantry-items", headers=headers).json()
    assert sorted(row["quantity"] for row in pantry) == [1, 10]  # only one additional 5kg purchase
    spending = client.get(f"/api/v1/households/{household_id}/spending-summary", headers=headers).json()
    assert spending["confirmed_receipt_count"] == 2 and spending["actual_spend_rm"] == 27.8
    assert calls == [first_id]
    assert upload(headers, household_id, FAKE_JPEG + b"new").status_code == 429  # cache did not change quota rules


def test_qa_can_confirm_a_previous_logical_duplicate_without_reanalysis(monkeypatch):
    headers, household_id = create_authenticated_household("cached-old-duplicate")
    monkeypatch.setattr(main.settings, "receipt_allow_repeat_purchases", False)
    monkeypatch.setattr(main.settings, "receipt_reprocess_done_uploads", True)
    monkeypatch.setattr(main, "run_receipt_extraction", fake_ocr_result)
    first = upload(headers, household_id, FAKE_JPEG).json()
    second = upload(headers, household_id, FAKE_JPEG + b"other-image").json()
    async def mark_duplicate():
        async with AsyncSessionLocal() as db:
            receipt = await db.get(Receipt, uuid.UUID(second["receipt_id"]))
            receipt.duplicate_of_receipt_id = uuid.UUID(first["receipt_id"])
            await db.commit()
    run_database(mark_duplicate())
    base = f"/api/v1/households/{household_id}/receipts/{second['receipt_id']}"
    row = client.get(base, headers=headers).json()["lines"][0]
    payload = {"lines": [{"line_id": row["line_id"], "canonical_food_id": "SEED001"}]}
    assert client.post(base + "/confirm", headers=headers, json=payload).status_code == 409
    monkeypatch.setattr(main.settings, "receipt_allow_repeat_purchases", True)
    confirmed = client.post(base + "/confirm", headers=headers, json=payload)
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["duplicate_of_receipt_id"] is None


@pytest.mark.parametrize("fresh", [False, True])
def test_completed_image_override_preserves_daily_quota_contract(monkeypatch, fresh):
    headers, household_id = create_authenticated_household(f"completed-quota-{fresh}")
    monkeypatch.setattr(main.settings, "receipt_reprocess_done_uploads", fresh)
    monkeypatch.setattr(main.settings, "receipt_uploads_per_day", 1)
    monkeypatch.setattr(main, "run_receipt_extraction", fake_ocr_result)
    first = upload(headers, household_id, FAKE_JPEG)
    assert first.status_code == 201
    again = upload(headers, household_id, FAKE_JPEG)
    if fresh:
        assert again.status_code == 429  # a fresh completed-image scan uses another quota slot
    else:
        assert again.status_code == 201
        assert again.json()["receipt_id"] == first.json()["receipt_id"]  # reuse never consumes quota


@pytest.mark.parametrize("legacy_without_effect", [False, True])
def test_fresh_same_image_cannot_apply_confirmed_stock_twice_without_identity(monkeypatch, legacy_without_effect):
    headers, household_id = create_authenticated_household(f"fresh-image-stock-{legacy_without_effect}")
    monkeypatch.setattr(main.settings, "receipt_reprocess_done_uploads", True)
    monkeypatch.setattr(main, "run_receipt_extraction", fake_ocr_result)
    first = upload(headers, household_id, FAKE_JPEG).json()
    first_id = first["receipt_id"]
    first_line = client.get(f"/api/v1/households/{household_id}/receipts/{first_id}", headers=headers).json()["lines"][0]
    first_url = f"/api/v1/households/{household_id}/receipts/{first_id}/confirm"
    payload = {"lines": [{"line_id": first_line["line_id"], "canonical_food_id": "SEED001"}]}
    assert client.post(first_url, headers=headers, json=payload).status_code == 200
    assert client.post(first_url, headers=headers, json=payload).status_code == 200  # same receipt remains idempotent

    async def check_identity_and_legacy():
        async with AsyncSessionLocal() as db:
            stored = await db.get(Receipt, uuid.UUID(first_id))
            assert stored.merchant is None and stored.logical_fingerprint is None
            if legacy_without_effect:
                await db.execute(delete(ReceiptLineEffect).where(ReceiptLineEffect.receipt_id == uuid.UUID(first_id)))
                await db.commit()
    run_database(check_identity_and_legacy())

    second_id = upload(headers, household_id, FAKE_JPEG).json()["receipt_id"]
    assert second_id != first_id
    second_url = f"/api/v1/households/{household_id}/receipts/{second_id}"
    second_line = client.get(second_url, headers=headers).json()["lines"][0]
    blocked = client.post(second_url + "/confirm", headers=headers, json={
        "lines": [{"line_id": second_line["line_id"], "canonical_food_id": "SEED001", "price_rm": 1, "qty": 1, "unit": "kg"}],
        "added_lines": [{"canonical_food_id": "SEED002", "qty": 2, "unit": "pcs", "price_rm": 1}],
    })
    assert blocked.status_code == 409, blocked.text
    assert blocked.json()["detail"] == {"code": "DUPLICATE_RECEIPT", "canonical_receipt_id": first_id}
    after = client.get(second_url, headers=headers).json()["lines"]
    assert len(after) == 2 and after[0]["status"] != "CONFIRMED"
    assert (after[0]["qty"], after[0]["price_rm"]) == (5, 13.9)  # rejected changes are atomic
    pantry = client.get(f"/api/v1/households/{household_id}/pantry-items", headers=headers).json()
    assert len(pantry) == 1 and pantry[0]["quantity"] == 5
    spending = client.get(f"/api/v1/households/{household_id}/spending-summary", headers=headers).json()
    assert spending["actual_spend_rm"] == 13.9 and spending["confirmed_receipt_count"] == 1

    async def no_new_effects():
        async with AsyncSessionLocal() as db:
            assert not (await db.scalars(select(ReceiptLineEffect).where(ReceiptLineEffect.receipt_id == uuid.UUID(second_id)))).all()
    run_database(no_new_effects())


def test_concurrent_fresh_same_image_confirmations_apply_stock_once_without_identity(monkeypatch):
    headers, household_id = create_authenticated_household("concurrent-fresh-image")
    monkeypatch.setattr(main.settings, "receipt_reprocess_done_uploads", True)
    monkeypatch.setattr(main, "run_receipt_extraction", fake_ocr_result)
    receipt_ids = [upload(headers, household_id, FAKE_JPEG).json()["receipt_id"] for _ in range(2)]
    assert len(set(receipt_ids)) == 2
    requests = []
    for receipt_id in receipt_ids:
        url = f"/api/v1/households/{household_id}/receipts/{receipt_id}"
        receipt = client.get(url, headers=headers).json()
        assert receipt["status"] == "DONE"
        requests.append((url + "/confirm", {"lines": [{
            "line_id": receipt["lines"][0]["line_id"], "canonical_food_id": "SEED001",
        }]}))

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda request: client.post(request[0], headers=headers, json=request[1]), requests))
    assert sorted(response.status_code for response in responses) == [200, 409]
    winning_id = receipt_ids[next(index for index, response in enumerate(responses) if response.status_code == 200)]
    rejected = next(response for response in responses if response.status_code == 409)
    assert rejected.json()["detail"] == {"code": "DUPLICATE_RECEIPT", "canonical_receipt_id": winning_id}
    pantry = client.get(f"/api/v1/households/{household_id}/pantry-items", headers=headers).json()
    assert len(pantry) == 1 and pantry[0]["quantity"] == 5

    async def verify_one_effect_without_identity():
        async with AsyncSessionLocal() as db:
            ids = [uuid.UUID(receipt_id) for receipt_id in receipt_ids]
            receipts = (await db.scalars(select(Receipt).where(Receipt.receipt_id.in_(ids)))).all()
            assert all(receipt.merchant is None and receipt.logical_fingerprint is None for receipt in receipts)
            effects = (await db.scalars(select(ReceiptLineEffect).where(ReceiptLineEffect.receipt_id.in_(ids)))).all()
            assert len(effects) == 1 and str(effects[0].receipt_id) == winning_id
    run_database(verify_one_effect_without_identity())


def test_same_image_confirmation_is_scoped_to_its_household(monkeypatch):
    monkeypatch.setattr(main, "run_receipt_extraction", fake_ocr_result)
    for scenario in ("image-household-one", "image-household-two"):
        headers, household_id = create_authenticated_household(scenario)
        receipt_id = upload(headers, household_id, FAKE_JPEG).json()["receipt_id"]
        url = f"/api/v1/households/{household_id}/receipts/{receipt_id}"
        line_id = client.get(url, headers=headers).json()["lines"][0]["line_id"]
        confirmed = client.post(url + "/confirm", headers=headers, json={"lines": [{"line_id": line_id, "canonical_food_id": "SEED001"}]})
        assert confirmed.status_code == 200, confirmed.text
        pantry = client.get(f"/api/v1/households/{household_id}/pantry-items", headers=headers).json()
        assert pantry[0]["quantity"] == 5


def test_failed_confirmation_rolls_back_stock_and_does_not_block_fresh_analysis(monkeypatch):
    headers, household_id = create_authenticated_household("fresh-after-rollback")
    monkeypatch.setattr(main.settings, "receipt_reprocess_done_uploads", True)
    monkeypatch.setattr(main, "run_receipt_extraction", fake_ocr_result)
    first_id = upload(headers, household_id, FAKE_JPEG).json()["receipt_id"]
    first_url = f"/api/v1/households/{household_id}/receipts/{first_id}"
    first_line = client.get(first_url, headers=headers).json()["lines"][0]["line_id"]
    failed = client.post(first_url + "/confirm", headers=headers, json={
        "lines": [{"line_id": first_line, "canonical_food_id": "SEED001"}],
        "added_lines": [{"canonical_food_id": "SF-BOGUS", "qty": 1, "unit": "kg"}],
    })
    assert failed.status_code == 422, failed.text
    assert client.get(f"/api/v1/households/{household_id}/pantry-items", headers=headers).json() == []

    async def no_effect_after_failure():
        async with AsyncSessionLocal() as db:
            assert not (await db.scalars(select(ReceiptLineEffect).where(ReceiptLineEffect.receipt_id == uuid.UUID(first_id)))).all()
    run_database(no_effect_after_failure())
    second_id = upload(headers, household_id, FAKE_JPEG).json()["receipt_id"]
    second_url = f"/api/v1/households/{household_id}/receipts/{second_id}"
    second_line = client.get(second_url, headers=headers).json()["lines"][0]["line_id"]
    confirmed = client.post(second_url + "/confirm", headers=headers, json={"lines": [{"line_id": second_line, "canonical_food_id": "SEED001"}]})
    assert confirmed.status_code == 200, confirmed.text
    assert client.get(f"/api/v1/households/{household_id}/pantry-items", headers=headers).json()[0]["quantity"] == 5


def test_worker_crash_marks_pending_receipt_failed_without_waiting_for_deadline(monkeypatch):
    headers, household_id = create_authenticated_household("worker-preclaim-failure")
    monkeypatch.setattr(main, "run_receipt_extraction", lambda rid: None)
    created = upload(headers, household_id, FAKE_JPEG)
    assert created.status_code == 201
    receipt_id = created.json()["receipt_id"]

    asyncio.run(receipt_tasks._fail_crashed_receipt(receipt_id, "RuntimeError"))

    fetched = client.get(
        f"/api/v1/households/{household_id}/receipts/{receipt_id}", headers=headers,
    )
    assert fetched.status_code == 200
    assert fetched.json()["status"] == "FAILED"
    assert fetched.json()["error"] == "WORKER_RuntimeError"


def test_daily_upload_limit_counts_new_images_not_replays(monkeypatch):
    headers, household_id = create_authenticated_household("daily-limit")
    monkeypatch.setattr(main, "run_receipt_extraction", lambda rid: None)
    for index in range(10):
        response = upload(headers, household_id, FAKE_JPEG + bytes([index]))
        assert response.status_code == 201, response.text
    replay = upload(headers, household_id, FAKE_JPEG + bytes([0]))
    assert replay.status_code == 201
    eleventh = upload(headers, household_id, FAKE_JPEG + bytes([10]))
    assert eleventh.status_code == 429


def test_receipt_full_lifecycle_to_confirmed_pantry_items(monkeypatch):
    headers, household_id = create_authenticated_household("lifecycle")
    monkeypatch.setattr(main, "run_receipt_extraction", fake_ocr_result)

    created = upload(headers, household_id, FAKE_JPEG)
    assert created.status_code == 201, created.text
    receipt_id = created.json()["receipt_id"]

    fetched = client.get(
        f"/api/v1/households/{household_id}/receipts/{receipt_id}", headers=headers
    )
    assert fetched.status_code == 200, fetched.text
    body = fetched.json()
    assert body["status"] == "DONE"
    assert [line["name_raw"] for line in body["lines"]] == ["BERAS 5KG", "UNKNOWN THING"]
    assert body["lines"][0]["proposed_food"]["canonical_food_id"] == "SEED001"
    assert body["lines"][0]["match_score"] == 0.91
    assert body["lines"][0]["expanded_name"] == "Beras 5kg"
    assert body["lines"][0]["candidates"] == [
        {"canonical_food_id": "SEED001", "score": 0.91},
        {"canonical_food_id": "SEED002", "score": 0.42},
    ]
    assert body["lines"][1]["proposed_food"] is None
    assert body["lines"][1]["expanded_name"] is None
    # Unmatched lines still offer top-k near-miss picks for the user to choose.
    assert body["lines"][1]["candidates"] == [{"canonical_food_id": "SEED002", "score": 0.3}]

    # Owner of another household cannot read this receipt.
    other_headers, other_household = create_authenticated_household("other")
    denied = client.get(
        f"/api/v1/households/{other_household}/receipts/{receipt_id}", headers=other_headers
    )
    assert denied.status_code == 404, denied.text

    # Confirm: accept the matched line, skip the unknown one.
    line_id = body["lines"][0]["line_id"]
    unknown_line_id = body["lines"][1]["line_id"]
    confirmed = client.post(
        f"/api/v1/households/{household_id}/receipts/{receipt_id}/confirm",
        headers=headers,
        json={
            "lines": [
                {"line_id": line_id, "canonical_food_id": "SEED001"},
                {"line_id": unknown_line_id, "canonical_food_id": None},
            ]
        },
    )
    assert confirmed.status_code == 200, confirmed.text
    confirm_body = confirmed.json()
    assert [line["status"] for line in confirm_body["lines"]] == ["CONFIRMED", "SKIPPED"]

    # The accepted line became a RECEIPT-source pantry item carrying qty/unit.
    pantry = client.get(
        f"/api/v1/households/{household_id}/pantry-items", headers=headers
    )
    assert pantry.status_code == 200, pantry.text
    items = pantry.json()
    assert len(items) == 1
    assert items[0]["food"]["canonical_food_id"] == "SEED001"
    assert items[0]["source"] == "RECEIPT"
    assert items[0]["quantity"] == 5.0
    assert items[0]["unit"] == "kg"


    # One household's confirmation must not overwrite a global alias. Until
    # independent purchase votes verify a retailer-specific mapping, it is
    # candidate-only evidence.
    async def read_learned_alias():
        async with AsyncSessionLocal() as db:
            return await db.scalar(
                select(FoodAlias).where(
                    FoodAlias.alias_name == "BERAS 5KG",
                    FoodAlias.language == "und",
                    FoodAlias.source_system == "RECEIPT_CONFIRMATION",
                )
            )

    learned_alias = run_database(read_learned_alias())
    assert learned_alias is None

    # Idempotent: re-confirming does not duplicate pantry items.
    reconfirmed = client.post(
        f"/api/v1/households/{household_id}/receipts/{receipt_id}/confirm",
        headers=headers,
        json={"lines": [{"line_id": line_id, "canonical_food_id": "SEED001"}]},
    )
    assert reconfirmed.status_code == 200, reconfirmed.text
    pantry = client.get(f"/api/v1/households/{household_id}/pantry-items", headers=headers)
    assert len(pantry.json()) == 1

    # A changed pantry must be confirmed again before recipes are requested.
    async def read_confirmed_at():
        async with AsyncSessionLocal() as db:
            household = await db.get(Household, household_id)
            return household.pantry_confirmed_at if household else None

    assert run_database(read_confirmed_at()) is None


def test_confirm_reviewed_food_requires_amount_and_unit(monkeypatch):
    headers, household_id = create_authenticated_household("unknown-amount")
    monkeypatch.setattr(main, "run_receipt_extraction", fake_ocr_result)
    receipt_id = upload(headers, household_id, FAKE_JPEG + b"unknown-amount").json()["receipt_id"]
    receipt = client.get(
        f"/api/v1/households/{household_id}/receipts/{receipt_id}", headers=headers,
    ).json()
    unknown_id = receipt["lines"][1]["line_id"]
    response = client.post(
        f"/api/v1/households/{household_id}/receipts/{receipt_id}/confirm",
        headers=headers,
        json={"lines": [{"line_id": unknown_id, "canonical_food_id": "SEED002",
                         "qty": None, "unit": None}]},
    )
    assert response.status_code == 422, response.text
    assert "quantity and unit" in response.json()["detail"]
    completed = client.post(
        f"/api/v1/households/{household_id}/receipts/{receipt_id}/confirm",
        headers=headers,
        json={"lines": [{"line_id": unknown_id, "canonical_food_id": "SEED002",
                         "qty": 0.25, "unit": "kg"}]},
    )
    assert completed.status_code == 200, completed.text
    confirmed = next(line for line in completed.json()["lines"] if line["line_id"] == unknown_id)
    assert confirmed["status"] == "CONFIRMED"
    pantry = client.get(f"/api/v1/households/{household_id}/pantry-items", headers=headers).json()
    item = next(item for item in pantry if item["food"]["canonical_food_id"] == "SEED002")
    assert item["quantity"] == 0.25 and item["unit"] == "kg"


def test_new_manual_food_requires_amount_and_unit(monkeypatch):
    headers, household_id = create_authenticated_household("manual-amount-required")
    monkeypatch.setattr(main, "run_receipt_extraction", fake_ocr_result)
    receipt_id = upload(headers, household_id, FAKE_JPEG + b"manual-amount-required").json()["receipt_id"]
    url = f"/api/v1/households/{household_id}/receipts/{receipt_id}/confirm"
    client_id = str(uuid.uuid4())
    payload = {"added_lines": [{"client_line_id": client_id,
                                "canonical_food_id": "SEED002", "name_raw": "Manual food"}]}
    blocked = client.post(url, headers=headers, json=payload)
    assert blocked.status_code == 422, blocked.text
    assert "quantity and unit" in blocked.json()["detail"]
    completed = client.post(url, headers=headers, json={"added_lines": [{
        **payload["added_lines"][0], "qty": 1, "unit": "kg",
    }]})
    assert completed.status_code == 200, completed.text
    assert any(line["client_line_id"] == client_id and line["status"] == "CONFIRMED"
               for line in completed.json()["lines"])


def test_confirm_receipt_rejects_unknown_food(monkeypatch):
    headers, household_id = create_authenticated_household("badfood")
    monkeypatch.setattr(main, "run_receipt_extraction", fake_ocr_result)
    created = upload(headers, household_id, FAKE_JPEG)
    receipt_id = created.json()["receipt_id"]
    fetched = client.get(
        f"/api/v1/households/{household_id}/receipts/{receipt_id}", headers=headers
    )
    line_id = fetched.json()["lines"][0]["line_id"]

    response = client.post(
        f"/api/v1/households/{household_id}/receipts/{receipt_id}/confirm",
        headers=headers,
        json={"lines": [{"line_id": line_id, "canonical_food_id": "SF-BOGUS"}]},
    )
    assert response.status_code == 422, response.text


def test_unauthenticated_receipt_access_is_rejected():
    response = client.get("/api/v1/households/1/receipts/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 401


def test_confirm_applies_price_correction_and_added_lines(monkeypatch):
    """AC 6.2.3 (edit price) + AC 6.2.5 (add missing item) + AC 6.3.1 (actual total)."""
    headers, household_id = create_authenticated_household("priceadded")
    monkeypatch.setattr(main, "run_receipt_extraction", fake_ocr_result)
    created = upload(headers, household_id, FAKE_JPEG)
    receipt_id = created.json()["receipt_id"]
    fetched = client.get(
        f"/api/v1/households/{household_id}/receipts/{receipt_id}", headers=headers
    )
    body = fetched.json()
    line_id = body["lines"][0]["line_id"]  # BERAS 5KG RM13.90

    confirmed = client.post(
        f"/api/v1/households/{household_id}/receipts/{receipt_id}/confirm",
        headers=headers,
        json={
            "lines": [{"line_id": line_id, "canonical_food_id": "SEED001", "price_rm": 12.5}],
            "added_lines": [
                {"canonical_food_id": "SEED002", "name_raw": "eggs (added by user)", "qty": 10, "unit": "pcs", "price_rm": 5.9}
            ],
        },
    )
    assert confirmed.status_code == 200, confirmed.text
    confirm_body = confirmed.json()
    by_name = {line["name_raw"]: line for line in confirm_body["lines"]}
    assert by_name["BERAS 5KG"]["status"] == "CONFIRMED"
    assert by_name["BERAS 5KG"]["price_rm"] == 12.5  # price corrected (was 13.90)
    added = by_name["eggs (added by user)"]
    assert added["status"] == "CONFIRMED" and added["match_score"] is None
    assert added["price_rm"] == 5.9 and added["qty"] == 10.0 and added["unit"] == "pcs"

    # Both the accepted OCR line and the manually added item land in the pantry.
    pantry = client.get(f"/api/v1/households/{household_id}/pantry-items", headers=headers)
    foods = {(i["food"]["canonical_food_id"], i["source"]) for i in pantry.json()}
    assert ("SEED001", "RECEIPT") in foods
    assert ("SEED002", "RECEIPT") in foods

    # Idempotent: re-confirming the same payload adds no duplicates.
    reconfirmed = client.post(
        f"/api/v1/households/{household_id}/receipts/{receipt_id}/confirm",
        headers=headers,
        json={
            "lines": [{"line_id": line_id, "canonical_food_id": "SEED001", "price_rm": 12.5}],
            "added_lines": [
                {"canonical_food_id": "SEED002", "name_raw": "eggs (added by user)", "qty": 10, "unit": "pcs", "price_rm": 5.9}
            ],
        },
    )
    assert reconfirmed.status_code == 200, reconfirmed.text
    lines_after = reconfirmed.json()["lines"]
    assert [l["name_raw"] for l in lines_after].count("eggs (added by user)") == 1
    pantry = client.get(f"/api/v1/households/{household_id}/pantry-items", headers=headers)
    assert len(pantry.json()) == 2

    # A corrected price also applies to an already-CONFIRMED line.
    refixed = client.post(
        f"/api/v1/households/{household_id}/receipts/{receipt_id}/confirm",
        headers=headers,
        json={"lines": [{"line_id": line_id, "canonical_food_id": "SEED001", "price_rm": 11.0}]},
    )
    assert refixed.status_code == 200, refixed.text
    refixed_line = {l["name_raw"]: l for l in refixed.json()["lines"]}["BERAS 5KG"]
    assert refixed_line["price_rm"] == 11.0
    assert refixed_line["status"] == "CONFIRMED"

    # Spending summary: actual spend reflects BOTH corrected lines (11.0 + 5.9).
    summary = client.get(
        f"/api/v1/households/{household_id}/spending-summary", headers=headers
    )
    assert summary.status_code == 200, summary.text
    summary_body = summary.json()
    assert summary_body["actual_spend_rm"] == 16.9
    assert summary_body["confirmed_receipt_count"] == 1
    assert summary_body["weekly_budget_rm"] is None  # no plan created in this test
    assert summary_body["estimated_cost_rm"] is None
    assert summary_body["remaining_budget_rm"] is None
    assert summary_body["amount_above_budget_rm"] is None
    assert summary_body["estimated_vs_actual_difference_rm"] is None
    assert summary_body["budget_status"] == "NO_BUDGET"


def test_legacy_manual_line_price_edit_reuses_purchase_without_changing_stock(monkeypatch):
    """An ID-less older client must not create a second purchase on price edit."""
    headers, household_id = create_authenticated_household("legacy-manual-price")
    monkeypatch.setattr(main, "run_receipt_extraction", fake_ocr_result)
    receipt_id = upload(headers, household_id, FAKE_JPEG).json()["receipt_id"]
    url = f"/api/v1/households/{household_id}/receipts/{receipt_id}/confirm"
    line = {"canonical_food_id": "SEED002", "name_raw": "EGG", "qty": 10, "unit": "pcs"}

    first = client.post(url, headers=headers, json={"added_lines": [{**line, "price_rm": 5.9}]})
    assert first.status_code == 200, first.text

    # Simulate a row persisted by the former whole-request-hash fallback;
    # its UUIDv5 differs from the new stable legacy slot.
    async def assign_old_fallback_id():
        async with AsyncSessionLocal() as db:
            stored = await db.scalar(select(ReceiptLine).where(
                ReceiptLine.receipt_id == uuid.UUID(receipt_id), ReceiptLine.name_raw == "EGG"
            ))
            assert stored is not None
            stored.client_line_id = uuid.uuid5(uuid.NAMESPACE_URL, "former-whole-request-hash")
            await db.commit()

    run_database(assign_old_fallback_id())
    edited = client.post(url, headers=headers, json={"added_lines": [{**line, "price_rm": 4.9}]})
    assert edited.status_code == 200, edited.text
    manual_rows = [row for row in edited.json()["lines"] if row["name_raw"] == "EGG"]
    assert len(manual_rows) == 1
    assert manual_rows[0]["price_rm"] == 4.9
    pantry = client.get(f"/api/v1/households/{household_id}/pantry-items", headers=headers).json()
    egg = next(item for item in pantry if item["food"]["canonical_food_id"] == "SEED002")
    assert egg["quantity"] == 10
    spending = client.get(f"/api/v1/households/{household_id}/spending-summary", headers=headers)
    assert spending.json()["actual_spend_rm"] == 4.9

    changed_quantity = client.post(
        url, headers=headers, json={"added_lines": [{**line, "qty": 12, "price_rm": 4.9}]}
    )
    assert changed_quantity.status_code == 409
    changed_food = client.post(
        url, headers=headers,
        json={"added_lines": [{**line, "canonical_food_id": "SEED001", "price_rm": 4.9}]},
    )
    assert changed_food.status_code == 409


@pytest.mark.parametrize("former_hash_id", [False, True])
def test_legacy_reviewed_manual_line_does_not_swallow_new_same_food_purchase(
    monkeypatch, former_hash_id,
):
    headers, household_id = create_authenticated_household(f"legacy-new-item-{former_hash_id}")
    monkeypatch.setattr(main, "run_receipt_extraction", fake_ocr_result)
    receipt_id = upload(headers, household_id, FAKE_JPEG).json()["receipt_id"]
    url = f"/api/v1/households/{household_id}/receipts/{receipt_id}/confirm"
    first = client.post(url, headers=headers, json={"added_lines": [{
        "canonical_food_id": "SEED002", "name_raw": "EGG", "qty": 10,
        "unit": "pcs", "price_rm": 5.9,
    }]})
    assert first.status_code == 200, first.text
    original_id = next(row["line_id"] for row in first.json()["lines"] if row["name_raw"] == "EGG")

    if former_hash_id:
        async def assign_old_fallback_id():
            async with AsyncSessionLocal() as db:
                stored = await db.get(ReceiptLine, uuid.UUID(original_id))
                stored.client_line_id = uuid.uuid5(uuid.NAMESPACE_URL, "former-whole-request-hash")
                await db.commit()
        run_database(assign_old_fallback_id())

    second = client.post(url, headers=headers, json={
        "lines": [{"line_id": original_id, "canonical_food_id": "SEED002"}],
        "added_lines": [{
            "canonical_food_id": "SEED002", "name_raw": "EGG", "qty": 2,
            "unit": "pcs", "price_rm": 1.0,
        }],
    })
    assert second.status_code == 200, second.text
    manual_rows = [row for row in second.json()["lines"] if row["name_raw"] == "EGG"]
    assert len(manual_rows) == 2
    pantry = client.get(f"/api/v1/households/{household_id}/pantry-items", headers=headers).json()
    egg = next(item for item in pantry if item["food"]["canonical_food_id"] == "SEED002")
    assert egg["quantity"] == 12
    spending = client.get(f"/api/v1/households/{household_id}/spending-summary", headers=headers)
    assert spending.json()["actual_spend_rm"] == 6.9


def test_confirm_added_line_rejects_unknown_food(monkeypatch):
    headers, household_id = create_authenticated_household("badadded")
    monkeypatch.setattr(main, "run_receipt_extraction", fake_ocr_result)
    created = upload(headers, household_id, FAKE_JPEG)
    receipt_id = created.json()["receipt_id"]
    fetched = client.get(
        f"/api/v1/households/{household_id}/receipts/{receipt_id}", headers=headers
    )
    line_id = fetched.json()["lines"][0]["line_id"]
    response = client.post(
        f"/api/v1/households/{household_id}/receipts/{receipt_id}/confirm",
        headers=headers,
        json={
            "lines": [{"line_id": line_id, "canonical_food_id": "SEED001"}],
            "added_lines": [{"canonical_food_id": "SF-BOGUS"}],
        },
    )
    assert response.status_code == 422, response.text


def test_manual_lines_same_food_same_name_are_distinct_and_replay_is_safe(monkeypatch):
    headers, household_id = create_authenticated_household("manual-identity")
    monkeypatch.setattr(main, "run_receipt_extraction", fake_ocr_result)
    receipt_id = upload(headers, household_id, FAKE_JPEG).json()["receipt_id"]
    first_id, second_id = str(uuid.uuid4()), str(uuid.uuid4())
    payload = {"lines": [], "added_lines": [
        {"client_line_id": first_id, "canonical_food_id": "SEED002", "name_raw": "EGG", "qty": 2, "unit": "pcs"},
        {"client_line_id": second_id, "canonical_food_id": "SEED002", "name_raw": "EGG", "qty": 3, "unit": "pcs"},
    ]}
    url = f"/api/v1/households/{household_id}/receipts/{receipt_id}/confirm"
    first = client.post(url, headers=headers, json=payload)
    assert first.status_code == 200, first.text
    replay = client.post(url, headers=headers, json=payload)
    assert replay.status_code == 200, replay.text
    manual_rows = [line for line in replay.json()["lines"] if line["name_raw"] == "EGG"]
    assert len(manual_rows) == 2
    assert {line["client_line_id"] for line in manual_rows} == {first_id, second_id}
    pantry = client.get(f"/api/v1/households/{household_id}/pantry-items", headers=headers).json()
    egg = next(item for item in pantry if item["food"]["canonical_food_id"] == "SEED002")
    assert egg["quantity"] == 5

    async def count_effects():
        async with AsyncSessionLocal() as db:
            return len((await db.scalars(select(ReceiptLineEffect).where(
                ReceiptLineEffect.receipt_id == uuid.UUID(receipt_id)
            ))).all())
    assert run_database(count_effects()) == 2


def test_confirmed_food_cannot_be_changed_and_duplicate_request_ids_rejected(monkeypatch):
    headers, household_id = create_authenticated_household("locked-food")
    monkeypatch.setattr(main, "run_receipt_extraction", fake_ocr_result)
    receipt_id = upload(headers, household_id, FAKE_JPEG).json()["receipt_id"]
    line_id = client.get(
        f"/api/v1/households/{household_id}/receipts/{receipt_id}", headers=headers
    ).json()["lines"][0]["line_id"]
    url = f"/api/v1/households/{household_id}/receipts/{receipt_id}/confirm"
    duplicate_ids = client.post(url, headers=headers, json={"lines": [
        {"line_id": line_id, "canonical_food_id": "SEED001"},
        {"line_id": line_id, "canonical_food_id": "SEED001"},
    ]})
    assert duplicate_ids.status_code == 422
    assert client.post(url, headers=headers, json={"lines": [
        {"line_id": line_id, "canonical_food_id": "SEED001"},
    ]}).status_code == 200
    changed = client.post(url, headers=headers, json={"lines": [
        {"line_id": line_id, "canonical_food_id": "SEED002"},
    ]})
    assert changed.status_code == 409
    changed_quantity = client.post(url, headers=headers, json={"lines": [
        {"line_id": line_id, "canonical_food_id": "SEED001", "qty": 6, "unit": "kg"},
    ]})
    assert changed_quantity.status_code == 409
    same_quantity = client.post(url, headers=headers, json={"lines": [
        {"line_id": line_id, "canonical_food_id": "SEED001", "qty": 5, "unit": "kg"},
    ]})
    assert same_quantity.status_code == 200


def test_concurrent_confirmation_applies_one_effect(monkeypatch):
    headers, household_id = create_authenticated_household("concurrent-confirm")
    monkeypatch.setattr(main, "run_receipt_extraction", fake_ocr_result)
    receipt_id = upload(headers, household_id, FAKE_JPEG).json()["receipt_id"]
    line_id = client.get(
        f"/api/v1/households/{household_id}/receipts/{receipt_id}", headers=headers
    ).json()["lines"][0]["line_id"]
    url = f"/api/v1/households/{household_id}/receipts/{receipt_id}/confirm"
    body = {"lines": [{"line_id": line_id, "canonical_food_id": "SEED001"}]}
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: client.post(url, headers=headers, json=body), range(2)))
    assert [response.status_code for response in responses] == [200, 200]
    pantry = client.get(f"/api/v1/households/{household_id}/pantry-items", headers=headers).json()
    assert next(item for item in pantry if item["food"]["canonical_food_id"] == "SEED001")["quantity"] == 5

    async def count_effects():
        async with AsyncSessionLocal() as db:
            return len((await db.scalars(select(ReceiptLineEffect).where(
                ReceiptLineEffect.receipt_id == uuid.UUID(receipt_id)
            ))).all())
    assert run_database(count_effects()) == 1


def test_pending_receipt_cannot_be_confirmed(monkeypatch):
    headers, household_id = create_authenticated_household("pending-confirm")
    monkeypatch.setattr(main, "run_receipt_extraction", lambda rid: None)
    receipt_id = upload(headers, household_id, FAKE_JPEG).json()["receipt_id"]
    response = client.post(
        f"/api/v1/households/{household_id}/receipts/{receipt_id}/confirm",
        headers=headers,
        json={"added_lines": [{"client_line_id": str(uuid.uuid4()), "canonical_food_id": "SEED001"}]},
    )
    assert response.status_code == 409


def test_get_marks_stale_pending_receipt_failed(monkeypatch):
    headers, household_id = create_authenticated_household("stale-pending")
    monkeypatch.setattr(main, "run_receipt_extraction", lambda rid: None)
    receipt_id = upload(headers, household_id, FAKE_JPEG).json()["receipt_id"]

    async def age_receipt():
        async with AsyncSessionLocal() as db:
            receipt = await db.get(Receipt, uuid.UUID(receipt_id))
            receipt.created_at = datetime.now(timezone.utc) - timedelta(minutes=5)
            await db.commit()

    run_database(age_receipt())
    stale = client.get(f"/api/v1/households/{household_id}/receipts/{receipt_id}", headers=headers)
    assert stale.status_code == 200
    assert stale.json()["status"] == "FAILED"
    assert stale.json()["error"] == "PROCESSING_DEADLINE_EXCEEDED"


def test_cloud_reservation_has_hard_monthly_and_two_call_gates(monkeypatch):
    headers, household_id = create_authenticated_household("cloud-budget")
    monkeypatch.setattr(main, "run_receipt_extraction", lambda rid: None)
    receipt_id = uuid.UUID(upload(headers, household_id, FAKE_JPEG).json()["receipt_id"])

    async def check_reservations():
        async with AsyncSessionLocal() as db:
            receipt = await db.get(Receipt, receipt_id)
            receipt.status = "PROCESSING"
            await db.flush()
            assert await reserve_receipt_cloud_call(
                db, receipt_id, "mock", "known", Decimal("6.00")
            ) == 1
            with pytest.raises(CloudBudgetUnavailable):
                await reserve_receipt_cloud_call(db, receipt_id, "mock", "known", Decimal("5.00"))
            assert await reserve_receipt_cloud_call(
                db, receipt_id, "mock", "known", Decimal("4.00")
            ) == 2
            with pytest.raises(CloudBudgetUnavailable):
                await reserve_receipt_cloud_call(db, receipt_id, "mock", "known", Decimal("0.01"))
            with pytest.raises(CloudBudgetUnavailable):
                await reserve_receipt_cloud_call(db, receipt_id, "mock", "unknown", None)
            await db.rollback()

    run_database(check_reservations())


def test_catalogue_model_hint_is_ranked_for_review_but_never_preselected(monkeypatch):
    headers, household_id = create_authenticated_household("catalogue-hints")
    monkeypatch.setattr(main, "run_receipt_extraction", lambda _rid: None)
    receipt_id = upload(headers, household_id, FAKE_JPEG + b"catalogue-hints").json()["receipt_id"]
    extracted = ReceiptExtraction(
        provider="deepseek", requested_model="deepseek-v4-flash",
        lines=[ExtractedLine(name_raw="UNFAMILIAR BRAND ITEM", line_total="2")],
    )

    async def fake_draft(_client, _receipt_id, _image, _deadline):
        return [{"name": "UNFAMILIAR BRAND ITEM", "price_rm": "2"}], extracted, None

    async def fake_catalogue(_client, _receipt_id, _extraction, _names, _settings, _deadline):
        return [["SF090"]]

    monkeypatch.setattr(receipt_extraction, "_extract_draft", fake_draft)
    monkeypatch.setattr(receipt_extraction, "suggest_catalogue_foods", fake_catalogue)
    monkeypatch.setattr(receipt_extraction, "get_settings", lambda: SimpleNamespace(
        inference_url="http://private-inference", receipt_processing_deadline_s=240,
        inference_timeout_s=180,
    ))
    run_database(receipt_extraction.run_extraction(receipt_id))
    reviewed = client.get(
        f"/api/v1/households/{household_id}/receipts/{receipt_id}", headers=headers,
    ).json()
    assert reviewed["status"] == "DONE"
    line = reviewed["lines"][0]
    assert line["match_basis"] == "CANDIDATE"
    assert line["proposed_food"] is None
    assert line["candidates"][0]["canonical_food_id"] == "SF090"


def test_peel_fresh_purchase_reaches_review_as_juice_not_model_suggested_orange(monkeypatch):
    headers, household_id = create_authenticated_household("juice-form-guard")
    monkeypatch.setattr(main, "run_receipt_extraction", lambda _rid: None)
    receipt_id = upload(headers, household_id, FAKE_JPEG + b"juice-form-guard").json()["receipt_id"]
    extracted = ReceiptExtraction(provider="deepseek", requested_model="deepseek-v4-flash",
                                  lines=[ExtractedLine(name_raw="PEEL FRESH ORANGE 2L", line_total="13.20")])

    async def fake_draft(*_args):
        return [{"name": "PEEL FRESH ORANGE 2L", "qty": "2", "unit": "l", "price_rm": "13.20"}], extracted, None

    async def fake_catalogue(*_args):
        return [["SF093"]]

    monkeypatch.setattr(receipt_extraction, "_extract_draft", fake_draft)
    monkeypatch.setattr(receipt_extraction, "suggest_catalogue_foods", fake_catalogue)
    monkeypatch.setattr(receipt_extraction, "get_settings", lambda: SimpleNamespace(
        inference_url="http://private-inference", receipt_processing_deadline_s=240, inference_timeout_s=180))
    run_database(receipt_extraction.run_extraction(receipt_id))
    line = client.get(f"/api/v1/households/{household_id}/receipts/{receipt_id}", headers=headers).json()["lines"][0]
    assert line["proposed_food"] is None and line["match_basis"] == "CANDIDATE"
    assert [(row["canonical_food_id"], row["score"]) for row in line["candidates"]] == [("SF178", 1.0)]
    assert line["qty"] == 2 and line["unit"] == "l" and line["price_rm"] == 13.20


def test_old_single_confirmation_alias_cannot_poison_new_receipt_candidates(monkeypatch):
    headers, household_id = create_authenticated_household("poisoned-old-alias")
    monkeypatch.setattr(main, "run_receipt_extraction", lambda _rid: None)
    receipt_id = upload(headers, household_id, FAKE_JPEG + b"old-alias").json()["receipt_id"]
    legacy_label = f"CHICK FILLET POISON {uuid.uuid4().hex[:10].upper()}"

    async def insert_bad_legacy_alias():
        async with AsyncSessionLocal() as db:
            db.add(FoodAlias(
                canonical_food_id="SF006", alias_name=legacy_label,
                language="und", source_system="RECEIPT_CONFIRMATION",
            ))
            await db.commit()

    run_database(insert_bad_legacy_alias())
    extracted = ReceiptExtraction(
        provider="deepseek", requested_model="deepseek-v4-flash",
        lines=[ExtractedLine(name_raw=legacy_label, line_total="2")],
    )

    async def fake_draft(_client, _receipt_id, _image, _deadline):
        return [{"name": legacy_label, "price_rm": "2"}], extracted, None

    async def fake_catalogue(_client, _receipt_id, _extraction, _names, _settings, _deadline):
        return [["SF017"]]

    monkeypatch.setattr(receipt_extraction, "_extract_draft", fake_draft)
    monkeypatch.setattr(receipt_extraction, "suggest_catalogue_foods", fake_catalogue)
    monkeypatch.setattr(receipt_extraction, "get_settings", lambda: SimpleNamespace(
        inference_url="http://private-inference", receipt_processing_deadline_s=240,
        inference_timeout_s=180,
    ))
    run_database(receipt_extraction.run_extraction(receipt_id))
    line = client.get(
        f"/api/v1/households/{household_id}/receipts/{receipt_id}", headers=headers,
    ).json()["lines"][0]
    assert line["match_basis"] == "CANDIDATE"
    assert line["proposed_food"] is None
    assert line["candidates"][0]["canonical_food_id"] == "SF017"
    assert all(candidate["canonical_food_id"] != "SF006" for candidate in line["candidates"])

    async def remove_bad_legacy_alias():
        async with AsyncSessionLocal() as db:
            await db.execute(delete(FoodAlias).where(FoodAlias.alias_name == legacy_label))
            await db.commit()

    run_database(remove_bad_legacy_alias())


def test_same_logical_purchase_from_two_photos_cannot_apply_twice(monkeypatch):
    headers, household_id = create_authenticated_household("logical-duplicate")
    monkeypatch.setattr(main, "run_receipt_extraction", fake_ocr_result)
    first_id = upload(headers, household_id, FAKE_JPEG + b"a").json()["receipt_id"]
    second_id = upload(headers, household_id, FAKE_JPEG + b"b").json()["receipt_id"]

    async def write_reliable_header():
        async with AsyncSessionLocal() as db:
            for receipt_id in (first_id, second_id):
                receipt = await db.get(Receipt, uuid.UUID(receipt_id))
                receipt.merchant = "Store X"
                receipt.transaction_at = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
                receipt.receipt_number = "TX-ABC"
                receipt.total_rm = Decimal("13.90")
            await db.commit()

    run_database(write_reliable_header())
    url = lambda rid: f"/api/v1/households/{household_id}/receipts/{rid}/confirm"
    first_line = client.get(
        f"/api/v1/households/{household_id}/receipts/{first_id}", headers=headers
    ).json()["lines"][0]["line_id"]
    second_line = client.get(
        f"/api/v1/households/{household_id}/receipts/{second_id}", headers=headers
    ).json()["lines"][0]["line_id"]
    assert client.post(url(first_id), headers=headers, json={"lines": [
        {"line_id": first_line, "canonical_food_id": "SEED001"},
    ]}).status_code == 200
    duplicate = client.post(url(second_id), headers=headers, json={"lines": [
        {"line_id": second_line, "canonical_food_id": "SEED001"},
    ]})
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["canonical_receipt_id"] == first_id
    receipt = client.get(f"/api/v1/households/{household_id}/receipts/{second_id}", headers=headers)
    assert receipt.json()["duplicate_of_receipt_id"] == first_id
    pantry = client.get(f"/api/v1/households/{household_id}/pantry-items", headers=headers).json()
    assert next(item for item in pantry if item["food"]["canonical_food_id"] == "SEED001")["quantity"] == 5


def test_alias_activates_after_three_independent_logical_purchases(monkeypatch):
    headers, household_id = create_authenticated_household("alias-three-votes")
    monkeypatch.setattr(main, "run_receipt_extraction", fake_ocr_result)
    for index in range(3):
        receipt_id = upload(headers, household_id, FAKE_JPEG + bytes([index])).json()["receipt_id"]

        async def set_header():
            async with AsyncSessionLocal() as db:
                receipt = await db.get(Receipt, uuid.UUID(receipt_id))
                receipt.merchant = "Store X"
                receipt.transaction_at = datetime(2026, 9, 23, 12, index, tzinfo=timezone.utc)
                receipt.receipt_number = f"TX-{index}"
                receipt.total_rm = Decimal("13.90")
                await db.commit()

        run_database(set_header())
        line_id = client.get(
            f"/api/v1/households/{household_id}/receipts/{receipt_id}", headers=headers
        ).json()["lines"][0]["line_id"]
        confirmed = client.post(
            f"/api/v1/households/{household_id}/receipts/{receipt_id}/confirm",
            headers=headers,
            json={"lines": [{"line_id": line_id, "canonical_food_id": "SEED001"}]},
        )
        assert confirmed.status_code == 200, confirmed.text

    async def read_trusted():
        async with AsyncSessionLocal() as db:
            return await db.get(ReceiptTrustedAlias, ("store x", "beras 5kg"))

    trusted = run_database(read_trusted())
    assert trusted is not None
    assert trusted.canonical_food_id == "SEED001"


def test_spending_summary_includes_plan_budget_and_estimate():
    """AC 6.3.2 + 6.3.5: budget and estimated cost come from the latest plan."""
    headers, household_id = create_authenticated_household("planned")

    async def write_planning_request():
        async with AsyncSessionLocal() as db:
            db.add(
                PlanningRequest(
                    household_id=household_id,
                    available_budget_rm=Decimal("80.00"),
                    planning_days=7,
                )
            )
            await db.commit()

    run_database(write_planning_request())
    summary = client.get(
        f"/api/v1/households/{household_id}/spending-summary", headers=headers
    )
    assert summary.status_code == 200, summary.text
    body = summary.json()
    assert body["weekly_budget_rm"] == 80.0
    # No receipts yet: nothing recorded as spent.
    assert body["actual_spend_rm"] == 0.0
    assert body["confirmed_receipt_count"] == 0


def test_spending_summary_reports_remaining_budget_when_actual_spend_is_lower():
    # Given a household planned to spend RM80 and confirmed an RM76 purchase.
    headers, household_id = create_authenticated_household("within-budget-summary")

    async def write_within_budget_purchase():
        async with AsyncSessionLocal() as db:
            request = PlanningRequest(
                household_id=household_id,
                available_budget_rm=Decimal("80.00"),
                planning_days=7,
            )
            db.add(request)
            receipt = Receipt(
                household_id=household_id,
                image_bytes=FAKE_JPEG,
                image_sha256="a" * 64,
                image_expires_at=datetime.now(timezone.utc),
                status="DONE",
            )
            db.add(receipt)
            await db.flush()
            db.add(
                ReceiptLine(
                    receipt_id=receipt.receipt_id,
                    display_order=1,
                    name_raw="Confirmed grocery purchase",
                    price_rm=Decimal("76.00"),
                    status="CONFIRMED",
                )
            )
            await db.commit()

    run_database(write_within_budget_purchase())

    # When the household views its spending summary.
    summary = client.get(
        f"/api/v1/households/{household_id}/spending-summary", headers=headers
    )

    # Then the remaining amount and clear within-budget status are returned.
    assert summary.status_code == 200, summary.text
    body = summary.json()
    assert body["remaining_budget_rm"] == 4.0
    assert body["amount_above_budget_rm"] is None
    assert body["estimated_vs_actual_difference_rm"] is None
    assert body["budget_status"] == "WITHIN_BUDGET"


def test_spending_summary_reports_overspend_and_estimate_difference():
    # Given a household planned RM50, estimated RM42 and confirmed RM58 spending.
    headers, household_id = create_authenticated_household("over-budget-summary")

    async def write_over_budget_purchase():
        async with AsyncSessionLocal() as db:
            request = PlanningRequest(
                household_id=household_id,
                available_budget_rm=Decimal("50.00"),
                planning_days=7,
            )
            db.add(request)
            await db.flush()
            db.add(
                GeneratedPlan(
                    planning_request_id=request.planning_request_id,
                    optimizer_version="test",
                    status="FEASIBLE",
                    estimated_total_cost_rm=Decimal("42.00"),
                    remaining_budget_rm=Decimal("8.00"),
                )
            )
            receipt = Receipt(
                household_id=household_id,
                image_bytes=FAKE_JPEG,
                image_sha256="b" * 64,
                image_expires_at=datetime.now(timezone.utc),
                status="DONE",
            )
            db.add(receipt)
            await db.flush()
            db.add(
                ReceiptLine(
                    receipt_id=receipt.receipt_id,
                    display_order=1,
                    name_raw="Over-budget grocery purchase",
                    price_rm=Decimal("58.00"),
                    status="CONFIRMED",
                )
            )
            await db.commit()

    run_database(write_over_budget_purchase())

    # When the household views its spending summary.
    summary = client.get(
        f"/api/v1/households/{household_id}/spending-summary", headers=headers
    )

    # Then the summary reports actual spending against both budget and estimate.
    assert summary.status_code == 200, summary.text
    body = summary.json()
    assert body["remaining_budget_rm"] == 0.0
    assert body["amount_above_budget_rm"] == 8.0
    assert body["estimated_vs_actual_difference_rm"] == 16.0
    assert body["budget_status"] == "OVER_BUDGET"
