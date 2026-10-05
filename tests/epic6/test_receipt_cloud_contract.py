"""Offline cloud adapter and scoring tests; no provider credentials or calls."""

import asyncio
import base64
import hashlib
import time
import uuid
from decimal import Decimal
from types import SimpleNamespace

import httpx
import pytest

from services.api.app.services.receipt_cloud_contract import (
    ReceiptExtraction, ReceiptHeader, ExtractedLine, choose_extraction,
    masked_item_quality_score, quality_score,
)
from services.api.app.services.receipt_cloud_providers import (
    ProviderConfig, estimate_kimi_input_tokens, extract, parse_azure_result, parse_chat_response,
    repair_repeated_barcode_lines,
)
from services.api.app.services.receipt_cloud_runtime import price_ceiling_usd
from services.api.app.services import receipt_cloud_providers, receipt_cloud_runtime
from services.api.app.services import receipt_extraction


def _extraction(*, line_total="2.00", total="2.00"):
    return ReceiptExtraction(
        provider="mock", requested_model="mock", header=ReceiptHeader(merchant="Test", total=total),
        lines=[ExtractedLine(name_raw="RICE", quantity="1", unit_price="2", line_total=line_total)],
    )


def test_numeric_validation_and_quality_are_deterministic():
    data = _extraction()
    assert quality_score(data) == quality_score(data)
    assert quality_score(data) > quality_score(_extraction(total="9"))
    assert choose_extraction(data, data) is data
    assert ExtractedLine(name_raw="RICE", line_total="NaN", quantity="-1").line_total is None
    assert ExtractedLine(name_raw="RICE", line_total="NaN", quantity="-1").quantity is None
    assert quality_score(ReceiptExtraction(provider="mock", requested_model="mock")) == 0
    assert masked_item_quality_score(ReceiptExtraction(provider="mock", requested_model="mock")) == 0
    assert masked_item_quality_score(
        ReceiptExtraction(provider="mock", requested_model="mock",
                          lines=[ExtractedLine(name_raw="RICE", line_total="2")])
    ) >= Decimal("0.75")  # masked header/total must not force a paid retry


def test_model_expansion_is_optional_and_not_coerced_from_a_provider_object():
    valid = ExtractedLine.model_validate({
        "name_raw": "AYM B/LESS", "name_expanded": "Boneless chicken", "line_total": 12,
    })
    assert valid.name_raw == "AYM B/LESS"
    assert valid.name_expanded == "Boneless chicken"
    invalid = ExtractedLine.model_validate({
        "name_raw": "AYM B/LESS", "name_expanded": {"guess": "beef"}, "line_total": 12,
    })
    assert invalid.name_expanded is None


def test_cloud_draft_keeps_raw_and_expanded_names_separate(monkeypatch):
    extraction = ReceiptExtraction(
        provider="deepseek", requested_model="deepseek-v4-flash",
        header=ReceiptHeader(merchant="HALLUCINATED CLOUD MERCHANT", total="999.99"),
        lines=[ExtractedLine(name_raw="AYM B/LESS", name_expanded="Boneless chicken", line_total="12")],
    )
    private_header = ReceiptHeader(
        merchant="Private Store", date="2026-09-23", time="12:17:00",
        receipt_number="R-2048", total="12.00",
    )

    async def fake_local(*_args):
        raise AssertionError("successful cloud path must not OCR the original twice")

    async def fake_cloud(*_args):
        return receipt_cloud_runtime.CloudReceiptResult(extraction, private_header)

    monkeypatch.setattr(receipt_extraction, "_extract_local", fake_local)
    monkeypatch.setattr(receipt_extraction, "extract_cloud_receipt", fake_cloud)

    async def run():
        async with httpx.AsyncClient() as client:
            return await receipt_extraction._extract_draft(
                client, uuid.uuid4(), "private-image", time.monotonic() + 10,
            )

    lines, used, identity = asyncio.run(run())
    assert used is extraction
    assert identity is private_header  # masked cloud header is never a dedup key
    assert lines[0]["name"] == "AYM B/LESS"
    assert lines[0]["expanded_name"] == "Boneless chicken"


def test_required_cloud_failure_never_silently_uses_local_ocr(monkeypatch):
    local_calls = []

    async def unavailable_cloud(*_args):
        return None

    async def fake_local(*_args):
        local_calls.append(True)
        return [{"name": "LOCAL", "price_rm": "2.00"}], None

    monkeypatch.setattr(receipt_extraction, "extract_cloud_receipt", unavailable_cloud)
    monkeypatch.setattr(receipt_extraction, "_extract_local", fake_local)
    monkeypatch.setattr(
        receipt_extraction, "get_settings",
        lambda: SimpleNamespace(receipt_cloud_required=True),
    )

    async def run():
        async with httpx.AsyncClient() as client:
            return await receipt_extraction._extract_draft(
                client, uuid.uuid4(), "private-image", time.monotonic() + 10,
            )

    with pytest.raises(receipt_extraction.ReceiptCloudRequiredError):
        asyncio.run(run())
    assert not local_calls


def test_normal_cloud_failure_keeps_local_ocr_fallback(monkeypatch):
    async def unavailable_cloud(*_args):
        return None

    async def fake_local(*_args):
        return [{"name": "LOCAL", "price_rm": "2.00"}], None

    monkeypatch.setattr(receipt_extraction, "extract_cloud_receipt", unavailable_cloud)
    monkeypatch.setattr(receipt_extraction, "_extract_local", fake_local)
    monkeypatch.setattr(
        receipt_extraction, "get_settings",
        lambda: SimpleNamespace(receipt_cloud_required=False),
    )

    async def run():
        async with httpx.AsyncClient() as client:
            return await receipt_extraction._extract_draft(
                client, uuid.uuid4(), "private-image", time.monotonic() + 10,
            )

    lines, extraction, _ = asyncio.run(run())
    assert lines[0]["name"] == "LOCAL"
    assert extraction is None


def test_local_ocr_private_identity_is_optional_and_invalid_data_does_not_break_rows(monkeypatch):
    payload = {"lines": [{"name": "AYAM", "price_rm": "2.00"}], "identity": {
        "merchant": "Store", "date": "2026-09-23", "time": "12:17:00",
        "receipt_number": "R-2048", "total": "2.00",
    }}

    async def fake_post(*_args):
        return httpx.Response(200, json=payload, request=httpx.Request("POST", "http://private-inference/receipt/extract"))

    monkeypatch.setattr(receipt_extraction, "_post_with_busy_retry", fake_post)
    monkeypatch.setattr(receipt_extraction, "get_settings", lambda: SimpleNamespace(inference_url="http://private-inference"))

    async def run():
        async with httpx.AsyncClient() as client:
            return await receipt_extraction._extract_local(client, "private-original")

    lines, identity = asyncio.run(run())
    assert lines == payload["lines"]
    assert identity is not None and identity.receipt_number == "R-2048"
    payload["identity"]["total"] = "NaN"
    lines, identity = asyncio.run(run())
    assert lines == payload["lines"]
    assert identity is None


def test_inference_http_timeout_uses_configured_ocr_budget_not_old_60_second_cap():
    assert receipt_extraction._inference_request_timeout_s(180, 240) == 180
    assert receipt_extraction._inference_request_timeout_s(180, 45) == 45


@pytest.mark.parametrize("provider", ["deepseek", "kimi", "azure"])
def test_all_provider_contracts_filter_metadata_and_keep_net_product_charge(provider):
    extraction = ReceiptExtraction(provider=provider, requested_model="mock", lines=[
        ExtractedLine(name_raw=name, line_total="1.00") for name in [
            "GST", "TOTAL 25.05", "MEMBERSHIP FEE", "Paid by CASH 25.05",
            "TOTAL GRAIN CEREAL", "GST BRAND RICE", "PLASTIC BAG CHARGE", "DISCOUNT COOKIES",
        ]
    ])
    assert [line.name_raw for line in extraction.lines] == [
        "TOTAL GRAIN CEREAL", "GST BRAND RICE", "PLASTIC BAG CHARGE", "DISCOUNT COOKIES",
    ]
    assert all(line.line_total == 1 for line in extraction.lines)


@pytest.mark.parametrize("private_lines,expected", [
    ([], (None, None)),  # old inference response: unknown, not a failed receipt
    ([{"name": "RED CHILLI KG", "qty": 150, "unit": "g", "price_rm": 1.01}], ("0.15", "kg")),
])
def test_cloud_draft_grounds_per_kg_quantity_before_backend_storage(monkeypatch, private_lines, expected):
    extracted = ReceiptExtraction(provider="deepseek", requested_model="mock", lines=[
        ExtractedLine(name_raw="RED CHILLI KG", quantity=1, unit="KG", line_total="1.01"),
    ])
    async def cloud(*_args):
        return receipt_cloud_runtime.CloudReceiptResult(extracted, None, private_lines)
    async def no_second_ocr(*_args):
        raise AssertionError("private purchase evidence must reuse the redaction pass")
    monkeypatch.setattr(receipt_extraction, "extract_cloud_receipt", cloud)
    monkeypatch.setattr(receipt_extraction, "_extract_local", no_second_ocr)
    async def run():
        async with httpx.AsyncClient() as client:
            return await receipt_extraction._extract_draft(client, uuid.uuid4(), "private", time.monotonic() + 10)
    lines, used, _ = asyncio.run(run())
    assert (lines[0]["qty"], lines[0]["unit"]) == expected
    assert (used.lines[0].quantity, used.lines[0].unit) == (Decimal(expected[0]) if expected[0] else None, expected[1])


def test_local_fallback_also_filters_metadata_without_touching_purchase_amounts(monkeypatch):
    payload = {"lines": [
        {"name": "TOTAL", "price_rm": "25.05"}, {"name": "GST", "price_rm": "0.50"},
        {"name": "ABF CHICKEN DRUMSTIC", "qty": 0.556, "unit": "kg", "price_rm": 11.40},
    ]}
    async def fake_post(*_args):
        return httpx.Response(200, json=payload, request=httpx.Request("POST", "http://private/receipt/extract"))
    monkeypatch.setattr(receipt_extraction, "_post_with_busy_retry", fake_post)
    monkeypatch.setattr(receipt_extraction, "get_settings", lambda: SimpleNamespace(inference_url="http://private"))
    async def run():
        async with httpx.AsyncClient() as client:
            return await receipt_extraction._extract_local(client, "private")
    lines, _ = asyncio.run(run())
    assert lines == [payload["lines"][2]]


def test_azure_price_mapping_and_currency_are_not_swapped():
    config = ProviderConfig("azure", "prebuilt-receipt", "https://wisebasket-receipt-resource.cognitiveservices.azure.com/", "x" * 16)
    data = {"analyzeResult": {"modelId": "prebuilt-receipt", "documents": [{"fields": {
        "Total": {"valueCurrency": {"amount": 6, "currencyCode": "MYR"}},
        "Items": {"valueArray": [{"valueObject": {
            "Description": {"valueString": "RICE"}, "Quantity": {"valueNumber": 2},
            "Price": {"valueCurrency": {"amount": 3}},
            "TotalPrice": {"valueCurrency": {"amount": 6}},
        }}]},
    }}]}}
    result = parse_azure_result(data, config, 123)
    assert result.lines[0].unit_price == Decimal("3")
    assert result.lines[0].line_total == Decimal("6")
    assert result.header.total == Decimal("6")
    assert result.header.currency == "MYR"


def test_azure_f0_retries_only_throttled_post_and_get(monkeypatch):
    config = ProviderConfig("azure", "prebuilt-receipt", "https://wisebasket-receipt-resource.cognitiveservices.azure.com/", "x" * 16)
    operation = ("https://wisebasket-receipt-resource.cognitiveservices.azure.com/"
                 "documentintelligence/documentModels/prebuilt-receipt/analyzeResults/test-id?api-version=2024-11-30")
    calls = []

    async def no_delay(_seconds):
        return None

    monkeypatch.setattr(receipt_cloud_providers.asyncio, "sleep", no_delay)

    def respond(request):
        calls.append(request.method)
        if request.method == "POST":
            if calls.count("POST") == 1:
                return httpx.Response(429, headers={"Retry-After": "1"})
            return httpx.Response(202, headers={"Operation-Location": operation})
        if calls.count("GET") == 1:
            return httpx.Response(429, headers={"Retry-After": "1"})
        if calls.count("GET") == 2:
            return httpx.Response(200, json={"status": "running"})
        return httpx.Response(200, json={
            "status": "succeeded", "analyzeResult": {"modelId": "prebuilt-receipt", "documents": []},
        })

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            return await extract(client, b"REDACTED", time.monotonic() + 60, config)

    assert asyncio.run(run()).returned_model == "prebuilt-receipt"
    assert calls == ["POST", "POST", "GET", "GET", "GET"]


def test_chat_adapter_uses_only_redacted_image_and_parses_usage():
    config = ProviderConfig("deepseek", "deepseek-v4-flash", "https://api.deepseek.com/v1", "x" * 16)

    def respond(request):
        body = request.content.decode()
        assert "data:image/jpeg;base64," in body
        payload = request.json() if hasattr(request, "json") else None
        if payload is None:
            import json
            payload = json.loads(body)
        url = payload["messages"][0]["content"][1]["image_url"]["url"]
        assert base64.b64decode(url.split(",", 1)[1], validate=True) == b"REDACTED"
        assert '"thinking":{"type":"disabled"}' in body
        return httpx.Response(200, json={
            "model": "deepseek-flash", "usage": {"prompt_tokens": 40, "completion_tokens": 30},
            "choices": [{"message": {"content": '{"header":{"total":2},"lines":[{"name_raw":"RICE","line_total":2}]}'}}],
        })

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            return await extract(client, b"REDACTED", time.monotonic() + 30, config)

    result = asyncio.run(run())
    assert result.lines[0].line_total == 2
    assert result.returned_model == "deepseek-flash"
    assert result.prompt_tokens == 40


def test_chat_adapter_keeps_valid_rows_when_provider_emits_nameless_row():
    config = ProviderConfig("kimi", "kimi-k3", "https://api.moonshot.cn/v1", "x" * 16)
    result = parse_chat_response({
        "model": "kimi-k3", "choices": [{"message": {"content": (
            '{"lines":[{"name_raw":"RICE","line_total":2},'
            '{"name_raw":null,"line_total":3}]}'
        )}}],
    }, config, 100)
    assert len(result.lines) == 1
    assert result.lines[0].name_raw == "RICE"


def test_repeated_charged_barcode_rows_inherit_only_adjacent_same_price_product():
    rows = [
        ExtractedLine(name_raw="CADBURY CHOCOLATE 180G", name_expanded="Chocolate bar", line_total="15.90"),
        ExtractedLine(name_raw="9300617065876 UNIT", line_total="15.90"),
        ExtractedLine(name_raw="9300617065876 UNIT", line_total="15.90"),
        ExtractedLine(name_raw="9300617065876 UNIT", line_total="15.90"),
        ExtractedLine(name_raw="1234567890123 UNIT", line_total="9.90"),
        ExtractedLine(name_raw="9999999999999 UNIT"),
    ]
    repaired = repair_repeated_barcode_lines(rows)
    assert [line.name_raw for line in repaired[:4]] == ["CADBURY CHOCOLATE 180G"] * 4
    assert [line.name_expanded for line in repaired[:4]] == ["Chocolate bar"] * 4
    assert repaired[4].name_raw == "1234567890123 UNIT"  # no safe identity to borrow
    assert len(repaired) == 5  # uncharged barcode metadata is not a purchase


def test_unknown_price_model_and_kimi_are_fail_closed():
    settings = SimpleNamespace(receipt_cloud_price_version="deepseek-v4.1-flash-2026-09-10", azure_document_intelligence_sku="F0")
    assert price_ceiling_usd(ProviderConfig("deepseek", "unknown", "https://api.deepseek.com/v1", "x"), settings) is None
    assert price_ceiling_usd(ProviderConfig("kimi", "kimi-k3", "https://api.moonshot.cn/v1", "x"), settings) is None
    assert price_ceiling_usd(ProviderConfig("deepseek", "deepseek-v4-flash", "https://api.deepseek.com/v1", "x"), settings) == Decimal("0.0200")
    settings.receipt_cloud_price_version = "stale"
    assert price_ceiling_usd(ProviderConfig("deepseek", "deepseek-v4-flash", "https://api.deepseek.com/v1", "x"), settings) is None


def test_all_three_explicit_price_markers_enable_only_known_models():
    settings = SimpleNamespace(
        receipt_cloud_price_version=(
            "deepseek-v4.1-flash-2026-09-10,"
            "kimi-k3-cny-2026-09-24-fx-floor-5,"
            "azure-f0-2024-11-30"
        ),
        azure_document_intelligence_sku="F0",
    )
    kimi = ProviderConfig("kimi", "kimi-k3", "https://api.moonshot.cn/v1", "x")
    azure = ProviderConfig("azure", "prebuilt-receipt", "https://wisebasket-receipt-resource.cognitiveservices.azure.com/", "x")
    assert price_ceiling_usd(kimi, settings) == Decimal("0.1200")
    assert price_ceiling_usd(azure, settings) == Decimal("0.0200")
    assert receipt_cloud_runtime._known_returned_model(
        ReceiptExtraction(provider="kimi", requested_model="kimi-k3", returned_model="kimi-k3"), settings,
    )
    assert not receipt_cloud_runtime._known_returned_model(
        ReceiptExtraction(provider="kimi", requested_model="kimi-k3", returned_model="other"), settings,
    )
    settings.azure_document_intelligence_sku = "S0"
    assert price_ceiling_usd(azure, settings) is None


def test_kimi_adapter_uses_k3_completion_fields_and_redacted_image():
    config = ProviderConfig("kimi", "kimi-k3", "https://api.moonshot.cn/v1", "x" * 16)

    def respond(request):
        body = request.content.decode()
        assert '"max_completion_tokens":4096' in body
        assert '"reasoning_effort":"low"' in body
        assert '"max_tokens"' not in body
        assert '"temperature"' not in body
        import json
        payload = json.loads(body)
        url = payload["messages"][0]["content"][1]["image_url"]["url"]
        assert base64.b64decode(url.split(",", 1)[1], validate=True) == b"REDACTED"
        return httpx.Response(200, json={
            "model": "kimi-k3", "usage": {"prompt_tokens": 1024, "completion_tokens": 60},
            "choices": [{"message": {"content": '{"lines":[{"name_raw":"RICE","line_total":2}]}'}}],
        })

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            return await extract(client, b"REDACTED", time.monotonic() + 30, config)

    result = asyncio.run(run())
    assert result.returned_model == "kimi-k3"
    assert result.lines[0].line_total == 2


def test_kimi_estimator_only_sees_redacted_image_and_rejects_large_inputs():
    config = ProviderConfig("kimi", "kimi-k3", "https://api.moonshot.cn/v1", "x" * 16)
    count = 2200

    def respond(request):
        import json
        assert request.url.path == "/v1/tokenizers/estimate-token-count"
        payload = json.loads(request.content)
        url = payload["messages"][0]["content"][1]["image_url"]["url"]
        assert base64.b64decode(url.split(",", 1)[1], validate=True) == b"REDACTED"
        return httpx.Response(200, json={"data": {"total_tokens": count}})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            return await estimate_kimi_input_tokens(client, b"REDACTED", time.monotonic() + 30, config)

    assert asyncio.run(run()) == 2200
    count = 4001
    with pytest.raises(ValueError, match="input-token limit"):
        asyncio.run(run())


def test_cloud_retry_uses_fresh_mask_and_keeps_first_on_tie(monkeypatch):
    settings = SimpleNamespace(
        receipt_cloud_enabled=True, receipt_cloud_keys_rotated=True,
        receipt_cloud_provider="deepseek", receipt_cloud_price_version="deepseek-v4.1-flash-2026-09-10",
        deepseek_model="deepseek-v4-flash", deepseek_base_url="https://api.deepseek.com/v1",
        deepseek_api_key="new-test-only-key", inference_url="http://private-inference",
        azure_document_intelligence_sku="F0",
    )
    profiles = []
    transmitted = []
    first = ReceiptExtraction(
        provider="deepseek", requested_model="deepseek-v4-flash", returned_model="deepseek-flash",
        lines=[ExtractedLine(name_raw="RICE", line_total="2"),
               ExtractedLine(name_raw="UNREADABLE")],
    )
    second = ReceiptExtraction.model_validate(first.model_dump())

    async def fake_redact(client, image_b64, profile, inference_url, deadline):
        profiles.append(profile)
        assert image_b64 == "ORIGINAL_PRIVATE_INPUT"
        return profile.encode(), None, [{"name": "RICE", "qty": 1, "unit": "kg", "price_rm": 2}]

    async def fake_reserved(client, receipt_id, image, deadline, config, ceiling, settings):
        transmitted.append(image)
        return first if len(transmitted) == 1 else second

    monkeypatch.setattr(receipt_cloud_runtime, "_redact", fake_redact)
    monkeypatch.setattr(receipt_cloud_runtime, "_reserved_extract", fake_reserved)

    async def run():
        async with httpx.AsyncClient() as client:
            return await receipt_cloud_runtime.extract_cloud_receipt(
                client, uuid.uuid4(), "ORIGINAL_PRIVATE_INPUT", time.monotonic() + 100, settings,
            )

    result = asyncio.run(run())
    assert result.extraction is first
    assert result.private_purchase_lines == [{"name": "RICE", "qty": 1, "unit": "kg", "price_rm": 2}]
    assert profiles == ["normal", "enhanced"]
    assert transmitted == [b"normal", b"enhanced"]


def test_complete_masked_items_leave_second_call_available_for_catalogue(monkeypatch):
    settings = SimpleNamespace(
        receipt_cloud_enabled=True, receipt_cloud_keys_rotated=True,
        receipt_cloud_provider="deepseek", receipt_cloud_price_version="deepseek-v4.1-flash-2026-09-10",
        deepseek_model="deepseek-v4-flash", deepseek_base_url="https://api.deepseek.com/v1",
        deepseek_api_key="new-test-only-key", inference_url="http://private-inference",
        azure_document_intelligence_sku="F0",
    )
    first = ReceiptExtraction(
        provider="deepseek", requested_model="deepseek-v4-flash", returned_model="deepseek-flash",
        lines=[ExtractedLine(name_raw="RICE", line_total="2")],
    )
    profiles = []

    async def fake_redact(_client, _image_b64, profile, _inference_url, _deadline):
        profiles.append(profile)
        return b"redacted", None, []

    async def fake_reserved(*_args):
        return first

    monkeypatch.setattr(receipt_cloud_runtime, "_redact", fake_redact)
    monkeypatch.setattr(receipt_cloud_runtime, "_reserved_extract", fake_reserved)

    async def run():
        async with httpx.AsyncClient() as client:
            return await receipt_cloud_runtime.extract_cloud_receipt(
                client, uuid.uuid4(), "private-image", time.monotonic() + 100, settings,
            )

    assert asyncio.run(run()).extraction is first
    assert profiles == ["normal"]


def test_provider_gm_unit_is_normalized_without_inventing_or_multiplying_quantity():
    assert ExtractedLine(name_raw="HORLICKS32GM", quantity=32, unit="GM").unit == "g"
    line = ExtractedLine(name_raw="NISSIN CHICKEN RAMEN5PX425G", quantity=1, unit="pack")
    assert (line.quantity, line.unit) == (Decimal("1"), "pack")
    unknown = ExtractedLine(name_raw="OTHER NOODLES5PX425G")
    assert (unknown.quantity, unknown.unit) == (None, None)


def test_unknown_returned_model_is_rejected_even_with_known_alias():
    settings = SimpleNamespace(receipt_cloud_price_version="deepseek-v4.1-flash-2026-09-10")
    result = ReceiptExtraction(provider="deepseek", requested_model="deepseek-v4-flash", returned_model="surprise-model")
    assert not receipt_cloud_runtime._known_returned_model(result, settings)


def test_private_redaction_response_hash_must_match_before_provider_use():
    image = b"\xff\xd8redacted-only"

    def respond(request):
        assert request.url.path == "/receipt/redact"
        return httpx.Response(200, json={
            "image_base64": base64.b64encode(image).decode(), "mime_type": "image/jpeg",
            "policy_version": "item-band-v2",
            "sha256": hashlib.sha256(b"different").hexdigest(), "width": 100, "height": 200,
        })

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            return await receipt_cloud_runtime._redact(
                client, "private-original", "normal", "http://private-inference", time.monotonic() + 10,
            )

    with pytest.raises(ValueError, match="masked image"):
        asyncio.run(run())


@pytest.mark.parametrize("evidence", [None, [], [{"name": "CHICKEN", "qty": 0.556, "unit": "kg", "price_rm": 11.40}]])
def test_optional_private_purchase_evidence_accepts_rolling_inference_response(evidence):
    image = b"\xff\xd8redacted-only"
    payload = {"image_base64": base64.b64encode(image).decode(), "mime_type": "image/jpeg",
               "policy_version": "item-band-v2", "sha256": hashlib.sha256(image).hexdigest(),
               "width": 100, "height": 200}
    if evidence is not None:
        payload["purchase_lines"] = evidence

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload))) as client:
            return await receipt_cloud_runtime._redact(client, "private-original", "normal", "http://private-inference", time.monotonic() + 10)

    assert asyncio.run(run()) == (image, None, evidence or [])


def test_legacy_redactor_response_cannot_reach_cloud_provider():
    image = b"\xff\xd8synthetic-test-image"

    def respond(request):
        return httpx.Response(200, json={
            "image_base64": base64.b64encode(image).decode(), "mime_type": "image/jpeg",
            "sha256": hashlib.sha256(image).hexdigest(), "width": 100, "height": 200,
        })

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            return await receipt_cloud_runtime._redact(
                client, "private-original", "normal", "http://private-inference", time.monotonic() + 10,
            )

    with pytest.raises(ValueError, match="masked image"):
        asyncio.run(run())


def test_expired_redaction_deadline_never_sends_private_image():
    calls = []

    def respond(request):
        calls.append(request)
        raise AssertionError("expired request must not reach inference")

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            return await receipt_cloud_runtime._redact(
                client, "private-original", "normal", "http://private-inference", time.monotonic() - 1,
            )

    with pytest.raises(TimeoutError, match="deadline"):
        asyncio.run(run())
    assert calls == []
