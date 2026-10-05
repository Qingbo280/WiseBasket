# Add household pantry items for Epic 5.
# Revision ID: h5a1b2c3d4e5
# Revises: g1a2b3c4d5e6
# Create Date: 2026-09-13
from alembic import op
import sqlalchemy as sa


revision = "h5a1b2c3d4e5"
down_revision = "g1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pantry_item",
        sa.Column("pantry_item_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("household_id", sa.Integer(), nullable=False),
        sa.Column("canonical_food_id", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False, server_default="MANUAL"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="AVAILABLE"),
        sa.Column("quantity", sa.Numeric(precision=12, scale=3), nullable=True),
        sa.Column("unit", sa.String(length=24), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("source in ('MANUAL','RECEIPT')", name="ck_pantry_item_source"),
        sa.CheckConstraint("status in ('AVAILABLE','REMOVED')", name="ck_pantry_item_status"),
        sa.CheckConstraint("quantity is null or quantity > 0", name="ck_pantry_item_quantity_positive"),
        sa.ForeignKeyConstraint(["canonical_food_id"], ["canonical_food.canonical_food_id"]),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("pantry_item_id"),
    )
    op.create_index("ix_pantry_item_household_status", "pantry_item", ["household_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_pantry_item_household_status", table_name="pantry_item")
    op.drop_table("pantry_item")
