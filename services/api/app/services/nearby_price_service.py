from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import math
from typing import Literal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from services.api.app.services.representative_price import (
    REAL_MARKET_SOURCE_SQL_REGEX,
    classify_price_provenance,
)
from services.api.app.services.store_recommendation import haversine_km


DEFAULT_RADIUS_KM = 5.0
@dataclass(frozen=True)
class NearbyFoodPriceQuote:
    location_id: int
    store_name: str
    premise_type: str | None
    state: str | None
    district: str | None
    address: str | None
    distance_km: float | None
    price_rm: float
    original_unit: str | None
    purchase_mass_g: float | None
    price_rm_per_100g_purchase: float
    estimated_total_rm: float
    purchase_units: int | None
    minimum_purchase_cost_rm: float
    pricing_method: Literal["EXACT_PACK", "MULTIPLE_PACKS", "LARGER_PACK", "BY_WEIGHT"]
    observed_date: date
    source_dataset_version: str
    price_provenance: str
    price_observation_id: int


@dataclass(frozen=True)
class NearbyFoodPriceResult:
    radius_km: float | None
    radius_expanded: bool
    max_age_days: int | None
    quotes: list[NearbyFoodPriceQuote]
    search_mode: Literal["GPS_RADIUS", "MANUAL_AREA"]
    status: Literal["FOUND", "NO_PRICE_IN_RADIUS", "NO_PRICE_IN_AREA"]


FETCH_NEARBY_PRICE_ROWS_SQL = text(
    """
    select latest.price_observation_id,
           latest.location_id,
           latest.price_rm,
           latest.original_unit,
           latest.purchase_mass_g,
           latest.price_rm_per_100g_purchase,
           latest.observed_date,
           latest.source_dataset_version,
           loc.location_name,
           loc.premise_type,
           loc.state,
           loc.district,
           loc.address,
           loc.latitude,
           loc.longitude
    from (
        select fpo.*,
               row_number() over (
                   partition by fpo.location_id,
                                fpo.purchase_mass_g,
                                lower(coalesce(fpo.original_unit, ''))
                   order by fpo.observed_date desc, fpo.price_observation_id desc
               ) as rn
        from food_price_observation fpo
        where fpo.canonical_food_id = :canonical_food_id
          and fpo.quality_status = 'PASS'
          and fpo.price_rm_per_100g_purchase is not null
          and fpo.source_dataset_version ~ '""" + REAL_MARKET_SOURCE_SQL_REGEX + """'
    ) latest
    join location loc on loc.location_id = latest.location_id
    where latest.rn = 1
      and loc.active = true
      and (cast(:state as text) is null or lower(loc.state) = lower(cast(:state as text)))
      and (cast(:district as text) is null or lower(loc.district) = lower(cast(:district as text)))
      and (
          cast(:require_coordinates as boolean) = false
          or (
              loc.latitude is not null
              and loc.longitude is not null
              and abs(loc.latitude - :latitude) <= :lat_delta
              and abs(loc.longitude - :longitude) <= :lon_delta
          )
      )
    """
)


def lon_delta_for_radius(latitude: float, radius_km: float) -> float:
    # Approximate bounding-box prefilter. Exact radius is enforced with
    # haversine_km below.
    import math

    km_per_degree = max(111.32 * abs(math.cos(math.radians(latitude))), 1.0)
    return radius_km / km_per_degree


async def find_nearby_food_prices(
    db: AsyncSession,
    canonical_food_id: str,
    *,
    latitude: float | None = None,
    longitude: float | None = None,
    state: str | None = None,
    district: str | None = None,
    quantity_g: float,
    purchase_mode: Literal["FIXED_PACK", "BY_WEIGHT"] = "BY_WEIGHT",
    limit: int = 10,
) -> NearbyFoodPriceResult:
    # GPS search is strictly limited to 5 km. Manual search uses state/district
    # area matching and omits distance. Results are sorted by estimated total
    # for the requested purchase quantity, then distance when available.
    has_gps = latitude is not None and longitude is not None
    if has_gps:
        state = None
        district = None
    rows = (
        await db.execute(
            FETCH_NEARBY_PRICE_ROWS_SQL,
            {
                "canonical_food_id": canonical_food_id,
                "latitude": latitude or 0.0,
                "longitude": longitude or 0.0,
                "lat_delta": DEFAULT_RADIUS_KM / 110.574 if has_gps else 999.0,
                "lon_delta": lon_delta_for_radius(latitude, DEFAULT_RADIUS_KM) if has_gps else 999.0,
                "state": state.strip() if state else None,
                "district": district.strip() if district else None,
                "require_coordinates": has_gps,
            },
        )
    ).all()

    candidate_quotes: list[NearbyFoodPriceQuote] = []
    for row in rows:
        data = row._mapping
        distance = None
        if has_gps:
            distance = haversine_km(
                latitude,
                longitude,
                float(data["latitude"]),
                float(data["longitude"]),
            )
            if distance > DEFAULT_RADIUS_KM:
                continue
        price_per_100g = float(data["price_rm_per_100g_purchase"])
        purchase_mass = data.get("purchase_mass_g")
        purchase_mass_g = float(purchase_mass) if purchase_mass is not None else None
        if purchase_mode == "FIXED_PACK" and not (purchase_mass_g and purchase_mass_g > 0):
            # Without a known pack mass there is no defensible way to turn a
            # full-pack observation into a requested-quantity checkout cost.
            continue
        if purchase_mode == "FIXED_PACK":
            purchase_units = max(1, math.ceil(quantity_g / purchase_mass_g))
            minimum_cost = round(float(data["price_rm"]) * purchase_units, 2)
            purchased_mass_g = purchase_mass_g * purchase_units
            if math.isclose(purchased_mass_g, quantity_g, abs_tol=0.5):
                pricing_method = "EXACT_PACK" if purchase_units == 1 else "MULTIPLE_PACKS"
            elif purchase_mass_g > quantity_g:
                pricing_method = "LARGER_PACK"
            else:
                pricing_method = "MULTIPLE_PACKS"
        else:
            purchase_units = None
            minimum_cost = round(price_per_100g * quantity_g / 100.0, 2)
            pricing_method = "BY_WEIGHT"

        candidate_quotes.append(
            NearbyFoodPriceQuote(
                location_id=data["location_id"],
                store_name=data["location_name"],
                premise_type=data["premise_type"],
                state=data["state"],
                district=data["district"],
                address=data["address"],
                distance_km=round(distance, 3) if distance is not None else None,
                price_rm=float(data["price_rm"]),
                original_unit=data["original_unit"],
                purchase_mass_g=purchase_mass_g,
                price_rm_per_100g_purchase=round(price_per_100g, 4),
                estimated_total_rm=minimum_cost,
                purchase_units=purchase_units,
                minimum_purchase_cost_rm=minimum_cost,
                pricing_method=pricing_method,
                observed_date=data["observed_date"],
                source_dataset_version=data["source_dataset_version"],
                price_provenance=classify_price_provenance(data["source_dataset_version"]),
                price_observation_id=data["price_observation_id"],
            )
        )

    # Keep one actionable quote per store even when several observed pack
    # variants exist. Fixed packs prefer least overbuy; weighed goods prefer
    # the lowest normalized checkout estimate.
    quotes_by_location: dict[int, list[NearbyFoodPriceQuote]] = {}
    for quote in candidate_quotes:
        quotes_by_location.setdefault(quote.location_id, []).append(quote)

    quotes = []
    for location_quotes in quotes_by_location.values():
        if purchase_mode == "FIXED_PACK":
            quotes.append(
                min(
                    location_quotes,
                    key=lambda quote: (
                        max(
                            (quote.purchase_mass_g or quantity_g) * (quote.purchase_units or 1)
                            - quantity_g,
                            0.0,
                        ),
                        quote.minimum_purchase_cost_rm,
                        -quote.observed_date.toordinal(),
                    ),
                )
            )
        else:
            quotes.append(
                min(
                    location_quotes,
                    key=lambda quote: (
                        quote.minimum_purchase_cost_rm,
                        -quote.observed_date.toordinal(),
                    ),
                )
            )

    if has_gps:
        selected = quotes
        selected_radius = DEFAULT_RADIUS_KM
        status = "FOUND" if selected else "NO_PRICE_IN_RADIUS"
        search_mode = "GPS_RADIUS"
    else:
        selected = quotes
        selected_radius = None
        status = "FOUND" if selected else "NO_PRICE_IN_AREA"
        search_mode = "MANUAL_AREA"
    selected = sorted(
        selected,
        key=lambda q: (q.minimum_purchase_cost_rm, q.distance_km if q.distance_km is not None else float("inf"), -q.observed_date.toordinal(), q.location_id),
    )[:limit]

    return NearbyFoodPriceResult(
        radius_km=selected_radius,
        radius_expanded=False,
        max_age_days=None,
        quotes=selected,
        search_mode=search_mode,
        status=status,
    )
