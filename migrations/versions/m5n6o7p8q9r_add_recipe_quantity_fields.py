# Add staged quantitative fields for Epic 5 household-sized recipe matching.
# Revision ID: m5n6o7p8q9r
# Revises: l4m5n6o7p8q9
# Create Date: 2026-09-14
from alembic import op
import sqlalchemy as sa


revision = "m5n6o7p8q9r"
down_revision = "l4m5n6o7p8q9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Fields are nullable while curated serving and gram values are reviewed.
    op.add_column("recipe_catalog", sa.Column("base_servings", sa.Integer(), nullable=True))
    op.add_column(
        "recipe_catalog_ingredient",
        sa.Column("base_quantity_g", sa.Numeric(12, 3), nullable=True),
    )
    op.create_check_constraint(
        "ck_recipe_catalog_ingredient_quantity_positive",
        "recipe_catalog_ingredient",
        "base_quantity_g is null or base_quantity_g > 0",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_recipe_catalog_ingredient_quantity_positive",
        "recipe_catalog_ingredient",
        type_="check",
    )
    op.drop_column("recipe_catalog_ingredient", "base_quantity_g")
    op.drop_column("recipe_catalog", "base_servings")
