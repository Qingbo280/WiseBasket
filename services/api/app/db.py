from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    ARRAY,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    LargeBinary,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    ForeignKeyConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.pool import NullPool

from .config import get_settings


class Base(DeclarativeBase):
    pass


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)


class AppUser(Base):
    __tablename__ = "app_user"

    user_id: Mapped[uuid.UUID] = _uuid_pk()
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    email_normalized: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False, default="USER")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ACTIVE")
    email_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint("role in ('USER', 'ADMIN')", name="ck_app_user_role"),
        CheckConstraint("status in ('ACTIVE', 'DISABLED', 'LOCKED')", name="ck_app_user_status"),
    )


class UserProfile(Base):
    __tablename__ = "user_profile"

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("app_user.user_id", ondelete="CASCADE"), primary_key=True)
    display_name: Mapped[str | None] = mapped_column(String(120))
    # Per-account app profile (frontend-owned JSON: household, budget,
    # location, restrictions, usual basket, habit adjustments).
    profile_data: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AdminProfile(Base):
    __tablename__ = "admin_profile"

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("app_user.user_id", ondelete="CASCADE"), primary_key=True)
    admin_level: Mapped[str] = mapped_column(String(16), nullable=False, default="ADMIN")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (CheckConstraint("admin_level in ('ADMIN', 'SUPER_ADMIN')", name="ck_admin_profile_level"),)


class AuthSession(Base):
    __tablename__ = "auth_session"

    session_id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("app_user.user_id", ondelete="CASCADE"), nullable=False)
    refresh_token_hash: Mapped[str] = mapped_column(Text, nullable=False)
    client_type: Mapped[str] = mapped_column(String(16), nullable=False)
    device_name: Mapped[str | None] = mapped_column(String(160))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint("client_type in ('MOBILE', 'ADMIN_WEB')", name="ck_auth_session_client_type"),
        Index("ix_auth_session_refresh_token_hash", "refresh_token_hash", unique=True),
    )


class Household(Base):
    __tablename__ = "households"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("app_user.user_id", ondelete="SET NULL"))
    name: Mapped[str | None] = mapped_column(String(100))
    adults: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    children: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    pantry_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("adults >= 0", name="ck_households_adults_nonnegative"),
        CheckConstraint("children >= 0", name="ck_households_children_nonnegative"),
        CheckConstraint("adults + children > 0", name="ck_households_has_member"),
    )


class HardExclusion(Base):
    __tablename__ = "hard_exclusion"

    exclusion_code: Mapped[str] = mapped_column(String(40), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class CanonicalFood(Base):
    __tablename__ = "canonical_food"

    canonical_food_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    canonical_name: Mapped[str] = mapped_column(String(240), nullable=False)
    canonical_name_ms: Mapped[str | None] = mapped_column(String(240))
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    food_form: Mapped[str | None] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ACTIVE")
    purchase_mode: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="FIXED_PACK",
        server_default="FIXED_PACK",
    )
    # Product-visible catalogue tag (2026-09-10 team decision): only foods on
    # the curated real-data list are shown in the app; everything else
    # (reference-price-only, zero-transaction, quality-gated) is hidden from
    # both the catalogue endpoint and the optimizer candidate set.
    catalog_eligible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint("status in ('ACTIVE', 'BLOCKED', 'RETIRED')", name="ck_canonical_food_status"),
        CheckConstraint(
            "purchase_mode in ('FIXED_PACK', 'BY_WEIGHT')",
            name="ck_canonical_food_purchase_mode",
        ),
    )


class FoodAlias(Base):
    __tablename__ = "food_alias"

    food_alias_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    canonical_food_id: Mapped[str] = mapped_column(String(32), ForeignKey("canonical_food.canonical_food_id"), nullable=False)
    alias_name: Mapped[str] = mapped_column(String(240), nullable=False)
    language: Mapped[str] = mapped_column(String(12), nullable=False, default="en")
    source_system: Mapped[str] = mapped_column(String(80), nullable=False, default="USER")

    __table_args__ = (UniqueConstraint("alias_name", "language", "source_system", name="uq_food_alias_name_language_source"),)


class PantryItem(Base):
    __tablename__ = "pantry_item"

    pantry_item_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"), nullable=False)
    canonical_food_id: Mapped[str] = mapped_column(String(32), ForeignKey("canonical_food.canonical_food_id"), nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="MANUAL")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="AVAILABLE")
    # Only a row created by the basket's Have sync may be removed by a later
    # basket choice. Manual and receipt writes take ownership of that row.
    basket_have_managed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    unit: Mapped[str | None] = mapped_column(String(24))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    __table_args__ = (
        CheckConstraint("source in ('MANUAL','RECEIPT')", name="ck_pantry_item_source"),
        CheckConstraint("status in ('AVAILABLE','REMOVED')", name="ck_pantry_item_status"),
        CheckConstraint("quantity is null or quantity > 0", name="ck_pantry_item_quantity_positive"),
        Index("ix_pantry_item_household_status", "household_id", "status"),
        Index(
            "uq_pantry_item_basket_have_available",
            "household_id", "canonical_food_id", unique=True,
            postgresql_where=text("status = 'AVAILABLE' AND basket_have_managed"),
        ),
    )


class RecipeCatalog(Base):
    __tablename__ = "recipe_catalog"

    recipe_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    # Nullable during the staged Epic 5 data migration. Once curated recipe
    # quantities are reviewed, every active recipe will receive a value.
    base_servings: Mapped[int | None] = mapped_column(Integer)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # V2 governance starts nullable/disabled so existing catalogue rows fail
    # closed until the data team reviews and backfills them.
    meal_type: Mapped[str | None] = mapped_column(String(24))
    recipe_version: Mapped[int | None] = mapped_column(Integer)
    review_status: Mapped[str | None] = mapped_column(String(16))
    optimizer_eligible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    optimizer_component_eligible: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    quantity_basis: Mapped[str | None] = mapped_column(String(24))
    max_weekly_occurrences: Mapped[int | None] = mapped_column(Integer)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("app_user.user_id")
    )
    review_source: Mapped[str | None] = mapped_column(String(120))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "meal_type is null or meal_type in ('COMPLETE_MEAL','MAIN_DISH','SIDE')",
            name="ck_recipe_catalog_meal_type",
        ),
        CheckConstraint(
            "recipe_version is null or recipe_version > 0",
            name="ck_recipe_catalog_version_positive",
        ),
        CheckConstraint(
            "review_status is null or review_status in ('DRAFT','APPROVED','REJECTED')",
            name="ck_recipe_catalog_review_status",
        ),
        CheckConstraint(
            "quantity_basis is null or quantity_basis in ('RAW_EDIBLE_KG','PURCHASE_KG')",
            name="ck_recipe_catalog_quantity_basis",
        ),
        CheckConstraint(
            "max_weekly_occurrences is null or max_weekly_occurrences > 0",
            name="ck_recipe_catalog_occurrences_positive",
        ),
        CheckConstraint(
            "not optimizer_eligible or (active and base_servings > 0 and "
            "meal_type = 'COMPLETE_MEAL' and recipe_version is not null and "
            "review_status = 'APPROVED' and quantity_basis = 'RAW_EDIBLE_KG' and "
            "max_weekly_occurrences > 0 and (reviewed_by is not null or review_source is not null) "
            "and reviewed_at is not null)",
            name="ck_recipe_catalog_optimizer_governance",
        ),
        CheckConstraint(
            "not optimizer_component_eligible or (active and base_servings > 0 and "
            "meal_type in ('MAIN_DISH','SIDE') and recipe_version is not null and "
            "review_status = 'APPROVED' and quantity_basis = 'RAW_EDIBLE_KG' and "
            "max_weekly_occurrences > 0 and "
            "(reviewed_by is not null or review_source is not null) and "
            "reviewed_at is not null)",
            name="ck_recipe_catalog_component_governance",
        ),
    )


class RecipeCatalogIngredient(Base):
    __tablename__ = "recipe_catalog_ingredient"

    recipe_ingredient_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    recipe_id: Mapped[str] = mapped_column(String(80), ForeignKey("recipe_catalog.recipe_id", ondelete="CASCADE"), nullable=False)
    canonical_food_id: Mapped[str] = mapped_column(String(32), ForeignKey("canonical_food.canonical_food_id"), nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Grams needed for the recipe's base_servings. Nullable until each curated
    # recipe quantity is independently reviewed and seeded.
    base_quantity_g: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    ingredient_role: Mapped[str | None] = mapped_column(String(32))
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        UniqueConstraint("recipe_id", "canonical_food_id", name="uq_recipe_catalog_ingredient_food"),
        UniqueConstraint("recipe_id", "display_order", name="uq_recipe_catalog_ingredient_order"),
        CheckConstraint("display_order > 0", name="ck_recipe_catalog_ingredient_order_positive"),
        CheckConstraint("base_quantity_g is null or base_quantity_g > 0", name="ck_recipe_catalog_ingredient_quantity_positive"),
        CheckConstraint(
            "ingredient_role is null or ingredient_role in "
            "('MAIN_PROTEIN','STAPLE','MAIN_VEGETABLE','SUPPORTING_VEGETABLE',"
            "'COOKING_ESSENTIAL','SEASONING','OPTIONAL')",
            name="ck_recipe_catalog_ingredient_role",
        ),
    )


class RecipeCookingStep(Base):
    __tablename__ = "recipe_cooking_step"

    recipe_cooking_step_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    recipe_id: Mapped[str] = mapped_column(String(80), ForeignKey("recipe_catalog.recipe_id", ondelete="CASCADE"), nullable=False)
    step_number: Mapped[int] = mapped_column(Integer, nullable=False)
    instruction: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        UniqueConstraint("recipe_id", "step_number", name="uq_recipe_cooking_step_order"),
        CheckConstraint("step_number > 0", name="ck_recipe_cooking_step_number_positive"),
    )


class RecipeCookingStepFood(Base):
    __tablename__ = "recipe_cooking_step_food"

    recipe_cooking_step_id: Mapped[int] = mapped_column(
        ForeignKey("recipe_cooking_step.recipe_cooking_step_id", ondelete="CASCADE"),
        primary_key=True,
    )
    canonical_food_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("canonical_food.canonical_food_id"),
        primary_key=True,
    )


class RecipeSubstitutionRule(Base):
    __tablename__ = "recipe_substitution_rule"

    rule_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    original_food_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("canonical_food.canonical_food_id"), nullable=False
    )
    substitute_food_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("canonical_food.canonical_food_id"), nullable=False
    )
    quantity_ratio: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    ingredient_role: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    review_status: Mapped[str] = mapped_column(String(16), nullable=False, default="DRAFT")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("app_user.user_id")
    )
    review_source: Mapped[str | None] = mapped_column(String(120))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "original_food_id <> substitute_food_id",
            name="ck_recipe_substitution_changes_food",
        ),
        CheckConstraint(
            "quantity_ratio > 0",
            name="ck_recipe_substitution_ratio_positive",
        ),
        CheckConstraint("version > 0", name="ck_recipe_substitution_version_positive"),
        CheckConstraint(
            "ingredient_role in ('MAIN_PROTEIN','STAPLE','MAIN_VEGETABLE',"
            "'SUPPORTING_VEGETABLE','COOKING_ESSENTIAL','SEASONING','OPTIONAL')",
            name="ck_recipe_substitution_role",
        ),
        CheckConstraint(
            "review_status in ('DRAFT','APPROVED','REJECTED')",
            name="ck_recipe_substitution_review_status",
        ),
        CheckConstraint(
            "review_status <> 'APPROVED' or ((reviewed_by is not null or review_source is not null) "
            "and reviewed_at is not null)",
            name="ck_recipe_substitution_approval_attribution",
        ),
    )


class RecipeSubstitutionScope(Base):
    __tablename__ = "recipe_substitution_scope"

    rule_id: Mapped[str] = mapped_column(
        String(80),
        ForeignKey("recipe_substitution_rule.rule_id", ondelete="CASCADE"),
        primary_key=True,
    )
    recipe_id: Mapped[str] = mapped_column(
        String(80),
        ForeignKey("recipe_catalog.recipe_id", ondelete="CASCADE"),
        primary_key=True,
    )


class FoodSafetyProfile(Base):
    __tablename__ = "food_safety_profile"

    canonical_food_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("canonical_food.canonical_food_id", ondelete="CASCADE"),
        primary_key=True,
    )
    vegetarian: Mapped[bool | None] = mapped_column(Boolean)
    vegan: Mapped[bool | None] = mapped_column(Boolean)
    contains_pork: Mapped[bool | None] = mapped_column(Boolean)
    allergen_assessment_complete: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    review_status: Mapped[str] = mapped_column(String(16), nullable=False, default="DRAFT")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("app_user.user_id")
    )
    review_source: Mapped[str | None] = mapped_column(String(120))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("version > 0", name="ck_food_safety_version_positive"),
        CheckConstraint(
            "review_status in ('DRAFT','APPROVED','REJECTED')",
            name="ck_food_safety_review_status",
        ),
        CheckConstraint(
            "not vegan or vegetarian",
            name="ck_food_safety_vegan_is_vegetarian",
        ),
        CheckConstraint(
            "not contains_pork or (not vegetarian and not vegan)",
            name="ck_food_safety_pork_not_vegetarian",
        ),
        CheckConstraint(
            "review_status <> 'APPROVED' or (vegetarian is not null and vegan is not null "
            "and contains_pork is not null and allergen_assessment_complete "
            "and (reviewed_by is not null or review_source is not null) and reviewed_at is not null)",
            name="ck_food_safety_approval_complete",
        ),
    )


class FoodAllergen(Base):
    __tablename__ = "food_allergen"

    canonical_food_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("canonical_food.canonical_food_id", ondelete="CASCADE"),
        primary_key=True,
    )
    allergen_code: Mapped[str] = mapped_column(String(24), primary_key=True)

    __table_args__ = (
        CheckConstraint(
            "allergen_code in ('EGG','MILK','PEANUT','TREE_NUT','SOY','WHEAT','FISH','SHELLFISH')",
            name="ck_food_allergen_code",
        ),
    )


class SourceFoodMapping(Base):
    __tablename__ = "source_food_mapping"

    source_food_mapping_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source_system: Mapped[str] = mapped_column(String(80), nullable=False)
    source_dataset_version: Mapped[str] = mapped_column(String(80), nullable=False)
    source_food_id: Mapped[str] = mapped_column(String(120), nullable=False)
    source_food_name: Mapped[str] = mapped_column(String(240), nullable=False)
    source_unit_or_form: Mapped[str | None] = mapped_column(String(80))
    canonical_food_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("canonical_food.canonical_food_id"))
    mapping_status: Mapped[str] = mapped_column(String(32), nullable=False, default="CANDIDATE")
    verification_status: Mapped[str] = mapped_column(String(32), nullable=False, default="NOT_VERIFIED")
    review_status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    evidence_note: Mapped[str | None] = mapped_column(Text)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("app_user.user_id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    variant_metadata: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint("source_system", "source_dataset_version", "source_food_id", name="uq_source_food_mapping_source_record"),
        CheckConstraint("mapping_status in ('CANDIDATE','EXACT','ACCEPTED_EQUIVALENT','NEEDS_CONVERSION','AMBIGUOUS','UNMAPPED','EXCLUDED')", name="ck_source_food_mapping_status"),
        CheckConstraint("verification_status in ('NOT_VERIFIED','VERIFIED','REJECTED')", name="ck_source_food_mapping_verification"),
        CheckConstraint("review_status in ('PENDING','APPROVED','REJECTED')", name="ck_source_food_mapping_review"),
        CheckConstraint("review_status != 'APPROVED' or (reviewed_by is not null and reviewed_at is not null)", name="ck_source_food_mapping_approval_attribution"),
    )


class FoodNutrition(Base):
    __tablename__ = "food_nutrition"

    nutrition_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    canonical_food_id: Mapped[str] = mapped_column(String(32), ForeignKey("canonical_food.canonical_food_id"), nullable=False)
    applies_to_item_code: Mapped[str | None] = mapped_column(String(120))
    source_dataset_version: Mapped[str] = mapped_column(String(80), nullable=False)
    source_record_id: Mapped[str] = mapped_column(String(120), nullable=False)
    basis_g: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False, default=100)
    energy_kcal: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    protein_g: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    fat_g: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    carbohydrate_g: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    fibre_g: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    fibre_basis: Mapped[str | None] = mapped_column(String(32))
    iron_mg: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    calcium_mg: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    vitamin_a_ug: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    vitamin_a_basis: Mapped[str | None] = mapped_column(String(32))
    vitamin_c_mg: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    quality_status: Mapped[str] = mapped_column(String(16), nullable=False, default="PASS")
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    source_url: Mapped[str | None] = mapped_column(Text)
    source_retrieved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("source_dataset_version", "source_record_id", "canonical_food_id", name="uq_food_nutrition_source_record"),
        CheckConstraint("basis_g > 0", name="ck_food_nutrition_basis_positive"),
        CheckConstraint("quality_status in ('PASS','WARN','BLOCK')", name="ck_food_nutrition_quality"),
        CheckConstraint("fibre_basis is null or fibre_basis in ('AOAC','NSP','UNKNOWN')", name="ck_food_nutrition_fibre_basis"),
        CheckConstraint("vitamin_a_basis is null or vitamin_a_basis in ('RAE','RE','UNKNOWN')", name="ck_food_nutrition_vitamin_a_basis"),
    )


class FoodTagDefinition(Base):
    __tablename__ = "food_tag_definition"

    tag_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    display_label: Mapped[str] = mapped_column(String(80), nullable=False)
    category: Mapped[str] = mapped_column(String(24), nullable=False)
    icon_key: Mapped[str] = mapped_column(String(40), nullable=False)
    colour_variant: Mapped[str] = mapped_column(String(24), nullable=False)
    evidence_source: Mapped[str] = mapped_column(Text, nullable=False)
    display_priority: Mapped[int] = mapped_column(
        Integer, nullable=False, default=100, server_default="100"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "category in ('NUTRIENT_CONTENT','HEALTH_BENEFIT','DIETARY_ATTRIBUTE')",
            name="ck_food_tag_definition_category",
        ),
        CheckConstraint(
            "display_priority >= 0",
            name="ck_food_tag_definition_priority_nonnegative",
        ),
        UniqueConstraint(
            "display_label",
            name="uq_food_tag_definition_display_label",
        ),
    )


class CanonicalFoodTag(Base):
    __tablename__ = "canonical_food_tag"

    canonical_food_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("canonical_food.canonical_food_id", ondelete="CASCADE"),
        primary_key=True,
    )
    tag_key: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("food_tag_definition.tag_key", ondelete="CASCADE"),
        primary_key=True,
    )
    source_nutrition_id: Mapped[int | None] = mapped_column(
        ForeignKey("food_nutrition.nutrition_id", ondelete="CASCADE")
    )
    nutrient_key: Mapped[str | None] = mapped_column(String(32))
    nutrient_value: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    qualifying_threshold: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    nutrient_unit: Mapped[str | None] = mapped_column(String(16))
    display_priority: Mapped[int] = mapped_column(Integer, nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "display_priority between 1 and 2",
            name="ck_canonical_food_tag_display_priority",
        ),
        CheckConstraint(
            "nutrient_value is null or nutrient_value >= 0",
            name="ck_canonical_food_tag_nutrient_value_nonnegative",
        ),
        CheckConstraint(
            "qualifying_threshold is null or qualifying_threshold > 0",
            name="ck_canonical_food_tag_threshold_positive",
        ),
        UniqueConstraint(
            "canonical_food_id",
            "display_priority",
            name="uq_canonical_food_tag_display_priority",
        ),
        Index("ix_canonical_food_tag_tag_key", "tag_key"),
    )


class FoodAsset(Base):
    __tablename__ = "food_asset"

    food_asset_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    canonical_food_id: Mapped[str] = mapped_column(String(32), ForeignKey("canonical_food.canonical_food_id"), nullable=False)
    asset_type: Mapped[str] = mapped_column(String(16), nullable=False)
    object_key: Mapped[str] = mapped_column(Text, nullable=False)
    alt_text: Mapped[str | None] = mapped_column(String(240))
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint("asset_type in ('IMAGE','THUMBNAIL')", name="ck_food_asset_type"),
        Index("uq_food_asset_primary_image", "canonical_food_id", unique=True, postgresql_where=text("is_primary and asset_type = 'IMAGE'")),
    )


class Location(Base):
    __tablename__ = "location"

    location_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source_premise_code: Mapped[str | None] = mapped_column(String(120), unique=True)
    location_name: Mapped[str] = mapped_column(String(240), nullable=False)
    premise_type: Mapped[str | None] = mapped_column(String(80))
    state: Mapped[str | None] = mapped_column(String(80))
    district: Mapped[str | None] = mapped_column(String(120))
    address: Mapped[str | None] = mapped_column(Text)
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 7))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 7))
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint("latitude is null or (latitude >= -90 and latitude <= 90)", name="ck_location_latitude"),
        CheckConstraint("longitude is null or (longitude >= -180 and longitude <= 180)", name="ck_location_longitude"),
    )


class UnitConversion(Base):
    __tablename__ = "unit_conversion"

    unit_conversion_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    canonical_food_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("canonical_food.canonical_food_id"))
    conversion_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_unit: Mapped[str | None] = mapped_column(String(80))
    target_unit: Mapped[str | None] = mapped_column(String(80))
    factor: Mapped[Decimal | None] = mapped_column(Numeric(14, 8))
    edible_yield_fraction: Mapped[Decimal | None] = mapped_column(Numeric(8, 6))
    production_eligible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    evidence_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint("conversion_type in ('PURCHASE_MASS','EDIBLE_YIELD')", name="ck_unit_conversion_type"),
        CheckConstraint("not production_eligible or factor is not null or edible_yield_fraction is not null", name="ck_unit_conversion_production_has_factor"),
        CheckConstraint("edible_yield_fraction is null or (edible_yield_fraction > 0 and edible_yield_fraction <= 1)", name="ck_unit_conversion_edible_yield"),
    )


class EtlRun(Base):
    __tablename__ = "etl_run"

    etl_run_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    pipeline_version: Mapped[str] = mapped_column(String(80), nullable=False)
    source_system: Mapped[str] = mapped_column(String(80), nullable=False)
    source_vintage: Mapped[str | None] = mapped_column(String(80))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    rows_in: Mapped[int | None] = mapped_column(Integer)
    rows_out: Mapped[int | None] = mapped_column(Integer)
    rows_blocked: Mapped[int | None] = mapped_column(Integer)

    __table_args__ = (CheckConstraint("status in ('RUNNING','PASS','FAIL')", name="ck_etl_run_status"),)


class FoodPriceObservation(Base):
    __tablename__ = "food_price_observation"

    price_observation_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    canonical_food_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("canonical_food.canonical_food_id"))
    source_item_code: Mapped[str] = mapped_column(String(120), nullable=False)
    source_food_name: Mapped[str] = mapped_column(String(240), nullable=False)
    source_premise_code: Mapped[str | None] = mapped_column(String(120))
    location_id: Mapped[int] = mapped_column(ForeignKey("location.location_id"), nullable=False)
    observed_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    price_rm: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    original_unit: Mapped[str | None] = mapped_column(String(80))
    purchase_mass_g: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    price_rm_per_kg_purchase: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    price_rm_per_100g_purchase: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    edible_yield_fraction: Mapped[Decimal | None] = mapped_column(Numeric(8, 6))
    price_rm_per_100g_edible: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    source_dataset_version: Mapped[str] = mapped_column(String(80), nullable=False)
    etl_run_id: Mapped[int | None] = mapped_column(ForeignKey("etl_run.etl_run_id"))
    quality_status: Mapped[str] = mapped_column(String(16), nullable=False, default="PASS")

    __table_args__ = (
        UniqueConstraint("source_item_code", "location_id", "observed_date", "source_dataset_version", name="uq_food_price_observation_logical"),
        CheckConstraint("price_rm >= 0", name="ck_food_price_observation_price_nonnegative"),
        CheckConstraint("quality_status in ('PASS','WARN','BLOCK')", name="ck_food_price_observation_quality"),
        Index(
            "ix_food_price_observation_latest_lookup",
            "location_id",
            "canonical_food_id",
            text("observed_date desc"),
            postgresql_where=text(
                "quality_status = 'PASS' and canonical_food_id is not null and price_rm_per_100g_edible is not null"
            ),
        ),
    )


class RniReference(Base):
    __tablename__ = "rni_reference"

    rni_reference_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    nutrient: Mapped[str] = mapped_column(String(80), nullable=False)
    age_group: Mapped[str | None] = mapped_column(String(80))
    sex: Mapped[str | None] = mapped_column(String(20))
    life_stage: Mapped[str | None] = mapped_column(String(80))
    value: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    unit: Mapped[str] = mapped_column(String(40), nullable=False)
    scenario: Mapped[str | None] = mapped_column(String(120))
    selected_for_optimizer: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    profile: Mapped[str | None] = mapped_column(String(120))
    pal: Mapped[str | None] = mapped_column(String(80))
    source_note: Mapped[str | None] = mapped_column(Text)


class DataQualityIssue(Base):
    __tablename__ = "data_quality_issue"

    data_quality_issue_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    etl_run_id: Mapped[int | None] = mapped_column(ForeignKey("etl_run.etl_run_id"))
    rule_code: Mapped[str] = mapped_column(String(80), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    source_row: Mapped[str | None] = mapped_column(Text)
    canonical_food_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("canonical_food.canonical_food_id"))
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (CheckConstraint("severity in ('INFO','WARN','BLOCK')", name="ck_data_quality_issue_severity"),)


class PlanningRequest(Base):
    __tablename__ = "planning_request"

    planning_request_id: Mapped[uuid.UUID] = _uuid_pk()
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id"), nullable=False)
    available_budget_rm: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    planning_days: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    exclusions: Mapped[list["PlanningRequestExclusion"]] = relationship(cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("available_budget_rm > 0", name="ck_planning_request_budget_positive"),
        CheckConstraint("planning_days > 0", name="ck_planning_request_days_positive"),
        Index("ix_planning_request_household_id", "household_id"),
    )


class PlanningRequestExclusion(Base):
    __tablename__ = "planning_request_exclusion"

    planning_request_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("planning_request.planning_request_id", ondelete="CASCADE"), primary_key=True)
    exclusion_code: Mapped[str] = mapped_column(String(40), ForeignKey("hard_exclusion.exclusion_code"), primary_key=True)


class HardExclusionFood(Base):
    __tablename__ = "hard_exclusion_food"

    exclusion_code: Mapped[str] = mapped_column(String(40), ForeignKey("hard_exclusion.exclusion_code", ondelete="CASCADE"), primary_key=True)
    canonical_food_id: Mapped[str] = mapped_column(String(32), ForeignKey("canonical_food.canonical_food_id", ondelete="CASCADE"), primary_key=True)


class PlanningLocation(Base):
    __tablename__ = "planning_location"

    planning_request_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("planning_request.planning_request_id", ondelete="CASCADE"), primary_key=True)
    latitude: Mapped[Decimal] = mapped_column(Numeric(10, 7), nullable=False)
    longitude: Mapped[Decimal] = mapped_column(Numeric(10, 7), nullable=False)
    location_source: Mapped[str] = mapped_column(String(16), nullable=False)
    selected_state: Mapped[str | None] = mapped_column(String(80))
    selected_district: Mapped[str | None] = mapped_column(String(120))

    __table_args__ = (
        CheckConstraint("latitude >= -90 and latitude <= 90", name="ck_planning_location_latitude"),
        CheckConstraint("longitude >= -180 and longitude <= 180", name="ck_planning_location_longitude"),
        CheckConstraint("location_source in ('GPS','MANUAL')", name="ck_planning_location_source"),
    )


class MealTemplate(Base):
    __tablename__ = "meal_template"

    meal_template_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    meal_name: Mapped[str] = mapped_column(String(160), nullable=False)
    meal_type: Mapped[str | None] = mapped_column(String(16))
    servings: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        CheckConstraint("servings > 0", name="ck_meal_template_servings_positive"),
        CheckConstraint("meal_type is null or meal_type in ('BREAKFAST','LUNCH','DINNER','SNACK')", name="ck_meal_template_type"),
    )


class MealTemplateIngredient(Base):
    __tablename__ = "meal_template_ingredient"

    meal_template_id: Mapped[int] = mapped_column(ForeignKey("meal_template.meal_template_id", ondelete="CASCADE"), primary_key=True)
    canonical_food_id: Mapped[str] = mapped_column(String(32), ForeignKey("canonical_food.canonical_food_id"), primary_key=True)
    grams_per_serving: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    __table_args__ = (CheckConstraint("grams_per_serving > 0", name="ck_meal_template_ingredient_grams_positive"),)


class GeneratedPlan(Base):
    __tablename__ = "generated_plan"

    plan_id: Mapped[uuid.UUID] = _uuid_pk()
    planning_request_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("planning_request.planning_request_id"), nullable=False)
    optimizer_version: Mapped[str] = mapped_column(String(40), nullable=False)
    generation_method: Mapped[str] = mapped_column(String(32), nullable=False, default="OPTIMIZER")
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    estimated_total_cost_rm: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    remaining_budget_rm: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    solver_runtime_ms: Mapped[int | None] = mapped_column(Integer)
    selected_store_option_id: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    items: Mapped[list["GeneratedPlanItem"]] = relationship(cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("generation_method in ('OPTIMIZER','OPTIMIZER_AI_ASSISTED')", name="ck_generated_plan_method"),
        CheckConstraint("status in ('FEASIBLE','TIGHT','INFEASIBLE')", name="ck_generated_plan_status"),
        CheckConstraint("estimated_total_cost_rm >= 0", name="ck_generated_plan_total_nonnegative"),
        ForeignKeyConstraint(
            ["plan_id", "selected_store_option_id"],
            ["plan_store_option.plan_id", "plan_store_option.plan_store_option_id"],
            name="fk_generated_plan_selected_store_same_plan",
            use_alter=True,
        ),
        Index("ix_generated_plan_planning_request_id", "planning_request_id"),
    )


class GeneratedPlanItem(Base):
    __tablename__ = "generated_plan_item"

    generated_plan_item_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    plan_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("generated_plan.plan_id", ondelete="CASCADE"), nullable=False)
    canonical_food_id: Mapped[str] = mapped_column(String(32), ForeignKey("canonical_food.canonical_food_id"), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    quantity_unit: Mapped[str] = mapped_column(String(24), nullable=False)
    estimated_cost_rm: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_generated_plan_item_quantity_positive"),
        CheckConstraint("estimated_cost_rm >= 0", name="ck_generated_plan_item_cost_nonnegative"),
        Index("ix_generated_plan_item_plan_id", "plan_id"),
    )


class PlanStoreOption(Base):
    __tablename__ = "plan_store_option"

    plan_store_option_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    plan_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("generated_plan.plan_id", ondelete="CASCADE"), nullable=False)
    location_id: Mapped[int] = mapped_column(ForeignKey("location.location_id"), nullable=False)
    distance_km: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    basket_cost_rm: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    items_available: Mapped[int] = mapped_column(Integer, nullable=False)
    items_missing: Mapped[int] = mapped_column(Integer, nullable=False)
    price_coverage_ratio: Mapped[Decimal] = mapped_column(Numeric(6, 5), nullable=False)
    recommendation_rank: Mapped[int] = mapped_column(Integer, nullable=False)
    recommendation_type: Mapped[str] = mapped_column(String(16), nullable=False)
    is_selected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint("recommendation_type in ('NEAREST','CHEAPEST','BEST_VALUE')", name="ck_plan_store_option_type"),
        CheckConstraint("items_available >= 0 and items_missing >= 0", name="ck_plan_store_option_item_counts"),
        CheckConstraint("price_coverage_ratio >= 0 and price_coverage_ratio <= 1", name="ck_plan_store_option_coverage"),
        UniqueConstraint("plan_id", "plan_store_option_id", name="uq_plan_store_option_plan_option"),
        Index("uq_plan_store_option_selected", "plan_id", unique=True, postgresql_where=text("is_selected")),
    )


class PlanStoreItem(Base):
    __tablename__ = "plan_store_item"

    plan_store_option_id: Mapped[int] = mapped_column(ForeignKey("plan_store_option.plan_store_option_id", ondelete="CASCADE"), primary_key=True)
    canonical_food_id: Mapped[str] = mapped_column(String(32), ForeignKey("canonical_food.canonical_food_id"), primary_key=True)
    price_observation_id: Mapped[int | None] = mapped_column(ForeignKey("food_price_observation.price_observation_id"))
    estimated_cost_rm: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    available: Mapped[bool] = mapped_column(Boolean, nullable=False)


# --- Epic 6: receipt capture + food embeddings -------------------------------


class FoodEmbedding(Base):
    """One BGE-M3 vector per canonical food, seeded offline by
    scripts/seed_food_embeddings.py. Plain float array (no pgvector) on
    purpose: 201 rows make brute-force cosine the fastest option anyway."""

    __tablename__ = "food_embedding"

    canonical_food_id: Mapped[str] = mapped_column(String(32), ForeignKey("canonical_food.canonical_food_id"), primary_key=True)
    embedding: Mapped[list[float]] = mapped_column(ARRAY(Float), nullable=False)
    model: Mapped[str] = mapped_column(String(40), nullable=False, default="BAAI/bge-m3")
    dim: Mapped[int] = mapped_column(Integer, nullable=False, default=1024)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class Receipt(Base):
    """Uploaded receipt photo awaiting/at/after OCR by the worker task."""

    __tablename__ = "receipt"

    receipt_id: Mapped[uuid.UUID] = _uuid_pk()
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"), nullable=False)
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("app_user.user_id", ondelete="SET NULL"))
    # The original photo is short-lived. OCR rows and confirmation history stay
    # available after the 24-hour image-retention window expires.
    image_bytes: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    image_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    image_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="PENDING")
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    merchant: Mapped[str | None] = mapped_column(String(240))
    transaction_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    receipt_number: Mapped[str | None] = mapped_column(String(120))
    total_rm: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    logical_fingerprint: Mapped[str | None] = mapped_column(String(64))
    duplicate_of_receipt_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("receipt.receipt_id", ondelete="SET NULL")
    )
    processing_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    processing_deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (
        CheckConstraint("status in ('PENDING','PROCESSING','DONE','FAILED')", name="ck_receipt_status"),
        # Covers concurrent duplicate uploads without invalidating existing
        # historic receipts that may already share the same image.
        Index(
            "uq_receipt_active_household_image_sha256",
            "household_id",
            "image_sha256",
            unique=True,
            postgresql_where=text("status in ('PENDING', 'PROCESSING')"),
        ),
        Index("ix_receipt_image_expires_at", "image_expires_at"),
    )


class ReceiptLine(Base):
    __tablename__ = "receipt_line"

    line_id: Mapped[uuid.UUID] = _uuid_pk()
    receipt_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("receipt.receipt_id", ondelete="CASCADE"), nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)
    name_raw: Mapped[str] = mapped_column(String(240), nullable=False)
    # OCR model's abbreviation expansion of name_raw (nullable = model unsure).
    expanded_name: Mapped[str | None] = mapped_column(String(240), nullable=True)
    qty: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    unit: Mapped[str | None] = mapped_column(String(24))
    price_rm: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    canonical_food_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("canonical_food.canonical_food_id"))
    match_score: Mapped[float | None] = mapped_column(Float)
    # Top-3 cosine candidates [{canonical_food_id, score}] (un-gated, may be
    # below the match threshold) for one-tap picks in the confirmation UI.
    candidates: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="PROPOSED")
    client_line_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    match_basis: Mapped[str | None] = mapped_column(String(32))

    __table_args__ = (
        CheckConstraint("status in ('PROPOSED','CONFIRMED','SKIPPED')", name="ck_receipt_line_status"),
        CheckConstraint("display_order > 0", name="ck_receipt_line_order_positive"),
        Index("ix_receipt_line_receipt", "receipt_id"),
        Index(
            "uq_receipt_line_client_line_id", "receipt_id", "client_line_id",
            unique=True, postgresql_where=text("client_line_id IS NOT NULL"),
        ),
    )


class ReceiptLineEffect(Base):
    """Permanent fact that a receipt line was applied to the pantry once."""

    __tablename__ = "receipt_line_effect"

    line_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("receipt_line.line_id", ondelete="CASCADE"), primary_key=True
    )
    receipt_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("receipt.receipt_id", ondelete="CASCADE"), nullable=False
    )
    household_id: Mapped[int] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), nullable=False
    )
    canonical_food_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("canonical_food.canonical_food_id"), nullable=False
    )
    pantry_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("pantry_item.pantry_item_id", ondelete="SET NULL")
    )
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    source_qty: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    source_unit: Mapped[str | None] = mapped_column(String(24))


class ReceiptLogicalPurchase(Base):
    __tablename__ = "receipt_logical_purchase"

    purchase_id: Mapped[uuid.UUID] = _uuid_pk()
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    canonical_receipt_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("receipt.receipt_id", ondelete="CASCADE"), nullable=False
    )

    __table_args__ = (UniqueConstraint("household_id", "fingerprint", name="uq_receipt_logical_purchase"),)


class ReceiptUploadDay(Base):
    __tablename__ = "receipt_upload_day"

    household_id: Mapped[int] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"), primary_key=True)
    local_day: Mapped[date] = mapped_column(Date, primary_key=True)
    image_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class ReceiptCloudMonth(Base):
    __tablename__ = "receipt_cloud_month"

    utc_month: Mapped[str] = mapped_column(String(7), primary_key=True)
    reserved_usd: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False, default=0)
    call_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class ReceiptCloudCall(Base):
    __tablename__ = "receipt_cloud_call"

    receipt_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("receipt.receipt_id", ondelete="CASCADE"), primary_key=True
    )
    attempt_no: Mapped[int] = mapped_column(Integer, primary_key=True)
    utc_month: Mapped[str] = mapped_column(String(7), ForeignKey("receipt_cloud_month.utc_month"), nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    reserved_usd: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ReceiptAliasVote(Base):
    __tablename__ = "receipt_alias_vote"

    logical_purchase_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("receipt_logical_purchase.purchase_id", ondelete="CASCADE"), primary_key=True
    )
    retailer_scope: Mapped[str] = mapped_column(String(240), primary_key=True)
    normalized_alias: Mapped[str] = mapped_column(String(240), primary_key=True)
    canonical_food_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("canonical_food.canonical_food_id"), nullable=False
    )


class ReceiptTrustedAlias(Base):
    __tablename__ = "receipt_trusted_alias"

    retailer_scope: Mapped[str] = mapped_column(String(240), primary_key=True)
    normalized_alias: Mapped[str] = mapped_column(String(240), primary_key=True)
    canonical_food_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("canonical_food.canonical_food_id", ondelete="CASCADE"), nullable=False
    )


settings = get_settings()
database_url = settings.database_url.strip().strip('"').strip("'").strip("{}")

if database_url.startswith("postgresql://"):
    database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

connect_args = {"ssl": "require"} if "proxy.rlwy.net" in database_url else {}
engine_kwargs = {"poolclass": NullPool} if settings.app_env.lower() in {"test", "testing"} else {}

engine = create_async_engine(
    database_url,
    pool_pre_ping=True,
    connect_args=connect_args,
    **engine_kwargs,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
