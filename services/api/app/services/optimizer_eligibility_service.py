from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


USABLE_MAPPING_STATUSES = {"EXACT", "ACCEPTED_EQUIVALENT", "NEEDS_CONVERSION"}

ELIGIBILITY_SQL = text(
    """
    with mapping as (
        select canonical_food_id,
               count(*) as mapping_count,
               bool_or(review_status = 'APPROVED') as mapping_approved,
               bool_or(verification_status = 'REJECTED' or review_status = 'REJECTED') as mapping_rejected,
               bool_or(
                   mapping_status in ('EXACT', 'ACCEPTED_EQUIVALENT', 'NEEDS_CONVERSION')
                   and verification_status = 'VERIFIED'
                   and review_status = 'APPROVED'
               ) as mapping_usable
        from source_food_mapping
        where canonical_food_id is not null
        group by canonical_food_id
    ),
    nutrition as (
        select canonical_food_id,
               count(*) filter (where is_current) as current_count,
               bool_or(is_current and quality_status in ('PASS', 'WARN')) as nutrition_usable,
               bool_or(is_current and quality_status = 'BLOCK') as nutrition_blocked
        from food_nutrition
        group by canonical_food_id
    ),
    price as (
        select canonical_food_id,
               count(*) as price_count,
               bool_or(quality_status = 'BLOCK') as price_blocked,
               bool_or(quality_status = 'PASS' and price_rm_per_100g_edible is not null) as price_usable,
               bool_or(quality_status = 'PASS' and price_rm_per_100g_edible is null) as normalized_price_missing,
               bool_or(location_id is not null) as location_available
        from food_price_observation
        where canonical_food_id is not null
        group by canonical_food_id
    ),
    unit_conversion as (
        select canonical_food_id,
               count(*) filter (where conversion_type = 'PURCHASE_MASS') as unit_conversion_count,
               bool_or(
                   conversion_type = 'PURCHASE_MASS'
                   and production_eligible = true
                   and factor is not null
               ) as unit_conversion_usable,
               bool_or(conversion_type = 'PURCHASE_MASS' and production_eligible = false) as unit_conversion_not_production_eligible
        from unit_conversion
        where canonical_food_id is not null
        group by canonical_food_id
    ),
    candidate as (
        select distinct canonical_food_id
        from v_optimizer_food_candidate
    )
    select cf.canonical_food_id,
           cf.canonical_name,
           cf.canonical_name_ms,
           cf.category,
           cf.status,
           coalesce(m.mapping_count, 0) as mapping_count,
           coalesce(m.mapping_approved, false) as mapping_approved,
           coalesce(m.mapping_rejected, false) as mapping_rejected,
           coalesce(m.mapping_usable, false) as mapping_usable,
           coalesce(n.current_count, 0) as current_nutrition_count,
           coalesce(n.nutrition_usable, false) as nutrition_usable,
           coalesce(n.nutrition_blocked, false) as nutrition_blocked,
           coalesce(p.price_count, 0) as price_count,
           coalesce(p.price_blocked, false) as price_blocked,
           coalesce(p.price_usable, false) as price_usable,
           coalesce(p.normalized_price_missing, false) as normalized_price_missing,
           coalesce(p.location_available, false) as location_available,
           coalesce(uc.unit_conversion_count, 0) as unit_conversion_count,
           coalesce(uc.unit_conversion_usable, false) as unit_conversion_usable,
           coalesce(uc.unit_conversion_not_production_eligible, false) as unit_conversion_not_production_eligible,
           (candidate.canonical_food_id is not null) as optimizer_eligible
    from canonical_food cf
    left join mapping m on m.canonical_food_id = cf.canonical_food_id
    left join nutrition n on n.canonical_food_id = cf.canonical_food_id
    left join price p on p.canonical_food_id = cf.canonical_food_id
    left join unit_conversion uc on uc.canonical_food_id = cf.canonical_food_id
    left join candidate on candidate.canonical_food_id = cf.canonical_food_id
    """
)


def _build_reasons(row: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    if not row["canonical_active"]:
        reasons.append("CANONICAL_FOOD_INACTIVE")
    if row["mapping_count"] == 0:
        reasons.append("MAPPING_MISSING")
    elif row["mapping_rejected"]:
        reasons.append("SOURCE_MAPPING_REJECTED")
    elif not row["mapping_approved"]:
        reasons.append("SOURCE_MAPPING_NOT_APPROVED")
    elif not row["mapping_usable"]:
        reasons.append("MAPPING_NOT_USABLE")
    if row["current_nutrition_count"] == 0:
        reasons.append("NUTRITION_MISSING")
    elif row["nutrition_blocked"]:
        reasons.append("NUTRITION_BLOCKED")
    elif not row["nutrition_usable"]:
        reasons.append("NUTRITION_NOT_USABLE")
    if row["price_count"] == 0:
        reasons.append("PRICE_MISSING")
    elif row["price_blocked"]:
        reasons.append("PRICE_BLOCKED")
    elif row["normalized_price_missing"]:
        reasons.append("NORMALIZED_PRICE_MISSING")
    elif not row["price_usable"]:
        reasons.append("PRICE_MISSING")
    if row["price_count"] > 0 and not row["location_available"]:
        reasons.append("LOCATION_MISSING")
    return reasons


def _diagnostic_from_mapping(data: dict[str, Any]) -> dict[str, Any]:
    checks = {
        "canonical_active": data["status"] == "ACTIVE",
        "mapping_approved": bool(data["mapping_approved"]),
        "mapping_usable": bool(data["mapping_usable"]),
        "nutrition_available": data["current_nutrition_count"] > 0,
        "nutrition_usable": bool(data["nutrition_usable"]),
        "price_available": data["price_count"] > 0,
        "price_usable": bool(data["price_usable"]),
        "unit_conversion_usable": bool(data["unit_conversion_usable"]),
        "location_available": bool(data["location_available"]),
        "optimizer_eligible": bool(data["optimizer_eligible"]),
    }
    row = dict(data)
    row["canonical_active"] = checks["canonical_active"]
    return {
        "canonical_food_id": data["canonical_food_id"],
        "canonical_name": data["canonical_name"],
        "canonical_name_ms": data["canonical_name_ms"],
        "category": data["category"],
        "status": data["status"],
        "eligible": bool(data["optimizer_eligible"]),
        "checks": checks,
        "reasons": [] if data["optimizer_eligible"] else _build_reasons(row),
        "counts": {
            "mappings": data["mapping_count"],
            "current_nutrition_records": data["current_nutrition_count"],
            "price_observations": data["price_count"],
            "unit_conversions": data["unit_conversion_count"],
        },
    }


async def list_optimizer_eligibility(
    db: AsyncSession,
    *,
    eligible: bool | None = None,
    canonical_food_id: str | None = None,
    category: str | None = None,
    reason: str | None = None,
    search: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    filters: list[str] = []
    params: dict[str, Any] = {"limit": min(max(limit, 1), 500), "offset": max(offset, 0)}
    if eligible is not None:
        filters.append("optimizer_eligible = :eligible")
        params["eligible"] = eligible
    if canonical_food_id:
        filters.append("canonical_food_id = :canonical_food_id")
        params["canonical_food_id"] = canonical_food_id.strip()
    if category:
        filters.append("lower(category) = lower(:category)")
        params["category"] = category.strip()
    if search:
        filters.append("(canonical_food_id ilike :search or canonical_name ilike :search or canonical_name_ms ilike :search)")
        params["search"] = f"%{search.strip()}%"
    where_clause = f" where {' and '.join(filters)}" if filters else ""
    result = await db.execute(
        text(
            f"""
            select *
            from ({ELIGIBILITY_SQL.text}) eligibility
            {where_clause}
            order by optimizer_eligible desc, category, canonical_name
            limit :limit offset :offset
            """
        ),
        params,
    )
    diagnostics = [_diagnostic_from_mapping(dict(row._mapping)) for row in result.all()]
    if reason:
        wanted = reason.strip().upper()
        diagnostics = [item for item in diagnostics if wanted in item["reasons"]]
    return diagnostics


async def get_optimizer_eligibility(db: AsyncSession, canonical_food_id: str) -> dict[str, Any] | None:
    rows = await list_optimizer_eligibility(db, canonical_food_id=canonical_food_id, limit=1)
    return rows[0] if rows else None
