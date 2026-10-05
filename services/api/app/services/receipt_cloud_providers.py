"""Cloud receipt adapters. They accept only an already-redacted image.

No adapter calls the network until its caller has committed a cost reservation.
Provider JSON is parsed in memory and must never enter logs or database columns.
"""

from __future__ import annotations

import asyncio
import base64
import json
import re
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from urllib.parse import urlparse

import httpx
from pydantic import ValidationError

from .receipt_cloud_contract import ExtractedLine, ReceiptExtraction, ReceiptHeader


_PROMPT = (
    "Read this Malaysian grocery receipt. Return exactly one JSON object with header "
    "{merchant,date,time,receipt_number,currency,total} and lines array of "
    "{name_raw,name_expanded,quantity,unit,unit_price,line_total,confidence,source_order}. "
    "name_raw must preserve the printed item text, including abbreviations, without translation. "
    "For name_expanded, write the likely full grocery product name only when the printed "
    "abbreviation and receipt context support one specific interpretation; otherwise use null. "
    "Keep brand, variant and food form when printed. Do not invent ingredients, quantity, "
    "unit, price, or a missing product. Use null for unreadable or absent fields. "
    "Create one line per charged purchase, including charged non-food goods. Adjacent barcodes, "
    "SKU numbers, UNIT markers, discounts, rounding, subtotals and payment rows are NOT purchases: "
    "do not put them in lines. A repeated charge for the same product is a separate purchase line. "
    "When a discount directly follows one purchase, use its net charge as line_total only if "
    "the pairing is unambiguous; otherwise retain the printed product charge. "
    "Use ISO YYYY-MM-DD and HH:MM:SS only when the printed date/time is unambiguous. "
    "Preserve printed line order. No prose."
)

# The Kimi token-estimation endpoint counts the actual multimodal request.
# A fixed-price hold is only offered for compact inputs; unfamiliar larger
# images fall back to local OCR instead of making an under-reserved paid call.
KIMI_INPUT_ESTIMATE_MAX = 4000
_BARCODE_UNIT_ROW = re.compile(r"^\s*\d{8,14}\s+(?:unit|pcs?)\s*$", re.IGNORECASE)


@dataclass(frozen=True)
class ProviderConfig:
    provider: str
    model: str
    base_url: str
    api_key: str


def _validate_endpoint(config: ProviderConfig) -> str:
    parsed = urlparse(config.base_url)
    allowed = {
        "deepseek": "api.deepseek.com",
        "kimi": "api.moonshot.cn",
        "azure": "wisebasket-receipt-resource.cognitiveservices.azure.com",
    }
    if parsed.scheme != "https" or parsed.hostname != allowed.get(config.provider) or parsed.username or parsed.password or parsed.port:
        raise ValueError("Unapproved receipt provider endpoint")
    if not config.api_key or len(config.api_key) < 12:
        raise ValueError("Receipt provider key unavailable")
    return config.base_url.rstrip("/")


def _json_content(content: Any) -> dict[str, Any]:
    if not isinstance(content, str) or len(content) > 150_000:
        raise ValueError("Invalid provider content")
    stripped = content.strip()
    if stripped.startswith("```json"):
        stripped = stripped[7:]
    if stripped.startswith("```"):
        stripped = stripped[3:]
    if stripped.endswith("```"):
        stripped = stripped[:-3]
    value = json.loads(stripped.strip())
    if not isinstance(value, dict):
        raise ValueError("Provider content is not an object")
    return value


def parse_chat_response(data: dict[str, Any], config: ProviderConfig, latency_ms: int) -> ReceiptExtraction:
    choices = data.get("choices") or []
    if choices and choices[0].get("finish_reason") == "length":
        raise ValueError("Provider completion truncated")
    content = choices[0].get("message", {}).get("content") if choices else None
    value = _json_content(content)
    raw_lines = value.get("lines") or []
    if not isinstance(raw_lines, list):
        raise ValueError("Provider lines are not an array")
    lines = []
    for line in raw_lines:
        if not isinstance(line, dict) or not isinstance(line.get("name_raw"), str):
            continue  # malformed/nameless provider rows count as misses, not usable purchases
        try:
            lines.append(ExtractedLine.model_validate(line))
        except ValidationError:
            continue  # keep valid siblings and let recall penalize malformed rows
    lines = repair_repeated_barcode_lines(lines)
    usage = data.get("usage") or {}
    return ReceiptExtraction(
        header=ReceiptHeader.model_validate(value.get("header") or {}), lines=lines,
        provider=config.provider, requested_model=config.model,
        returned_model=str(data.get("model") or "")[:120] or None,
        prompt_tokens=usage.get("prompt_tokens"), completion_tokens=usage.get("completion_tokens"),
        latency_ms=latency_ms,
    )


def repair_repeated_barcode_lines(lines: list[ExtractedLine]) -> list[ExtractedLine]:
    """Carry a printed repeated charge's name across its barcode-only rows.

    A barcode line without a charge is metadata and never a purchase. A charged
    barcode line inherits only the immediately previous named purchase, and
    only when both printed charges agree; otherwise it stays reviewable with
    no guessed identity.
    """
    repaired: list[ExtractedLine] = []
    previous_named: ExtractedLine | None = None
    for line in lines:
        if not _BARCODE_UNIT_ROW.fullmatch(line.name_raw):
            repaired.append(line)
            previous_named = line
            continue
        if line.line_total is None:
            continue
        if (previous_named is not None and previous_named.line_total is not None
                and abs(previous_named.line_total - line.line_total) <= Decimal("0.01")):
            repaired.append(line.model_copy(update={
                "name_raw": previous_named.name_raw,
                "name_expanded": previous_named.name_expanded,
            }))
        else:
            repaired.append(line)
            previous_named = None
    return repaired


def _receipt_messages(image: bytes) -> list[dict[str, Any]]:
    return [{"role": "user", "content": [
        {"type": "text", "text": _PROMPT},
        {"type": "image_url", "image_url": {
            "url": "data:image/jpeg;base64," + base64.b64encode(image).decode("ascii"),
        }},
    ]}]


async def estimate_kimi_input_tokens(
    client: httpx.AsyncClient, image: bytes, deadline: float, config: ProviderConfig,
) -> int:
    """Use Moonshot's preflight estimator on the already-redacted image only."""
    base = _validate_endpoint(config)
    if config.provider != "kimi" or config.model != "kimi-k3" or not image or len(image) > 4_000_000:
        raise ValueError("Unsupported Kimi token-estimation input")
    response = await client.post(
        f"{base}/tokenizers/estimate-token-count",
        headers={"Authorization": f"Bearer {config.api_key}"},
        json={"model": config.model, "messages": _receipt_messages(image)},
        timeout=max(1.0, deadline - time.monotonic()),
    )
    response.raise_for_status()
    count = (response.json().get("data") or {}).get("total_tokens")
    if not isinstance(count, int) or isinstance(count, bool) or not 0 < count <= KIMI_INPUT_ESTIMATE_MAX:
        raise ValueError("Kimi receipt exceeds the guarded input-token limit")
    return count


async def _extract_chat(
    client: httpx.AsyncClient, image: bytes, deadline: float, config: ProviderConfig,
) -> ReceiptExtraction:
    base = _validate_endpoint(config)
    if config.provider not in {"kimi", "deepseek"}:
        raise ValueError("Unknown chat provider")
    if not image or len(image) > 4_000_000:
        raise ValueError("Redacted image exceeds safe cloud limit")
    start = time.monotonic()
    remaining = deadline - start
    if remaining < 10:
        raise TimeoutError("Receipt deadline too close")
    payload = {
        "model": config.model, "max_tokens": 4096,
        "messages": _receipt_messages(image),
    }
    if config.provider == "deepseek":
        payload["temperature"] = 0
        # The current DeepSeek model defaults to thinking mode; that can spend
        # the bounded output budget before producing any JSON answer.
        payload["thinking"] = {"type": "disabled"}
        payload["response_format"] = {"type": "json_object"}
    elif config.provider == "kimi":
        # K3 fixes temperature at 1.0; an explicit zero is rejected. K3 always
        # thinks, so low effort leaves more bounded completion for review JSON.
        # max_tokens is deprecated by Kimi.
        payload.pop("max_tokens")
        payload["max_completion_tokens"] = 4096
        payload["reasoning_effort"] = "low"
    response = await client.post(
        f"{base}/chat/completions",
        headers={"Authorization": f"Bearer {config.api_key}"},
        json=payload,
        timeout=remaining,
    )
    response.raise_for_status()
    return parse_chat_response(response.json(), config, int((time.monotonic() - start) * 1000))


def _azure_value(field: Any) -> Any:
    if not isinstance(field, dict):
        return None
    for key in ("valueCurrency", "valueNumber", "valueDate", "valueTime", "valueString"):
        if key in field:
            value = field[key]
            return value.get("amount") if key == "valueCurrency" and isinstance(value, dict) else value
    return field.get("content")


def parse_azure_result(data: dict[str, Any], config: ProviderConfig, latency_ms: int) -> ReceiptExtraction:
    result = data.get("analyzeResult") or {}
    documents = result.get("documents") or []
    fields = (documents[0].get("fields") or {}) if documents else {}
    items = fields.get("Items") or {}
    lines = []
    for order, item in enumerate(items.get("valueArray") or []):
        obj = item.get("valueObject") or {}
        name = _azure_value(obj.get("Description")) or _azure_value(obj.get("Name"))
        if not name:
            continue
        lines.append(ExtractedLine(
            name_raw=str(name), quantity=_azure_value(obj.get("Quantity")),
            unit=_azure_value(obj.get("Unit")),
            unit_price=_azure_value(obj.get("Price")),
            line_total=_azure_value(obj.get("TotalPrice")),
            confidence=item.get("confidence"), source_order=order,
        ))
    total_currency = (fields.get("Total") or {}).get("valueCurrency") or {}
    return ReceiptExtraction(
        header=ReceiptHeader(
            merchant=_azure_value(fields.get("MerchantName")),
            date=_azure_value(fields.get("TransactionDate")),
            time=_azure_value(fields.get("TransactionTime")),
            receipt_number=_azure_value(fields.get("TransactionId")) or _azure_value(fields.get("ReceiptNumber")),
            currency=total_currency.get("currencyCode") if isinstance(total_currency, dict) else None,
            total=_azure_value(fields.get("Total")),
        ),
        lines=lines, provider="azure", requested_model=config.model,
        returned_model=str(result.get("modelId") or "")[:120] or None,
        latency_ms=latency_ms,
    )


async def _extract_azure(
    client: httpx.AsyncClient, image: bytes, deadline: float, config: ProviderConfig,
) -> ReceiptExtraction:
    base = _validate_endpoint(config)
    if config.model != "prebuilt-receipt":
        raise ValueError("Unsupported Azure receipt model")
    if not image or len(image) > 4_000_000:
        raise ValueError("Redacted image exceeds Azure F0 4 MB limit")
    start = time.monotonic()
    path = "/documentintelligence/documentModels/prebuilt-receipt:analyze?api-version=2024-11-30"
    headers = {"Ocp-Apim-Subscription-Key": config.api_key}
    async def request_with_backoff(method: str, url: str, payload: dict | None = None) -> httpx.Response:
        # Azure F0 permits only 1 POST and 1 GET per second, and can still
        # return 429 under shared-resource load. Retry only explicit 429s;
        # never retry a possibly accepted POST after a transport timeout.
        for attempt in range(4):
            if deadline - time.monotonic() < 3:
                raise TimeoutError("Azure receipt analysis deadline elapsed")
            response = await client.request(
                method, url, headers=headers, json=payload,
                timeout=max(1.0, deadline - time.monotonic()),
            )
            if response.status_code != 429:
                response.raise_for_status()
                return response
            if attempt == 3:
                response.raise_for_status()
            delay = (2, 5, 13)[attempt]
            try:
                delay = max(delay, float(response.headers.get("Retry-After", "")))
            except ValueError:
                pass
            if delay + 3 >= deadline - time.monotonic():
                raise TimeoutError("Azure receipt throttling exceeded deadline")
            await asyncio.sleep(delay)
        raise TimeoutError("Azure receipt throttling exceeded retry limit")

    response = await request_with_backoff(
        "POST", base + path, {"base64Source": base64.b64encode(image).decode("ascii")},
    )
    operation = response.headers.get("Operation-Location", "")
    # Never follow an untrusted absolute URL from the response (SSRF).
    if not operation.startswith(base + "/documentintelligence/documentModels/prebuilt-receipt/analyzeResults/"):
        raise ValueError("Unexpected Azure operation URL")
    poll_delay = 2.0
    while deadline - time.monotonic() > poll_delay + 2:
        await asyncio.sleep(poll_delay)
        result = await request_with_backoff("GET", operation)
        data = result.json()
        if data.get("status") == "succeeded":
            return parse_azure_result(data, config, int((time.monotonic() - start) * 1000))
        if data.get("status") in {"failed", "canceled"}:
            raise ValueError("Azure analysis failed")
        try:
            poll_delay = max(2.0, float(result.headers.get("Retry-After", "")))
        except ValueError:
            poll_delay = 2.0
    raise TimeoutError("Azure receipt analysis deadline elapsed")


async def extract(
    client: httpx.AsyncClient, redacted_image: bytes, deadline: float, config: ProviderConfig,
) -> ReceiptExtraction:
    if config.provider == "azure":
        return await _extract_azure(client, redacted_image, deadline, config)
    return await _extract_chat(client, redacted_image, deadline, config)
