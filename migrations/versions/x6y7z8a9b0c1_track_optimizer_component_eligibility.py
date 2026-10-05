"""Track optimizer eligibility for reviewed meal components.

Revision ID: x6y7z8a9b0c1
Revises: w5x6y7z8a9b0
Create Date: 2026-09-21
"""

from alembic import op
import sqlalchemy as sa


revision = "x6y7z8a9b0c1"
down_revision = "w5x6y7z8a9b0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "recipe_catalog",
        sa.Column(
            "optimizer_component_eligible",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.create_check_constraint(
        "ck_recipe_catalog_component_governance",
        "recipe_catalog",
        "not optimizer_component_eligible or (active and base_servings > 0 and "
        "meal_type in ('MAIN_DISH','SIDE') and recipe_version is not null and "
        "review_status = 'APPROVED' and quantity_basis = 'RAW_EDIBLE_KG' and "
        "max_weekly_occurrences > 0 and "
        "(reviewed_by is not null or review_source is not null) and "
        "reviewed_at is not null)",
    )
    op.execute(
        """
        UPDATE recipe_catalog
        SET optimizer_component_eligible=true
        WHERE active
          AND review_status='APPROVED'
          AND meal_type IN ('MAIN_DISH','SIDE')
        """
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_recipe_catalog_component_governance",
        "recipe_catalog",
        type_="check",
    )
    op.drop_column("recipe_catalog", "optimizer_component_eligible")
