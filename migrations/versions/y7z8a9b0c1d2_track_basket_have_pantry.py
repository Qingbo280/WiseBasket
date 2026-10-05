"""Track pantry rows owned by the basket Have sync.

Revision ID: y7z8a9b0c1d2
Revises: x6y7z8a9b0c1
Create Date: 2026-09-23
"""

from alembic import op
import sqlalchemy as sa


revision = "y7z8a9b0c1d2"
down_revision = "x6y7z8a9b0c1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "pantry_item",
        sa.Column("basket_have_managed", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index(
        "uq_pantry_item_basket_have_available",
        "pantry_item",
        ["household_id", "canonical_food_id"],
        unique=True,
        postgresql_where=sa.text("status = 'AVAILABLE' AND basket_have_managed"),
    )


def downgrade() -> None:
    op.drop_index("uq_pantry_item_basket_have_available", table_name="pantry_item")
    op.drop_column("pantry_item", "basket_have_managed")
