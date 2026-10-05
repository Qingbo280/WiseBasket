"""Enable reviewed recipes and complete-meal component pairing.

Revision ID: w5x6y7z8a9b0
Revises: v4w5x6y7z8a9
Create Date: 2026-09-21
"""

from datetime import UTC, date, datetime
from decimal import Decimal
import json
from pathlib import Path
import uuid

from alembic import op
import sqlalchemy as sa


revision = "w5x6y7z8a9b0"
down_revision = "v4w5x6y7z8a9"
branch_labels = None
depends_on = None

DATA_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "recipe_v2_full_review_2026_09_21.json"
)
REFERENCE_DATASET = "REFERENCE_ESTIMATE_2026-09"
REFERENCE_DATE = date(2026, 9, 21)
REFERENCE_LOCATION_CODE = "REFERENCE_JAYA_GROCER_KL"
REVIEWER_EMAIL = "optimizer-reference-price-import@wisebasket.local"
REVIEWER_ID = uuid.UUID("faaa8070-4b1f-5c14-ad76-7a49f0373d77")
PREVIOUS_REVIEW_SOURCE = "WISEBASKET_35_RECIPE_STAPLE_FIRST_REVIEW_2026_09_21"
INITIAL_REVIEW_SOURCE = "WISEBASKET_CURATED_V2_INITIAL_SET_2026_09_21"

INITIAL_RECIPES = (
    "dhal-curry-with-rice",
    "egg-potato-curry-with-rice",
    "malay-chicken-soup",
    "onion-omelette",
    "tomato-egg-stir-fry",
    "turmeric-chicken-with-rice",
)

INITIAL_SAFETY_FOOD_IDS = (
    "SF006", "SF014", "SF018", "SF056", "SF057", "SF058", "SF064",
    "SF069", "SF071", "SF072", "SF077", "SF084", "SF102", "SF110",
    "SF118", "SF120", "SF124", "SF133", "SF134", "SF135", "SF136",
    "SF148", "SF151",
)

INITIAL_STEP_FOOD_LINKS = (
    ("dhal-curry-with-rice", 1, "SF124"),
    ("dhal-curry-with-rice", 1, "SF057"),
    ("dhal-curry-with-rice", 1, "SF072"),
    ("dhal-curry-with-rice", 2, "SF135"),
    ("dhal-curry-with-rice", 4, "SF110"),
    ("egg-potato-curry-with-rice", 1, "SF018"),
    ("egg-potato-curry-with-rice", 3, "SF057"),
    ("egg-potato-curry-with-rice", 3, "SF072"),
    ("egg-potato-curry-with-rice", 2, "SF133"),
    ("egg-potato-curry-with-rice", 4, "SF102"),
    ("egg-potato-curry-with-rice", 5, "SF110"),
    ("malay-chicken-soup", 2, "SF006"),
    ("malay-chicken-soup", 3, "SF057"),
    ("malay-chicken-soup", 3, "SF077"),
    ("malay-chicken-soup", 2, "SF134"),
    ("malay-chicken-soup", 5, "SF110"),
    ("onion-omelette", 1, "SF018"),
    ("onion-omelette", 2, "SF056"),
    ("onion-omelette", 4, "SF110"),
    ("tomato-egg-stir-fry", 1, "SF018"),
    ("tomato-egg-stir-fry", 3, "SF072"),
    ("tomato-egg-stir-fry", 4, "SF110"),
    ("turmeric-chicken-with-rice", 1, "SF014"),
    ("turmeric-chicken-with-rice", 4, "SF084"),
    ("turmeric-chicken-with-rice", 4, "SF077"),
    ("turmeric-chicken-with-rice", 5, "SF110"),
    ("turmeric-chicken-with-rice", 1, "SF135"),
)


def load_review_data() -> dict[str, object]:
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))


def ensure_reviewer(connection) -> uuid.UUID:
    reviewer_id = connection.execute(
        sa.text("SELECT user_id FROM app_user WHERE email_normalized = :email"),
        {"email": REVIEWER_EMAIL},
    ).scalar_one_or_none()
    if reviewer_id is not None:
        return reviewer_id
    connection.execute(
        sa.text(
            """
            INSERT INTO app_user (
                user_id, email, email_normalized, password_hash, role, status,
                email_verified
            ) VALUES (
                :user_id, :email, :email,
                'reference-import-no-login', 'ADMIN', 'ACTIVE', true
            )
            """
        ),
        {"user_id": REVIEWER_ID, "email": REVIEWER_EMAIL},
    )
    return REVIEWER_ID


def ensure_reference_location(connection) -> int:
    return connection.execute(
        sa.text(
            """
            INSERT INTO location (
                source_premise_code, location_name, premise_type, state,
                district, address, active
            ) VALUES (
                :code, 'Jaya Grocer KL Online Reference', 'ONLINE_REFERENCE',
                'W.P. Kuala Lumpur', 'Kuala Lumpur',
                'https://klec.jayagrocer.com/', true
            )
            ON CONFLICT (source_premise_code) DO UPDATE SET
                location_name=excluded.location_name,
                premise_type=excluded.premise_type,
                state=excluded.state,
                district=excluded.district,
                address=excluded.address,
                active=true
            RETURNING location_id
            """
        ),
        {"code": REFERENCE_LOCATION_CODE},
    ).scalar_one()


def upsert_reference_price(connection, row, reviewer_id, location_id) -> None:
    mass_g = Decimal(row["package_mass_g"])
    price_rm = Decimal(row["package_price_rm"])
    price_per_kg = price_rm / (mass_g / Decimal("1000"))
    price_per_100g = price_per_kg / Decimal("10")
    source_unit = f"{mass_g:f} g"
    evidence = (
        f"Governed Jaya Grocer reference retrieved 2026-09-21 from "
        f"{row['source_url']}; reference estimate, not PriceCatcher market data."
    )
    connection.execute(
        sa.text(
            """
            INSERT INTO source_food_mapping (
                source_system, source_dataset_version, source_food_id,
                source_food_name, source_unit_or_form, canonical_food_id,
                mapping_status, verification_status, review_status,
                evidence_note, reviewed_by, reviewed_at, variant_metadata
            ) VALUES (
                'WISEBASKET_REFERENCE', :dataset, :code, :name, :unit,
                :food_id, 'EXACT', 'VERIFIED', 'APPROVED', :evidence,
                :reviewer, :reviewed_at, :metadata
            )
            ON CONFLICT (source_system, source_dataset_version, source_food_id)
            DO UPDATE SET
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
            """
        ),
        {
            "dataset": REFERENCE_DATASET,
            "code": row["source_item_code"],
            "name": row["source_food_name"],
            "unit": source_unit,
            "food_id": row["food_id"],
            "evidence": evidence,
            "reviewer": reviewer_id,
            "reviewed_at": datetime.now(UTC),
            "metadata": f"source_url={row['source_url']}",
        },
    )
    connection.execute(
        sa.text(
            """
            INSERT INTO food_price_observation (
                canonical_food_id, source_item_code, source_food_name,
                source_premise_code, location_id, observed_date, price_rm,
                original_unit, purchase_mass_g, price_rm_per_kg_purchase,
                price_rm_per_100g_purchase, edible_yield_fraction,
                price_rm_per_100g_edible, source_dataset_version, quality_status
            ) VALUES (
                :food_id, :code, :name, :premise, :location_id, :observed_date,
                :price_rm, :unit, :mass_g, :per_kg, :per_100g, 1, :per_100g,
                :dataset, 'PASS'
            )
            ON CONFLICT (
                source_item_code, location_id, observed_date,
                source_dataset_version
            ) DO UPDATE SET
                canonical_food_id=excluded.canonical_food_id,
                source_food_name=excluded.source_food_name,
                price_rm=excluded.price_rm,
                original_unit=excluded.original_unit,
                purchase_mass_g=excluded.purchase_mass_g,
                price_rm_per_kg_purchase=excluded.price_rm_per_kg_purchase,
                price_rm_per_100g_purchase=excluded.price_rm_per_100g_purchase,
                edible_yield_fraction=1,
                price_rm_per_100g_edible=excluded.price_rm_per_100g_purchase,
                quality_status='PASS'
            """
        ),
        {
            "food_id": row["food_id"],
            "code": row["source_item_code"],
            "name": row["source_food_name"],
            "premise": REFERENCE_LOCATION_CODE,
            "location_id": location_id,
            "observed_date": REFERENCE_DATE,
            "price_rm": price_rm,
            "unit": source_unit,
            "mass_g": mass_g,
            "per_kg": price_per_kg,
            "per_100g": price_per_100g,
            "dataset": REFERENCE_DATASET,
        },
    )
    connection.execute(
        sa.text(
            """
            INSERT INTO unit_conversion (
                canonical_food_id, conversion_type, source_unit, target_unit,
                factor, production_eligible, evidence_note
            )
            SELECT CAST(:food_id AS varchar), 'PURCHASE_MASS',
                   CAST(:unit AS varchar), 'g', CAST(:mass_g AS numeric), true,
                   CAST(:evidence AS text)
            WHERE NOT EXISTS (
                SELECT 1 FROM unit_conversion
                WHERE canonical_food_id=CAST(:food_id AS varchar)
                  AND conversion_type='PURCHASE_MASS'
                  AND production_eligible=true
                  AND factor=CAST(:mass_g AS numeric)
            )
            """
        ),
        {
            "food_id": row["food_id"],
            "unit": source_unit,
            "mass_g": mass_g,
            "evidence": evidence,
        },
    )


def upgrade() -> None:
    data = load_review_data()
    connection = op.get_bind()
    review_source = data["review_source"]

    for recipe_id, step_number, food_id in data["step_food_links"]:
        connection.execute(
            sa.text(
                """
                INSERT INTO recipe_cooking_step_food (
                    recipe_cooking_step_id, canonical_food_id
                )
                SELECT recipe_cooking_step_id, :food_id
                FROM recipe_cooking_step
                WHERE recipe_id=:recipe_id AND step_number=:step_number
                ON CONFLICT DO NOTHING
                """
            ),
            {
                "recipe_id": recipe_id,
                "step_number": step_number,
                "food_id": food_id,
            },
        )

    for row in data["safety_profiles"]:
        connection.execute(
            sa.text(
                """
                INSERT INTO food_safety_profile (
                    canonical_food_id, vegetarian, vegan, contains_pork,
                    allergen_assessment_complete, review_status, version,
                    review_source, reviewed_at
                ) VALUES (
                    :food_id, :vegetarian, :vegan, :contains_pork, true,
                    'APPROVED', 2, :source, :reviewed_at
                )
                ON CONFLICT (canonical_food_id) DO UPDATE SET
                    vegetarian=excluded.vegetarian,
                    vegan=excluded.vegan,
                    contains_pork=excluded.contains_pork,
                    allergen_assessment_complete=true,
                    review_status='APPROVED',
                    version=2,
                    review_source=excluded.review_source,
                    reviewed_at=excluded.reviewed_at
                """
            ),
            {
                **row,
                "source": review_source,
                "reviewed_at": datetime.now(UTC),
            },
        )

    food_ids = tuple(row["food_id"] for row in data["safety_profiles"])
    connection.execute(
        sa.text(
            "DELETE FROM food_allergen WHERE canonical_food_id IN :food_ids"
        ).bindparams(sa.bindparam("food_ids", expanding=True, value=food_ids))
    )
    for food_id, codes in data["allergens"].items():
        for code in codes:
            connection.execute(
                sa.text(
                    "INSERT INTO food_allergen (canonical_food_id, allergen_code) "
                    "VALUES (:food_id, :code)"
                ),
                {"food_id": food_id, "code": code},
            )

    reviewer_id = ensure_reviewer(connection)
    location_id = ensure_reference_location(connection)
    for row in data["reference_prices"]:
        upsert_reference_price(connection, row, reviewer_id, location_id)

    connection.execute(
        sa.text(
            """
            UPDATE recipe_catalog
            SET review_status='APPROVED',
                optimizer_eligible=(meal_type='COMPLETE_MEAL'),
                recipe_version=3,
                review_source=:source,
                reviewed_at=:reviewed_at
            WHERE active
            """
        ),
        {"source": review_source, "reviewed_at": datetime.now(UTC)},
    )


def downgrade() -> None:
    data = load_review_data()
    connection = op.get_bind()
    recipe_ids = tuple({row[0] for row in data["step_food_links"]})
    connection.execute(
        sa.text(
            """
            DELETE FROM recipe_cooking_step_food
            WHERE recipe_cooking_step_id IN (
                SELECT recipe_cooking_step_id FROM recipe_cooking_step
                WHERE recipe_id IN :recipe_ids
            )
            """
        ).bindparams(sa.bindparam("recipe_ids", expanding=True, value=recipe_ids))
    )
    for recipe_id, step_number, food_id in INITIAL_STEP_FOOD_LINKS:
        connection.execute(
            sa.text(
                """
                INSERT INTO recipe_cooking_step_food (
                    recipe_cooking_step_id, canonical_food_id
                )
                SELECT recipe_cooking_step_id, :food_id
                FROM recipe_cooking_step
                WHERE recipe_id=:recipe_id AND step_number=:step_number
                """
            ),
            {
                "recipe_id": recipe_id,
                "step_number": step_number,
                "food_id": food_id,
            },
        )

    food_ids = tuple(row["food_id"] for row in data["safety_profiles"])
    connection.execute(
        sa.text(
            "DELETE FROM food_allergen WHERE canonical_food_id IN :food_ids"
        ).bindparams(sa.bindparam("food_ids", expanding=True, value=food_ids))
    )
    connection.execute(
        sa.text(
            "INSERT INTO food_allergen (canonical_food_id, allergen_code) "
            "VALUES ('SF018', 'EGG')"
        )
    )
    connection.execute(
        sa.text(
            "DELETE FROM food_safety_profile "
            "WHERE canonical_food_id NOT IN :initial_ids"
        ).bindparams(
            sa.bindparam(
                "initial_ids",
                expanding=True,
                value=INITIAL_SAFETY_FOOD_IDS,
            )
        )
    )
    connection.execute(
        sa.text(
            """
            UPDATE food_safety_profile
            SET version=1, review_source=:source
            WHERE canonical_food_id IN :initial_ids
            """
        ).bindparams(
            sa.bindparam("source", value=INITIAL_REVIEW_SOURCE),
            sa.bindparam(
                "initial_ids",
                expanding=True,
                value=INITIAL_SAFETY_FOOD_IDS,
            ),
        )
    )

    for row in data["reference_prices"]:
        connection.execute(
            sa.text(
                """
                DELETE FROM food_price_observation
                WHERE source_item_code=:code
                  AND source_dataset_version=:dataset
                """
            ),
            {"code": row["source_item_code"], "dataset": REFERENCE_DATASET},
        )
        connection.execute(
            sa.text(
                """
                DELETE FROM source_food_mapping
                WHERE source_system='WISEBASKET_REFERENCE'
                  AND source_dataset_version=:dataset
                  AND source_food_id=:code
                """
            ),
            {"code": row["source_item_code"], "dataset": REFERENCE_DATASET},
        )
        connection.execute(
            sa.text(
                """
                DELETE FROM unit_conversion
                WHERE canonical_food_id=:food_id
                  AND conversion_type='PURCHASE_MASS'
                  AND factor=:mass_g
                  AND evidence_note LIKE 'Governed Jaya Grocer reference%'
                """
            ),
            {
                "food_id": row["food_id"],
                "mass_g": Decimal(row["package_mass_g"]),
            },
        )

    connection.execute(
        sa.text(
            """
            UPDATE recipe_catalog
            SET review_status=CASE
                    WHEN recipe_id IN :initial THEN 'APPROVED'
                    ELSE 'DRAFT'
                END,
                optimizer_eligible=(recipe_id IN :initial),
                recipe_version=2,
                review_source=CASE
                    WHEN recipe_id IN :initial THEN :initial_source
                    ELSE :previous_source
                END,
                reviewed_at=CASE
                    WHEN recipe_id IN :initial THEN reviewed_at
                    ELSE NULL
                END
            WHERE active
            """
        ).bindparams(
            sa.bindparam("initial", expanding=True, value=INITIAL_RECIPES),
            sa.bindparam("initial_source", value=INITIAL_REVIEW_SOURCE),
            sa.bindparam("previous_source", value=PREVIOUS_REVIEW_SOURCE),
        )
    )
