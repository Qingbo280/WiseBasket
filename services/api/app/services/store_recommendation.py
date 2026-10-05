from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date
from typing import Iterable


@dataclass(frozen=True)
class StoreLocationCandidate:
    location_id: int
    location_name: str
    latitude: float
    longitude: float
    address: str | None = None
    state: str | None = None
    district: str | None = None
    premise_type: str | None = None


@dataclass(frozen=True)
class BasketItem:
    canonical_food_id: str
    grams: float


@dataclass(frozen=True)
class LatestPrice:
    price_observation_id: int
    canonical_food_id: str
    location_id: int
    price_rm_per_100g_edible: float
    observed_date: date


@dataclass
class StoreItemEvaluation:
    canonical_food_id: str
    available: bool
    estimated_cost_rm: float | None = None
    price_observation_id: int | None = None


@dataclass
class StoreEvaluation:
    location_id: int
    location_name: str
    distance_km: float
    basket_cost_rm: float | None
    items_available: int
    items_missing: int
    price_coverage_ratio: float
    recommendation_rank: int
    recommendation_type: str
    is_selected: bool
    items: list[StoreItemEvaluation] = field(default_factory=list)
    freshest_observed_date: date | None = None


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371.0088
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    return radius_km * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def evaluate_store_candidates(
    user_latitude: float,
    user_longitude: float,
    stores: Iterable[StoreLocationCandidate],
    basket_items: Iterable[BasketItem],
    latest_prices: Iterable[LatestPrice],
) -> list[StoreEvaluation]:
    items = list(basket_items)
    prices_by_store_food = {
        (p.location_id, p.canonical_food_id): p
        for p in latest_prices
        if p.price_rm_per_100g_edible is not None
    }
    evaluations: list[StoreEvaluation] = []

    for store in stores:
        item_evaluations: list[StoreItemEvaluation] = []
        cost = 0.0
        freshest: date | None = None
        for item in items:
            price = prices_by_store_food.get((store.location_id, item.canonical_food_id))
            if price is None:
                item_evaluations.append(StoreItemEvaluation(canonical_food_id=item.canonical_food_id, available=False))
                continue
            item_cost = price.price_rm_per_100g_edible * item.grams / 100.0
            cost += item_cost
            freshest = price.observed_date if freshest is None else max(freshest, price.observed_date)
            item_evaluations.append(
                StoreItemEvaluation(
                    canonical_food_id=item.canonical_food_id,
                    available=True,
                    estimated_cost_rm=round(item_cost, 2),
                    price_observation_id=price.price_observation_id,
                )
            )

        available = sum(1 for i in item_evaluations if i.available)
        missing = len(items) - available
        coverage = available / len(items) if items else 0.0
        evaluations.append(
            StoreEvaluation(
                location_id=store.location_id,
                location_name=store.location_name,
                distance_km=round(haversine_km(user_latitude, user_longitude, store.latitude, store.longitude), 3),
                basket_cost_rm=round(cost, 2) if available else None,
                items_available=available,
                items_missing=missing,
                price_coverage_ratio=round(coverage, 5),
                recommendation_rank=0,
                recommendation_type="BEST_VALUE",
                is_selected=False,
                items=item_evaluations,
                freshest_observed_date=freshest,
            )
        )

    if not evaluations:
        return []

    nearest_id = min(evaluations, key=lambda e: e.distance_km).location_id
    cheapest_id = min(
        evaluations,
        key=lambda e: (e.basket_cost_rm is None, e.basket_cost_rm or float("inf"), -e.price_coverage_ratio, e.distance_km),
    ).location_id
    selected = max(
        evaluations,
        key=lambda e: (e.price_coverage_ratio, -(e.basket_cost_rm or float("inf")), -e.distance_km),
    )

    ranked = sorted(
        evaluations,
        key=lambda e: (-e.price_coverage_ratio, e.basket_cost_rm is None, e.basket_cost_rm or float("inf"), e.distance_km),
    )
    for rank, evaluation in enumerate(ranked, start=1):
        evaluation.recommendation_rank = rank
        evaluation.is_selected = evaluation.location_id == selected.location_id
        if evaluation.location_id == selected.location_id:
            evaluation.recommendation_type = "BEST_VALUE"
        elif evaluation.location_id == cheapest_id:
            evaluation.recommendation_type = "CHEAPEST"
        elif evaluation.location_id == nearest_id:
            evaluation.recommendation_type = "NEAREST"
    return ranked
