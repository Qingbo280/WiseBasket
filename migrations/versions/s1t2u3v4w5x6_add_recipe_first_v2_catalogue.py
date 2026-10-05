"""Add reviewed recipe-first V2 catalogue contracts.

Revision ID: s1t2u3v4w5x6
Revises: r0s1t2u3v4w5
Create Date: 2026-09-21
"""

from alembic import op
import sqlalchemy as sa


revision = "s1t2u3v4w5x6"
down_revision = "r0s1t2u3v4w5"
branch_labels = None
depends_on = None


INGREDIENT_ROLES = (
    "'MAIN_PROTEIN','STAPLE','MAIN_VEGETABLE','SUPPORTING_VEGETABLE',"
    "'COOKING_ESSENTIAL','SEASONING','OPTIONAL'"
)


def upgrade() -> None:
    # Existing recipes remain visible but fail closed for optimization until
    # their governance and quantities are reviewed and backfilled.
    op.add_column("recipe_catalog", sa.Column("meal_type", sa.String(24)))
    op.add_column("recipe_catalog", sa.Column("recipe_version", sa.Integer()))
    op.add_column("recipe_catalog", sa.Column("review_status", sa.String(16)))
    op.add_column(
        "recipe_catalog",
        sa.Column(
            "optimizer_eligible",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column("recipe_catalog", sa.Column("quantity_basis", sa.String(24)))
    op.add_column("recipe_catalog", sa.Column("max_weekly_occurrences", sa.Integer()))
    op.add_column("recipe_catalog", sa.Column("reviewed_by", sa.Uuid()))
    op.add_column(
        "recipe_catalog",
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
    )
    op.create_foreign_key(
        "fk_recipe_catalog_reviewed_by",
        "recipe_catalog",
        "app_user",
        ["reviewed_by"],
        ["user_id"],
    )
    op.create_check_constraint(
        "ck_recipe_catalog_meal_type",
        "recipe_catalog",
        "meal_type is null or meal_type in ('COMPLETE_MEAL','MAIN_DISH','SIDE')",
    )
    op.create_check_constraint(
        "ck_recipe_catalog_version_positive",
        "recipe_catalog",
        "recipe_version is null or recipe_version > 0",
    )
    op.create_check_constraint(
        "ck_recipe_catalog_review_status",
        "recipe_catalog",
        "review_status is null or review_status in ('DRAFT','APPROVED','REJECTED')",
    )
    op.create_check_constraint(
        "ck_recipe_catalog_quantity_basis",
        "recipe_catalog",
        "quantity_basis is null or quantity_basis in ('RAW_EDIBLE_KG','PURCHASE_KG')",
    )
    op.create_check_constraint(
        "ck_recipe_catalog_occurrences_positive",
        "recipe_catalog",
        "max_weekly_occurrences is null or max_weekly_occurrences > 0",
    )
    op.create_check_constraint(
        "ck_recipe_catalog_optimizer_governance",
        "recipe_catalog",
        "not optimizer_eligible or (active and base_servings > 0 and "
        "meal_type = 'COMPLETE_MEAL' and recipe_version is not null and "
        "review_status = 'APPROVED' and quantity_basis = 'RAW_EDIBLE_KG' and "
        "max_weekly_occurrences > 0 and reviewed_by is not null and reviewed_at is not null)",
    )

    op.add_column(
        "recipe_catalog_ingredient",
        sa.Column("ingredient_role", sa.String(32)),
    )
    op.create_check_constraint(
        "ck_recipe_catalog_ingredient_role",
        "recipe_catalog_ingredient",
        f"ingredient_role is null or ingredient_role in ({INGREDIENT_ROLES})",
    )

    op.create_table(
        "recipe_cooking_step_food",
        sa.Column(
            "recipe_cooking_step_id",
            sa.Integer(),
            sa.ForeignKey(
                "recipe_cooking_step.recipe_cooking_step_id",
                ondelete="CASCADE",
            ),
            primary_key=True,
        ),
        sa.Column(
            "canonical_food_id",
            sa.String(32),
            sa.ForeignKey("canonical_food.canonical_food_id"),
            primary_key=True,
        ),
    )

    op.create_table(
        "recipe_substitution_rule",
        sa.Column("rule_id", sa.String(80), primary_key=True),
        sa.Column(
            "original_food_id",
            sa.String(32),
            sa.ForeignKey("canonical_food.canonical_food_id"),
            nullable=False,
        ),
        sa.Column(
            "substitute_food_id",
            sa.String(32),
            sa.ForeignKey("canonical_food.canonical_food_id"),
            nullable=False,
        ),
        sa.Column("quantity_ratio", sa.Numeric(12, 6), nullable=False),
        sa.Column("ingredient_role", sa.String(32), nullable=False),
        sa.Column("reason", sa.Text()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "review_status",
            sa.String(16),
            nullable=False,
            server_default="DRAFT",
        ),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("reviewed_by", sa.Uuid(), sa.ForeignKey("app_user.user_id")),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "original_food_id <> substitute_food_id",
            name="ck_recipe_substitution_changes_food",
        ),
        sa.CheckConstraint(
            "quantity_ratio > 0",
            name="ck_recipe_substitution_ratio_positive",
        ),
        sa.CheckConstraint(
            "version > 0",
            name="ck_recipe_substitution_version_positive",
        ),
        sa.CheckConstraint(
            f"ingredient_role in ({INGREDIENT_ROLES})",
            name="ck_recipe_substitution_role",
        ),
        sa.CheckConstraint(
            "review_status in ('DRAFT','APPROVED','REJECTED')",
            name="ck_recipe_substitution_review_status",
        ),
        sa.CheckConstraint(
            "review_status <> 'APPROVED' or (reviewed_by is not null and reviewed_at is not null)",
            name="ck_recipe_substitution_approval_attribution",
        ),
    )

    op.create_table(
        "recipe_substitution_scope",
        sa.Column(
            "rule_id",
            sa.String(80),
            sa.ForeignKey("recipe_substitution_rule.rule_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "recipe_id",
            sa.String(80),
            sa.ForeignKey("recipe_catalog.recipe_id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )

    op.create_table(
        "food_safety_profile",
        sa.Column(
            "canonical_food_id",
            sa.String(32),
            sa.ForeignKey("canonical_food.canonical_food_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("vegetarian", sa.Boolean()),
        sa.Column("vegan", sa.Boolean()),
        sa.Column("contains_pork", sa.Boolean()),
        sa.Column(
            "allergen_assessment_complete",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "review_status",
            sa.String(16),
            nullable=False,
            server_default="DRAFT",
        ),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("reviewed_by", sa.Uuid(), sa.ForeignKey("app_user.user_id")),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint("version > 0", name="ck_food_safety_version_positive"),
        sa.CheckConstraint(
            "review_status in ('DRAFT','APPROVED','REJECTED')",
            name="ck_food_safety_review_status",
        ),
        sa.CheckConstraint(
            "not vegan or vegetarian",
            name="ck_food_safety_vegan_is_vegetarian",
        ),
        sa.CheckConstraint(
            "not contains_pork or (not vegetarian and not vegan)",
            name="ck_food_safety_pork_not_vegetarian",
        ),
        sa.CheckConstraint(
            "review_status <> 'APPROVED' or (vegetarian is not null and vegan is not null "
            "and contains_pork is not null and allergen_assessment_complete "
            "and reviewed_by is not null and reviewed_at is not null)",
            name="ck_food_safety_approval_complete",
        ),
    )

    op.create_table(
        "food_allergen",
        sa.Column(
            "canonical_food_id",
            sa.String(32),
            sa.ForeignKey("canonical_food.canonical_food_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("allergen_code", sa.String(24), primary_key=True),
        sa.CheckConstraint(
            "allergen_code in ('EGG','MILK','PEANUT','TREE_NUT','SOY','WHEAT','FISH','SHELLFISH')",
            name="ck_food_allergen_code",
        ),
    )


def downgrade() -> None:
    op.drop_table("food_allergen")
    op.drop_table("food_safety_profile")
    op.drop_table("recipe_substitution_scope")
    op.drop_table("recipe_substitution_rule")
    op.drop_table("recipe_cooking_step_food")

    op.drop_constraint(
        "ck_recipe_catalog_ingredient_role",
        "recipe_catalog_ingredient",
        type_="check",
    )
    op.drop_column("recipe_catalog_ingredient", "ingredient_role")

    op.drop_constraint(
        "ck_recipe_catalog_optimizer_governance",
        "recipe_catalog",
        type_="check",
    )
    op.drop_constraint(
        "ck_recipe_catalog_occurrences_positive",
        "recipe_catalog",
        type_="check",
    )
    op.drop_constraint(
        "ck_recipe_catalog_quantity_basis",
        "recipe_catalog",
        type_="check",
    )
    op.drop_constraint(
        "ck_recipe_catalog_review_status",
        "recipe_catalog",
        type_="check",
    )
    op.drop_constraint(
        "ck_recipe_catalog_version_positive",
        "recipe_catalog",
        type_="check",
    )
    op.drop_constraint(
        "ck_recipe_catalog_meal_type",
        "recipe_catalog",
        type_="check",
    )
    op.drop_constraint(
        "fk_recipe_catalog_reviewed_by",
        "recipe_catalog",
        type_="foreignkey",
    )
    op.drop_column("recipe_catalog", "reviewed_at")
    op.drop_column("recipe_catalog", "reviewed_by")
    op.drop_column("recipe_catalog", "max_weekly_occurrences")
    op.drop_column("recipe_catalog", "quantity_basis")
    op.drop_column("recipe_catalog", "optimizer_eligible")
    op.drop_column("recipe_catalog", "review_status")
    op.drop_column("recipe_catalog", "recipe_version")
    op.drop_column("recipe_catalog", "meal_type")
