"""Add normalized schema for evidence-backed food benefit tags.

Revision ID: z9y8x7w6v5u4
Revises: c4f19a7e2b6d
Create Date: 2026-09-24
"""

from alembic import op
import sqlalchemy as sa


revision = "z9y8x7w6v5u4"
down_revision = "c4f19a7e2b6d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "food_tag_definition",
        sa.Column("tag_key", sa.String(length=64), primary_key=True),
        sa.Column("display_label", sa.String(length=80), nullable=False),
        sa.Column("category", sa.String(length=24), nullable=False),
        sa.Column("icon_key", sa.String(length=40), nullable=False),
        sa.Column("colour_variant", sa.String(length=24), nullable=False),
        sa.Column("evidence_source", sa.Text(), nullable=False),
        sa.Column("display_priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
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
            "category in ('NUTRIENT_CONTENT','HEALTH_BENEFIT','DIETARY_ATTRIBUTE')",
            name="ck_food_tag_definition_category",
        ),
        sa.CheckConstraint(
            "display_priority >= 0",
            name="ck_food_tag_definition_priority_nonnegative",
        ),
        sa.UniqueConstraint("display_label", name="uq_food_tag_definition_display_label"),
    )
    op.create_table(
        "canonical_food_tag",
        sa.Column("canonical_food_id", sa.String(length=32), nullable=False),
        sa.Column("tag_key", sa.String(length=64), nullable=False),
        sa.Column("source_nutrition_id", sa.Integer(), nullable=True),
        sa.Column("nutrient_key", sa.String(length=32), nullable=True),
        sa.Column("nutrient_value", sa.Numeric(12, 4), nullable=True),
        sa.Column("qualifying_threshold", sa.Numeric(12, 4), nullable=True),
        sa.Column("nutrient_unit", sa.String(length=16), nullable=True),
        sa.Column("display_priority", sa.Integer(), nullable=False),
        sa.Column(
            "assigned_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "display_priority between 1 and 2",
            name="ck_canonical_food_tag_display_priority",
        ),
        sa.CheckConstraint(
            "nutrient_value is null or nutrient_value >= 0",
            name="ck_canonical_food_tag_nutrient_value_nonnegative",
        ),
        sa.CheckConstraint(
            "qualifying_threshold is null or qualifying_threshold > 0",
            name="ck_canonical_food_tag_threshold_positive",
        ),
        sa.ForeignKeyConstraint(
            ["canonical_food_id"],
            ["canonical_food.canonical_food_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tag_key"],
            ["food_tag_definition.tag_key"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_nutrition_id"],
            ["food_nutrition.nutrition_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("canonical_food_id", "tag_key"),
        sa.UniqueConstraint(
            "canonical_food_id",
            "display_priority",
            name="uq_canonical_food_tag_display_priority",
        ),
    )
    op.create_index(
        "ix_canonical_food_tag_tag_key",
        "canonical_food_tag",
        ["tag_key"],
    )


def downgrade() -> None:
    op.drop_index("ix_canonical_food_tag_tag_key", table_name="canonical_food_tag")
    op.drop_table("canonical_food_tag")
    op.drop_table("food_tag_definition")
