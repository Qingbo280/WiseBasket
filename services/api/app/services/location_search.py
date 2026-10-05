from __future__ import annotations

from typing import Any

import httpx

from ..config import Settings
from ..schemas import LocationSearchSuggestion


def text_value(row: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = str(row.get(key) or "").strip()
        if value:
            return value
    return None


def suggestion_id(row: dict[str, Any], latitude: float, longitude: float) -> str:
    place_id = text_value(row, ("place_id",))
    if place_id:
        return f"geoapify:{place_id}"
    return f"geoapify:{latitude:.6f}:{longitude:.6f}"


def map_geoapify_suggestions(payload: Any) -> list[LocationSearchSuggestion]:
    if not isinstance(payload, dict):
        return []

    rows = payload.get("results")
    if not isinstance(rows, list):
        return []

    suggestions: list[LocationSearchSuggestion] = []
    seen_ids: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        try:
            latitude = float(row["lat"])
            longitude = float(row["lon"])
        except (KeyError, TypeError, ValueError):
            continue

        formatted = text_value(row, ("formatted",))
        label = text_value(row, ("address_line1", "name", "city", "suburb"))
        address = formatted or text_value(row, ("address_line2",)) or label
        if not label or not address:
            continue

        item_id = suggestion_id(row, latitude, longitude)
        if item_id in seen_ids:
            continue
        seen_ids.add(item_id)
        suggestions.append(
            LocationSearchSuggestion(
                id=item_id,
                label=label,
                address=address,
                latitude=latitude,
                longitude=longitude,
                state=text_value(row, ("state",)),
                district=text_value(row, ("county", "district")),
            )
        )

    return suggestions


async def search_geoapify_locations(
    query: str,
    settings: Settings,
    limit: int = 5,
) -> list[LocationSearchSuggestion]:
    search_text = query.strip()
    if len(search_text) < 3:
        return []
    if not settings.geoapify_api_key.strip():
        raise RuntimeError("GEOAPIFY_API_KEY is not configured")

    async with httpx.AsyncClient(timeout=settings.geoapify_timeout_s) as client:
        response = await client.get(
            settings.geoapify_base_url,
            params={
                "text": search_text,
                "format": "json",
                "filter": "countrycode:my",
                "limit": limit,
                "apiKey": settings.geoapify_api_key,
            },
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()
        return map_geoapify_suggestions(response.json())[:limit]
