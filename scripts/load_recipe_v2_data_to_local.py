from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import re
import uuid
from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlparse

import asyncpg


IMPORT_REVIEWER_EMAIL = "recipe-v2-data-import@wisebasket.local"
IMPORT_DATASET_VERSION = "PriceCatcher 2026-08"
LEGACY_NUTRITION_PREFIX = "IDENTITY_TRANSFER_2026_09_21:"
TARGET_MATCH_STATUSES = {"EXACT_IDENTITY_MATCH", "DEFENSIBLE_ALIAS_MATCH"}
TARGET_CONFIDENCE = {"HIGH", "MEDIUM"}
SAFE_PRICE_DISPLAY = "SHOW"
GRAMS_PER_KG = Decimal("1000")

PIECE_GRAMS = {
    "1109": Decimal("58"),
    "1110": Decimal("58"),
    "1111": Decimal("58"),
    "118": Decimal("57.5"),
    "119": Decimal("62.5"),
    "120": Decimal("67.5"),
}

DENSITY_G_PER_ML = {
    "SF102": Decimal("1.00"),
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def verify_manifest(handoff_dir: Path) -> None:
    manifest_path = handoff_dir / "MANIFEST_SHA256.txt"
    for line in manifest_path.read_text(encoding="utf-8").splitlines():
        expected, name = line.split(" *", 1)
        actual = hashlib.sha256((handoff_dir / name).read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError(f"Handoff checksum mismatch: {name}")


def require_local_database_url(database_url: str) -> str:
    normalized = database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    parsed = urlparse(normalized)
    if parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("This loader only runs against a local PostgreSQL database.")
    return normalized


def parse_purchase_mass_g(
    source_unit: str,
    item_code: str,
    food_id: str,
) -> Decimal | None:
    unit = (source_unit or "").strip().lower().replace(" ", "")
    match = re.fullmatch(r"([0-9.]+)(kg|g)", unit)
    if match:
        value = Decimal(match.group(1))
        return value * GRAMS_PER_KG if match.group(2) == "kg" else value
    match = re.fullmatch(r"([0-9.]+)biji", unit)
    if match and item_code in PIECE_GRAMS:
        return Decimal(match.group(1)) * PIECE_GRAMS[item_code]
    match = re.fullmatch(r"([0-9.]+)(liter|l|ml)", unit)
    density = DENSITY_G_PER_ML.get(food_id)
    if match and density is not None:
        amount = Decimal(match.group(1))
        if match.group(2) in {"liter", "l"}:
            amount *= Decimal("1000")
        return amount * density
    return None


def build_identity_transfers(
    crosswalk_rows: list[dict[str, str]],
    target_food_ids: set[str],
) -> dict[str, dict[str, str]]:
    candidates: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in crosswalk_rows:
        if (
            row["new_canonical_food_id"] in target_food_ids
            and row["MATCH_STATUS"] in TARGET_MATCH_STATUSES
            and row["CONFIDENCE"] in TARGET_CONFIDENCE
            and row["GRANULARITY_CHANGE"] == "NONE"
        ):
            candidates[row["new_canonical_food_id"]].append(row)
    transfers = {}
    for food_id, rows in candidates.items():
        if len(rows) == 1:
            transfers[food_id] = rows[0]
    return transfers


def build_safe_price_food_ids(
    master_rows: list[dict[str, str]],
    target_food_ids: set[str],
) -> set[str]:
    return {
        row["canonical_food_id"]
        for row in master_rows
        if row["canonical_food_id"] in target_food_ids
        and row["representative_price_safe"] == "YES"
        and row["app_canonical_price_display"] == SAFE_PRICE_DISPLAY
    }


def build_contributing_item_codes(
    quality_rows: list[dict[str, str]],
    safe_food_ids: set[str],
) -> set[str]:
    return {
        row["item_code"]
        for row in quality_rows
        if row["canonical_food_id"] in safe_food_ids
        and row["contributes_to_canonical_aggregate"] == "YES"
        and row["item_unit_series_status"] == "CONFIRMED_IDENTITY"
    }


def build_mapping_rows(
    detail_rows: list[dict[str, str]],
    safe_food_ids: set[str],
    contributing_item_codes: set[str],
) -> list[dict[str, str]]:
    return [
        row
        for row in detail_rows
        if row["canonical_food_id"] in safe_food_ids
        and row["item_code"] in contributing_item_codes
        and row["mapping_identity_status"] == "CONFIRMED_IDENTITY"
    ]


def collect_latest_price_rows(
    path: Path,
    safe_food_ids: set[str],
    contributing_item_codes: set[str],
) -> tuple[list[dict[str, object]], set[str]]:
    latest: dict[tuple[str, str], dict[str, object]] = {}
    unparseable_units = set()
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            food_id = row["canonical_food_id"]
            item_code = row["item_code"]
            if food_id not in safe_food_ids or item_code not in contributing_item_codes:
                continue
            if row["mapping_identity_status"] != "CONFIRMED_IDENTITY":
                continue
            purchase_mass_g = parse_purchase_mass_g(row["source_unit"], item_code, food_id)
            if purchase_mass_g is None:
                unparseable_units.add(f"{food_id}:{item_code}:{row['source_unit']}")
                continue
            observed_date = date.fromisoformat(row["observation_date"])
            key = (item_code, row["source_premise_code"])
            current = latest.get(key)
            if current is not None and current["observed_date"] >= observed_date:
                continue
            price_rm = Decimal(row["price"])
            price_per_100g = price_rm * Decimal("100") / purchase_mass_g
            latest[key] = {
                "canonical_food_id": food_id,
                "source_item_code": item_code,
                "source_food_name": row["item_name"],
                "source_premise_code": row["source_premise_code"],
                "observed_date": observed_date,
                "price_rm": price_rm,
                "original_unit": row["source_unit"],
                "purchase_mass_g": purchase_mass_g,
                "price_rm_per_kg_purchase": price_per_100g * Decimal("10"),
                "price_rm_per_100g_purchase": price_per_100g,
                "source_dataset_version": IMPORT_DATASET_VERSION,
                "quality_status": "PASS",
            }
    return list(latest.values()), unparseable_units


def prepare_legacy_nutrition_rows(
    legacy_rows: list[dict[str, str]],
    transfers: dict[str, dict[str, str]],
) -> list[dict[str, object]]:
    legacy_by_id = {row["canonical_food_id"]: row for row in legacy_rows}
    output = []
    for new_food_id, transfer in transfers.items():
        row = legacy_by_id.get(transfer["old_canonical_food_id"])
        if row is None or row["quality_status"] != "PASS":
            continue
        output.append({
            "canonical_food_id": new_food_id,
            "source_dataset_version": LEGACY_NUTRITION_PREFIX + row["source_dataset_version"],
            "source_record_id": row["source_record_id"],
            "basis_g": Decimal(row["basis_g"]),
            "energy_kcal": decimal_or_none(row["energy_kcal"]),
            "protein_g": decimal_or_none(row["protein_g"]),
            "fat_g": decimal_or_none(row["fat_g"]),
            "carbohydrate_g": decimal_or_none(row["carbohydrate_g"]),
            "fibre_g": decimal_or_none(row["fibre_g"]),
            "fibre_basis": "UNKNOWN" if row["fibre_g"] else None,
            "iron_mg": decimal_or_none(row["iron_mg"]),
            "calcium_mg": decimal_or_none(row["calcium_mg"]),
            "vitamin_a_ug": decimal_or_none(row["vitamin_a_ug"]),
            "vitamin_a_basis": "RE" if row["vitamin_a_ug"] else None,
            "vitamin_c_mg": decimal_or_none(row["vitamin_c_mg"]),
            "quality_status": "PASS",
            "source_url": row["source_url"],
            "source_retrieved_at": parse_datetime(row["source_retrieved_at"]),
        })
    return output


def prepare_legacy_conversion_rows(
    legacy_rows: list[dict[str, str]],
    transfers: dict[str, dict[str, str]],
) -> list[dict[str, object]]:
    new_by_old = {
        transfer["old_canonical_food_id"]: new_food_id
        for new_food_id, transfer in transfers.items()
    }
    output = []
    for row in legacy_rows:
        new_food_id = new_by_old.get(row["canonical_food_id"])
        if new_food_id is None or row["production_eligible"] != "YES":
            continue
        factor = Decimal(row["factor"])
        output.append({
            "canonical_food_id": new_food_id,
            "conversion_type": row["conversion_type"],
            "source_unit": row["from_unit"],
            "target_unit": row["to_unit"],
            "factor": factor if row["conversion_type"] == "PURCHASE_MASS" else None,
            "edible_yield_fraction": (
                factor if row["conversion_type"] == "EDIBLE_YIELD" else None
            ),
            "production_eligible": True,
            "evidence_note": (
                f"Identity transfer from legacy {row['canonical_food_id']} to {new_food_id}; "
                f"{row['evidence_source']}; {row['evidence_note']}"
            ),
        })
    return output


def decimal_or_none(value: str) -> Decimal | None:
    return Decimal(value) if value else None


def parse_datetime(value: str) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


async def enabled_recipe_foods(conn: asyncpg.Connection) -> dict[str, str]:
    rows = await conn.fetch(
        """
        select distinct cf.canonical_food_id, cf.canonical_name
        from recipe_catalog rc
        join recipe_catalog_ingredient rci on rci.recipe_id = rc.recipe_id
        join canonical_food cf on cf.canonical_food_id = rci.canonical_food_id
        where rc.active and rc.optimizer_eligible and rc.review_status = 'APPROVED'
          and rci.base_quantity_g is not null
        order by cf.canonical_food_id
        """
    )
    return {row["canonical_food_id"]: row["canonical_name"] for row in rows}


async def ensure_reviewer(conn: asyncpg.Connection) -> uuid.UUID:
    existing = await conn.fetchval(
        "select user_id from app_user where email_normalized = $1",
        IMPORT_REVIEWER_EMAIL,
    )
    if existing is not None:
        return existing
    reviewer_id = uuid.uuid5(uuid.NAMESPACE_URL, IMPORT_REVIEWER_EMAIL)
    await conn.execute(
        """
        insert into app_user (
            user_id, email, email_normalized, password_hash, role, status, email_verified
        ) values ($1, $2, $2, 'local-data-import-no-login', 'ADMIN', 'ACTIVE', true)
        """,
        reviewer_id,
        IMPORT_REVIEWER_EMAIL,
    )
    return reviewer_id


async def load_local_database(
    database_url: str,
    handoff_dir: Path,
    legacy_dir: Path,
    dry_run: bool,
) -> dict[str, object]:
    verify_manifest(handoff_dir)
    conn = await asyncpg.connect(require_local_database_url(database_url))
    try:
        target_foods = await enabled_recipe_foods(conn)
        if not target_foods:
            raise ValueError("No approved optimizer recipes were found.")

        canonical_rows = read_csv(handoff_dir / "canonical_food_FINAL.csv")
        handoff_names = {row["canonical_food_id"]: row["canonical_name"] for row in canonical_rows}
        for food_id, local_name in target_foods.items():
            if handoff_names.get(food_id) != local_name:
                raise ValueError(f"Canonical identity mismatch for {food_id}")

        target_food_ids = set(target_foods)
        transfers = build_identity_transfers(
            read_csv(handoff_dir / "OLD_TO_NEW_CANONICAL_CROSSWALK.csv"),
            target_food_ids,
        )
        safe_price_food_ids = build_safe_price_food_ids(
            read_csv(handoff_dir / "wisebasket_food_data_FINAL.csv"),
            target_food_ids,
        )
        contributing_item_codes = build_contributing_item_codes(
            read_csv(handoff_dir / "PRICE_DATA_QUALITY_REPORT.csv"),
            safe_price_food_ids,
        )
        mapping_rows = build_mapping_rows(
            read_csv(handoff_dir / "FOOD_SOURCE_VARIANT_DETAILS.csv"),
            safe_price_food_ids,
            contributing_item_codes,
        )
        price_rows, unparseable_units = collect_latest_price_rows(
            handoff_dir / "food_price_observation_FINAL.csv",
            safe_price_food_ids,
            contributing_item_codes,
        )
        nutrition_rows = prepare_legacy_nutrition_rows(
            read_csv(legacy_dir / "food_nutrition.csv"),
            transfers,
        )
        conversion_rows = prepare_legacy_conversion_rows(
            read_csv(legacy_dir / "unit_conversion.csv"),
            transfers,
        )
        pack_rows = build_pack_conversion_rows(mapping_rows)

        report = {
            "target_foods": len(target_food_ids),
            "identity_transfers": len(transfers),
            "safe_price_foods": len(safe_price_food_ids),
            "mapping_rows": len(mapping_rows),
            "latest_price_rows": len(price_rows),
            "nutrition_rows": len(nutrition_rows),
            "legacy_conversion_rows": len(conversion_rows),
            "pack_conversion_rows": len(pack_rows),
            "unparseable_units": sorted(unparseable_units),
        }
        if dry_run:
            return report

        async with conn.transaction():
            reviewer_id = await ensure_reviewer(conn)
            await replace_imported_rows(
                conn,
                reviewer_id,
                target_food_ids,
                mapping_rows,
                price_rows,
                nutrition_rows,
                [*conversion_rows, *pack_rows],
                handoff_dir,
            )
        return report
    finally:
        await conn.close()


def build_pack_conversion_rows(
    mapping_rows: list[dict[str, str]],
) -> list[dict[str, object]]:
    unique = {}
    for row in mapping_rows:
        mass = parse_purchase_mass_g(row["unit"], row["item_code"], row["canonical_food_id"])
        if mass is None:
            continue
        key = (row["canonical_food_id"], row["unit"], mass)
        unique[key] = {
            "canonical_food_id": row["canonical_food_id"],
            "conversion_type": "PURCHASE_MASS",
            "source_unit": row["unit"],
            "target_unit": "g",
            "factor": mass,
            "edible_yield_fraction": None,
            "production_eligible": True,
            "evidence_note": (
                f"Deterministic parse of confirmed PriceCatcher item {row['item_code']} "
                f"unit {row['unit']} from final 201-food handoff."
            ),
        }
    return list(unique.values())


async def replace_imported_rows(
    conn: asyncpg.Connection,
    reviewer_id: uuid.UUID,
    target_food_ids: set[str],
    mapping_rows: list[dict[str, str]],
    price_rows: list[dict[str, object]],
    nutrition_rows: list[dict[str, object]],
    conversion_rows: list[dict[str, object]],
    handoff_dir: Path,
) -> None:
    target_ids = sorted(target_food_ids)
    await conn.execute(
        "delete from food_price_observation where source_dataset_version = $1 "
        "and canonical_food_id = any($2::text[])",
        IMPORT_DATASET_VERSION,
        target_ids,
    )
    await conn.execute(
        "delete from source_food_mapping where source_system = 'PRICECATCHER' "
        "and source_dataset_version = $1 and canonical_food_id = any($2::text[])",
        IMPORT_DATASET_VERSION,
        target_ids,
    )
    await conn.execute(
        "delete from food_nutrition where source_dataset_version like $1 "
        "and canonical_food_id = any($2::text[])",
        LEGACY_NUTRITION_PREFIX + "%",
        target_ids,
    )
    await conn.execute(
        "delete from unit_conversion where evidence_note like 'Identity transfer from legacy %' "
        "and canonical_food_id = any($1::text[])",
        target_ids,
    )
    await conn.execute(
        "delete from unit_conversion where evidence_note like 'Deterministic parse of confirmed PriceCatcher item %' "
        "and canonical_food_id = any($1::text[])",
        target_ids,
    )

    location_rows = read_csv(handoff_dir / "location_grocery_FINAL.csv")
    await conn.executemany(
        """
        insert into location (
            location_id, source_premise_code, location_name, premise_type, state, district,
            address, latitude, longitude, active
        ) values ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
        on conflict (source_premise_code) do update set
            location_name=excluded.location_name, premise_type=excluded.premise_type,
            state=excluded.state, district=excluded.district, address=excluded.address,
            latitude=excluded.latitude, longitude=excluded.longitude, active=excluded.active
        """,
        [
            (
                int(row["location_id"]), row["source_premise_code"], row["location_name"],
                row["premise_type"] or None, row["state"] or None, row["district"] or None,
                row["address"] or None, decimal_or_none(row["latitude"]),
                decimal_or_none(row["longitude"]), row["active"].lower() == "true",
            )
            for row in location_rows
        ],
    )
    await conn.execute(
        "select setval(pg_get_serial_sequence('location','location_id'), "
        "greatest((select max(location_id) from location), 1), true)"
    )

    reviewed_at = datetime(2026, 9, 21, tzinfo=timezone.utc)
    await conn.executemany(
        """
        insert into source_food_mapping (
            source_system, source_dataset_version, source_food_id, source_food_name,
            source_unit_or_form, canonical_food_id, mapping_status, verification_status,
            review_status, evidence_note, reviewed_by, reviewed_at, variant_metadata
        ) values ('PRICECATCHER',$1,$2,$3,$4,$5,'EXACT','VERIFIED','APPROVED',$6,$7,$8,$9)
        """,
        [
            (
                IMPORT_DATASET_VERSION, row["item_code"], row["item_name"], row["unit"],
                row["canonical_food_id"],
                "Confirmed identity in final 201-food handoff; included in safe canonical aggregate.",
                reviewer_id, reviewed_at,
                f"variant_type={row['variant_type']}; variant_label={row['variant_label']}",
            )
            for row in mapping_rows
        ],
    )

    location_ids = {
        row["source_premise_code"]: row["location_id"]
        for row in await conn.fetch(
            "select source_premise_code, location_id from location where source_premise_code is not null"
        )
    }
    price_records = []
    for row in price_rows:
        location_id = location_ids.get(row["source_premise_code"])
        if location_id is None:
            continue
        price_records.append((
            row["canonical_food_id"], row["source_item_code"], row["source_food_name"],
            row["source_premise_code"], location_id, row["observed_date"], row["price_rm"],
            row["original_unit"], row["purchase_mass_g"],
            row["price_rm_per_kg_purchase"], row["price_rm_per_100g_purchase"],
            IMPORT_DATASET_VERSION, "PASS",
        ))
    await conn.copy_records_to_table(
        "food_price_observation",
        records=price_records,
        columns=[
            "canonical_food_id", "source_item_code", "source_food_name",
            "source_premise_code", "location_id", "observed_date", "price_rm",
            "original_unit", "purchase_mass_g", "price_rm_per_kg_purchase",
            "price_rm_per_100g_purchase", "source_dataset_version", "quality_status",
        ],
    )

    await conn.executemany(
        """
        insert into food_nutrition (
            canonical_food_id, source_dataset_version, source_record_id, basis_g,
            energy_kcal, protein_g, fat_g, carbohydrate_g, fibre_g, fibre_basis,
            iron_mg, calcium_mg, vitamin_a_ug, vitamin_a_basis, vitamin_c_mg,
            quality_status, is_current, source_url, source_retrieved_at
        ) values ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,true,$17,$18)
        """,
        [tuple(row.values()) for row in nutrition_rows],
    )
    await conn.executemany(
        """
        insert into unit_conversion (
            canonical_food_id, conversion_type, source_unit, target_unit, factor,
            edible_yield_fraction, production_eligible, evidence_note
        ) values ($1,$2,$3,$4,$5,$6,$7,$8)
        """,
        [tuple(row.values()) for row in conversion_rows],
    )


async def run(args: argparse.Namespace) -> None:
    report = await load_local_database(
        args.database_url,
        Path(args.handoff_dir),
        Path(args.legacy_curated_dir),
        args.dry_run,
    )
    for key, value in report.items():
        print(f"{key}={value}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--handoff-dir", required=True)
    parser.add_argument("--legacy-curated-dir", required=True)
    parser.add_argument("--dry-run", action="store_true")
    asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    main()
