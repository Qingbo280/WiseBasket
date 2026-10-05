# Store the current pantry-list confirmation for Epic 5 recipe suggestions.
# Revision ID: i6b7c8d9e0f1
# Revises: h5a1b2c3d4e5
# Create Date: 2026-09-13
from alembic import op
import sqlalchemy as sa


revision = "i6b7c8d9e0f1"
down_revision = "h5a1b2c3d4e5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("households", sa.Column("pantry_confirmed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("households", "pantry_confirmed_at")
