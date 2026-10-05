import asyncio

from packages.receipt_food_classifier import classify_receipt_food_lines


def test_only_high_confidence_non_food_rows_are_skipped():
    async def complete(_system: str, _user: str) -> str:
        return '''{"lines":[
            {"index":0,"kind":"FOOD","confidence":0.99},
            {"index":1,"kind":"NON_FOOD","confidence":0.99},
            {"index":2,"kind":"UNCERTAIN","confidence":0.72}
        ]}'''

    result = asyncio.run(
        classify_receipt_food_lines(["Bawang Merah", "Auth Code=442922", "M/GOLD STR"], complete)
    )

    assert not result[0].should_skip
    assert result[1].should_skip
    assert not result[2].should_skip


def test_malformed_or_partial_ai_output_never_removes_a_line():
    async def partial(_system: str, _user: str) -> str:
        return '{"lines":[{"index":0,"kind":"NON_FOOD","confidence":1.0}]}'

    result = asyncio.run(classify_receipt_food_lines(["TOTAL", "MILK"], partial))

    assert result == {}
