"""No paid I/O: review-only catalogue suggestions and reservation boundaries."""

import asyncio
import json
import time
import uuid
from types import SimpleNamespace

import httpx
import pytest

from packages.receipt_catalog_suggestions import (
    build_catalogue_suggestion_prompt, combine_review_candidates,
    parse_catalogue_suggestions,
)
from services.api.app.services.receipt_cloud_contract import ExtractedLine, ReceiptExtraction
from services.api.app.services import receipt_catalog_suggestions as service


def test_prompt_contains_only_product_names_and_catalogue_not_header():
    line = ExtractedLine(
        name_raw="AUS CH OY BL GF (PR)", name_expanded="Choy Sum", line_total="18.00",
    )
    prompt = build_catalogue_suggestion_prompt([line], [("SF002", "beef")])
    assert "Australian Chilled Oyster Blade GF PR" in prompt
    assert '"name_raw":"AUS CH OY BL GF (PR)"' in prompt
    assert '"id":"SF002"' in prompt
    assert "18.00" not in prompt  # no price or receipt header leaves this boundary


@pytest.mark.parametrize("content", [
    '{"assignments":[{"index":0,"ranked_food_ids":["INVENTED"]}]}',
    '{"assignments":[{"index":0,"ranked_food_ids":["A","A"]}]}',
    '{"assignments":[{"index":1,"ranked_food_ids":["A"]}]}',
    '{"assignments":[],"other":"ignore me"}',
])
def test_parser_rejects_invented_duplicate_and_malformed_assignments(content):
    with pytest.raises(ValueError):
        parse_catalogue_suggestions(content, 1, {"A"})


def test_model_rank_is_candidate_only_and_exact_printed_evidence_wins():
    assert combine_review_candidates([], ["A", "B", "C"], None) == [
        ("A", 0.80), ("B", 0.77), ("C", 0.74),
    ]
    assert combine_review_candidates([("B", 0.95)], ["A", "B"], None) == [
        ("B", 0.95), ("A", 0.80),
    ]
    assert combine_review_candidates([("B", 1.0)], ["A"], "B") == [("B", 1.0)]


def test_paid_mapper_commits_hold_before_sending_and_never_accepts_unknown_id(monkeypatch):
    order = []

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def commit(self):
            order.append("commit")

    async def fake_reserve(*_args, **_kwargs):
        order.append("reserve")
        return 2

    monkeypatch.setattr(service, "AsyncSessionLocal", FakeSession)
    monkeypatch.setattr(service, "reserve_receipt_cloud_call", fake_reserve)
    settings = SimpleNamespace(
        receipt_cloud_enabled=True, receipt_cloud_keys_rotated=True,
        receipt_cloud_provider="deepseek", receipt_cloud_price_version="deepseek-v4.1-flash-2026-09-10",
        deepseek_model="deepseek-v4-flash", deepseek_base_url="https://api.deepseek.com/v1",
        deepseek_api_key="test-only-rotated-key", receipt_cloud_monthly_budget_usd=10,
    )
    extraction = ReceiptExtraction(
        provider="deepseek", requested_model="deepseek-v4-flash",
        lines=[ExtractedLine(name_raw="BANANA", line_total="2")],
    )

    def respond(request):
        order.append("network")
        assert "BANANA" in request.content.decode()
        return httpx.Response(200, json={
            "model": "deepseek-flash", "choices": [{"finish_reason": "stop", "message": {
                "content": json.dumps({"assignments": [{"index": 0, "ranked_food_ids": ["SF090"]}]})
            }}],
        })

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            return await service.suggest_catalogue_foods(
                client, uuid.uuid4(), extraction, [("SF090", "banana")], settings,
                time.monotonic() + 30,
            )

    assert asyncio.run(run()) == [["SF090"]]
    assert order == ["reserve", "commit", "network"]
