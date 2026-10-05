"""Add durable receipt limits, deadlines, and scoped alias evidence.

Revision ID: a9b0c1d2e3f4
Revises: z8a9b0c1d2e3
Create Date: 2026-09-23
"""

from alembic import op
import sqlalchemy as sa


revision = "a9b0c1d2e3f4"
down_revision = "z8a9b0c1d2e3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("receipt", sa.Column("processing_started_at", sa.DateTime(timezone=True)))
    op.add_column("receipt", sa.Column("processing_deadline_at", sa.DateTime(timezone=True)))
    op.add_column("receipt", sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"))
    op.create_table(
        "receipt_upload_day",
        sa.Column("household_id", sa.Integer(), sa.ForeignKey("households.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("local_day", sa.Date(), primary_key=True),
        sa.Column("image_count", sa.Integer(), nullable=False),
        sa.CheckConstraint("image_count >= 0 AND image_count <= 10", name="ck_receipt_upload_day_count"),
    )
    op.execute("""
        INSERT INTO receipt_upload_day (household_id, local_day, image_count)
        SELECT household_id, timezone('Asia/Kuala_Lumpur', created_at)::date,
               LEAST(count(*), 10)::integer
        FROM receipt
        GROUP BY household_id, timezone('Asia/Kuala_Lumpur', created_at)::date
    """)
    op.create_table(
        "receipt_cloud_month",
        sa.Column("utc_month", sa.String(7), primary_key=True),
        sa.Column("reserved_usd", sa.Numeric(12, 4), nullable=False),
        sa.Column("call_count", sa.Integer(), nullable=False),
    )
    op.create_table(
        "receipt_cloud_call",
        sa.Column("receipt_id", sa.Uuid(), sa.ForeignKey("receipt.receipt_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("attempt_no", sa.Integer(), primary_key=True),
        sa.Column("utc_month", sa.String(7), sa.ForeignKey("receipt_cloud_month.utc_month"), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("model", sa.String(120), nullable=False),
        sa.Column("reserved_usd", sa.Numeric(12, 4), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("attempt_no BETWEEN 1 AND 2", name="ck_receipt_cloud_attempt"),
    )
    op.create_table(
        "receipt_alias_vote",
        sa.Column("logical_purchase_id", sa.Uuid(), sa.ForeignKey("receipt_logical_purchase.purchase_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("retailer_scope", sa.String(240), primary_key=True),
        sa.Column("normalized_alias", sa.String(240), primary_key=True),
        sa.Column("canonical_food_id", sa.String(32), sa.ForeignKey("canonical_food.canonical_food_id"), nullable=False),
    )
    op.create_table(
        "receipt_trusted_alias",
        sa.Column("retailer_scope", sa.String(240), primary_key=True),
        sa.Column("normalized_alias", sa.String(240), primary_key=True),
        sa.Column("canonical_food_id", sa.String(32), sa.ForeignKey("canonical_food.canonical_food_id", ondelete="CASCADE"), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("receipt_trusted_alias")
    op.drop_table("receipt_alias_vote")
    op.drop_table("receipt_cloud_call")
    op.drop_table("receipt_cloud_month")
    op.drop_table("receipt_upload_day")
    op.drop_column("receipt", "attempt_count")
    op.drop_column("receipt", "processing_deadline_at")
    op.drop_column("receipt", "processing_started_at")
