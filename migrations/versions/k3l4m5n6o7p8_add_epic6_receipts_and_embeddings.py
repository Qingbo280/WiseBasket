# Epic 6: receipt capture pipeline + food embeddings for semantic matching.
#
# - food_embedding: one BGE-M3 vector per canonical food (seeded offline by
#   scripts/seed_food_embeddings.py). Stored as a plain float array: 201 foods
#   fit in memory, cosine search in Python is milliseconds, and this keeps the
#   migration runnable on stock PostgreSQL 16 images (no pgvector extension
#   needed; upgrade path later = add a vector column + index when row counts
#   actually require it).
# - receipt / receipt_line: photo -> OCR (worker task calls the inference
#   service) -> proposed canonical-food matches -> user confirmation gate
#   writes PantryItem rows (source='RECEIPT', filling the Epic 5 placeholder).
#
# Revision ID: k3l4m5n6o7p8
# Revises: j7c8d9e0f1a2
# Create Date: 2026-09-14
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "k3l4m5n6o7p8"
down_revision = "j7c8d9e0f1a2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "food_embedding",
        sa.Column("canonical_food_id", sa.String(32), sa.ForeignKey("canonical_food.canonical_food_id"), primary_key=True),
        sa.Column("embedding", sa.ARRAY(sa.Float), nullable=False),
        sa.Column("model", sa.String(40), nullable=False, server_default="BAAI/bge-m3"),
        sa.Column("dim", sa.Integer, nullable=False, server_default="1024"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "receipt",
        sa.Column("receipt_id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("household_id", sa.Integer, sa.ForeignKey("households.id", ondelete="CASCADE"), nullable=False),
        sa.Column("uploaded_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("app_user.user_id", ondelete="SET NULL"), nullable=True),
        sa.Column("image_bytes", sa.LargeBinary, nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="PENDING"),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status in ('PENDING','PROCESSING','DONE','FAILED')", name="ck_receipt_status"),
    )
    op.create_index("ix_receipt_household", "receipt", ["household_id"])

    op.create_table(
        "receipt_line",
        sa.Column("line_id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("receipt_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("receipt.receipt_id", ondelete="CASCADE"), nullable=False),
        sa.Column("display_order", sa.Integer, nullable=False),
        sa.Column("name_raw", sa.String(240), nullable=False),
        sa.Column("qty", sa.Numeric(12, 3), nullable=True),
        sa.Column("unit", sa.String(24), nullable=True),
        sa.Column("price_rm", sa.Numeric(12, 2), nullable=True),
        sa.Column("canonical_food_id", sa.String(32), sa.ForeignKey("canonical_food.canonical_food_id"), nullable=True),
        sa.Column("match_score", sa.Float, nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="PROPOSED"),
        sa.CheckConstraint("status in ('PROPOSED','CONFIRMED','SKIPPED')", name="ck_receipt_line_status"),
        sa.CheckConstraint("display_order > 0", name="ck_receipt_line_order_positive"),
    )
    op.create_index("ix_receipt_line_receipt", "receipt_line", ["receipt_id"])


def downgrade() -> None:
    op.drop_index("ix_receipt_line_receipt", table_name="receipt_line")
    op.drop_table("receipt_line")
    op.drop_index("ix_receipt_household", table_name="receipt")
    op.drop_table("receipt")
    op.drop_table("food_embedding")
