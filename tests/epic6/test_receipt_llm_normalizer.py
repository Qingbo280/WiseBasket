import asyncio

from packages.receipt_llm_normalizer import (
    normalize_uncertain_receipt_label,
    normalize_unmatched_receipt_label,
)


def test_accepts_valid_high_confidence_deepseek_json():
    async def complete(_system: str, _user: str) -> str:
        return '{"item_name":"Farm Fresh UHT Milk","confidence":0.93}'

    result = asyncio.run(normalize_uncertain_receipt_label("FRMFRSH UHT MLK 1L 7.90", complete))

    assert result is not None
    assert result.item_name == "Farm Fresh UHT Milk"


def test_rejects_low_confidence_invalid_json_and_unsupported_units():
    async def low_confidence(_system: str, _user: str) -> str:
        return '{"item_name":"Milk","confidence":0.4}'

    async def invented_number(_system: str, _user: str) -> str:
        return '{"item_name":"Milk","quantity":1,"confidence":0.95}'

    async def invalid_json(_system: str, _user: str) -> str:
        return 'not json'

    assert asyncio.run(normalize_uncertain_receipt_label("MILK", low_confidence)) is None
    assert asyncio.run(normalize_uncertain_receipt_label("MILK", invented_number)) is None
    assert asyncio.run(normalize_uncertain_receipt_label("MILK", invalid_json)) is None


def test_only_calls_ai_for_an_unmatched_receipt_label():
    calls = 0
    received_user_prompt = ""

    async def complete(_system: str, user: str) -> str:
        nonlocal calls, received_user_prompt
        calls += 1
        received_user_prompt = user
        return '{"item_name":"Farm Fresh UHT Milk","confidence":0.93}'

    result = asyncio.run(
        normalize_unmatched_receipt_label(
            ["FFM 1L"],
            [("SF001", "farm fresh uht milk")],
            complete,
        )
    )
    assert result is not None
    assert result.item_name == "Farm Fresh UHT Milk"
    assert calls == 1
    assert "farm fresh uht milk" in received_user_prompt.casefold()

    already_matched = asyncio.run(
        normalize_unmatched_receipt_label(
            ["farm fresh uht milk"],
            [("SF001", "farm fresh uht milk")],
            complete,
        )
    )
    assert already_matched is None
    assert calls == 1
