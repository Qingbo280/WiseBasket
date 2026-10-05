from __future__ import annotations

import argparse
import asyncio
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from urllib.parse import urlparse

import asyncpg

REFERENCE_REVIEWER_EMAIL = "optimizer-reference-price-import@wisebasket.local"
REFERENCE_LOCATION_CODE = "REFERENCE_LOTUSS_ONLINE"
REFERENCE_LOCATION_NAME = "Lotus's Online Reference"
REFERENCE_DATASET_VERSION = "REFERENCE_ESTIMATE_2026-09"
REFERENCE_DATE = date(2026, 9, 21)
GRAMS_PER_KG = Decimal("1000")


@dataclass(frozen=True)
class ReferencePrice:
    food_id: str
    canonical_name: str
    source_item_code: str
    source_food_name: str
    package_mass_g: Decimal
    package_price_rm: Decimal
    source_url: str
    mapping_status: str
    dataset_version: str = REFERENCE_DATASET_VERSION

    @property
    def price_rm_per_kg(self) -> Decimal:
        return self.package_price_rm / (self.package_mass_g / GRAMS_PER_KG)

    @property
    def price_rm_per_100g(self) -> Decimal:
        return self.price_rm_per_kg / Decimal("10")


REFERENCE_PRICES = (
    ReferencePrice(
        food_id="SF006",
        canonical_name="whole chicken",
        source_item_code="LOTUSS_ONLINE_2071037",
        source_food_name="LOTUSS WHOLE CHICKEN W H&F KG (7730)",
        package_mass_g=Decimal("1000"),
        package_price_rm=Decimal("8.49"),
        source_url="https://www.lotuss.com.my/ms/p/lotuss-fresh-whole-chicken-with-head-and-feet-2071037",
        mapping_status="EXACT",
    ),
    ReferencePrice(
        food_id="SF056",
        canonical_name="onion",
        source_item_code="LOTUSS_ONLINE_73750948",
        source_food_name="BAWANG MERAH BESAR 2KG",
        package_mass_g=Decimal("2000"),
        package_price_rm=Decimal("4.30"),
        source_url="https://www.lotuss.com.my/p/bawang-merah-besar-2big-red-onion-2kg-73750948",
        mapping_status="ACCEPTED_EQUIVALENT",
    ),
    ReferencePrice(
        food_id="SF077",
        canonical_name="carrot",
        source_item_code="LOTUSS_ONLINE_3668746",
        source_food_name="LOBAK MERAH AUST/AUST CARROTS 1KG -PKT",
        package_mass_g=Decimal("1000"),
        package_price_rm=Decimal("4.99"),
        source_url="https://www.lotuss.com.my/p/lobak-merah-australia-carrots-1kg-pkt-3668746",
        mapping_status="ACCEPTED_EQUIVALENT",
    ),
    ReferencePrice(
        food_id="SF124",
        canonical_name="dhal (lentils)",
        source_item_code="LOTUSS_ONLINE_75193613",
        source_food_name="LOTUSS DHAL MASSOR 500G",
        package_mass_g=Decimal("500"),
        package_price_rm=Decimal("3.99"),
        source_url="https://www.lotuss.com.my/p/lotuss-dhal-massor-500g-75193613",
        mapping_status="ACCEPTED_EQUIVALENT",
    ),
)


def require_local_database_url(database_url: str) -> str:
    normalized = database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    parsed = urlparse(normalized)
    if parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("This loader only runs against a local PostgreSQL database.")
    return normalized


async def ensure_reviewer(conn: asyncpg.Connection) -> uuid.UUID:
    reviewer_id = await conn.fetchval(
        "select user_id from app_user where email_normalized = $1",
        REFERENCE_REVIEWER_EMAIL,
    )
    if reviewer_id is not None:
        return reviewer_id
    reviewer_id = uuid.uuid5(uuid.NAMESPACE_URL, REFERENCE_REVIEWER_EMAIL)
    await conn.execute(
        """
        insert into app_user (
            user_id, email, email_normalized, password_hash, role, status, email_verified
        ) values ($1, $2, $2, 'local-reference-import-no-login', 'ADMIN', 'ACTIVE', true)
        """,
        reviewer_id,
        REFERENCE_REVIEWER_EMAIL,
    )
    return reviewer_id


async def ensure_reference_location(conn: asyncpg.Connection) -> int:
    return await conn.fetchval(
        """
        insert into location (
            source_premise_code, location_name, premise_type, address, active
        ) values ($1, $2, 'ONLINE_REFERENCE', 'https://www.lotuss.com.my/', true)
        on conflict (source_premise_code) do update set
            location_name=excluded.location_name,
            premise_type=excluded.premise_type,
            address=excluded.address,
            active=true
        returning location_id
        """,
        REFERENCE_LOCATION_CODE,
        REFERENCE_LOCATION_NAME,
    )


async def validate_canonical_foods(conn: asyncpg.Connection) -> None:
    rows = await conn.fetch(
        "select canonical_food_id, canonical_name from canonical_food where canonical_food_id = any($1::text[])",
        [row.food_id for row in REFERENCE_PRICES],
    )
    actual = {row["canonical_food_id"]: row["canonical_name"] for row in rows}
    expected = {row.food_id: row.canonical_name for row in REFERENCE_PRICES}
    if actual != expected:
        raise ValueError(f"Canonical identity mismatch: expected {expected}, found {actual}")


async def upsert_reference_price(
    conn: asyncpg.Connection,
    row: ReferencePrice,
    reviewer_id: uuid.UUID,
    location_id: int,
) -> None:
    reviewed_at = datetime(2026, 9, 21, tzinfo=timezone.utc)
    source_unit = f"{row.package_mass_g:f} g"
    evidence_note = (
        f"Governed retailer reference retrieved 2026-09-21 from {row.source_url}; "
        "reference estimate, not PriceCatcher market data."
    )
    await conn.execute(
        """
        insert into source_food_mapping (
            source_system, source_dataset_version, source_food_id, source_food_name,
            source_unit_or_form, canonical_food_id, mapping_status, verification_status,
            review_status, evidence_note, reviewed_by, reviewed_at, variant_metadata
        ) values ('WISEBASKET_REFERENCE',$1,$2,$3,$4,$5,$6,'VERIFIED','APPROVED',$7,$8,$9,$10)
        on conflict (source_system, source_dataset_version, source_food_id) do update set
            source_food_name=excluded.source_food_name,
            source_unit_or_form=excluded.source_unit_or_form,
            canonical_food_id=excluded.canonical_food_id,
            mapping_status=excluded.mapping_status,
            verification_status=excluded.verification_status,
            review_status=excluded.review_status,
            evidence_note=excluded.evidence_note,
            reviewed_by=excluded.reviewed_by,
            reviewed_at=excluded.reviewed_at,
            variant_metadata=excluded.variant_metadata
        """,
        row.dataset_version,
        row.source_item_code,
        row.source_food_name,
        source_unit,
        row.food_id,
        row.mapping_status,
        evidence_note,
        reviewer_id,
        reviewed_at,
        f"source_url={row.source_url}",
    )
    await conn.execute(
        """
        insert into food_price_observation (
            canonical_food_id, source_item_code, source_food_name, source_premise_code,
            location_id, observed_date, price_rm, original_unit, purchase_mass_g,
            price_rm_per_kg_purchase, price_rm_per_100g_purchase,
            source_dataset_version, quality_status
        ) values ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,'PASS')
        on conflict (source_item_code, location_id, observed_date, source_dataset_version)
        do update set
            canonical_food_id=excluded.canonical_food_id,
            source_food_name=excluded.source_food_name,
            source_premise_code=excluded.source_premise_code,
            price_rm=excluded.price_rm,
            original_unit=excluded.original_unit,
            purchase_mass_g=excluded.purchase_mass_g,
            price_rm_per_kg_purchase=excluded.price_rm_per_kg_purchase,
            price_rm_per_100g_purchase=excluded.price_rm_per_100g_purchase,
            quality_status='PASS'
        """,
        row.food_id,
        row.source_item_code,
        row.source_food_name,
        REFERENCE_LOCATION_CODE,
        location_id,
        REFERENCE_DATE,
        row.package_price_rm,
        source_unit,
        row.package_mass_g,
        row.price_rm_per_kg,
        row.price_rm_per_100g,
        row.dataset_version,
    )
    await conn.execute(
        """
        insert into unit_conversion (
            canonical_food_id, conversion_type, source_unit, target_unit, factor,
            production_eligible, evidence_note
        )
        select $1::varchar, 'PURCHASE_MASS', $2::varchar, 'g', $3::numeric, true, $4::text
        where not exists (
            select 1 from unit_conversion
            where canonical_food_id=$1::varchar and conversion_type='PURCHASE_MASS'
              and production_eligible=true and factor=$3::numeric
        )
        """,
        row.food_id,
        source_unit,
        row.package_mass_g,
        evidence_note,
    )


async def load_reference_prices(database_url: str, dry_run: bool = False) -> dict[str, object]:
    normalized_url = require_local_database_url(database_url)
    if dry_run:
        return {
            "dataset_version": REFERENCE_DATASET_VERSION,
            "foods": [row.food_id for row in REFERENCE_PRICES],
            "rows": len(REFERENCE_PRICES),
            "dry_run": True,
        }
    conn = await asyncpg.connect(normalized_url)
    try:
        async with conn.transaction():
            await validate_canonical_foods(conn)
            reviewer_id = await ensure_reviewer(conn)
            location_id = await ensure_reference_location(conn)
            for row in REFERENCE_PRICES:
                await upsert_reference_price(conn, row, reviewer_id, location_id)
        return {
            "dataset_version": REFERENCE_DATASET_VERSION,
            "foods": [row.food_id for row in REFERENCE_PRICES],
            "rows": len(REFERENCE_PRICES),
            "dry_run": False,
        }
    finally:
        await conn.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    report = asyncio.run(load_reference_prices(args.database_url, args.dry_run))
    for key, value in report.items():
        print(f"{key}={value}")


if __name__ == "__main__":
    main()
