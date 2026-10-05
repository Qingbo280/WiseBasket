"""Add a receipt effect ledger and exact logical-purchase identity.

Revision ID: z8a9b0c1d2e3
Revises: y7z8a9b0c1d2
Create Date: 2026-09-23
"""

from alembic import op
import sqlalchemy as sa


revision = "z8a9b0c1d2e3"
down_revision = "y7z8a9b0c1d2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("receipt", sa.Column("merchant", sa.String(240), nullable=True))
    op.add_column("receipt", sa.Column("transaction_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("receipt", sa.Column("receipt_number", sa.String(120), nullable=True))
    op.add_column("receipt", sa.Column("total_rm", sa.Numeric(12, 2), nullable=True))
    op.add_column("receipt", sa.Column("logical_fingerprint", sa.String(64), nullable=True))
    op.add_column("receipt", sa.Column("duplicate_of_receipt_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_receipt_duplicate_of", "receipt", "receipt",
        ["duplicate_of_receipt_id"], ["receipt_id"], ondelete="SET NULL",
    )
    op.add_column("receipt_line", sa.Column("client_line_id", sa.Uuid(), nullable=True))
    op.add_column("receipt_line", sa.Column("match_basis", sa.String(32), nullable=True))
    op.create_index(
        "uq_receipt_line_client_line_id", "receipt_line", ["receipt_id", "client_line_id"],
        unique=True, postgresql_where=sa.text("client_line_id IS NOT NULL"),
    )
    op.create_table(
        "receipt_line_effect",
        sa.Column("line_id", sa.Uuid(), sa.ForeignKey("receipt_line.line_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("receipt_id", sa.Uuid(), sa.ForeignKey("receipt.receipt_id", ondelete="CASCADE"), nullable=False),
        sa.Column("household_id", sa.Integer(), sa.ForeignKey("households.id", ondelete="CASCADE"), nullable=False),
        sa.Column("canonical_food_id", sa.String(32), sa.ForeignKey("canonical_food.canonical_food_id"), nullable=False),
        sa.Column("pantry_item_id", sa.Integer(), sa.ForeignKey("pantry_item.pantry_item_id", ondelete="SET NULL")),
        sa.Column("applied_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("source_qty", sa.Numeric(12, 3)),
        sa.Column("source_unit", sa.String(24)),
    )
    # Existing CONFIRMED rows have already affected stock. Record their effect
    # without adding stock again; the exact historic pantry row is unknowable.
    op.execute("""
        INSERT INTO receipt_line_effect
            (line_id, receipt_id, household_id, canonical_food_id, source_qty, source_unit)
        SELECT line.line_id, line.receipt_id, receipt.household_id,
               line.canonical_food_id, line.qty, line.unit
        FROM receipt_line AS line
        JOIN receipt ON receipt.receipt_id = line.receipt_id
        WHERE line.status = 'CONFIRMED' AND line.canonical_food_id IS NOT NULL
        ON CONFLICT (line_id) DO NOTHING
    """)
    op.create_table(
        "receipt_logical_purchase",
        sa.Column("purchase_id", sa.Uuid(), primary_key=True),
        sa.Column("household_id", sa.Integer(), sa.ForeignKey("households.id", ondelete="CASCADE"), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("canonical_receipt_id", sa.Uuid(), sa.ForeignKey("receipt.receipt_id", ondelete="CASCADE"), nullable=False),
        sa.UniqueConstraint("household_id", "fingerprint", name="uq_receipt_logical_purchase"),
    )


def downgrade() -> None:
    op.drop_table("receipt_logical_purchase")
    op.drop_table("receipt_line_effect")
    op.drop_index("uq_receipt_line_client_line_id", table_name="receipt_line")
    op.drop_column("receipt_line", "match_basis")
    op.drop_column("receipt_line", "client_line_id")
    op.drop_constraint("fk_receipt_duplicate_of", "receipt", type_="foreignkey")
    for column in ("duplicate_of_receipt_id", "logical_fingerprint", "total_rm", "receipt_number", "transaction_at", "merchant"):
        op.drop_column("receipt", column)
