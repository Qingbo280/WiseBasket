"""Add data-driven purchase modes to canonical foods.

Revision ID: c4f19a7e2b6d
Revises: x6y7z8a9b0c1
Create Date: 2026-09-24
"""

from alembic import op
import sqlalchemy as sa


revision = "c4f19a7e2b6d"
down_revision = "x6y7z8a9b0c1"
branch_labels = None
depends_on = None


# Reviewed fresh meat and seafood lines sold by variable weight. Everything
# else remains a fixed purchase unit until explicitly curated in the database.
BY_WEIGHT_FOOD_IDS = (
    "SF001", "SF002", "SF003", "SF004", "SF005", "SF006", "SF008",
    "SF009", "SF013", "SF014", "SF015", "SF016", "SF017", "SF022",
    "SF023", "SF024", "SF025", "SF027", "SF028", "SF030", "SF032",
    "SF034", "SF035", "SF036", "SF037", "SF039", "SF042", "SF043",
    "SF046", "SF050",
)


def upgrade() -> None:
    op.add_column(
        "canonical_food",
        sa.Column(
            "purchase_mode",
            sa.String(length=16),
            nullable=False,
            server_default="FIXED_PACK",
        ),
    )
    op.create_check_constraint(
        "ck_canonical_food_purchase_mode",
        "canonical_food",
        "purchase_mode in ('FIXED_PACK', 'BY_WEIGHT')",
    )
    ids = ", ".join(f"'{food_id}'" for food_id in BY_WEIGHT_FOOD_IDS)
    op.execute(
        f"UPDATE canonical_food SET purchase_mode='BY_WEIGHT' "
        f"WHERE canonical_food_id IN ({ids})"
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_canonical_food_purchase_mode",
        "canonical_food",
        type_="check",
    )
    op.drop_column("canonical_food", "purchase_mode")
