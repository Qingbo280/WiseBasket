"""FastAPI entry point for WiseBasket services and recipe-first planning."""
from __future__ import annotations

import asyncio
import dataclasses
import hashlib
import json
import re
import time
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, List, Literal
from zoneinfo import ZoneInfo

from fastapi import BackgroundTasks, Body, Depends, FastAPI, File, HTTPException, Query, Response, UploadFile, status
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError
from sqlalchemy import func, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import selectinload

from packages.optimizer.wisebasket_optimizer.models import (
    FoodInfo,
)
from packages.optimizer.wisebasket_optimizer.portions import is_by_weight_food
from packages.optimizer.wisebasket_optimizer.rni import NUTRIENT_KEYS
from packages.optimizer.wisebasket_optimizer.week_floors import solo_week_floor_g
from packages.optimizer.wisebasket_optimizer.v2.oil_equivalence import OIL_FOOD_IDS, oil_raw_kg

from .config import get_settings
from .db import (
    AsyncSessionLocal,
    AppUser,
    AuthSession,
    CanonicalFood,
    DataQualityIssue,
    EtlRun,
    FoodAlias,
    FoodNutrition,
    FoodPriceObservation,
    GeneratedPlan,
    GeneratedPlanItem,
    HardExclusion,
    HardExclusionFood,
    Household,
    Location,
    PlanStoreItem,
    PlanStoreOption,
    PlanningLocation,
    PlanningRequest,
    PlanningRequestExclusion,
    PantryItem,
    Receipt,
    ReceiptLine,
    ReceiptLineEffect,
    ReceiptLogicalPurchase,
    ReceiptUploadDay,
    RecipeCatalog,
    RecipeCatalogIngredient,
    RecipeCookingStep,
    SourceFoodMapping,
    UnitConversion,
    UserProfile,
    get_db,
)
from .schemas import (
    AdminSummaryResponse,
    AuthLoginRequest,
    AuthRegisterRequest,
    BasketPriceItemResponse,
    BasketPriceRequest,
    BasketPriceResponse,
    BasketPriceStoreItemResponse,
    BasketPriceStoreResponse,
    BasketPriceSummaryResponse,
    FoodPriceUnitResponse,
    LocationSearchResponse,
    LogoutRequest,
    NearbyFoodPriceResponse,
    NearbyFoodPriceStoreResponse,
    PantryFoodResponse,
    PantryConfirmationResponse,
    BasketHaveSyncRequest,
    PantryItemCreateRequest,
    PantryItemResponse,
    PantryItemUpdateRequest,
    RecipeDetailResponse,
    RecipeIngredientResponse,
    RecipeSuggestionResponse,
    RecipeSuggestionsAdviceResponse,
    RecipeSubstitutionResponse,
    ReceiptConfirmRequest,
    ReceiptLineCandidate,
    ReceiptLineResponse,
    ReceiptResponse,
    RefreshRequest,
    SpendingSummaryResponse,
    SupportedLocationResponse,
    TokenResponse,
    UnlockSuggestion,
    PlannedUnlockSummary,
    QuickWinSuggestion,
    UserResponse,
)
from .security import (
    create_access_token,
    find_user_by_email,
    generate_refresh_token,
    get_current_user,
    hash_password,
    hash_refresh_token,
    normalize_email,
    require_admin,
    verify_password,
)
from .planner_v2_catalog_db import DatabasePlannerV2CatalogProvider
from .planner_v2_routes import create_planner_v2_router
from .services.catalogue_detail_service import load_full_catalogue
from .services.receipt_alias_votes import record_receipt_alias_vote
from .services.catalogue_priority import (
    catalogue_priority_or_fallback,
    load_catalogue_priority,
)
from .services.food_tag_service import compute_tags
from .services.location_search import search_geoapify_locations
from .services.nearby_price_service import find_nearby_food_prices
from .services.optimizer_eligibility_service import get_optimizer_eligibility, list_optimizer_eligibility
from .services.recipe_matching import Recipe as MatchRecipe
from .services.recipe_matching import RecipeIngredient as MatchRecipeIngredient
from .services.recipe_matching import match_recipe
from .services.recipe_portions import scale_recipe_for_household
from .services.recipe_quantities import PantryQuantity, normalize_pantry_quantity
from .services.recipe_quantity_summary import (
    RecipeQuantityIngredientInput,
    RecipeQuantitySummary,
    summarize_recipe_quantities,
)
from .services.recipe_substitutions import suggest_recipe_substitutions
from .services.recipe_ranking import MAIN_ROLES, main_required_food_ids, rank_recipe_suggestions
from .services.recipe_readiness import build_recipe_readiness
from .services.recipe_restrictions import recipe_matches_name_restrictions
from .services.recipe_ingredient_reuse import (
    ReusedIngredient, resolve_reused_ingredients, reused_pantry_quantities,
)
from .services.representative_price import (
    fetch_shop_latest_prices_batch,
    minimum_purchase_price,
    resolve_food_prices,
)
from .services.receipt_extraction import run_extraction as run_receipt_extraction
from .services.pantry_stock import available_pantry_rows, sync_basket_have_items, upsert_pantry_stock
from .services.pantry_units import normalize_quantity_unit
from .services.recipe_semantic import SEMANTIC_INCLUDE_THRESHOLD, semantic_scores
from .services.store_recommendation import BasketItem, LatestPrice, StoreLocationCandidate, evaluate_store_candidates, haversine_km

settings = get_settings()

app = FastAPI(
    title="WiseBasket API",
    version="0.2.0",
    description="Recipe-first household grocery planner",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[x.strip() for x in settings.cors_origins.split(",") if x.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(
    create_planner_v2_router(DatabasePlannerV2CatalogProvider(AsyncSessionLocal))
)

# NOTE: no food catalogue is loaded at startup. Every planning/foods request
# reads the candidates live from PostgreSQL (v_optimizer_food_candidate) so
# PriceCatcher price updates take effect immediately; the packaged pilot CSV
# is a solver-level test fixture only, never a serving data source.


async def get_db_session():
    async for session in get_db():
        yield session


@app.get("/health")
def infra_health() -> dict:
    """Railway healthcheck endpoint (keep path in sync with railway-api.toml)."""
    return {"status": "ok", "service": "wisebasket-api", "environment": settings.app_env}


@app.get("/", include_in_schema=False)
def root() -> dict:
    return {
        "service": "wisebasket-api",
        "status": "ok",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/api/v1/health")
async def health(db: AsyncSession = Depends(get_db_session)) -> dict:
    active_foods = (
        await db.execute(
            select(func.count())
            .select_from(CanonicalFood)
            .where(CanonicalFood.status == "ACTIVE")
        )
    ).scalar_one()
    return {
        "status": "ok",
        "foods_loaded": active_foods,
        # Updated by the SF009 price-recovery port: GET /api/v1/foods and plan
        # generation now resolve price via representative_price.resolve_food_price()
        # at query time (District->State->National median cascade over
        # food_price_observation/unit_conversion) rather than the stored,
        # potentially-stale v_optimizer_food_candidate.price_rm_per_100g_edible
        # column -- this string previously named that view and would otherwise
        # now be an inaccurate description of how prices are actually served.
        "data_source": "postgresql (live, query-time representative-price resolution)",
        "planner_mode": "recipe-first-rebuild",
    }


async def _exclusion_codes_by_food(db: AsyncSession) -> dict[str, set[str]]:
    """canonical_food_id -> active hard-exclusion codes mapped to it."""
    rows = await db.execute(
        select(HardExclusionFood.exclusion_code, HardExclusionFood.canonical_food_id)
    )
    out: dict[str, set[str]] = {}
    for code, food_id in rows.all():
        out.setdefault(food_id, set()).add(code)
    return out


_PRICE_UNIT_AMOUNT_RE = re.compile(
    r"(?P<amount>\d+(?:\.\d+)?)\s*(?P<unit>kg|g|lit(?:er|re)?s?|l|ml|biji|pcs?)\b",
    re.IGNORECASE,
)
_PRICE_UNIT_MULTIPACK_RE = re.compile(
    r"(?P<count>\d+(?:\.\d+)?)\s*[x×]\s*"
    r"(?P<amount>\d+(?:\.\d+)?)\s*(?P<unit>kg|g|lit(?:er|re)?s?|l|ml)\b",
    re.IGNORECASE,
)


def _price_unit_display_size(label: str) -> float:
    """Return package magnitude for display ordering, never price arithmetic."""
    multipack = _PRICE_UNIT_MULTIPACK_RE.search(label)
    if multipack:
        amount = float(multipack.group("count")) * float(multipack.group("amount"))
        unit = multipack.group("unit").lower()
    else:
        match = _PRICE_UNIT_AMOUNT_RE.search(label)
        if not match:
            return 0.0
        amount = float(match.group("amount"))
        unit = match.group("unit").lower()

    if unit == "kg" or unit.startswith("lit") or unit == "l":
        return amount * 1000.0
    return amount


async def _largest_source_price_unit_by_food(
    db: AsyncSession,
    canonical_food_ids: list[str],
) -> dict[str, str]:
    """Find the largest real PriceCatcher label when no conversion exists."""
    if not canonical_food_ids:
        return {}

    rows = (
        await db.execute(
            select(
                SourceFoodMapping.canonical_food_id,
                SourceFoodMapping.source_unit_or_form,
            )
            .where(SourceFoodMapping.canonical_food_id.in_(canonical_food_ids))
            .where(func.upper(SourceFoodMapping.source_system) == "PRICECATCHER")
            .where(SourceFoodMapping.source_unit_or_form.is_not(None))
            .where(SourceFoodMapping.verification_status == "VERIFIED")
            .where(SourceFoodMapping.review_status == "APPROVED")
            .where(
                SourceFoodMapping.mapping_status.in_(
                    ("CANDIDATE", "EXACT", "ACCEPTED_EQUIVALENT", "NEEDS_CONVERSION")
                )
            )
        )
    ).all()

    candidates: dict[str, set[str]] = {}
    for food_id, source_unit in rows:
        label = (source_unit or "").strip()
        if food_id and label:
            candidates.setdefault(food_id, set()).add(label)

    return {
        food_id: max(labels, key=lambda label: (_price_unit_display_size(label), label))
        for food_id, labels in candidates.items()
    }


@app.get("/api/v1/foods", response_model=List[FoodInfo])
async def list_foods(
    include_hidden: bool = False,
    include_min_purchase_price: bool = False,
    db: AsyncSession = Depends(get_db_session),
) -> List[FoodInfo]:
    """Full live catalogue: every ACTIVE, catalogue-eligible canonical food
    (the catalog_eligible tag hides foods the team curated out of the app --
    they stay in the DB but are not served here; see migration
    f7a8b9c0d1e2), at whatever detail
    level it actually has real evidence for (FULL_DETAIL / PARTIAL_DETAIL /
    NO_DETAIL -- see catalogue_detail_service). Catalogue visibility is
    deliberately separate from optimizer eligibility: a PARTIAL/NO_DETAIL
    food is never hidden here just because the optimizer cannot currently
    use it (optimizer_eligible discloses that fact per-food instead). Price
    and nutrition are resolved fresh at query time via the same real,
    fail-closed resolvers the optimizer itself uses, and are simply absent
    (null / empty) for a food that doesn't have them -- never fabricated.

    ``?include_hidden=true`` additionally serves the catalog_eligible=false
    foods for the what-you-have/pantry layer (2026-09-16 two-layer
    visibility): those foods have no trustworthy price so they stay out of
    the planning layer, but the user can still buy them in a real shop and
    must be able to record them as stock. Default stays catalogue-eligible
    only, and ordering is curated B40-staple-first (see
    catalogue_priority.py; fail-open to plain food_id order)."""
    entries = await load_full_catalogue(db, include_hidden=include_hidden)
    priority = load_catalogue_priority()
    entries = sorted(
        entries,
        key=lambda e: (catalogue_priority_or_fallback(priority, e.food_id), e.food_id),
    )
    exclusion_map = await _exclusion_codes_by_food(db)
    fallback_unit_map = await _largest_source_price_unit_by_food(
        db,
        [entry.food_id for entry in entries if not entry.pack_label],
    )
    # Receipt review asks for this explicitly. Use the same vetted, latest
    # per-shop observations as the representative-price resolver, but select
    # the lowest purchase-basis rate instead of its median.
    weighed_food_ids = [
        entry.food_id for entry in entries
        if is_by_weight_food(entry.food_id, entry.category, entry.name)
    ]
    shop_prices = (
        await fetch_shop_latest_prices_batch(db, weighed_food_ids)
        if include_min_purchase_price else {}
    )
    min_purchase_prices = {
        food_id: price
        for food_id, rows in shop_prices.items()
        if (price := minimum_purchase_price(rows)) is not None
    }
    return [
        FoodInfo(
            food_id=e.food_id,
            name=e.name,
            name_ms=e.name_ms,
            category=e.category,
            exclusion_codes=sorted(exclusion_map.get(e.food_id, ())),
            price_rm_per_100g=e.price_rm_per_100g,
            price_rm_per_100g_purchase=e.price_rm_per_100g_purchase,
            min_price_rm_per_100g_purchase=min_purchase_prices.get(e.food_id),
            sold_by_weight=is_by_weight_food(e.food_id, e.category, e.name),
            price_available=e.price_rm_per_100g is not None,
            price_is_estimated=e.price_is_estimated,
            price_provenance=e.price_provenance,
            price_source=e.price_source,
            price_updated=e.price_updated,
            nutrients={k: e.nutrients.get(k) for k in NUTRIENT_KEYS},
            nutrition_available=any(e.nutrients.get(k) is not None for k in NUTRIENT_KEYS),
            nutrition_source=e.nutrition_source,
            pack_grams=e.pack_grams,
            pack_label=e.pack_label or fallback_unit_map.get(e.food_id, ""),
            detail_level=e.detail_level,
            missing_detail_fields=e.missing_detail_fields,
            optimizer_eligible=e.optimizer_eligible,
            week_floor_g_per_person=solo_week_floor_g(e.food_id),
            tags=[t.text for t in await compute_tags(db, e.food_id)],
        )
        for e in entries
    ]


@app.get("/api/v1/locations/supported", response_model=List[SupportedLocationResponse])
async def list_supported_locations(
    db: AsyncSession = Depends(get_db_session),
) -> List[SupportedLocationResponse]:
    """Active state/district options from the canonical location table."""
    rows = (
        await db.execute(
            select(Location.state, Location.district)
            .where(Location.active.is_(True))
            .where(Location.state.is_not(None))
            .where(Location.district.is_not(None))
            .group_by(Location.state, Location.district)
            .order_by(Location.state, Location.district)
        )
    ).all()

    grouped: dict[str, list[str]] = {}
    for state, district in rows:
        if not state or not district:
            continue
        grouped.setdefault(state, []).append(district)

    return [
        SupportedLocationResponse(state=state, districts=districts)
        for state, districts in grouped.items()
    ]


async def _food_price_units(
    db: AsyncSession, canonical_food_id: str
) -> list[FoodPriceUnitResponse]:
    rows = (
        await db.execute(
            select(UnitConversion)
            .where(UnitConversion.canonical_food_id == canonical_food_id)
            .where(UnitConversion.conversion_type == "PURCHASE_MASS")
            .where(UnitConversion.production_eligible.is_(True))
            .where(UnitConversion.factor.is_not(None))
            .order_by(UnitConversion.unit_conversion_id)
        )
    ).scalars().all()
    return [
        FoodPriceUnitResponse(
            unit=row.source_unit or "unit",
            unit_label=row.source_unit or "unit",
            target_unit=row.target_unit or "g",
            factor=float(row.factor),
        )
        for row in rows
    ]


async def _resolve_price_check_quantity_g(
    db: AsyncSession,
    canonical_food_id: str,
    *,
    quantity_g: float | None,
    quantity: float | None,
    unit: str | None,
) -> tuple[float, float | None, str | None, list[FoodPriceUnitResponse]]:
    units = await _food_price_units(db, canonical_food_id)
    has_display_quantity = quantity is not None or unit is not None
    if quantity_g is not None and has_display_quantity:
        raise HTTPException(
            status_code=422,
            detail="Use either quantity_g or quantity/unit, not both.",
        )
    if has_display_quantity:
        if quantity is None or unit is None:
            raise HTTPException(
                status_code=422,
                detail="quantity and unit must be provided together.",
            )
        matched = (
            await db.execute(
                select(UnitConversion)
                .where(UnitConversion.canonical_food_id == canonical_food_id)
                .where(UnitConversion.conversion_type == "PURCHASE_MASS")
                .where(UnitConversion.production_eligible.is_(True))
                .where(UnitConversion.factor.is_not(None))
                .where(func.lower(UnitConversion.source_unit) == unit.strip().lower())
                .order_by(UnitConversion.unit_conversion_id)
            )
        ).scalars().first()
        if matched is None:
            raise HTTPException(
                status_code=422,
                detail="This quantity unit is not available for this food.",
            )
        return round(quantity * float(matched.factor), 3), quantity, matched.source_unit, units
    if quantity_g is None and units:
        matched = (
            await db.execute(
                select(UnitConversion)
                .where(UnitConversion.canonical_food_id == canonical_food_id)
                .where(UnitConversion.conversion_type == "PURCHASE_MASS")
                .where(UnitConversion.production_eligible.is_(True))
                .where(UnitConversion.factor.is_not(None))
                .where(func.lower(UnitConversion.source_unit) == units[0].unit.strip().lower())
                .order_by(UnitConversion.unit_conversion_id)
            )
        ).scalars().first()
        if matched is not None:
            return round(float(matched.factor), 3), 1.0, matched.source_unit, units
    return quantity_g if quantity_g is not None else 100.0, None, None, units


@app.get(
    "/api/v1/foods/{canonical_food_id}/price-units",
    response_model=List[FoodPriceUnitResponse],
)
async def food_price_units(
    canonical_food_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> List[FoodPriceUnitResponse]:
    food = (
        await db.execute(
            select(CanonicalFood).where(
                CanonicalFood.canonical_food_id == canonical_food_id,
                CanonicalFood.status == "ACTIVE",
            )
        )
    ).scalar_one_or_none()
    if food is None:
        raise HTTPException(status_code=404, detail="Food not found.")
    return await _food_price_units(db, canonical_food_id)


@app.get(
    "/api/v1/foods/{canonical_food_id}/nearby-prices",
    response_model=NearbyFoodPriceResponse,
)
async def nearby_food_prices(
    canonical_food_id: str,
    latitude: float | None = Query(default=None, ge=-90, le=90),
    longitude: float | None = Query(default=None, ge=-180, le=180),
    state: str | None = Query(default=None, max_length=80),
    district: str | None = Query(default=None, max_length=120),
    quantity_g: float | None = Query(default=None, gt=0, le=200_000),
    quantity: float | None = Query(default=None, gt=0, le=10_000),
    unit: str | None = Query(default=None, max_length=80),
    limit: int = Query(default=10, ge=1, le=50),
    db: AsyncSession = Depends(get_db_session),
) -> NearbyFoodPriceResponse:
    # Guest-safe price check for one item near the user's location. GPS mode
    # is strictly limited to 5 km. Manual mode filters by state/district and
    # omits distance because no exact user point exists.
    has_lat = latitude is not None
    has_lon = longitude is not None
    if has_lat != has_lon:
        raise HTTPException(
            status_code=422,
            detail="latitude and longitude must be provided together.",
        )
    if not has_lat and not state:
        raise HTTPException(
            status_code=422,
            detail="Provide latitude/longitude or a manual state.",
        )

    if has_lat:
        normalized_state, normalized_district = None, None
    else:
        normalized_state, normalized_district = await _normalize_request_area(db, state, district)
    food = (
        await db.execute(
            select(CanonicalFood).where(
                CanonicalFood.canonical_food_id == canonical_food_id,
                CanonicalFood.status == "ACTIVE",
            )
        )
    ).scalar_one_or_none()
    if food is None:
        raise HTTPException(status_code=404, detail="Food not found.")
    requested_quantity_g, requested_quantity, requested_unit, available_units = (
        await _resolve_price_check_quantity_g(
            db,
            canonical_food_id,
            quantity_g=quantity_g,
            quantity=quantity,
            unit=unit,
        )
    )

    result = await find_nearby_food_prices(
        db,
        canonical_food_id,
        latitude=latitude,
        longitude=longitude,
        state=normalized_state,
        district=normalized_district,
        quantity_g=requested_quantity_g,
        purchase_mode=food.purchase_mode,
        limit=limit,
    )
    area_label = None
    distance_note = None
    if result.search_mode == "MANUAL_AREA":
        area_parts = [part for part in (normalized_district, normalized_state) if part]
        area_label = ", ".join(area_parts)
        distance_note = (
            "Manual area search. Showing cheapest observed prices in this area; "
            "exact distance is only available when current location is used."
        )
    return NearbyFoodPriceResponse(
        canonical_food_id=food.canonical_food_id,
        food_name=food.canonical_name,
        food_name_ms=food.canonical_name_ms or food.canonical_name,
        requested_quantity=requested_quantity,
        requested_unit=requested_unit,
        requested_quantity_g=requested_quantity_g,
        available_units=available_units,
        search_mode=result.search_mode,
        state=normalized_state,
        district=normalized_district,
        area_label=area_label,
        radius_km=result.radius_km,
        radius_expanded=result.radius_expanded,
        distance_note=distance_note,
        max_age_days=result.max_age_days,
        result_status=result.status,
        stores=[
            NearbyFoodPriceStoreResponse(
                rank=rank,
                store_id=str(quote.location_id),
                store_name=quote.store_name,
                premise_type=quote.premise_type,
                state=quote.state,
                district=quote.district,
                address=quote.address,
                distance_km=quote.distance_km,
                price_rm=quote.price_rm,
                original_unit=quote.original_unit,
                price_rm_per_100g_purchase=quote.price_rm_per_100g_purchase,
                requested_quantity=requested_quantity,
                requested_unit=requested_unit,
                requested_quantity_g=requested_quantity_g,
                estimated_total_rm=quote.estimated_total_rm,
                purchase_mass_g=quote.purchase_mass_g,
                purchase_units=quote.purchase_units,
                minimum_purchase_cost_rm=quote.minimum_purchase_cost_rm,
                pricing_method=quote.pricing_method,
                last_updated=quote.observed_date.isoformat(),
                source_dataset_version=quote.source_dataset_version,
                price_provenance=quote.price_provenance,
                price_observation_id=quote.price_observation_id,
            )
            for rank, quote in enumerate(result.quotes, start=1)
        ],
    )


def _basket_store_sort_key(
    store: BasketPriceStoreResponse,
) -> tuple[int, float, float, str]:
    """Prefer the store pricing most items, then the nearest equivalent."""
    return (
        -store.matched_item_count,
        store.distance_km if store.distance_km is not None else float("inf"),
        store.basket_cost_rm,
        store.store_id,
    )


@app.post("/api/v2/basket-prices", response_model=BasketPriceResponse)
async def basket_prices(
    request: BasketPriceRequest,
    db: AsyncSession = Depends(get_db_session),
) -> BasketPriceResponse:
    """Price a V2 basket using purchasable packs and recent observations."""
    location = request.location
    if location.latitude is not None:
        state, district = None, None
    else:
        state, district = await _normalize_request_area(
            db,
            location.state,
            location.district,
        )

    requested_ids = list(dict.fromkeys(item.food_id for item in request.items))
    foods = (
        await db.execute(
            select(CanonicalFood).where(
                CanonicalFood.canonical_food_id.in_(requested_ids),
                CanonicalFood.status == "ACTIVE",
            )
        )
    ).scalars().all()
    food_by_id = {food.canonical_food_id: food for food in foods}

    response_items: list[BasketPriceItemResponse] = []
    store_baskets: dict[int, dict[str, Any]] = {}
    for item in request.items:
        food = food_by_id.get(item.food_id)
        if food is None:
            response_items.append(
                BasketPriceItemResponse(
                    food_id=item.food_id,
                    food_name=item.food_id,
                    quantity_kg=item.quantity_kg,
                    purchase_mode="FIXED_PACK",
                    price_source="UNAVAILABLE",
                    matched_store_count=0,
                    estimated_cost_rm=None,
                    latest_observed_date=None,
                    recommended_pack_label=None,
                    recommended_pack_count=None,
                    pricing_method=None,
                )
            )
            continue

        result = await find_nearby_food_prices(
            db,
            item.food_id,
            latitude=location.latitude,
            longitude=location.longitude,
            state=state,
            district=district,
            quantity_g=item.quantity_kg * 1000.0,
            purchase_mode=food.purchase_mode,
            limit=50,
        )
        best = result.quotes[0] if result.quotes else None
        response_items.append(
            BasketPriceItemResponse(
                food_id=item.food_id,
                food_name=food.canonical_name,
                quantity_kg=item.quantity_kg,
                purchase_mode=food.purchase_mode,
                price_source="OBSERVED_STORE_PRICE" if best else "UNAVAILABLE",
                matched_store_count=len(result.quotes),
                estimated_cost_rm=best.minimum_purchase_cost_rm if best else None,
                latest_observed_date=best.observed_date.isoformat() if best else None,
                recommended_pack_label=best.original_unit if best else None,
                recommended_pack_count=best.purchase_units if best else None,
                pricing_method=best.pricing_method if best else None,
            )
        )
        for quote in result.quotes:
            basket = store_baskets.setdefault(
                quote.location_id,
                {
                    "store_name": quote.store_name,
                    "matched_item_count": 0,
                    "basket_cost_rm": 0.0,
                    "distance_km": quote.distance_km,
                    "latest_observed_date": quote.observed_date,
                    "items": [],
                },
            )
            basket["matched_item_count"] += 1
            basket["basket_cost_rm"] += quote.minimum_purchase_cost_rm
            basket["latest_observed_date"] = max(
                basket["latest_observed_date"],
                quote.observed_date,
            )
            basket["items"].append(
                BasketPriceStoreItemResponse(
                    food_id=item.food_id,
                    cost_rm=quote.minimum_purchase_cost_rm,
                )
            )

    stores = sorted(
        (
            BasketPriceStoreResponse(
                store_id=str(store_id),
                store_name=basket["store_name"],
                matched_item_count=basket["matched_item_count"],
                basket_cost_rm=round(basket["basket_cost_rm"], 2),
                distance_km=basket["distance_km"],
                latest_observed_date=basket["latest_observed_date"].isoformat(),
                items=basket["items"],
            )
            for store_id, basket in store_baskets.items()
        ),
        key=_basket_store_sort_key,
    )
    matched_count = sum(
        item.price_source == "OBSERVED_STORE_PRICE" for item in response_items
    )
    estimated_count = sum(
        item.price_source == "CATALOGUE_ESTIMATE" for item in response_items
    )
    return BasketPriceResponse(
        currency="MYR",
        pricing_scope="LATEST_AVAILABLE_OBSERVED_PRICES",
        items=response_items,
        stores=stores,
        summary=BasketPriceSummaryResponse(
            total_item_count=len(response_items),
            matched_item_count=matched_count,
            estimated_item_count=estimated_count,
            unavailable_item_count=len(response_items) - matched_count - estimated_count,
        ),
    )


@app.get("/api/v1/locations/search", response_model=LocationSearchResponse)
async def search_locations(
    q: str = Query(min_length=3, max_length=120),
    limit: int = Query(default=5, ge=1, le=10),
) -> LocationSearchResponse:
    """Malaysia-only location suggestions from Geoapify."""
    try:
        return LocationSearchResponse(
            results=await search_geoapify_locations(q, settings, limit=limit)
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Location search is temporarily unavailable.",
        )


def _user_response(user: AppUser) -> UserResponse:
    return UserResponse(
        user_id=user.user_id,
        email=user.email,
        role=user.role,
        status=user.status,
        email_verified=user.email_verified,
    )


async def _issue_tokens(
    user: AppUser,
    db: AsyncSession,
    client_type: str,
    device_name: str | None = None,
    *,
    commit: bool = True,
) -> TokenResponse:
    refresh_token = generate_refresh_token()
    expires_at = datetime.now(UTC) + timedelta(days=settings.refresh_token_days)
    session = AuthSession(
        user_id=user.user_id,
        refresh_token_hash=hash_refresh_token(refresh_token),
        client_type=client_type,
        device_name=device_name,
        expires_at=expires_at,
    )
    db.add(session)
    if commit:
        await db.commit()
    return TokenResponse(
        access_token=create_access_token(user),
        refresh_token=refresh_token,
        expires_in_seconds=settings.access_token_minutes * 60,
        user=_user_response(user),
    )


@app.post("/api/v1/auth/register", response_model=TokenResponse)
async def register(request: AuthRegisterRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    user = AppUser(
        email=request.email.strip(),
        email_normalized=normalize_email(request.email),
        password_hash=hash_password(request.password),
        role="USER",
        status="ACTIVE",
        email_verified=False,
    )
    db.add(user)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Email is already registered.") from exc

    try:
        response = await _issue_tokens(user, db, request.client_type, request.device_name, commit=False)
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return response


@app.post("/api/v1/auth/login", response_model=TokenResponse)
async def login(request: AuthLoginRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    user = await find_user_by_email(db, request.email)
    if user is None or not verify_password(request.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password.")
    if user.status != "ACTIVE":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account is not active.")
    if request.client_type == "ADMIN_WEB" and user.role != "ADMIN":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required.")
    return await _issue_tokens(user, db, request.client_type, request.device_name)


@app.post("/api/v1/auth/refresh", response_model=TokenResponse)
async def refresh(request: RefreshRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    token_hash = hash_refresh_token(request.refresh_token)
    result = await db.execute(
        select(AuthSession, AppUser)
        .join(AppUser, AppUser.user_id == AuthSession.user_id)
        .where(
            AuthSession.refresh_token_hash == token_hash,
            AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > datetime.now(UTC),
            AppUser.status == "ACTIVE",
        )
    )
    row = result.first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token.")
    session, user = row
    session.revoked_at = datetime.now(UTC)
    return await _issue_tokens(user, db, session.client_type, session.device_name)


@app.post("/api/v1/auth/logout")
async def logout(request: LogoutRequest, db: AsyncSession = Depends(get_db)) -> dict:
    token_hash = hash_refresh_token(request.refresh_token)
    result = await db.execute(select(AuthSession).where(AuthSession.refresh_token_hash == token_hash))
    session = result.scalar_one_or_none()
    if session is not None and session.revoked_at is None:
        session.revoked_at = datetime.now(UTC)
        await db.commit()
    return {"status": "ok"}


@app.get("/api/v1/auth/me", response_model=UserResponse)
async def me(current_user: AppUser = Depends(get_current_user)) -> UserResponse:
    return _user_response(current_user)


# ---------------------------------------------------------------------------
# Per-account app profile (frontend-owned JSON blob). A signed-in user never
# re-enters household/budget/location/restrictions/usual-basket on a new
# device: the mobile app hydrates from here after login and syncs edits back.
# Anonymous usage is unaffected (nothing is stored server-side).
# ---------------------------------------------------------------------------

_PROFILE_MAX_BYTES = 64 * 1024


@app.get("/api/v1/profile")
async def get_profile(
    current_user: AppUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    row = await db.get(UserProfile, current_user.user_id)
    return {"profile": row.profile_data if row else None}


@app.put("/api/v1/profile")
async def put_profile(
    payload: dict[str, Any] = Body(...),
    current_user: AppUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    profile = payload.get("profile")
    if profile is not None and not isinstance(profile, dict):
        raise HTTPException(status_code=422, detail="profile must be an object or null.")
    if len(json.dumps(profile or {})) > _PROFILE_MAX_BYTES:
        raise HTTPException(status_code=422, detail="profile payload too large.")
    row = await db.get(UserProfile, current_user.user_id)
    if row is None:
        row = UserProfile(user_id=current_user.user_id, profile_data=profile)
        db.add(row)
    else:
        row.profile_data = profile
    await db.commit()
    return {"ok": True}


# Legacy request restriction -> authoritative DB hard_exclusion code.
# Legacy allergies use lowercase tags; dietary_patterns use the API names.
_ALLERGY_EXCLUSION_CODES = {
    "egg": "EGGS",
    "dairy": "MILK",
    "peanut": "PEANUTS",
    "shellfish": "SHELLFISH",
}
_PATTERN_EXCLUSION_CODES = {
    "vegetarian": "VEGETARIAN",
    "no-pork": "NO_PORK",
    "shellfish-free": "SHELLFISH",
}






async def _resolve_excluded_food_ids(db: AsyncSession, exclusion_codes: list[str]) -> set[str]:
    """Resolve requested hard-exclusion codes to canonical food_ids.

    The PostgreSQL hard_exclusion / hard_exclusion_food tables are the
    authoritative restriction mapping (Data team). Codes are validated
    explicitly: unknown OR inactive codes are rejected with 422 rather than
    silently ignored. A code with zero current food mappings is a safe
    no-op (there is simply nothing to remove right now).
    """
    if not exclusion_codes:
        return set()
    normalized = [code.strip().upper() for code in exclusion_codes if code.strip()]
    if not normalized:
        return set()
    supported = await db.execute(
        select(HardExclusion.exclusion_code).where(
            HardExclusion.exclusion_code.in_(normalized),
            HardExclusion.active.is_(True),
        )
    )
    supported_codes = {row[0] for row in supported.all()}
    unknown = sorted(set(normalized) - supported_codes)
    if unknown:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported hard exclusions: {', '.join(unknown)}",
        )
    # DB canonical-food mappings are used when present; pilot optimizer falls back to tag mapping below.
    food_rows = await db.execute(
        select(HardExclusionFood.canonical_food_id).where(HardExclusionFood.exclusion_code.in_(normalized))
    )
    return {row[0] for row in food_rows.all()}




# Real store comparison: with a precise user location, only geocoded stores
# within this straight-line radius are quoted.
MAX_STORE_DISTANCE_KM = 5.0

# GPS area resolution: a precise location overrides the request's stated
# state/district with the nearest geocoded store's area - but only when the
# nearest store is within this distance. Beyond it the fix is treated as
# out-of-area (e.g. public builds run from abroad) and the stated area stands.
GPS_AREA_MAX_KM = 50.0

# Budget buffer: every solve runs against this share of the real budget so
# the final basket leaves roughly a 5% emergency reserve. Applied to both the
# area-priced pass and the store-priced pass.
STORE_PASS_BUDGET_FACTOR = 0.95

# The location pickers offer friendly area names while PriceCatcher registers
# federal territories with a "W.P. " prefix (and parliamentary sub-districts -
# Bangsar is "Lembah Pantai", not "Kuala Lumpur"). Without this mapping a
# manual KL/Putrajaya/Labuan selection matches zero stores (2026-08-31
# teammate field report from Bangsar).
_STATE_ALIASES = {
    "kuala lumpur": "W.P. Kuala Lumpur",
    "wp kuala lumpur": "W.P. Kuala Lumpur",
    "putrajaya": "W.P. Putrajaya",
    "wp putrajaya": "W.P. Putrajaya",
    "labuan": "W.P. Labuan",
    "wp labuan": "W.P. Labuan",
}


def _canonical_state(state: str | None) -> str | None:
    if not state:
        return state
    return _STATE_ALIASES.get(state.strip().lower(), state)


async def _normalize_request_area(
    db: AsyncSession, state: str | None, district: str | None
) -> tuple[str | None, str | None]:
    """Map the request's stated area onto canonical location rows.

    State aliases are resolved ("Kuala Lumpur" -> "W.P. Kuala Lumpur"). A
    district with no active stores in the state degrades to state-level so
    the user still gets area pricing and store comparison instead of an
    empty feed; resolved_location echoes the normalized values honestly.
    """
    state = _canonical_state(state)
    if state and district:
        count = (
            await db.execute(
                select(func.count())
                .select_from(Location)
                .where(Location.active.is_(True))
                .where(func.lower(Location.state) == state.strip().lower())
                .where(func.lower(Location.district) == district.strip().lower())
            )
        ).scalar_one()
        if not count:
            district = None
    return state, district


async def _resolve_area_from_gps(
    db: AsyncSession, lat: float, lon: float
) -> tuple[str, str] | None:
    """(state, district) of the nearest geocoded active store, or None.

    The nearest store is a proxy for "which market area is this user in".
    The SQL scan is limited to a ~1-degree bounding box to stay cheap; None
    means no store is close enough to trust the fix for area resolution.
    """
    rows = (
        await db.execute(
            select(
                Location.state,
                Location.district,
                Location.latitude,
                Location.longitude,
            )
            .where(Location.active.is_(True))
            .where(Location.latitude.is_not(None))
            .where(Location.longitude.is_not(None))
            .where(func.abs(Location.latitude - lat) <= 1.0)
            .where(func.abs(Location.longitude - lon) <= 1.0)
        )
    ).all()
    best: tuple[float, str, str] | None = None
    for state, district, store_lat, store_lon in rows:
        distance = haversine_km(lat, lon, float(store_lat), float(store_lon))
        if best is None or distance < best[0]:
            best = (distance, state, district)
    if best is None or best[0] > GPS_AREA_MAX_KM:
        return None
    return best[1], best[2]




@app.post("/api/v1/plans")
async def create_plan(
    payload: dict[str, Any] = Body(...),
):
    """Retired V1 boundary while the recipe-first planner is rebuilt.

    Returning an explicit terminal response is safer than routing either of
    the endpoint's former payload shapes into the basket-first optimizer.
    ``payload`` remains in the signature so both former request shapes receive
    the same stable retirement response.
    """
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail={
            "code": "PLANNER_V1_RETIRED",
            "message": "The basket-first planner has been retired while the recipe-first planner is rebuilt.",
        },
    )


@app.post("/api/v1/households")
async def create_household(
    household: dict[str, Any],
    current_user: AppUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    adults = int(household.get("adults", 1))
    children = int(household.get("children", 0))
    if adults + children <= 0:
        raise HTTPException(status_code=422, detail="Household must have at least 1 member.")
    entity = Household(
        owner_user_id=current_user.user_id,
        name=household.get("name"),
        adults=adults,
        children=children,
    )
    db.add(entity)
    await db.commit()
    await db.refresh(entity)
    return {"id": entity.id, "name": entity.name, "adults": entity.adults, "children": entity.children}


@app.get("/api/v1/households")
async def list_households(
    current_user: AppUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    result = await db.execute(select(Household).where(Household.owner_user_id == current_user.user_id))
    households = result.scalars().all()
    return [{"id": h.id, "name": h.name, "adults": h.adults, "children": h.children} for h in households]


@app.patch("/api/v1/households/{household_id}")
async def update_household(
    household_id: int,
    household: dict[str, Any],
    current_user: AppUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    entity = await find_owned_household(household_id, current_user, db)
    adults = int(household.get("adults", entity.adults))
    children = int(household.get("children", entity.children))
    if adults + children <= 0:
        raise HTTPException(status_code=422, detail="Household must have at least 1 member.")
    entity.name = household.get("name", entity.name)
    entity.adults = adults
    entity.children = children
    await db.commit()
    await db.refresh(entity)
    return {"id": entity.id, "name": entity.name, "adults": entity.adults, "children": entity.children}


async def find_owned_household(
    household_id: int,
    current_user: AppUser,
    db: AsyncSession,
    *,
    for_update: bool = False,
) -> Household:
    if for_update:
        household = await db.scalar(
            select(Household)
            .where(Household.id == household_id, Household.owner_user_id == current_user.user_id)
            .with_for_update()
        )
    else:
        household = await db.get(Household, household_id)
    if household is None or household.owner_user_id != current_user.user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Household not found.")
    return household


def pantry_item_response(item: PantryItem, food: CanonicalFood) -> PantryItemResponse:
    quantity = float(item.quantity) if item.quantity is not None else None
    unit = item.unit
    # Receipt imports and earlier manual entries may still be stored in grams.
    # Normalize them at the API boundary so every Epic 5 consumer sees kg.
    if quantity is not None and unit == "g":
        quantity = quantity / 1000
        unit = "kg"
    return PantryItemResponse(
        pantry_item_id=item.pantry_item_id,
        household_id=item.household_id,
        food=PantryFoodResponse(
            canonical_food_id=food.canonical_food_id,
            name=food.canonical_name,
            name_ms=food.canonical_name_ms,
            category=food.category,
        ),
        source=item.source,
        status=item.status,
        basket_have_managed=item.basket_have_managed,
        quantity=quantity,
        unit=unit,
        created_at=item.created_at,
    )


@app.post(
    "/api/v1/households/{household_id}/pantry-items",
    response_model=PantryItemResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_pantry_item(
    household_id: int,
    request: PantryItemCreateRequest,
    current_user: AppUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> PantryItemResponse:
    household = await find_owned_household(household_id, current_user, db, for_update=True)
    food = await db.scalar(
        select(CanonicalFood).where(
            CanonicalFood.canonical_food_id == request.canonical_food_id,
            CanonicalFood.status == "ACTIVE",
        )
    )
    if food is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Active food not found.")

    item = await upsert_pantry_stock(
        db,
        household_id,
        food.canonical_food_id,
        Decimal(str(request.quantity)) if request.quantity is not None else None,
        request.unit,
        "MANUAL",
    )
    # A changed pantry must be confirmed again before recipes are requested.
    household.pantry_confirmed_at = None
    await db.commit()
    await db.refresh(item)
    return pantry_item_response(item, food)


@app.put(
    "/api/v1/households/{household_id}/basket-have-items",
    response_model=list[PantryItemResponse],
)
async def replace_basket_have_items(
    household_id: int,
    request: BasketHaveSyncRequest,
    current_user: AppUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> list[PantryItemResponse]:
    household = await find_owned_household(household_id, current_user, db, for_update=True)
    if request.food_ids:
        active_ids = set((await db.scalars(
            select(CanonicalFood.canonical_food_id).where(
                CanonicalFood.canonical_food_id.in_(request.food_ids),
                CanonicalFood.status == "ACTIVE",
            )
        )).all())
        if active_ids != set(request.food_ids):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Active food not found.")
    await sync_basket_have_items(db, household, request.food_ids)
    await db.commit()
    return [pantry_item_response(item, food) for item, food in await available_pantry_rows(db, household_id)]


@app.get(
    "/api/v1/households/{household_id}/pantry-items",
    response_model=list[PantryItemResponse],
)
async def list_pantry_items(
    household_id: int,
    current_user: AppUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> list[PantryItemResponse]:
    await find_owned_household(household_id, current_user, db)
    return [pantry_item_response(item, food) for item, food in await available_pantry_rows(db, household_id)]


@app.patch(
    "/api/v1/households/{household_id}/pantry-items/{pantry_item_id}",
    response_model=PantryItemResponse,
)
async def update_pantry_item(
    household_id: int,
    pantry_item_id: int,
    request: PantryItemUpdateRequest,
    current_user: AppUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> PantryItemResponse:
    household = await find_owned_household(household_id, current_user, db, for_update=True)
    item = await db.scalar(
        select(PantryItem).where(
            PantryItem.pantry_item_id == pantry_item_id,
            PantryItem.household_id == household_id,
            PantryItem.status == "AVAILABLE",
        ).with_for_update()
    )
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pantry item not found.")

    food = await db.scalar(
        select(CanonicalFood).where(
            CanonicalFood.canonical_food_id == request.canonical_food_id,
            CanonicalFood.status == "ACTIVE",
        )
    )
    if food is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Active food not found.")

    item.canonical_food_id = food.canonical_food_id
    item.basket_have_managed = False
    # Existing callers may change only the food. Quantity changes are applied
    # only when the PATCH request explicitly includes the quantity pair.
    if "quantity" in request.model_fields_set:
        item.quantity = Decimal(str(request.quantity)) if request.quantity is not None else None
        item.unit = request.unit
    household.pantry_confirmed_at = None
    await db.commit()
    await db.refresh(item)
    return pantry_item_response(item, food)


@app.delete(
    "/api/v1/households/{household_id}/pantry-items/{pantry_item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_pantry_item(
    household_id: int,
    pantry_item_id: int,
    current_user: AppUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> Response:
    household = await find_owned_household(household_id, current_user, db, for_update=True)
    item = await db.scalar(
        select(PantryItem).where(
            PantryItem.pantry_item_id == pantry_item_id,
            PantryItem.household_id == household_id,
            PantryItem.status == "AVAILABLE",
        ).with_for_update()
    )
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pantry item not found.")

    # Keep the pantry history while excluding removed food from recipe matching.
    item.status = "REMOVED"
    item.basket_have_managed = False
    household.pantry_confirmed_at = None
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.post(
    "/api/v1/households/{household_id}/pantry-confirmations",
    response_model=PantryConfirmationResponse,
)
async def confirm_pantry_items(
    household_id: int,
    current_user: AppUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> PantryConfirmationResponse:
    household = await find_owned_household(household_id, current_user, db, for_update=True)
    available_item_count = await db.scalar(
        select(func.count())
        .select_from(PantryItem)
        .where(PantryItem.household_id == household_id, PantryItem.status == "AVAILABLE")
    )
    household.pantry_confirmed_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(household)

    return PantryConfirmationResponse(
        household_id=household_id,
        available_item_count=int(available_item_count or 0),
        confirmed_at=household.pantry_confirmed_at,
    )


async def require_confirmed_pantry(
    household_id: int,
    current_user: AppUser,
    db: AsyncSession,
) -> Household:
    household = await find_owned_household(household_id, current_user, db)
    if household.pantry_confirmed_at is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Confirm available food before requesting recipe suggestions.",
        )
    return household


def pantry_food_response(food: CanonicalFood) -> PantryFoodResponse:
    return PantryFoodResponse(
        canonical_food_id=food.canonical_food_id,
        name=food.canonical_name,
        name_ms=food.canonical_name_ms,
        category=food.category,
    )


async def recipe_ingredient_rows(recipe_id: str, db: AsyncSession):
    result = await db.execute(
        select(RecipeCatalogIngredient, CanonicalFood)
        .join(CanonicalFood, CanonicalFood.canonical_food_id == RecipeCatalogIngredient.canonical_food_id)
        .where(RecipeCatalogIngredient.recipe_id == recipe_id)
        .order_by(RecipeCatalogIngredient.display_order)
    )
    return result.all()


async def eligible_reuse_pantry_ids(
    db: AsyncSession,
    pantry_food_ids: set[str],
    excluded_food_ids: set[str],
    *,
    gluten_free: bool,
    custom_restriction: str,
) -> set[str]:
    """Never satisfy a recipe slot with a prohibited pantry alternative."""
    eligible = pantry_food_ids - excluded_food_ids
    if not eligible or not (gluten_free or custom_restriction):
        return eligible
    foods = (await db.scalars(
        select(CanonicalFood).where(CanonicalFood.canonical_food_id.in_(eligible))
    )).all()
    return {
        food.canonical_food_id for food in foods
        if not recipe_matches_name_restrictions(
            [food.canonical_name], gluten_free=gluten_free,
            custom_restriction=custom_restriction,
        )
    }


async def load_reused_recipe_foods(
    db: AsyncSession, reused_food_ids: set[str],
) -> dict[str, CanonicalFood]:
    if not reused_food_ids:
        return {}
    foods = (await db.scalars(
        select(CanonicalFood).where(CanonicalFood.canonical_food_id.in_(reused_food_ids))
    )).all()
    return {food.canonical_food_id: food for food in foods}


def displayed_recipe_food(
    recipe_food: CanonicalFood,
    reused_ingredients: dict[str, ReusedIngredient],
    reused_foods_by_id: dict[str, CanonicalFood],
) -> CanonicalFood:
    """Project a pantry-owned SKU without changing the stored recipe slot."""
    match = reused_ingredients.get(recipe_food.canonical_food_id)
    return reused_foods_by_id[match.pantry_food_id] if match else recipe_food


def pantry_quantity_for_recipe(item: PantryItem) -> PantryQuantity:
    # Pantry entries without a measured amount remain visible but are never
    # treated as proof that the recipe has enough of that ingredient.
    if item.quantity is None or item.unit is None:
        return PantryQuantity(quantity_status="UNKNOWN", quantity_g=None, source=item.source)

    if item.canonical_food_id in OIL_FOOD_IDS:
        raw_kg = oil_raw_kg(Decimal(item.quantity), item.unit)
        return PantryQuantity(
            quantity_status="KNOWN" if raw_kg is not None else "UNKNOWN",
            quantity_g=float(raw_kg * 1000) if raw_kg is not None else None,
            source=item.source,
        )

    quantity = normalize_pantry_quantity(float(item.quantity), item.unit)
    return PantryQuantity(
        quantity_status=quantity.quantity_status,
        quantity_g=quantity.quantity_g,
        source=item.source,
    )


def quantity_in_kg(quantity_g: float | None) -> float | None:
    # Recipe calculations remain in grams to avoid changing their precision,
    # while the API presents one consistent kilogram unit to mobile clients.
    if quantity_g is None:
        return None
    return round(quantity_g / 1000, 6)


def build_recipe_quantity_summary(
    recipe: RecipeCatalog,
    ingredient_rows,
    household: Household,
    pantry_items: tuple[PantryItem, ...],
    reused_ingredients: dict[str, ReusedIngredient] | None = None,
) -> RecipeQuantitySummary:
    reused_ingredients = reused_ingredients or {}
    pantry_quantities_by_food: dict[str, list[PantryQuantity]] = {}
    for item in pantry_items:
        pantry_quantities_by_food.setdefault(item.canonical_food_id, []).append(
            pantry_quantity_for_recipe(item)
        )

    # Equivalent oils share one stock pool. Allocate it once, in reviewed
    # ingredient order, so two oil lines cannot each claim the same pantry lot.
    oil_quantities = [
        quantity for food_id in OIL_FOOD_IDS
        for quantity in pantry_quantities_by_food.get(food_id, [])
    ]
    oil_remaining_g = sum(q.quantity_g or 0 for q in oil_quantities if q.quantity_status == "KNOWN")
    oil_unknown = any(q.quantity_status == "UNKNOWN" for q in oil_quantities)
    oil_allocations: dict[int, float] = {}
    for index in sorted(
        (index for index, (ingredient, _) in enumerate(ingredient_rows)
         if ingredient.canonical_food_id in OIL_FOOD_IDS),
        key=lambda index: (not ingredient_rows[index][0].required, index),
    ):
        ingredient = ingredient_rows[index][0]
        required_g = (
            float(ingredient.base_quantity_g) * (household.adults + household.children * 0.5) / recipe.base_servings
            if ingredient.base_quantity_g is not None and recipe.base_servings else oil_remaining_g
        )
        oil_allocations[index] = min(oil_remaining_g, required_g)
        oil_remaining_g -= oil_allocations[index]
    ingredient_inputs = []
    for index, (ingredient, food) in enumerate(ingredient_rows):
        quantities = tuple(pantry_quantities_by_food.get(ingredient.canonical_food_id, []))
        reused = reused_ingredients.get(ingredient.canonical_food_id)
        if reused is not None:
            quantities = reused_pantry_quantities(reused, pantry_quantities_by_food)
        if ingredient.canonical_food_id in OIL_FOOD_IDS:
            allocated_g = oil_allocations[index]
            quantities = (
                (PantryQuantity("KNOWN", allocated_g),) if allocated_g > 0 else ()
            ) + ((PantryQuantity("UNKNOWN", None),) if oil_unknown else ())
        ingredient_inputs.append(RecipeQuantityIngredientInput(
            canonical_food_id=ingredient.canonical_food_id,
            required=ingredient.required,
            base_quantity_g=float(ingredient.base_quantity_g) if ingredient.base_quantity_g is not None else None,
            pantry_quantities=quantities,
        ))

    return summarize_recipe_quantities(
        base_servings=recipe.base_servings,
        adult_count=household.adults,
        child_count=household.children,
        ingredients=tuple(ingredient_inputs),
    )


def recipe_suggestion_response(
    recipe: RecipeCatalog,
    ingredient_rows,
    pantry_food_ids: set[str],
    quantity_summary: RecipeQuantitySummary,
    reused_ingredients: dict[str, ReusedIngredient] | None = None,
    reused_foods_by_id: dict[str, CanonicalFood] | None = None,
) -> RecipeSuggestionResponse:
    reused_ingredients = reused_ingredients or {}
    reused_foods_by_id = reused_foods_by_id or {}
    recipe_definition = MatchRecipe(
        recipe_id=recipe.recipe_id,
        title=recipe.name,
        ingredients=tuple(
            MatchRecipeIngredient(
                canonical_food_id=ingredient.canonical_food_id,
                required=ingredient.required,
            )
            for ingredient, food in ingredient_rows
        ),
    )
    matched_pantry_ids = pantry_food_ids | reused_ingredients.keys()
    result = match_recipe(recipe_definition, matched_pantry_ids)
    foods_by_id = {food.canonical_food_id: food for ingredient, food in ingredient_rows}
    # Main-role statistics drive honest "can I cook this" signalling: oil and
    # seasonings never count, so a basics-only pantry cannot fake a match.
    main_food_ids = main_required_food_ids(ingredient_rows)
    missing_main_ids = [
        ingredient.canonical_food_id for ingredient, _ in ingredient_rows
        if ingredient.required
        and ingredient.canonical_food_id in main_food_ids
        and ingredient.canonical_food_id not in matched_pantry_ids
    ]
    main_match_count = len(main_food_ids) - len(missing_main_ids)
    available_main_ids = [
        ingredient.canonical_food_id for ingredient, _ in ingredient_rows
        if ingredient.required
        and ingredient.canonical_food_id in main_food_ids
        and ingredient.canonical_food_id in matched_pantry_ids
    ]

    return RecipeSuggestionResponse(
        recipe_id=recipe.recipe_id,
        name=recipe.name,
        description=recipe.description,
        available_ingredients=[
            pantry_food_response(displayed_recipe_food(foods_by_id[food_id], reused_ingredients, reused_foods_by_id))
            for food_id in result.available_food_ids
        ],
        missing_required_ingredients=[pantry_food_response(foods_by_id[food_id]) for food_id in result.missing_food_ids],
        required_match_count=result.required_match_count,
        required_ingredient_count=result.required_ingredient_count,
        main_ingredient_count=len(main_food_ids),
        main_match_count=main_match_count,
        available_main_ingredients=[
            pantry_food_response(foods_by_id[food_id]) for food_id in available_main_ids
        ],
        missing_main_ingredients=[
            pantry_food_response(foods_by_id[food_id]) for food_id in missing_main_ids
        ],
        can_make=main_match_count == len(main_food_ids),
        ingredient_count=len(recipe_definition.ingredients),
        optional_ingredient_count=sum(not ingredient.required for ingredient, _ in ingredient_rows),
        matched_alternatives={food_id: match.pantry_food_id
                              for food_id, match in reused_ingredients.items()},
        base_servings=quantity_summary.base_servings,
        household_servings=quantity_summary.household_servings,
        quantity_status=quantity_summary.quantity_status,
        is_quantity_sufficient=quantity_summary.is_quantity_sufficient,
        required_quantity_sufficient_count=quantity_summary.required_quantity_sufficient_count,
        readiness=build_recipe_readiness(
            quantity_summary,
            {ingredient.canonical_food_id: pantry_food_response(displayed_recipe_food(
                food, reused_ingredients, reused_foods_by_id,
            )) for ingredient, food in ingredient_rows if ingredient.required},
            set(result.available_food_ids),
            frozenset(food_id for food_id, match in reused_ingredients.items()
                      if not match.purchase_mass_comparable),
        ),
    )


def recipe_detail_ingredient_response(
    ingredient: RecipeCatalogIngredient,
    food: CanonicalFood,
    quantity,
    reused_ingredients: dict[str, ReusedIngredient],
    reused_foods_by_id: dict[str, CanonicalFood],
) -> RecipeIngredientResponse:
    reused = reused_ingredients.get(ingredient.canonical_food_id)
    comparable = reused is None or reused.purchase_mass_comparable
    return RecipeIngredientResponse(
        food=pantry_food_response(displayed_recipe_food(food, reused_ingredients, reused_foods_by_id)),
        required=ingredient.required,
        # The recipe's raw grams belong to its original cut/concentration.
        # Never label them as a substitute's purchase amount without a yield.
        base_quantity_kg=quantity_in_kg(quantity.base_quantity_g) if comparable else None,
        required_quantity_kg=quantity_in_kg(quantity.required_quantity_g) if comparable else None,
        available_quantity_kg=quantity_in_kg(quantity.available_quantity_g),
        quantity_status=quantity.quantity_status,
        is_quantity_sufficient=quantity.is_quantity_sufficient,
        shortfall_quantity_kg=quantity_in_kg(quantity.shortfall_quantity_g),
        remaining_quantity_kg=quantity_in_kg(quantity.remaining_quantity_g),
    )


# Ordering priority for main roles in unlock suggestions: proteins first,
# vegetables next, staples last. NULL roles (grams-heuristic mains) sit in
# the middle tier.
_MAIN_ROLE_PRIORITY = {
    "MAIN_PROTEIN": 0,
    "MAIN_VEGETABLE": 1,
    "SUPPORTING_VEGETABLE": 1,
    "STAPLE": 2,
}


async def load_estimated_prices_rm(db, food_ids) -> dict[str, float]:
    """Representative purchase price (RM/100g) per food, read-only.

    Reuses the batch representative-price path (no new price logic). Foods
    without a resolvable price are absent; callers sort them last.
    """
    resolved = await resolve_food_prices(db, sorted(set(food_ids)))
    return {
        food_id: float(price.price_rm_per_100g_purchase)
        for food_id, price in resolved.items()
    }


def _main_role_of(ingredient) -> str | None:
    role = getattr(ingredient, "ingredient_role", None)
    return role if role in MAIN_ROLES else None


def recipe_quick_win_suggestions(
    eligible_recipes, prices: dict[str, float], limit: int = 5,
) -> list[QuickWinSuggestion]:
    """Single-main dishes that become cookable with exactly one purchase.

    Only eligible recipes whose required main-role set has exactly one
    ingredient qualify. One entry per food (the alphabetically first recipe
    wins the slot), ordered by estimated price ascending with unpriced foods
    last and a food_id tiebreak.
    """
    by_food: dict[str, tuple] = {}
    for recipe, ingredient_rows, _ in eligible_recipes:
        main_food_ids = main_required_food_ids(ingredient_rows)
        if len(main_food_ids) != 1:
            continue
        food_id = next(iter(main_food_ids))
        food = next(
            food for ingredient, food in ingredient_rows
            if ingredient.canonical_food_id == food_id
        )
        current = by_food.get(food_id)
        if current is None or (recipe.name.casefold(), recipe.recipe_id) < current[0]:
            by_food[food_id] = ((recipe.name.casefold(), recipe.recipe_id), food, recipe)
    ordered = sorted(
        by_food.items(),
        key=lambda item: (
            prices.get(item[0]) is None,
            prices.get(item[0]) or 0.0,
            item[0],
        ),
    )[:limit]
    return [
        QuickWinSuggestion(
            canonical_food_id=food_id,
            name=food.canonical_name,
            name_ms=food.canonical_name_ms,
            category=food.category,
            recipe_id=recipe.recipe_id,
            recipe_name=recipe.name,
            estimated_price_rm=prices.get(food_id),
        )
        for food_id, (_, food, recipe) in ordered
    ]


def recipe_unlock_suggestions(
    eligible_recipes, prices: dict[str, float] | None = None,
) -> list[UnlockSuggestion]:
    """Top main ingredients whose purchase would unlock the most dishes.

    Only computed for a basics-only pantry. Counts how many eligible active
    recipes list each food as a required main-role ingredient, ordered by
    count descending, then role priority (MAIN_PROTEIN < vegetables <
    STAPLE), then estimated price ascending (unpriced last), then food_id;
    capped at 8. Sample recipe names are alphabetical for determinism.
    """
    prices = prices or {}
    main_foods: dict[str, list] = {}
    for recipe, ingredient_rows, _ in eligible_recipes:
        main_food_ids = main_required_food_ids(ingredient_rows)
        for ingredient, food in ingredient_rows:
            if ingredient.required and ingredient.canonical_food_id in main_food_ids:
                entry = main_foods.setdefault(
                    ingredient.canonical_food_id, [food, [], None, 99]
                )
                entry[1].append(recipe.name)
                priority = _MAIN_ROLE_PRIORITY.get(_main_role_of(ingredient), 1)
                if priority < entry[3]:
                    entry[2] = _main_role_of(ingredient)
                    entry[3] = priority
    ordered = sorted(
        main_foods.items(),
        key=lambda item: (
            -len(item[1][1]),
            item[1][3],
            prices.get(item[0]) is None,
            prices.get(item[0]) or 0.0,
            item[0],
        ),
    )[:8]
    return [
        UnlockSuggestion(
            canonical_food_id=food_id,
            name=food.canonical_name,
            name_ms=food.canonical_name_ms,
            category=food.category,
            recipes_unlocked=len(recipe_names),
            sample_recipe_names=sorted(recipe_names)[:3],
            estimated_price_rm=prices.get(food_id),
            ingredient_role=role,
        )
        for food_id, (food, recipe_names, role, _priority) in ordered
    ]


def planned_unlock_summary(
    eligible_recipes, planned_food_ids,
) -> PlannedUnlockSummary | None:
    """Dishes a basics-only pantry's week plan already unlocks.

    Counts eligible recipes with at least one planned (unpurchased) food in
    their required main-role set. None when the plan has no such food.
    """
    planned = set(planned_food_ids or ())
    if not planned:
        return None
    dish_names: list[str] = []
    matched_food_ids: set[str] = set()
    for recipe, ingredient_rows, _ in eligible_recipes:
        matched = main_required_food_ids(ingredient_rows) & planned
        if matched:
            dish_names.append(recipe.name)
            matched_food_ids.update(matched)
    if not dish_names:
        return None
    return PlannedUnlockSummary(
        dishes_count=len(dish_names),
        sample_recipe_names=sorted(dish_names)[:3],
        planned_main_food_ids=sorted(matched_food_ids),
    )


@app.get(
    "/api/v1/households/{household_id}/recipe-suggestions",
    # The default response is the bare list (byte-identical for older
    # clients); ?advice=true opts into the wrapper carrying the basics_only
    # pantry-level advice that an empty list cannot carry.
    response_model=list[RecipeSuggestionResponse] | RecipeSuggestionsAdviceResponse,
)
async def list_recipe_suggestions(
    household_id: int,
    exclusions: list[str] | None = Query(default=None),
    use_semantic: bool = Query(default=False),
    gluten_free: bool = Query(default=False),
    custom_restriction: str = Query(default="", max_length=1024),
    planned_food_ids: list[str] | None = Query(default=None),
    advice: bool = Query(default=False),
    current_user: AppUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> list[RecipeSuggestionResponse] | RecipeSuggestionsAdviceResponse:
    # Browsing recipes is read-only. A first-time user may have no pantry yet,
    # but should still see the full catalogue with pantry matches ranked first.
    household = await find_owned_household(household_id, current_user, db)
    # Optional hard-exclusion codes (e.g. NO_PORK, SHELLFISH): recipes containing
    # an excluded food are omitted, mirroring the planner's CC1 pre-modelling
    # removal. Unknown/inactive codes are rejected with 422 by the resolver.
    # Q2 gluten/other choices have no database code, so their canonical-name
    # checks are applied to *all* ingredients below, including optional ones.
    excluded_food_ids = await _resolve_excluded_food_ids(db, exclusions or [])
    pantry_items = tuple(
        (
            await db.scalars(
                select(PantryItem).where(
                    PantryItem.household_id == household_id,
                    PantryItem.status == "AVAILABLE",
                )
            )
        ).all()
    )
    pantry_food_ids = {item.canonical_food_id for item in pantry_items}
    if pantry_food_ids & OIL_FOOD_IDS:
        pantry_food_ids.update(OIL_FOOD_IDS)
    measured_pantry_food_ids = frozenset(
        item.canonical_food_id for item in pantry_items
        if pantry_quantity_for_recipe(item).quantity_status == "KNOWN"
    )
    reuse_pantry_ids = await eligible_reuse_pantry_ids(
        db, pantry_food_ids, excluded_food_ids,
        gluten_free=gluten_free, custom_restriction=custom_restriction,
    )
    recipes = (
        await db.scalars(select(RecipeCatalog).where(RecipeCatalog.active.is_(True)).order_by(RecipeCatalog.name))
    ).all()
    # Epic 6 semantic recall: score every recipe by its strongest embedding
    # bridge between pantry foods and recipe ingredients (food_embedding table,
    # no runtime inference call). Relaxes the exact-match gate so recipes with
    # similar-but-not-identical ingredients still surface.
    ingredient_rows_by_recipe: dict[str, list] = {recipe.recipe_id: [] for recipe in recipes}
    if recipes:
        all_ingredients = await db.execute(
            select(RecipeCatalogIngredient, CanonicalFood)
            .join(CanonicalFood, CanonicalFood.canonical_food_id == RecipeCatalogIngredient.canonical_food_id)
            .where(RecipeCatalogIngredient.recipe_id.in_(ingredient_rows_by_recipe))
            .order_by(RecipeCatalogIngredient.recipe_id, RecipeCatalogIngredient.display_order)
        )
        for ingredient, food in all_ingredients.all():
            ingredient_rows_by_recipe[ingredient.recipe_id].append((ingredient, food))
    scores: dict[str, float] = {}
    if use_semantic:
        recipe_food_ids_by_recipe = {
            recipe_id: {ingredient.canonical_food_id for ingredient, _ in rows}
            for recipe_id, rows in ingredient_rows_by_recipe.items()
        }
        scores = await semantic_scores(db, pantry_food_ids, recipe_food_ids_by_recipe)

    eligible_recipes = []
    for recipe in recipes:
        ingredient_rows = ingredient_rows_by_recipe[recipe.recipe_id]
        recipe_food_ids = {ingredient.canonical_food_id for ingredient, _ in ingredient_rows}
        if recipe_food_ids & excluded_food_ids:
            continue
        if recipe_matches_name_restrictions(
            [food.canonical_name for _, food in ingredient_rows],
            gluten_free=gluten_free,
            custom_restriction=custom_restriction,
        ):
            continue
        reused = resolve_reused_ingredients(
            recipe.recipe_id,
            tuple(ingredient.canonical_food_id for ingredient, _ in ingredient_rows if ingredient.required),
            reuse_pantry_ids,
            measured_pantry_food_ids=measured_pantry_food_ids,
        )
        eligible_recipes.append((recipe, ingredient_rows, reused))

    reused_foods_by_id = await load_reused_recipe_foods(
        db,
        {match.pantry_food_id for _, _, reused in eligible_recipes for match in reused.values()},
    )
    entries = []
    for recipe, ingredient_rows, reused in eligible_recipes:
        quantity_summary = build_recipe_quantity_summary(
            recipe, ingredient_rows, household, pantry_items, reused,
        )
        suggestion = recipe_suggestion_response(
            recipe, ingredient_rows, pantry_food_ids, quantity_summary, reused,
            reused_foods_by_id,
        )
        suggestion.semantic_score = scores.get(recipe.recipe_id)
        entries.append((suggestion, ingredient_rows, quantity_summary))

    # Product rule: every eligible recipe is listed; ranking alone puts
    # pantry-matching dishes first (owned mains lead, then fewest missing).
    # pantry_state still reports basics_only when no recipe matched any main
    # ingredient, so clients can hint that the pantry has no cookable main.
    pantry_state = (
        "ok"
        if any((suggestion.main_match_count or 0) > 0 for suggestion, _, _ in entries)
        else "basics_only"
    )
    ranked = rank_recipe_suggestions(
        entries, pantry_food_ids=frozenset(pantry_food_ids),
        planned_food_ids=frozenset(planned_food_ids or ()),
    )
    # The basics-only advice layers ride both on the items and on the
    # ?advice=true wrapper.
    unlock_suggestions = None
    quick_win_suggestions = None
    planned_summary = None
    if pantry_state == "basics_only":
        main_food_ids = {
            food_id
            for _, ingredient_rows, _ in eligible_recipes
            for food_id in main_required_food_ids(ingredient_rows)
        }
        prices = await load_estimated_prices_rm(db, main_food_ids) if main_food_ids else {}
        unlock_suggestions = recipe_unlock_suggestions(eligible_recipes, prices)
        quick_win_suggestions = recipe_quick_win_suggestions(eligible_recipes, prices)
        planned_summary = planned_unlock_summary(eligible_recipes, planned_food_ids)
    for suggestion in ranked:
        suggestion.pantry_state = pantry_state
        suggestion.unlock_suggestions = unlock_suggestions
        suggestion.quick_win_suggestions = quick_win_suggestions
        suggestion.planned_unlock_summary = planned_summary
    if advice:
        # Opt-in wrapper: lift the same computed payloads to the top level.
        # The suggestions list always carries the full ranked set; in
        # basics_only the advice fields are populated alongside it.
        return RecipeSuggestionsAdviceResponse(
            suggestions=ranked,
            pantry_state=pantry_state,
            quick_win_suggestions=quick_win_suggestions,
            unlock_suggestions=unlock_suggestions,
            planned_unlock_summary=planned_summary,
        )
    return ranked


@app.get(
    "/api/v1/households/{household_id}/recipes/{recipe_id}",
    response_model=RecipeDetailResponse,
)
async def get_recipe_detail(
    household_id: int,
    recipe_id: str,
    exclusions: list[str] | None = Query(default=None),
    gluten_free: bool = Query(default=False),
    custom_restriction: str = Query(default="", max_length=1024),
    current_user: AppUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> RecipeDetailResponse:
    household = await find_owned_household(household_id, current_user, db)
    recipe = await db.get(RecipeCatalog, recipe_id)
    if recipe is None or not recipe.active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipe not found.")

    excluded_food_ids = await _resolve_excluded_food_ids(db, exclusions or [])
    ingredient_rows = await recipe_ingredient_rows(recipe.recipe_id, db)
    recipe_food_ids = {ingredient.canonical_food_id for ingredient, _ in ingredient_rows}
    if recipe_food_ids & excluded_food_ids:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recipe not found.",
        )
    if recipe_matches_name_restrictions(
        [food.canonical_name for _, food in ingredient_rows],
        gluten_free=gluten_free,
        custom_restriction=custom_restriction,
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipe not found.")
    pantry_items = tuple(
        (
            await db.scalars(
                select(PantryItem).where(
                    PantryItem.household_id == household_id,
                    PantryItem.status == "AVAILABLE",
                )
            )
        ).all()
    )
    pantry_food_ids = {item.canonical_food_id for item in pantry_items}
    if pantry_food_ids & OIL_FOOD_IDS:
        pantry_food_ids.update(OIL_FOOD_IDS)
    measured_pantry_food_ids = frozenset(
        item.canonical_food_id for item in pantry_items
        if pantry_quantity_for_recipe(item).quantity_status == "KNOWN"
    )
    reuse_pantry_ids = await eligible_reuse_pantry_ids(
        db, pantry_food_ids, excluded_food_ids,
        gluten_free=gluten_free, custom_restriction=custom_restriction,
    )
    reused = resolve_reused_ingredients(
        recipe.recipe_id,
        tuple(ingredient.canonical_food_id for ingredient, _ in ingredient_rows if ingredient.required),
        reuse_pantry_ids,
        measured_pantry_food_ids=measured_pantry_food_ids,
    )
    reused_foods_by_id = await load_reused_recipe_foods(
        db, {match.pantry_food_id for match in reused.values()},
    )
    quantity_summary = build_recipe_quantity_summary(
        recipe, ingredient_rows, household, pantry_items, reused,
    )
    suggestion = recipe_suggestion_response(
        recipe, ingredient_rows, pantry_food_ids, quantity_summary, reused,
        reused_foods_by_id,
    )
    quantity_by_food = {
        ingredient.canonical_food_id: ingredient for ingredient in quantity_summary.ingredients
    }
    required_quantity_status_by_food = {
        ingredient.canonical_food_id: ingredient.quantity_status
        for ingredient in quantity_summary.ingredients
        if ingredient.required
    }
    substitution_suggestions = suggest_recipe_substitutions(
        required_quantity_status_by_food=required_quantity_status_by_food,
        pantry_food_ids=pantry_food_ids | reused.keys(),
        excluded_food_ids=excluded_food_ids,
    )
    substitution_food_ids = {suggestion.substitute_food_id for suggestion in substitution_suggestions}
    substitute_foods = (
        await db.scalars(
            select(CanonicalFood).where(CanonicalFood.canonical_food_id.in_(substitution_food_ids))
        )
    ).all() if substitution_food_ids else []
    foods_by_id = {
        food.canonical_food_id: food for ingredient, food in ingredient_rows
    }
    foods_by_id.update({food.canonical_food_id: food for food in substitute_foods})
    cooking_steps = (
        await db.scalars(
            select(RecipeCookingStep.instruction)
            .where(RecipeCookingStep.recipe_id == recipe.recipe_id)
            .order_by(RecipeCookingStep.step_number)
        )
    ).all()

    return RecipeDetailResponse(
        **suggestion.model_dump(),
        ingredients=[
            recipe_detail_ingredient_response(
                ingredient, food, quantity_by_food[ingredient.canonical_food_id],
                reused, reused_foods_by_id,
            )
            for ingredient, food in ingredient_rows
        ],
        substitution_suggestions=[
            RecipeSubstitutionResponse(
                rule_id=substitution.rule_id,
                original_food=pantry_food_response(foods_by_id[substitution.original_food_id]),
                substitute_food=pantry_food_response(foods_by_id[substitution.substitute_food_id]),
                reason=substitution.reason,
            )
            for substitution in substitution_suggestions
        ],
        cooking_steps=list(cooking_steps),
    )


# --- Epic 6: receipt capture -----------------------------------------------

RECEIPT_IMAGE_MAX_BYTES = 8 * 1024 * 1024
RECEIPT_IMAGE_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}


def _dispatch_receipt_extraction(background_tasks: BackgroundTasks, receipt_id: uuid.UUID) -> None:
    """Worker-first dispatch; inline BackgroundTask fallback without a broker."""
    redis_url = settings.redis_url
    if redis_url:
        try:
            from celery import Celery

            Celery("wisebasket_dispatch", broker=redis_url).send_task(
                "scripts.receipt_tasks.extract_receipt_task", args=[str(receipt_id)]
            )
            return
        except Exception:
            # 2026-09-14 UAT: silent fallthrough hid a broker-publish failure
            # (receipt sat PENDING then the inline path timed out). Log it.
            import logging

            logging.getLogger("receipt_dispatch").exception(
                "celery dispatch failed; falling back to inline extraction"
            )
    background_tasks.add_task(run_receipt_extraction, str(receipt_id))


async def receipt_response(receipt: Receipt, db: AsyncSession) -> ReceiptResponse:
    if receipt.status in {"PENDING", "PROCESSING"}:
        deadline = receipt.processing_deadline_at or (
            receipt.created_at + timedelta(seconds=settings.receipt_processing_deadline_s)
        )
        if datetime.now(UTC) >= deadline:
            await db.execute(
                update(Receipt)
                .where(Receipt.receipt_id == receipt.receipt_id, Receipt.status.in_(("PENDING", "PROCESSING")))
                .values(status="FAILED", error="PROCESSING_DEADLINE_EXCEEDED", processed_at=datetime.now(UTC))
            )
            await db.commit()
            await db.refresh(receipt)
    lines = (
        await db.scalars(
            select(ReceiptLine)
            .where(ReceiptLine.receipt_id == receipt.receipt_id)
            .order_by(ReceiptLine.display_order)
        )
    ).all()
    proposed_food_ids = {line.canonical_food_id for line in lines if line.canonical_food_id}
    foods_by_id = {}
    if proposed_food_ids:
        foods = (
            await db.scalars(
                select(CanonicalFood).where(CanonicalFood.canonical_food_id.in_(proposed_food_ids))
            )
        ).all()
        foods_by_id = {food.canonical_food_id: food for food in foods}
    return ReceiptResponse(
        receipt_id=receipt.receipt_id,
        household_id=receipt.household_id,
        status=receipt.status,
        error=receipt.error,
        created_at=receipt.created_at,
        processed_at=receipt.processed_at,
        lines=[
            ReceiptLineResponse(
                line_id=line.line_id,
                client_line_id=line.client_line_id,
                display_order=line.display_order,
                name_raw=line.name_raw,
                expanded_name=line.expanded_name,
                qty=float(line.qty) if line.qty is not None else None,
                unit=line.unit,
                price_rm=float(line.price_rm) if line.price_rm is not None else None,
                proposed_food=(
                    pantry_food_response(foods_by_id[line.canonical_food_id])
                    if line.canonical_food_id in foods_by_id
                    else None
                ),
                match_score=line.match_score,
                candidates=[
                    ReceiptLineCandidate(canonical_food_id=c["canonical_food_id"], score=c["score"])
                    for c in (line.candidates or [])
                    if isinstance(c, dict) and "canonical_food_id" in c and "score" in c
                ],
                status=line.status,
                match_basis=line.match_basis,
            )
            for line in lines
        ],
        duplicate_of_receipt_id=receipt.duplicate_of_receipt_id,
    )


async def reuse_receipt_for_review(receipt: Receipt, user_id: uuid.UUID, db: AsyncSession) -> ReceiptResponse:
    """QA re-purchases get fresh line IDs, never a second effect on old IDs.

    Reuse the saved review values (which may include earlier corrections),
    not a promise of immutable raw OCR. Manual additions are not OCR cache.
    The caller holds the household lock, so an unconfirmed copy is reused by
    concurrent/retried uploads instead of creating multiple test purchases.
    """
    if not settings.receipt_allow_repeat_purchases or receipt.status != "DONE":
        return await receipt_response(receipt, db)
    lines = (await db.scalars(select(ReceiptLine).where(
        ReceiptLine.receipt_id == receipt.receipt_id,
    ).order_by(ReceiptLine.display_order, ReceiptLine.line_id))).all()
    has_effect = await db.scalar(select(ReceiptLineEffect.line_id).where(
        ReceiptLineEffect.receipt_id == receipt.receipt_id,
    ).limit(1))
    if not any(line.status == "CONFIRMED" for line in lines) and has_effect is None:
        return await receipt_response(receipt, db)
    cached = Receipt(
        household_id=receipt.household_id, uploaded_by=user_id,
        image_sha256=receipt.image_sha256, image_bytes=None,
        image_expires_at=datetime.now(UTC), status="DONE",
        processed_at=receipt.processed_at, merchant=receipt.merchant,
        transaction_at=receipt.transaction_at, receipt_number=receipt.receipt_number,
        total_rm=receipt.total_rm,
    )
    db.add(cached)
    await db.flush()
    for line in lines:
        if line.client_line_id is not None:
            continue
        db.add(ReceiptLine(
            receipt_id=cached.receipt_id, display_order=line.display_order,
            name_raw=line.name_raw, expanded_name=line.expanded_name,
            qty=line.qty, unit=line.unit, price_rm=line.price_rm,
            canonical_food_id=line.canonical_food_id, match_score=line.match_score,
            candidates=line.candidates, match_basis=line.match_basis, status="PROPOSED",
        ))
    await db.commit()
    return await receipt_response(cached, db)


@app.post(
    "/api/v1/households/{household_id}/receipts",
    response_model=ReceiptResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_receipt(
    household_id: int,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: AppUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> ReceiptResponse:
    household = await find_owned_household(household_id, current_user, db, for_update=True)
    content_type = (file.content_type or "").lower()
    if content_type not in RECEIPT_IMAGE_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported image type {content_type!r}; use JPEG, PNG or WebP.",
        )
    image_bytes = await file.read()
    if not image_bytes or len(image_bytes) > RECEIPT_IMAGE_MAX_BYTES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Receipt image must be non-empty and at most 8 MB.",
        )
    image_sha256 = hashlib.sha256(image_bytes).hexdigest()
    reusable_statuses = (
        ("PENDING", "PROCESSING")
        if settings.receipt_reprocess_done_uploads
        else ("PENDING", "PROCESSING", "DONE")
    )
    reuse_order = (
        (Receipt.status.in_(("PENDING", "PROCESSING")).desc(),
         Receipt.created_at.desc(), Receipt.receipt_id.desc())
        if settings.receipt_allow_repeat_purchases
        else (Receipt.created_at, Receipt.receipt_id)
    )
    existing = await db.scalar(
        select(Receipt).where(
            Receipt.household_id == household.id,
            Receipt.image_sha256 == image_sha256,
            Receipt.status.in_(reusable_statuses),
        ).order_by(*reuse_order)
    )
    # QA reuses active work first, otherwise the latest saved result, and can
    # start another purchase from it without another extraction or quota slot.
    # Production retains its original canonical-receipt ordering.
    if existing is not None:
        return await reuse_receipt_for_review(existing, current_user.user_id, db)
    local_day = datetime.now(ZoneInfo("Asia/Kuala_Lumpur")).date()
    quota = await db.get(ReceiptUploadDay, (household.id, local_day))
    if quota is None:
        quota = ReceiptUploadDay(household_id=household.id, local_day=local_day, image_count=0)
        db.add(quota)
    if quota.image_count >= min(settings.receipt_uploads_per_day, 10):
        raise HTTPException(status_code=429, detail="Daily receipt upload limit reached.")
    quota.image_count += 1
    receipt = Receipt(
        household_id=household.id,
        uploaded_by=current_user.user_id,
        image_bytes=image_bytes,
        image_sha256=image_sha256,
        image_expires_at=datetime.now(UTC) + timedelta(hours=24),
        status="PENDING",
    )
    db.add(receipt)
    try:
        await db.commit()
    except IntegrityError:
        # Concurrent identical uploads can both pass the read above. The
        # database constraint is authoritative; reuse the winning receipt.
        await db.rollback()
        existing = await db.scalar(
            select(Receipt).where(
                Receipt.household_id == household.id,
                Receipt.image_sha256 == image_sha256,
                Receipt.status.in_(reusable_statuses),
            ).order_by(Receipt.created_at, Receipt.receipt_id)
        )
        if existing is None:
            raise
        return await receipt_response(existing, db)
    await db.refresh(receipt)
    _dispatch_receipt_extraction(background_tasks, receipt.receipt_id)
    return await receipt_response(receipt, db)


async def find_owned_receipt(household_id: int, receipt_id: uuid.UUID, db: AsyncSession) -> Receipt:
    receipt = await db.scalar(
        select(Receipt).where(Receipt.receipt_id == receipt_id, Receipt.household_id == household_id)
    )
    if receipt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Receipt not found.")
    return receipt


def receipt_logical_fingerprint(receipt: Receipt) -> str | None:
    """Conservative identity: never infer a duplicate from date/amount alone."""
    merchant = " ".join((receipt.merchant or "").casefold().split())
    number = " ".join((receipt.receipt_number or "").casefold().split())
    if not merchant or not number or receipt.transaction_at is None or receipt.total_rm is None:
        return None
    total = Decimal(str(receipt.total_rm))
    if not total.is_finite() or total < 0:
        return None
    transaction_at = receipt.transaction_at
    if transaction_at.tzinfo is None:
        transaction_at = transaction_at.replace(tzinfo=ZoneInfo("Asia/Kuala_Lumpur"))
    identity = [
        merchant,
        transaction_at.astimezone(UTC).isoformat(timespec="seconds"),
        number,
        str(total.quantize(Decimal("0.01"))),
    ]
    return hashlib.sha256(json.dumps(identity, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


async def claim_logical_receipt(receipt: Receipt, db: AsyncSession) -> None:
    fingerprint = receipt_logical_fingerprint(receipt)
    if fingerprint is None:
        return
    receipt.logical_fingerprint = fingerprint
    await db.execute(
        pg_insert(ReceiptLogicalPurchase)
        .values(
            purchase_id=uuid.uuid4(), household_id=receipt.household_id,
            fingerprint=fingerprint, canonical_receipt_id=receipt.receipt_id,
        )
        .on_conflict_do_nothing(constraint="uq_receipt_logical_purchase")
    )
    canonical_id = await db.scalar(
        select(ReceiptLogicalPurchase.canonical_receipt_id).where(
            ReceiptLogicalPurchase.household_id == receipt.household_id,
            ReceiptLogicalPurchase.fingerprint == fingerprint,
        )
    )
    if canonical_id != receipt.receipt_id:
        receipt.duplicate_of_receipt_id = canonical_id
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "DUPLICATE_RECEIPT", "canonical_receipt_id": str(canonical_id)},
        )


async def reject_confirmed_image_replay(receipt: Receipt, db: AsyncSession) -> None:
    """Fresh QA analysis must not apply the same image's stock twice.

    Called under the household lock, before any confirmation writes. The
    image hash remains usable when private OCR could not identify a receipt;
    confirmed legacy lines also count even when no effect ledger was recorded.
    """
    confirmed_line = select(ReceiptLine.line_id).where(
        ReceiptLine.receipt_id == Receipt.receipt_id,
        ReceiptLine.status == "CONFIRMED",
        ReceiptLine.canonical_food_id.is_not(None),
    ).exists()
    applied_effect = select(ReceiptLineEffect.line_id).where(
        ReceiptLineEffect.receipt_id == Receipt.receipt_id,
    ).exists()
    original_id = await db.scalar(
        select(Receipt.receipt_id).where(
            Receipt.household_id == receipt.household_id,
            Receipt.image_sha256 == receipt.image_sha256,
            Receipt.receipt_id != receipt.receipt_id,
            confirmed_line | applied_effect,
        ).order_by(Receipt.created_at, Receipt.receipt_id).limit(1)
    )
    if original_id is not None:
        raise HTTPException(status_code=409, detail={
            "code": "DUPLICATE_RECEIPT", "canonical_receipt_id": str(original_id),
        })


async def save_confirmed_receipt_alias(
    receipt_line: ReceiptLine,
    canonical_food_id: str,
    db: AsyncSession,
) -> None:
    """Learn an OCR label only after a user explicitly confirms its food.

    The label is stored as data in ``food_alias`` rather than as a retailer- or
    product-specific condition in Python. ``und`` means the language is
    undetermined: receipt labels can be English, Malay, or a mixture of both.
    A later explicit confirmation may correct an earlier mapping for the same
    receipt label.
    """
    alias_name = receipt_line.name_raw.strip()[:240]
    if not alias_name:
        return
    language = "und"
    source_system = "RECEIPT_CONFIRMATION"
    food_alias = await db.scalar(
        select(FoodAlias).where(
            FoodAlias.alias_name == alias_name,
            FoodAlias.language == language,
            FoodAlias.source_system == source_system,
        )
    )
    if food_alias is None:
        db.add(
            FoodAlias(
                canonical_food_id=canonical_food_id,
                alias_name=alias_name,
                language=language,
                source_system=source_system,
            )
        )
        return
    food_alias.canonical_food_id = canonical_food_id


@app.get(
    "/api/v1/households/{household_id}/receipts/{receipt_id}",
    response_model=ReceiptResponse,
)
async def get_receipt(
    household_id: int,
    receipt_id: uuid.UUID,
    current_user: AppUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> ReceiptResponse:
    await find_owned_household(household_id, current_user, db)
    receipt = await find_owned_receipt(household_id, receipt_id, db)
    return await receipt_response(receipt, db)


@app.post(
    "/api/v1/households/{household_id}/receipts/{receipt_id}/confirm",
    response_model=ReceiptResponse,
)
async def confirm_receipt(
    household_id: int,
    receipt_id: uuid.UUID,
    request: ReceiptConfirmRequest,
    current_user: AppUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> ReceiptResponse:
    """Apply each accepted line to pantry exactly once under a household lock."""
    household = await find_owned_household(household_id, current_user, db, for_update=True)
    receipt = await db.scalar(
        select(Receipt).where(
            Receipt.receipt_id == receipt_id, Receipt.household_id == household_id
        ).with_for_update()
    )
    if receipt is None:
        raise HTTPException(status_code=404, detail="Receipt not found.")
    if receipt.status != "DONE":
        raise HTTPException(status_code=409, detail="Only a completed receipt can be confirmed.")
    if not settings.receipt_allow_repeat_purchases and receipt.duplicate_of_receipt_id is not None:
        raise HTTPException(status_code=409, detail={
            "code": "DUPLICATE_RECEIPT",
            "canonical_receipt_id": str(receipt.duplicate_of_receipt_id),
        })
    if not settings.receipt_allow_repeat_purchases:
        await reject_confirmed_image_replay(receipt, db)
        await claim_logical_receipt(receipt, db)
    else:
        # QA-only historical duplicate flags must not keep blocking review.
        # Keep the per-line effect ledger below: double-clicks/retries on this
        # receipt are still idempotent, even when repeat purchases are enabled.
        receipt.duplicate_of_receipt_id = None
    line_ids = [line.line_id for line in request.lines]
    rows = (
        await db.scalars(
            select(ReceiptLine)
            .where(ReceiptLine.receipt_id == receipt.receipt_id, ReceiptLine.line_id.in_(line_ids))
            .order_by(ReceiptLine.line_id)
            .with_for_update()
        )
    ).all() if line_ids else []
    lines_by_id = {line.line_id: line for line in rows}
    for requested in request.lines:
        line = lines_by_id.get(requested.line_id)
        if line is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Receipt line not found.")
        effect = await db.get(ReceiptLineEffect, line.line_id)
        if effect is not None and requested.canonical_food_id != effect.canonical_food_id:
            raise HTTPException(status_code=409, detail="Confirmed food cannot be changed without a stock adjustment.")
        if line.status == "CONFIRMED" and effect is None:
            # Pre-ledger historical row: never add its stock a second time.
            if requested.canonical_food_id != line.canonical_food_id:
                raise HTTPException(status_code=409, detail="Confirmed food cannot be changed without a stock adjustment.")
            db.add(ReceiptLineEffect(
                line_id=line.line_id, receipt_id=receipt.receipt_id, household_id=household_id,
                canonical_food_id=line.canonical_food_id,
                source_qty=line.qty, source_unit=line.unit,
            ))
            effect = True
        if effect is not None and "qty" in requested.model_fields_set:
            source_qty = effect.source_qty if isinstance(effect, ReceiptLineEffect) else line.qty
            source_unit = effect.source_unit if isinstance(effect, ReceiptLineEffect) else line.unit
            try:
                source_qty, source_unit = normalize_quantity_unit(source_qty, source_unit)
            except ValueError:
                # Historical OCR units can be opaque; do not guess a stock
                # adjustment from them during a receipt price correction.
                raise HTTPException(status_code=409, detail="Confirmed quantity requires a stock adjustment.")
            requested_qty = Decimal(str(requested.qty)) if requested.qty is not None else None
            if (requested_qty, requested.unit) != (source_qty, source_unit):
                raise HTTPException(status_code=409, detail="Confirmed quantity requires a stock adjustment.")
        if requested.price_rm is not None:
            line.price_rm = Decimal(str(requested.price_rm))
        if effect is None and "qty" in requested.model_fields_set:
            line.qty = Decimal(str(requested.qty)) if requested.qty is not None else None
            line.unit = requested.unit
        if effect is not None:
            # Display/spending corrections do not silently alter applied stock.
            continue
        if requested.canonical_food_id is None:
            line.status = "SKIPPED"
            continue
        if line.qty is None or line.unit is None:
            raise HTTPException(
                status_code=422,
                detail="Enter a positive quantity and unit before confirming this food.",
            )
        food = await db.scalar(
            select(CanonicalFood).where(
                CanonicalFood.canonical_food_id == requested.canonical_food_id,
                CanonicalFood.status == "ACTIVE",
            )
        )
        if food is None:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Active food not found.")
        line.canonical_food_id = food.canonical_food_id
        pantry_item = await upsert_pantry_stock(
            db, household_id, food.canonical_food_id, line.qty, line.unit, "RECEIPT"
        )
        await db.flush()
        db.add(ReceiptLineEffect(
            line_id=line.line_id, receipt_id=receipt.receipt_id, household_id=household_id,
            canonical_food_id=food.canonical_food_id, pantry_item_id=pantry_item.pantry_item_id,
            source_qty=line.qty, source_unit=line.unit,
        ))
        await record_receipt_alias_vote(db, receipt, line, food.canonical_food_id)
        line.status = "CONFIRMED"
    if request.added_lines:
        all_lines = (
            await db.scalars(
                select(ReceiptLine).where(ReceiptLine.receipt_id == receipt.receipt_id)
                .order_by(ReceiptLine.line_id).with_for_update()
            )
        ).all()
        max_display_order = max((line.display_order for line in all_lines), default=0)
        existing_added = {line.client_line_id: line for line in all_lines if line.client_line_id}
        # Older clients omit client_line_id. Their previous fallback hashed the
        # *whole* request, so a price edit became a different purchase. Keep a
        # stable per-receipt ordinal for new legacy calls and also recognise
        # already-persisted UUIDv5 fallback rows from the former algorithm.
        # Current mobile clients send UUIDv4 IDs and are never matched by this
        # compatibility path. An ambiguous reordered legacy request fails
        # explicitly rather than silently adding stock a second time.
        legacy_rows = sorted(
            (line for line in all_lines if line.client_line_id is not None
             and line.client_line_id.version == 5 and line.match_score is None
             and line.line_id not in line_ids),
            key=lambda line: (line.display_order, line.line_id),
        )
        legacy_slot = 0
        legacy_row_cursor = 0
        matched_legacy_ids: set[uuid.UUID] = set()
        for added in request.added_lines:
            if added.client_line_id is None:
                while True:
                    client_id = uuid.uuid5(
                        uuid.NAMESPACE_URL, f"wisebasket:{receipt.receipt_id}:legacy-slot:{legacy_slot}"
                    )
                    legacy_slot += 1
                    old_line = existing_added.get(client_id)
                    # A persisted row included in `lines` is being reviewed,
                    # not replayed as a newly added purchase. Reserve its slot
                    # and move on, or this new item would be silently swallowed.
                    if old_line is None or old_line.line_id not in line_ids:
                        break
                if old_line is None:
                    while (legacy_row_cursor < len(legacy_rows)
                           and legacy_rows[legacy_row_cursor].client_line_id in matched_legacy_ids):
                        legacy_row_cursor += 1
                    if legacy_row_cursor < len(legacy_rows):
                        old_line = legacy_rows[legacy_row_cursor]
                        legacy_row_cursor += 1
                if old_line is not None:
                    if old_line.client_line_id in matched_legacy_ids:
                        raise HTTPException(status_code=409, detail="Ambiguous legacy manual line; update the app and retry.")
                    matched_legacy_ids.add(old_line.client_line_id)
            else:
                client_id = added.client_line_id
                old_line = existing_added.get(client_id)
            if old_line is not None:
                if old_line.canonical_food_id != added.canonical_food_id:
                    raise HTTPException(status_code=409, detail="Manual line ID already belongs to another food.")
                # Quantity changes need a separate stock adjustment; a receipt
                # replay must never silently rewrite only the visible quantity.
                if "qty" in added.model_fields_set and (
                    old_line.qty != (Decimal(str(added.qty)) if added.qty is not None else None)
                    or old_line.unit != added.unit
                ):
                    raise HTTPException(status_code=409, detail="Confirmed quantity requires a stock adjustment.")
                if "price_rm" in added.model_fields_set:
                    old_line.price_rm = Decimal(str(added.price_rm)) if added.price_rm is not None else None
                continue
            if added.qty is None or added.unit is None:
                raise HTTPException(
                    status_code=422,
                    detail="Enter a positive quantity and unit before confirming this food.",
                )
            food = await db.scalar(
                select(CanonicalFood).where(
                    CanonicalFood.canonical_food_id == added.canonical_food_id,
                    CanonicalFood.status == "ACTIVE",
                )
            )
            if food is None:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Active food not found.")
            name_raw = (added.name_raw or food.canonical_name or food.canonical_food_id)[:240]
            max_display_order += 1
            new_line = ReceiptLine(
                receipt_id=receipt.receipt_id, display_order=max_display_order,
                name_raw=name_raw, client_line_id=client_id,
                qty=Decimal(str(added.qty)) if added.qty is not None else None,
                unit=added.unit,
                price_rm=Decimal(str(added.price_rm)) if added.price_rm is not None else None,
                canonical_food_id=food.canonical_food_id,
                match_score=None, status="CONFIRMED",
            )
            db.add(new_line)
            pantry_item = await upsert_pantry_stock(
                db,
                household_id,
                food.canonical_food_id,
                Decimal(str(added.qty)) if added.qty is not None else None,
                added.unit,
                "RECEIPT",
            )
            await db.flush()
            db.add(ReceiptLineEffect(
                line_id=new_line.line_id, receipt_id=receipt.receipt_id,
                household_id=household_id, canonical_food_id=food.canonical_food_id,
                pantry_item_id=pantry_item.pantry_item_id,
                source_qty=new_line.qty, source_unit=new_line.unit,
            ))
            existing_added[client_id] = new_line
    # A changed pantry must be confirmed again before recipes are requested.
    household.pantry_confirmed_at = None
    await db.commit()
    receipt = await find_owned_receipt(household_id, receipt_id, db)
    return await receipt_response(receipt, db)


@app.get(
    "/api/v1/households/{household_id}/spending-summary",
    response_model=SpendingSummaryResponse,
)
async def spending_summary(
    household_id: int,
    current_user: AppUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> SpendingSummaryResponse:
    """Actual grocery spending vs the current weekly plan (AC 6.3 / AC 6.4).

    weekly_budget_rm / estimated_cost_rm come from the household's LATEST
    planning request + generated plan (null when no plan exists yet).
    actual_spend_rm is the sum of every CONFIRMED receipt line price, i.e.
    the total the household has recorded as actually spent.
    """
    await find_owned_household(household_id, current_user, db)
    latest_request = await db.scalar(
        select(PlanningRequest)
        .where(PlanningRequest.household_id == household_id)
        .order_by(PlanningRequest.created_at.desc())
    )
    weekly_budget_rm = float(latest_request.available_budget_rm) if latest_request else None
    estimated_cost_rm = None
    if latest_request is not None:
        latest_plan = await db.scalar(
            select(GeneratedPlan)
            .where(GeneratedPlan.planning_request_id == latest_request.planning_request_id)
            .order_by(GeneratedPlan.created_at.desc())
        )
        if latest_plan is not None:
            estimated_cost_rm = float(latest_plan.estimated_total_cost_rm)
    actual_spend_rm, last_confirmed_at = (
        await db.execute(
            select(
                func.coalesce(func.sum(ReceiptLine.price_rm), 0),
                func.max(Receipt.created_at),
            )
            .select_from(ReceiptLine)
            .join(Receipt, Receipt.receipt_id == ReceiptLine.receipt_id)
            .where(
                Receipt.household_id == household_id,
                ReceiptLine.status == "CONFIRMED",
                ReceiptLine.price_rm.isnot(None),
            )
        )
    ).one()
    confirmed_receipt_count = await db.scalar(
        select(func.count(func.distinct(Receipt.receipt_id)))
        .select_from(ReceiptLine)
        .join(Receipt, Receipt.receipt_id == ReceiptLine.receipt_id)
        .where(Receipt.household_id == household_id, ReceiptLine.status == "CONFIRMED")
    ) or 0
    actual_spend = Decimal(actual_spend_rm or 0)
    remaining_budget_rm = None
    amount_above_budget_rm = None
    budget_status = "NO_BUDGET"
    if weekly_budget_rm is not None:
        budget_difference = Decimal(str(weekly_budget_rm)) - actual_spend
        remaining_budget_rm = float(max(budget_difference, Decimal("0")))
        if budget_difference < 0:
            amount_above_budget_rm = float(abs(budget_difference))
            budget_status = "OVER_BUDGET"
        else:
            budget_status = "WITHIN_BUDGET"

    estimated_vs_actual_difference_rm = None
    if estimated_cost_rm is not None:
        estimated_vs_actual_difference_rm = float(
            actual_spend - Decimal(str(estimated_cost_rm))
        )
    return SpendingSummaryResponse(
        household_id=household_id,
        weekly_budget_rm=weekly_budget_rm,
        estimated_cost_rm=estimated_cost_rm,
        actual_spend_rm=float(actual_spend),
        confirmed_receipt_count=confirmed_receipt_count,
        last_confirmed_at=last_confirmed_at,
        remaining_budget_rm=remaining_budget_rm,
        amount_above_budget_rm=amount_above_budget_rm,
        estimated_vs_actual_difference_rm=estimated_vs_actual_difference_rm,
        budget_status=budget_status,
    )


@app.get("/api/v1/admin/dashboard", response_model=AdminSummaryResponse)
async def admin_dashboard(_: AppUser = Depends(require_admin), db: AsyncSession = Depends(get_db_session)):
    async def count(model):
        result = await db.execute(select(func.count()).select_from(model))
        return int(result.scalar_one())

    async def scalar_count(statement):
        result = await db.execute(statement)
        return int(result.scalar_one())

    latest_etl = (
        await db.execute(select(EtlRun).order_by(EtlRun.started_at.desc()).limit(1))
    ).scalar_one_or_none()
    pending = await db.execute(
        select(func.count()).select_from(SourceFoodMapping).where(SourceFoodMapping.review_status == "PENDING")
    )
    eligible = await scalar_count(text("select count(distinct canonical_food_id) from v_optimizer_food_candidate"))
    canonical_total = await count(CanonicalFood)
    active_canonical = await scalar_count(
        select(func.count()).select_from(CanonicalFood).where(CanonicalFood.status == "ACTIVE")
    )
    block_issues = await scalar_count(
        select(func.count()).select_from(DataQualityIssue).where(DataQualityIssue.severity == "BLOCK")
    )
    active_locations = await scalar_count(
        select(func.count()).select_from(Location).where(Location.active.is_(True))
    )
    return AdminSummaryResponse(
        canonical_foods=canonical_total,
        active_canonical_foods=active_canonical,
        optimizer_eligible_foods=eligible,
        optimizer_ineligible_foods=max(canonical_total - eligible, 0),
        price_observations=await count(FoodPriceObservation),
        locations=await count(Location),
        active_locations=active_locations,
        pending_mappings=int(pending.scalar_one()),
        block_data_quality_issues=block_issues,
        generated_plans=await count(GeneratedPlan),
        latest_etl_run_at=latest_etl.started_at if latest_etl else None,
        latest_etl_status=latest_etl.status if latest_etl else None,
    )


def _serialize_mapping(row) -> dict[str, Any]:
    return jsonable_encoder(dict(row._mapping))


def _serialize_model(row) -> dict[str, Any]:
    data = row.__dict__.copy()
    data.pop("_sa_instance_state", None)
    return jsonable_encoder(data)


async def _admin_list(model, limit: int, offset: int, db: AsyncSession):
    result = await db.execute(select(model).limit(min(max(limit, 1), 500)).offset(max(offset, 0)))
    return [_serialize_model(row) for row in result.scalars().all()]


@app.get("/api/v1/admin/optimizer-eligibility")
async def admin_optimizer_eligibility(
    eligible: bool | None = None,
    canonical_food_id: str | None = None,
    category: str | None = None,
    reason: str | None = None,
    search: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _: AppUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
):
    return await list_optimizer_eligibility(
        db,
        eligible=eligible,
        canonical_food_id=canonical_food_id,
        category=category,
        reason=reason,
        search=search,
        limit=limit,
        offset=offset,
    )


@app.get("/api/v1/admin/optimizer-eligibility/{canonical_food_id}")
async def admin_optimizer_eligibility_detail(
    canonical_food_id: str,
    _: AppUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
):
    diagnostic = await get_optimizer_eligibility(db, canonical_food_id)
    if diagnostic is None:
        raise HTTPException(status_code=404, detail="Canonical food not found.")
    return diagnostic


@app.get("/api/v1/admin/canonical-foods")
async def admin_canonical_foods(
    search: str | None = None,
    category: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _: AppUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
):
    filters = []
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    if search:
        filters.append("(cf.canonical_food_id ilike :search or cf.canonical_name ilike :search or cf.canonical_name_ms ilike :search)")
        params["search"] = f"%{search.strip()}%"
    if category:
        filters.append("lower(cf.category) = lower(:category)")
        params["category"] = category.strip()
    if status_filter:
        filters.append("cf.status = :status")
        params["status"] = status_filter.strip().upper()
    where_clause = f"where {' and '.join(filters)}" if filters else ""
    rows = await db.execute(
        text(
            f"""
            select cf.canonical_food_id,
                   cf.canonical_name,
                   cf.canonical_name_ms,
                   cf.category,
                   cf.status,
                   cf.created_at,
                   fa.object_key as image_object_key,
                   (voc.canonical_food_id is not null) as optimizer_eligible,
                   exists (
                       select 1 from food_nutrition fn
                       where fn.canonical_food_id = cf.canonical_food_id
                         and fn.is_current = true
                         and fn.quality_status in ('PASS', 'WARN')
                   ) as nutrition_available,
                   exists (
                       select 1 from v_latest_food_price lfp
                       where lfp.canonical_food_id = cf.canonical_food_id
                   ) as latest_price_available
            from canonical_food cf
            left join (select distinct canonical_food_id from v_optimizer_food_candidate) voc
                   on voc.canonical_food_id = cf.canonical_food_id
            left join food_asset fa
                   on fa.canonical_food_id = cf.canonical_food_id
                  and fa.is_primary = true
                  and fa.asset_type in ('IMAGE', 'THUMBNAIL')
            {where_clause}
            order by cf.category, cf.canonical_name
            limit :limit offset :offset
            """
        ),
        params,
    )
    return [_serialize_mapping(row) for row in rows.all()]


@app.get("/api/v1/admin/foods")
async def admin_foods(
    search: str | None = None,
    category: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _: AppUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
):
    return await admin_canonical_foods(search, category, status_filter, limit, offset, _, db)


@app.get("/api/v1/admin/food-nutrition")
async def admin_food_nutrition(
    canonical_food_id: str | None = None,
    quality_status: str | None = None,
    current: bool | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _: AppUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
):
    statement = (
        select(FoodNutrition, CanonicalFood.canonical_name)
        .join(CanonicalFood, CanonicalFood.canonical_food_id == FoodNutrition.canonical_food_id)
    )
    if canonical_food_id:
        statement = statement.where(FoodNutrition.canonical_food_id == canonical_food_id.strip())
    if quality_status:
        statement = statement.where(FoodNutrition.quality_status == quality_status.strip().upper())
    if current is not None:
        statement = statement.where(FoodNutrition.is_current.is_(current))
    statement = statement.order_by(CanonicalFood.canonical_name).limit(limit).offset(offset)
    result = await db.execute(statement)
    rows = []
    for nutrition, canonical_name in result.all():
        row = _serialize_model(nutrition)
        row["canonical_name"] = canonical_name
        rows.append(row)
    return rows


@app.get("/api/v1/admin/price-observations")
async def admin_price_observations(
    canonical_food_id: str | None = None,
    location_id: int | None = None,
    quality_status: str | None = None,
    observed_date: str | None = None,
    source_dataset_version: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _: AppUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
):
    statement = (
        select(FoodPriceObservation, CanonicalFood.canonical_name, Location.location_name)
        .outerjoin(CanonicalFood, CanonicalFood.canonical_food_id == FoodPriceObservation.canonical_food_id)
        .join(Location, Location.location_id == FoodPriceObservation.location_id)
    )
    if canonical_food_id:
        statement = statement.where(FoodPriceObservation.canonical_food_id == canonical_food_id.strip())
    if location_id is not None:
        statement = statement.where(FoodPriceObservation.location_id == location_id)
    if quality_status:
        statement = statement.where(FoodPriceObservation.quality_status == quality_status.strip().upper())
    if observed_date:
        statement = statement.where(FoodPriceObservation.observed_date == observed_date)
    if source_dataset_version:
        statement = statement.where(FoodPriceObservation.source_dataset_version == source_dataset_version.strip())
    statement = statement.order_by(FoodPriceObservation.observed_date.desc()).limit(limit).offset(offset)
    result = await db.execute(statement)
    rows = []
    for price, canonical_name, location_name in result.all():
        row = _serialize_model(price)
        row["canonical_name"] = canonical_name
        row["location_name"] = location_name
        rows.append(row)
    return rows


@app.get("/api/v1/admin/source-mappings")
async def admin_source_mappings(
    source_system: str | None = None,
    review_status: str | None = None,
    search: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _: AppUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
):
    statement = (
        select(SourceFoodMapping, CanonicalFood.canonical_name, AppUser.email.label("reviewed_by_email"))
        .outerjoin(CanonicalFood, CanonicalFood.canonical_food_id == SourceFoodMapping.canonical_food_id)
        .outerjoin(AppUser, AppUser.user_id == SourceFoodMapping.reviewed_by)
    )
    if source_system:
        statement = statement.where(SourceFoodMapping.source_system == source_system.strip())
    if review_status:
        statement = statement.where(SourceFoodMapping.review_status == review_status.strip().upper())
    if search:
        pattern = f"%{search.strip()}%"
        statement = statement.where(
            SourceFoodMapping.source_food_name.ilike(pattern)
            | SourceFoodMapping.source_food_id.ilike(pattern)
            | CanonicalFood.canonical_name.ilike(pattern)
        )
    statement = statement.order_by(SourceFoodMapping.review_status, SourceFoodMapping.source_food_name).limit(limit).offset(offset)
    result = await db.execute(statement)
    rows = []
    for mapping, canonical_name, reviewed_by_email in result.all():
        row = _serialize_model(mapping)
        row["canonical_name"] = canonical_name
        row["reviewed_by_email"] = reviewed_by_email
        rows.append(row)
    return rows


@app.get("/api/v1/admin/locations")
async def admin_locations(
    search: str | None = None,
    state: str | None = None,
    district: str | None = None,
    active: bool | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _: AppUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
):
    statement = (
        select(Location, func.count(FoodPriceObservation.price_observation_id).label("usable_price_observations"))
        .outerjoin(
            FoodPriceObservation,
            (FoodPriceObservation.location_id == Location.location_id)
            & (FoodPriceObservation.quality_status == "PASS")
            & FoodPriceObservation.price_rm_per_100g_edible.is_not(None),
        )
        .group_by(Location.location_id)
    )
    if search:
        pattern = f"%{search.strip()}%"
        statement = statement.where(Location.location_name.ilike(pattern) | Location.source_premise_code.ilike(pattern))
    if state:
        statement = statement.where(func.lower(Location.state) == state.strip().lower())
    if district:
        statement = statement.where(func.lower(Location.district) == district.strip().lower())
    if active is not None:
        statement = statement.where(Location.active.is_(active))
    statement = statement.order_by(Location.state, Location.district, Location.location_name).limit(limit).offset(offset)
    result = await db.execute(statement)
    rows = []
    for location, usable_count in result.all():
        row = _serialize_model(location)
        row["usable_price_observations"] = int(usable_count)
        rows.append(row)
    return rows


@app.get("/api/v1/admin/unit-conversions")
async def admin_unit_conversions(limit: int = 100, offset: int = 0, _: AppUser = Depends(require_admin), db: AsyncSession = Depends(get_db_session)):
    return await _admin_list(UnitConversion, limit, offset, db)


@app.get("/api/v1/admin/etl-runs")
async def admin_etl_runs(limit: int = 100, offset: int = 0, _: AppUser = Depends(require_admin), db: AsyncSession = Depends(get_db_session)):
    result = await db.execute(select(EtlRun).order_by(EtlRun.started_at.desc()).limit(min(limit, 500)).offset(offset))
    return [_serialize_model(row) for row in result.scalars().all()]


@app.get("/api/v1/admin/data-quality-issues")
async def admin_data_quality_issues(
    severity: str | None = None,
    source: str | None = None,
    rule: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _: AppUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
):
    statement = (
        select(DataQualityIssue, CanonicalFood.canonical_name, EtlRun.source_system)
        .outerjoin(CanonicalFood, CanonicalFood.canonical_food_id == DataQualityIssue.canonical_food_id)
        .outerjoin(EtlRun, EtlRun.etl_run_id == DataQualityIssue.etl_run_id)
    )
    if severity:
        statement = statement.where(DataQualityIssue.severity == severity.strip().upper())
    if source:
        statement = statement.where(EtlRun.source_system == source.strip())
    if rule:
        statement = statement.where(DataQualityIssue.rule_code == rule.strip())
    statement = statement.order_by(DataQualityIssue.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(statement)
    rows = []
    for issue, canonical_name, source_system in result.all():
        row = _serialize_model(issue)
        row["canonical_name"] = canonical_name
        row["source_system"] = source_system
        rows.append(row)
    return rows


@app.get("/api/v1/admin/generated-plans")
async def admin_generated_plans(limit: int = 100, offset: int = 0, _: AppUser = Depends(require_admin), db: AsyncSession = Depends(get_db_session)):
    result = await db.execute(
        select(
            GeneratedPlan,
            PlanningRequest.available_budget_rm,
            Household.id.label("household_id"),
            Household.name.label("household_name"),
            Location.location_name.label("selected_store_name"),
        )
        .join(PlanningRequest, PlanningRequest.planning_request_id == GeneratedPlan.planning_request_id)
        .join(Household, Household.id == PlanningRequest.household_id)
        .outerjoin(PlanStoreOption, PlanStoreOption.plan_store_option_id == GeneratedPlan.selected_store_option_id)
        .outerjoin(Location, Location.location_id == PlanStoreOption.location_id)
        .order_by(GeneratedPlan.created_at.desc())
        .limit(min(limit, 500))
        .offset(offset)
    )
    rows = []
    for plan, budget, household_id, household_name, selected_store_name in result.all():
        row = _serialize_model(plan)
        row["available_budget_rm"] = budget
        row["household_id"] = household_id
        row["household_name"] = household_name
        row["selected_store_name"] = selected_store_name
        rows.append(jsonable_encoder(row))
    return rows


@app.get("/api/v1/admin/generated-plans/{plan_id}")
async def admin_generated_plan_detail(plan_id: str, _: AppUser = Depends(require_admin), db: AsyncSession = Depends(get_db_session)):
    try:
        plan_uuid = uuid.UUID(plan_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid plan_id.") from exc
    row = (
        await db.execute(
            select(GeneratedPlan, PlanningRequest, Household, PlanningLocation)
            .join(PlanningRequest, PlanningRequest.planning_request_id == GeneratedPlan.planning_request_id)
            .join(Household, Household.id == PlanningRequest.household_id)
            .outerjoin(PlanningLocation, PlanningLocation.planning_request_id == PlanningRequest.planning_request_id)
            .where(GeneratedPlan.plan_id == plan_uuid)
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Generated plan not found.")
    plan, request, household, planning_location = row
    items = (
        await db.execute(
            select(GeneratedPlanItem, CanonicalFood.canonical_name)
            .join(CanonicalFood, CanonicalFood.canonical_food_id == GeneratedPlanItem.canonical_food_id)
            .where(GeneratedPlanItem.plan_id == plan.plan_id)
            .order_by(CanonicalFood.canonical_name)
        )
    ).all()
    exclusions = (
        await db.execute(
            select(PlanningRequestExclusion.exclusion_code).where(
                PlanningRequestExclusion.planning_request_id == request.planning_request_id
            )
        )
    ).scalars().all()
    store_rows = (
        await db.execute(
            select(PlanStoreOption, Location.location_name)
            .join(Location, Location.location_id == PlanStoreOption.location_id)
            .where(PlanStoreOption.plan_id == plan.plan_id)
            .order_by(PlanStoreOption.recommendation_rank)
        )
    ).all()
    store_options = []
    for option, location_name in store_rows:
        store_items = (
            await db.execute(
                select(PlanStoreItem, CanonicalFood.canonical_name)
                .join(CanonicalFood, CanonicalFood.canonical_food_id == PlanStoreItem.canonical_food_id)
                .where(PlanStoreItem.plan_store_option_id == option.plan_store_option_id)
                .order_by(CanonicalFood.canonical_name)
            )
        ).all()
        option_row = _serialize_model(option)
        option_row["location_name"] = location_name
        option_row["items"] = [
            {**_serialize_model(store_item), "canonical_name": canonical_name}
            for store_item, canonical_name in store_items
        ]
        store_options.append(option_row)
    return jsonable_encoder(
        {
            "plan": _serialize_model(plan),
            "planning_request": _serialize_model(request),
            "household": _serialize_model(household),
            "planning_location": _serialize_model(planning_location) if planning_location else None,
            "exclusions": exclusions,
            "generated_items": [
                {**_serialize_model(item), "canonical_name": canonical_name}
                for item, canonical_name in items
            ],
            "store_options": store_options,
        }
    )


# --- Dev test page: Epic 6 end-to-end flow (static mount, optional dir) ---
_EPIC6_TEST_DIR = Path(__file__).resolve().parent / "static" / "epic6test"
if _EPIC6_TEST_DIR.is_dir():
    from fastapi.staticfiles import StaticFiles

    app.mount(
        "/epic6test",
        StaticFiles(directory=_EPIC6_TEST_DIR, html=True),
        name="epic6-test",
    )

