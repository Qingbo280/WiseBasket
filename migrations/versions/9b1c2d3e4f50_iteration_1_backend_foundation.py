"""iteration 1 backend foundation

Revision ID: 9b1c2d3e4f50
Revises: 24ebf6c51805
Create Date: 2026-08-28 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9b1c2d3e4f50"
down_revision: Union[str, Sequence[str], None] = "24ebf6c51805"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Declares to scripts/validate_canonical_id_ledger.py that the FINAL
# authoritative identities seeded here live in the bundled JSON data
# (applied last, overriding every later corrective/cleanup migration).
LEDGER_SOURCE_JSON = ("new_canonical_foods_201.json",)


def upgrade() -> None:
    op.create_table(
        "app_user",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("email_normalized", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("email_verified", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("role in ('USER', 'ADMIN')", name="ck_app_user_role"),
        sa.CheckConstraint("status in ('ACTIVE', 'DISABLED', 'LOCKED')", name="ck_app_user_status"),
        sa.PrimaryKeyConstraint("user_id"),
        sa.UniqueConstraint("email_normalized"),
    )
    op.create_table(
        "user_profile",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.create_table(
        "admin_profile",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("admin_level", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("admin_level in ('ADMIN', 'SUPER_ADMIN')", name="ck_admin_profile_level"),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.create_table(
        "auth_session",
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("refresh_token_hash", sa.Text(), nullable=False),
        sa.Column("client_type", sa.String(length=16), nullable=False),
        sa.Column("device_name", sa.String(length=160), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("client_type in ('MOBILE', 'ADMIN_WEB')", name="ck_auth_session_client_type"),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("session_id"),
    )
    op.add_column("households", sa.Column("owner_user_id", sa.Uuid(), nullable=True))
    op.add_column("households", sa.Column("adults", sa.Integer(), server_default="1", nullable=False))
    op.add_column("households", sa.Column("children", sa.Integer(), server_default="0", nullable=False))
    op.add_column("households", sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False))
    op.add_column("households", sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False))
    op.alter_column("households", "name", existing_type=sa.String(length=100), nullable=True)
    op.create_foreign_key("fk_households_owner_user_id", "households", "app_user", ["owner_user_id"], ["user_id"], ondelete="SET NULL")
    op.create_check_constraint("ck_households_adults_nonnegative", "households", "adults >= 0")
    op.create_check_constraint("ck_households_children_nonnegative", "households", "children >= 0")
    op.create_check_constraint("ck_households_has_member", "households", "adults + children > 0")

    op.create_table(
        "hard_exclusion",
        sa.Column("exclusion_code", sa.String(length=40), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("exclusion_code"),
    )
    hard_exclusion = sa.table(
        "hard_exclusion",
        sa.column("exclusion_code", sa.String),
        sa.column("display_name", sa.String),
        sa.column("active", sa.Boolean),
    )
    op.bulk_insert(
        hard_exclusion,
        [
            {"exclusion_code": "PEANUTS", "display_name": "Peanuts", "active": True},
            {"exclusion_code": "SHELLFISH", "display_name": "Shellfish", "active": True},
            {"exclusion_code": "EGGS", "display_name": "Eggs", "active": True},
            {"exclusion_code": "MILK", "display_name": "Milk", "active": True},
            {"exclusion_code": "VEGETARIAN", "display_name": "Vegetarian", "active": True},
            {"exclusion_code": "NO_PORK", "display_name": "No pork", "active": True},
        ],
    )

    op.create_table(
        "canonical_food",
        sa.Column("canonical_food_id", sa.String(length=32), nullable=False),
        sa.Column("canonical_name", sa.String(length=240), nullable=False),
        sa.Column("canonical_name_ms", sa.String(length=240), nullable=True),
        sa.Column("category", sa.String(length=80), nullable=False),
        sa.Column("food_form", sa.String(length=80), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("status in ('ACTIVE', 'BLOCKED', 'RETIRED')", name="ck_canonical_food_status"),
        sa.PrimaryKeyConstraint("canonical_food_id"),
    )
    canonical_food = sa.table(
        "canonical_food",
        sa.column("canonical_food_id", sa.String),
        sa.column("canonical_name", sa.String),
        sa.column("canonical_name_ms", sa.String),
        sa.column("category", sa.String),
        sa.column("status", sa.String),
    )
    # Seed the Data-team 201-food namespace as the single authority, plus the
    # one WiseBasket extension (SF202 sweet potato, carried over from the
    # pre-rebuild SF018 identity). This foundation deliberately seeds the NEW
    # namespace: fresh databases (CI, rebuilds) never contain the old one.
    import json
    from pathlib import Path

    _data_dir = Path(__file__).resolve().parent.parent / "data"
    _foods = json.loads((_data_dir / "new_canonical_foods_201.json").read_text(encoding="utf-8"))
    _addon = json.loads((_data_dir / "sweet_potato_addon.json").read_text(encoding="utf-8"))
    op.bulk_insert(
        canonical_food,
        [
            {"canonical_food_id": f["canonical_food_id"], "canonical_name": f["canonical_name"],
             "canonical_name_ms": f["canonical_name_ms"], "category": f["category"], "status": "ACTIVE"}
            for f in [_addon, *_foods]
        ],
    )

    op.create_table("food_alias", sa.Column("food_alias_id", sa.Integer(), autoincrement=True, nullable=False), sa.Column("canonical_food_id", sa.String(length=32), nullable=False), sa.Column("alias_name", sa.String(length=240), nullable=False), sa.Column("language", sa.String(length=12), nullable=False), sa.Column("source_system", sa.String(length=80), nullable=False), sa.ForeignKeyConstraint(["canonical_food_id"], ["canonical_food.canonical_food_id"]), sa.PrimaryKeyConstraint("food_alias_id"), sa.UniqueConstraint("alias_name", "language", "source_system", name="uq_food_alias_name_language_source"))
    op.create_table(
        "source_food_mapping",
        sa.Column("source_food_mapping_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source_system", sa.String(length=80), nullable=False),
        sa.Column("source_dataset_version", sa.String(length=80), nullable=False),
        sa.Column("source_food_id", sa.String(length=120), nullable=False),
        sa.Column("source_food_name", sa.String(length=240), nullable=False),
        sa.Column("source_unit_or_form", sa.String(length=80), nullable=True),
        sa.Column("canonical_food_id", sa.String(length=32), nullable=True),
        sa.Column("mapping_status", sa.String(length=32), nullable=False),
        sa.Column("verification_status", sa.String(length=32), nullable=False),
        sa.Column("review_status", sa.String(length=32), nullable=False),
        sa.Column("evidence_note", sa.Text(), nullable=True),
        sa.Column("reviewed_by", sa.Uuid(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("variant_metadata", sa.Text(), nullable=True),
        sa.CheckConstraint("mapping_status in ('CANDIDATE','EXACT','ACCEPTED_EQUIVALENT','NEEDS_CONVERSION','AMBIGUOUS','UNMAPPED','EXCLUDED')", name="ck_source_food_mapping_status"),
        sa.CheckConstraint("verification_status in ('NOT_VERIFIED','VERIFIED','REJECTED')", name="ck_source_food_mapping_verification"),
        sa.CheckConstraint("review_status in ('PENDING','APPROVED','REJECTED')", name="ck_source_food_mapping_review"),
        sa.CheckConstraint("review_status != 'APPROVED' or (reviewed_by is not null and reviewed_at is not null)", name="ck_source_food_mapping_approval_attribution"),
        sa.ForeignKeyConstraint(["canonical_food_id"], ["canonical_food.canonical_food_id"]),
        sa.ForeignKeyConstraint(["reviewed_by"], ["app_user.user_id"]),
        sa.PrimaryKeyConstraint("source_food_mapping_id"),
        sa.UniqueConstraint("source_system", "source_dataset_version", "source_food_id", name="uq_source_food_mapping_source_record"),
    )
    op.create_table(
        "food_nutrition",
        sa.Column("nutrition_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("canonical_food_id", sa.String(length=32), nullable=False),
        sa.Column("applies_to_item_code", sa.String(length=120), nullable=True),
        sa.Column("source_dataset_version", sa.String(length=80), nullable=False),
        sa.Column("source_record_id", sa.String(length=120), nullable=False),
        sa.Column("basis_g", sa.Numeric(10, 3), nullable=False),
        sa.Column("energy_kcal", sa.Numeric(12, 4), nullable=True),
        sa.Column("protein_g", sa.Numeric(12, 4), nullable=True),
        sa.Column("fat_g", sa.Numeric(12, 4), nullable=True),
        sa.Column("carbohydrate_g", sa.Numeric(12, 4), nullable=True),
        sa.Column("fibre_g", sa.Numeric(12, 4), nullable=True),
        sa.Column("fibre_basis", sa.String(length=32), nullable=True),
        sa.Column("iron_mg", sa.Numeric(12, 4), nullable=True),
        sa.Column("calcium_mg", sa.Numeric(12, 4), nullable=True),
        sa.Column("vitamin_a_ug", sa.Numeric(12, 4), nullable=True),
        sa.Column("vitamin_a_basis", sa.String(length=32), nullable=True),
        sa.Column("vitamin_c_mg", sa.Numeric(12, 4), nullable=True),
        sa.Column("quality_status", sa.String(length=16), nullable=False),
        sa.Column("is_current", sa.Boolean(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("source_retrieved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("basis_g > 0", name="ck_food_nutrition_basis_positive"),
        sa.CheckConstraint("quality_status in ('PASS','WARN','BLOCK')", name="ck_food_nutrition_quality"),
        sa.CheckConstraint("fibre_basis is null or fibre_basis in ('AOAC','NSP','UNKNOWN')", name="ck_food_nutrition_fibre_basis"),
        sa.CheckConstraint("vitamin_a_basis is null or vitamin_a_basis in ('RAE','RE','UNKNOWN')", name="ck_food_nutrition_vitamin_a_basis"),
        sa.ForeignKeyConstraint(["canonical_food_id"], ["canonical_food.canonical_food_id"]),
        sa.PrimaryKeyConstraint("nutrition_id"),
        sa.UniqueConstraint("source_dataset_version", "source_record_id", "canonical_food_id", name="uq_food_nutrition_source_record"),
    )
    op.create_table("food_asset", sa.Column("food_asset_id", sa.Integer(), autoincrement=True, nullable=False), sa.Column("canonical_food_id", sa.String(length=32), nullable=False), sa.Column("asset_type", sa.String(length=16), nullable=False), sa.Column("object_key", sa.Text(), nullable=False), sa.Column("alt_text", sa.String(length=240), nullable=True), sa.Column("is_primary", sa.Boolean(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.CheckConstraint("asset_type in ('IMAGE','THUMBNAIL')", name="ck_food_asset_type"), sa.ForeignKeyConstraint(["canonical_food_id"], ["canonical_food.canonical_food_id"]), sa.PrimaryKeyConstraint("food_asset_id"))
    op.create_index("uq_food_asset_primary_image", "food_asset", ["canonical_food_id"], unique=True, postgresql_where=sa.text("is_primary and asset_type = 'IMAGE'"))
    op.create_table("location", sa.Column("location_id", sa.Integer(), autoincrement=True, nullable=False), sa.Column("source_premise_code", sa.String(length=120), nullable=True), sa.Column("location_name", sa.String(length=240), nullable=False), sa.Column("premise_type", sa.String(length=80), nullable=True), sa.Column("state", sa.String(length=80), nullable=True), sa.Column("district", sa.String(length=120), nullable=True), sa.Column("address", sa.Text(), nullable=True), sa.Column("latitude", sa.Numeric(10, 7), nullable=True), sa.Column("longitude", sa.Numeric(10, 7), nullable=True), sa.Column("active", sa.Boolean(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.CheckConstraint("latitude is null or (latitude >= -90 and latitude <= 90)", name="ck_location_latitude"), sa.CheckConstraint("longitude is null or (longitude >= -180 and longitude <= 180)", name="ck_location_longitude"), sa.PrimaryKeyConstraint("location_id"), sa.UniqueConstraint("source_premise_code"))
    op.create_table("unit_conversion", sa.Column("unit_conversion_id", sa.Integer(), autoincrement=True, nullable=False), sa.Column("canonical_food_id", sa.String(length=32), nullable=True), sa.Column("conversion_type", sa.String(length=32), nullable=False), sa.Column("source_unit", sa.String(length=80), nullable=True), sa.Column("target_unit", sa.String(length=80), nullable=True), sa.Column("factor", sa.Numeric(14, 8), nullable=True), sa.Column("edible_yield_fraction", sa.Numeric(8, 6), nullable=True), sa.Column("production_eligible", sa.Boolean(), nullable=False), sa.Column("evidence_note", sa.Text(), nullable=True), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.CheckConstraint("conversion_type in ('PURCHASE_MASS','EDIBLE_YIELD')", name="ck_unit_conversion_type"), sa.CheckConstraint("not production_eligible or factor is not null or edible_yield_fraction is not null", name="ck_unit_conversion_production_has_factor"), sa.CheckConstraint("edible_yield_fraction is null or (edible_yield_fraction > 0 and edible_yield_fraction <= 1)", name="ck_unit_conversion_edible_yield"), sa.ForeignKeyConstraint(["canonical_food_id"], ["canonical_food.canonical_food_id"]), sa.PrimaryKeyConstraint("unit_conversion_id"))
    op.create_table("etl_run", sa.Column("etl_run_id", sa.Integer(), autoincrement=True, nullable=False), sa.Column("pipeline_version", sa.String(length=80), nullable=False), sa.Column("source_system", sa.String(length=80), nullable=False), sa.Column("source_vintage", sa.String(length=80), nullable=True), sa.Column("started_at", sa.DateTime(timezone=True), nullable=False), sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True), sa.Column("status", sa.String(length=16), nullable=False), sa.Column("rows_in", sa.Integer(), nullable=True), sa.Column("rows_out", sa.Integer(), nullable=True), sa.Column("rows_blocked", sa.Integer(), nullable=True), sa.CheckConstraint("status in ('RUNNING','PASS','FAIL')", name="ck_etl_run_status"), sa.PrimaryKeyConstraint("etl_run_id"))
    op.create_table("food_price_observation", sa.Column("price_observation_id", sa.Integer(), autoincrement=True, nullable=False), sa.Column("canonical_food_id", sa.String(length=32), nullable=True), sa.Column("source_item_code", sa.String(length=120), nullable=False), sa.Column("source_food_name", sa.String(length=240), nullable=False), sa.Column("source_premise_code", sa.String(length=120), nullable=True), sa.Column("location_id", sa.Integer(), nullable=False), sa.Column("observed_date", sa.Date(), nullable=False), sa.Column("price_rm", sa.Numeric(12, 2), nullable=False), sa.Column("original_unit", sa.String(length=80), nullable=True), sa.Column("purchase_mass_g", sa.Numeric(12, 3), nullable=True), sa.Column("price_rm_per_kg_purchase", sa.Numeric(12, 4), nullable=True), sa.Column("price_rm_per_100g_purchase", sa.Numeric(12, 4), nullable=True), sa.Column("edible_yield_fraction", sa.Numeric(8, 6), nullable=True), sa.Column("price_rm_per_100g_edible", sa.Numeric(12, 4), nullable=True), sa.Column("source_dataset_version", sa.String(length=80), nullable=False), sa.Column("etl_run_id", sa.Integer(), nullable=True), sa.Column("quality_status", sa.String(length=16), nullable=False), sa.CheckConstraint("price_rm >= 0", name="ck_food_price_observation_price_nonnegative"), sa.CheckConstraint("quality_status in ('PASS','WARN','BLOCK')", name="ck_food_price_observation_quality"), sa.ForeignKeyConstraint(["canonical_food_id"], ["canonical_food.canonical_food_id"]), sa.ForeignKeyConstraint(["etl_run_id"], ["etl_run.etl_run_id"]), sa.ForeignKeyConstraint(["location_id"], ["location.location_id"]), sa.PrimaryKeyConstraint("price_observation_id"), sa.UniqueConstraint("source_item_code", "location_id", "observed_date", "source_dataset_version", name="uq_food_price_observation_logical"))
    op.create_table("rni_reference", sa.Column("rni_reference_id", sa.Integer(), autoincrement=True, nullable=False), sa.Column("nutrient", sa.String(length=80), nullable=False), sa.Column("age_group", sa.String(length=80), nullable=True), sa.Column("sex", sa.String(length=20), nullable=True), sa.Column("life_stage", sa.String(length=80), nullable=True), sa.Column("value", sa.Numeric(12, 4), nullable=True), sa.Column("unit", sa.String(length=40), nullable=False), sa.Column("scenario", sa.String(length=120), nullable=True), sa.Column("selected_for_optimizer", sa.Boolean(), nullable=False), sa.Column("profile", sa.String(length=120), nullable=True), sa.Column("pal", sa.String(length=80), nullable=True), sa.Column("source_note", sa.Text(), nullable=True), sa.PrimaryKeyConstraint("rni_reference_id"))
    op.create_table("data_quality_issue", sa.Column("data_quality_issue_id", sa.Integer(), autoincrement=True, nullable=False), sa.Column("etl_run_id", sa.Integer(), nullable=True), sa.Column("rule_code", sa.String(length=80), nullable=False), sa.Column("severity", sa.String(length=16), nullable=False), sa.Column("source_row", sa.Text(), nullable=True), sa.Column("canonical_food_id", sa.String(length=32), nullable=True), sa.Column("reason", sa.Text(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.CheckConstraint("severity in ('INFO','WARN','BLOCK')", name="ck_data_quality_issue_severity"), sa.ForeignKeyConstraint(["canonical_food_id"], ["canonical_food.canonical_food_id"]), sa.ForeignKeyConstraint(["etl_run_id"], ["etl_run.etl_run_id"]), sa.PrimaryKeyConstraint("data_quality_issue_id"))
    op.create_table("planning_request", sa.Column("planning_request_id", sa.Uuid(), nullable=False), sa.Column("household_id", sa.Integer(), nullable=False), sa.Column("available_budget_rm", sa.Numeric(12, 2), nullable=False), sa.Column("planning_days", sa.Integer(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.CheckConstraint("available_budget_rm > 0", name="ck_planning_request_budget_positive"), sa.CheckConstraint("planning_days > 0", name="ck_planning_request_days_positive"), sa.ForeignKeyConstraint(["household_id"], ["households.id"]), sa.PrimaryKeyConstraint("planning_request_id"))
    op.create_table("planning_request_exclusion", sa.Column("planning_request_id", sa.Uuid(), nullable=False), sa.Column("exclusion_code", sa.String(length=40), nullable=False), sa.ForeignKeyConstraint(["exclusion_code"], ["hard_exclusion.exclusion_code"]), sa.ForeignKeyConstraint(["planning_request_id"], ["planning_request.planning_request_id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("planning_request_id", "exclusion_code"))
    op.create_table("hard_exclusion_food", sa.Column("exclusion_code", sa.String(length=40), nullable=False), sa.Column("canonical_food_id", sa.String(length=32), nullable=False), sa.ForeignKeyConstraint(["canonical_food_id"], ["canonical_food.canonical_food_id"], ondelete="CASCADE"), sa.ForeignKeyConstraint(["exclusion_code"], ["hard_exclusion.exclusion_code"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("exclusion_code", "canonical_food_id"))
    hard_exclusion_food = sa.table("hard_exclusion_food", sa.column("exclusion_code", sa.String), sa.column("canonical_food_id", sa.String))
    # Allergy filter rows against the NEW namespace identities (namespace
    # rebuild 2026-09; SF202 addon keeps sweet potato available). Every pair
    # is identity-exact; scripts/audit_crosswalk_identity.py + the import
    # validator fail closed if any of these ever drift.
    op.bulk_insert(hard_exclusion_food, [
        {"exclusion_code": "EGGS", "canonical_food_id": "SF018"},        # chicken egg
        {"exclusion_code": "MILK", "canonical_food_id": "SF176"},        # fresh / UHT milk
        {"exclusion_code": "NO_PORK", "canonical_food_id": "SF009"},     # pork (lean & fat)
        {"exclusion_code": "PEANUTS", "canonical_food_id": "SF127"},     # peanuts
        {"exclusion_code": "SHELLFISH", "canonical_food_id": "SF131"},  # oyster sauce (pre-build semantic, reported to data team)
        {"exclusion_code": "VEGETARIAN", "canonical_food_id": "SF006"},  # whole chicken
        {"exclusion_code": "VEGETARIAN", "canonical_food_id": "SF051"},  # dried anchovy
        {"exclusion_code": "VEGETARIAN", "canonical_food_id": "SF156"},  # canned sardine in tomato sauce
    ])
    op.create_table("planning_location", sa.Column("planning_request_id", sa.Uuid(), nullable=False), sa.Column("latitude", sa.Numeric(10, 7), nullable=False), sa.Column("longitude", sa.Numeric(10, 7), nullable=False), sa.Column("location_source", sa.String(length=16), nullable=False), sa.Column("selected_state", sa.String(length=80), nullable=True), sa.Column("selected_district", sa.String(length=120), nullable=True), sa.CheckConstraint("latitude >= -90 and latitude <= 90", name="ck_planning_location_latitude"), sa.CheckConstraint("longitude >= -180 and longitude <= 180", name="ck_planning_location_longitude"), sa.CheckConstraint("location_source in ('GPS','MANUAL')", name="ck_planning_location_source"), sa.ForeignKeyConstraint(["planning_request_id"], ["planning_request.planning_request_id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("planning_request_id"))
    op.create_table("meal_template", sa.Column("meal_template_id", sa.Integer(), autoincrement=True, nullable=False), sa.Column("meal_name", sa.String(length=160), nullable=False), sa.Column("meal_type", sa.String(length=16), nullable=True), sa.Column("servings", sa.Integer(), nullable=False), sa.Column("active", sa.Boolean(), nullable=False), sa.CheckConstraint("servings > 0", name="ck_meal_template_servings_positive"), sa.CheckConstraint("meal_type is null or meal_type in ('BREAKFAST','LUNCH','DINNER','SNACK')", name="ck_meal_template_type"), sa.PrimaryKeyConstraint("meal_template_id"))
    op.create_table("meal_template_ingredient", sa.Column("meal_template_id", sa.Integer(), nullable=False), sa.Column("canonical_food_id", sa.String(length=32), nullable=False), sa.Column("grams_per_serving", sa.Numeric(10, 2), nullable=False), sa.CheckConstraint("grams_per_serving > 0", name="ck_meal_template_ingredient_grams_positive"), sa.ForeignKeyConstraint(["canonical_food_id"], ["canonical_food.canonical_food_id"]), sa.ForeignKeyConstraint(["meal_template_id"], ["meal_template.meal_template_id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("meal_template_id", "canonical_food_id"))
    op.create_table("generated_plan", sa.Column("plan_id", sa.Uuid(), nullable=False), sa.Column("planning_request_id", sa.Uuid(), nullable=False), sa.Column("optimizer_version", sa.String(length=40), nullable=False), sa.Column("generation_method", sa.String(length=32), nullable=False), sa.Column("status", sa.String(length=16), nullable=False), sa.Column("estimated_total_cost_rm", sa.Numeric(12, 2), nullable=False), sa.Column("remaining_budget_rm", sa.Numeric(12, 2), nullable=False), sa.Column("solver_runtime_ms", sa.Integer(), nullable=True), sa.Column("selected_store_option_id", sa.Integer(), nullable=True), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.CheckConstraint("generation_method in ('OPTIMIZER','OPTIMIZER_AI_ASSISTED')", name="ck_generated_plan_method"), sa.CheckConstraint("status in ('FEASIBLE','TIGHT','INFEASIBLE')", name="ck_generated_plan_status"), sa.CheckConstraint("estimated_total_cost_rm >= 0", name="ck_generated_plan_total_nonnegative"), sa.ForeignKeyConstraint(["planning_request_id"], ["planning_request.planning_request_id"]), sa.PrimaryKeyConstraint("plan_id"))
    op.create_table("generated_plan_item", sa.Column("generated_plan_item_id", sa.Integer(), autoincrement=True, nullable=False), sa.Column("plan_id", sa.Uuid(), nullable=False), sa.Column("canonical_food_id", sa.String(length=32), nullable=False), sa.Column("quantity", sa.Numeric(12, 3), nullable=False), sa.Column("quantity_unit", sa.String(length=24), nullable=False), sa.Column("estimated_cost_rm", sa.Numeric(12, 2), nullable=False), sa.CheckConstraint("quantity > 0", name="ck_generated_plan_item_quantity_positive"), sa.CheckConstraint("estimated_cost_rm >= 0", name="ck_generated_plan_item_cost_nonnegative"), sa.ForeignKeyConstraint(["canonical_food_id"], ["canonical_food.canonical_food_id"]), sa.ForeignKeyConstraint(["plan_id"], ["generated_plan.plan_id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("generated_plan_item_id"))
    op.create_table("plan_store_option", sa.Column("plan_store_option_id", sa.Integer(), autoincrement=True, nullable=False), sa.Column("plan_id", sa.Uuid(), nullable=False), sa.Column("location_id", sa.Integer(), nullable=False), sa.Column("distance_km", sa.Numeric(10, 3), nullable=False), sa.Column("basket_cost_rm", sa.Numeric(12, 2), nullable=True), sa.Column("items_available", sa.Integer(), nullable=False), sa.Column("items_missing", sa.Integer(), nullable=False), sa.Column("price_coverage_ratio", sa.Numeric(6, 5), nullable=False), sa.Column("recommendation_rank", sa.Integer(), nullable=False), sa.Column("recommendation_type", sa.String(length=16), nullable=False), sa.Column("is_selected", sa.Boolean(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.CheckConstraint("recommendation_type in ('NEAREST','CHEAPEST','BEST_VALUE')", name="ck_plan_store_option_type"), sa.CheckConstraint("items_available >= 0 and items_missing >= 0", name="ck_plan_store_option_item_counts"), sa.CheckConstraint("price_coverage_ratio >= 0 and price_coverage_ratio <= 1", name="ck_plan_store_option_coverage"), sa.ForeignKeyConstraint(["location_id"], ["location.location_id"]), sa.ForeignKeyConstraint(["plan_id"], ["generated_plan.plan_id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("plan_store_option_id"))
    op.create_index("uq_plan_store_option_selected", "plan_store_option", ["plan_id"], unique=True, postgresql_where=sa.text("is_selected"))
    op.create_table("plan_store_item", sa.Column("plan_store_option_id", sa.Integer(), nullable=False), sa.Column("canonical_food_id", sa.String(length=32), nullable=False), sa.Column("price_observation_id", sa.Integer(), nullable=True), sa.Column("estimated_cost_rm", sa.Numeric(12, 2), nullable=True), sa.Column("available", sa.Boolean(), nullable=False), sa.ForeignKeyConstraint(["canonical_food_id"], ["canonical_food.canonical_food_id"]), sa.ForeignKeyConstraint(["plan_store_option_id"], ["plan_store_option.plan_store_option_id"], ondelete="CASCADE"), sa.ForeignKeyConstraint(["price_observation_id"], ["food_price_observation.price_observation_id"]), sa.PrimaryKeyConstraint("plan_store_option_id", "canonical_food_id"))

    # --- SF202 sweet potato addon child data (carried over from pre-rebuild ---
    # --- SF018; the addon JSON is the single source of truth) -------------
    for _a in _addon["aliases"]:
        op.execute(
            sa.text("insert into food_alias (canonical_food_id, alias_name, language, source_system) "
                    "values ('SF202', :name, :lang, :src)")
            .bindparams(name=_a["alias_name"], lang=_a["language"], src=_a["source_system"])
        )
    for _m in _addon["mappings"]:
        op.execute(
            sa.text("insert into source_food_mapping (source_system, source_dataset_version, source_food_id, "
                    "source_food_name, source_unit_or_form, canonical_food_id, mapping_status, "
                    "verification_status, review_status, evidence_note) "
                    "values (:s, :v, :fid, :name, :unit, 'SF202', :ms, :vs, 'PENDING', :note)")
            .bindparams(s=_m["source_system"], v=_m["source_dataset_version"], fid=_m["source_food_id"],
                        name=_m["source_food_name"], unit=_m["source_unit_or_form"],
                        ms=_m["mapping_status"], vs=_m["verification_status"], note=_m["evidence_note"])
        )
    _n = _addon["nutrition"]
    op.execute(
        sa.text("insert into food_nutrition (canonical_food_id, source_dataset_version, source_record_id, "
                "basis_g, energy_kcal, protein_g, fat_g, carbohydrate_g, quality_status, is_current, "
                "source_url) "
                "values ('SF202', :v, :rec, :basis, :kcal, :protein, :fat, :carbs, :qs, true, :note)")
        .bindparams(v=_n["source_dataset_version"], rec=_n["source_record_id"], basis=_n["basis_g"],
                    kcal=_n["energy_kcal"], protein=_n["protein_g"], fat=_n["fat_g"],
                    carbs=_n["carbohydrate_g"], qs=_n["quality_status"], note=_n["evidence_note"])
    )
    for _u in _addon["unit_conversions"]:
        op.execute(
            sa.text("insert into unit_conversion (canonical_food_id, conversion_type, source_unit, factor, "
                    "edible_yield_fraction, production_eligible, evidence_note) "
                    "values ('SF202', :ct, :unit, :factor, :y, :eligible, :note)")
            .bindparams(ct=_u["conversion_type"], unit=_u["source_unit"], factor=_u["factor"],
                        y=_u["edible_yield_fraction"], eligible=_u["production_eligible"],
                        note=_u["evidence_note"])
        )

    op.execute(
        """
        create or replace view v_latest_food_price as
        select *
        from (
            select fpo.*,
                   row_number() over (
                     partition by fpo.canonical_food_id, fpo.location_id
                     order by fpo.observed_date desc, fpo.price_observation_id desc
                   ) as rn
            from food_price_observation fpo
            where fpo.quality_status = 'PASS'
              and fpo.canonical_food_id is not null
              and fpo.price_rm_per_100g_edible is not null
        ) latest
        where rn = 1
        """
    )
    op.execute(
        """
        create or replace view v_optimizer_food_candidate as
        select cf.canonical_food_id,
               cf.canonical_name,
               cf.category,
               fn.basis_g,
               fn.energy_kcal,
               fn.protein_g,
               fn.fat_g,
               fn.carbohydrate_g,
               fn.fibre_g,
               fn.iron_mg,
               fn.calcium_mg,
               fn.vitamin_a_ug,
               fn.vitamin_c_mg,
               lfp.location_id,
               lfp.observed_date,
               lfp.price_rm_per_100g_edible,
               lfp.quality_status as price_quality_status,
               fn.quality_status as nutrition_quality_status
        from canonical_food cf
        join food_nutrition fn on fn.canonical_food_id = cf.canonical_food_id
        join v_latest_food_price lfp on lfp.canonical_food_id = cf.canonical_food_id
        where cf.status = 'ACTIVE'
          and fn.is_current = true
          and fn.quality_status in ('PASS', 'WARN')
          and lfp.quality_status = 'PASS'
        """
    )


def downgrade() -> None:
    op.execute("drop view if exists v_optimizer_food_candidate")
    op.execute("drop view if exists v_latest_food_price")
    op.drop_table("plan_store_item")
    op.drop_index("uq_plan_store_option_selected", table_name="plan_store_option", postgresql_where=sa.text("is_selected"))
    op.drop_table("plan_store_option")
    op.drop_table("generated_plan_item")
    op.drop_table("generated_plan")
    op.drop_table("meal_template_ingredient")
    op.drop_table("meal_template")
    op.drop_table("planning_location")
    op.drop_table("hard_exclusion_food")
    op.drop_table("planning_request_exclusion")
    op.drop_table("planning_request")
    op.drop_table("data_quality_issue")
    op.drop_table("rni_reference")
    op.drop_table("food_price_observation")
    op.drop_table("etl_run")
    op.drop_table("unit_conversion")
    op.drop_table("location")
    op.drop_index("uq_food_asset_primary_image", table_name="food_asset", postgresql_where=sa.text("is_primary and asset_type = 'IMAGE'"))
    op.drop_table("food_asset")
    op.drop_table("food_nutrition")
    op.drop_table("source_food_mapping")
    op.drop_table("food_alias")
    op.drop_table("canonical_food")
    op.drop_table("hard_exclusion")
    op.drop_constraint("ck_households_has_member", "households", type_="check")
    op.drop_constraint("ck_households_children_nonnegative", "households", type_="check")
    op.drop_constraint("ck_households_adults_nonnegative", "households", type_="check")
    op.drop_constraint("fk_households_owner_user_id", "households", type_="foreignkey")
    op.alter_column("households", "name", existing_type=sa.String(length=100), nullable=False)
    op.drop_column("households", "updated_at")
    op.drop_column("households", "created_at")
    op.drop_column("households", "children")
    op.drop_column("households", "adults")
    op.drop_column("households", "owner_user_id")
    op.drop_table("auth_session")
    op.drop_table("admin_profile")
    op.drop_table("user_profile")
    op.drop_table("app_user")
