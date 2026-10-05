"""Add short-lived receipt images and idempotent duplicate-upload protection."""
from alembic import op
import sqlalchemy as sa


revision = "o7p8q9r0s1t"
down_revision = "n6o7p8q9r0s"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ``digest(bytea, 'sha256')`` is supplied by pgcrypto. A fresh PostgreSQL
    # database does not enable extensions automatically, so declare this
    # dependency before backfilling hashes for existing receipt images.
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.add_column("receipt", sa.Column("image_sha256", sa.String(64), nullable=True))
    op.add_column("receipt", sa.Column("image_expires_at", sa.DateTime(timezone=True), nullable=True))
    # Backfill lets existing receipt rows participate in idempotency before
    # enforcing NOT NULL.
    op.execute(
        """
        update receipt
        set image_sha256 = encode(digest(image_bytes, 'sha256'), 'hex'),
            image_expires_at = created_at + interval '24 hours'
        where image_sha256 is null
        """
    )
    op.alter_column("receipt", "image_sha256", nullable=False)
    op.alter_column("receipt", "image_expires_at", nullable=False)
    op.alter_column("receipt", "image_bytes", existing_type=sa.LargeBinary(), nullable=True)
    op.create_index(
        "uq_receipt_active_household_image_sha256",
        "receipt",
        ["household_id", "image_sha256"],
        unique=True,
        postgresql_where=sa.text("status in ('PENDING', 'PROCESSING')"),
    )
    op.create_index("ix_receipt_image_expires_at", "receipt", ["image_expires_at"])


def downgrade() -> None:
    # A downgrade cannot restore purged image bytes, so only allow it before
    # retention cleanup has run in the target environment.
    op.drop_index("ix_receipt_image_expires_at", table_name="receipt")
    op.drop_index("uq_receipt_active_household_image_sha256", table_name="receipt")
    op.alter_column("receipt", "image_bytes", existing_type=sa.LargeBinary(), nullable=False)
    op.drop_column("receipt", "image_expires_at")
    op.drop_column("receipt", "image_sha256")
