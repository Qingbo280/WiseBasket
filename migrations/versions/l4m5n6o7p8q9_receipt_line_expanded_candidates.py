# Epic 6 follow-up: OCR abbreviation expansion + top-3 match candidates.
#
# - receipt_line.expanded_name: the OCR model's abbreviation expansion of the
#   printed name ("AUS CH OY BL GF" -> "Australian chilled oyster blade
#   beef"); kept for display and re-matching context. Nullable: the model is
#   explicitly allowed to leave it null when unsure (fail-closed).
# - receipt_line.candidates: JSONB list of {canonical_food_id, score} top-3
#   cosine candidates per line (UN-gated - may sit below the 0.55 threshold).
#   The confirmation UI offers these as one-tap picks; the user stays the
#   final authority, and a null canonical_food_id still means skip.
#
# Revision ID: l4m5n6o7p8q9
# Revises: k3l4m5n6o7p8
# Create Date: 2026-09-14
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "l4m5n6o7p8q9"
down_revision = "k3l4m5n6o7p8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "receipt_line",
        sa.Column("expanded_name", sa.String(240), nullable=True),
    )
    op.add_column(
        "receipt_line",
        sa.Column("candidates", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("receipt_line", "candidates")
    op.drop_column("receipt_line", "expanded_name")
