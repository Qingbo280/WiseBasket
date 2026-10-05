"""Merge receipt-batch and develop catalog migration histories.

Revision ID: d0e1f2a3b4c5
Revises: a9b0c1d2e3f4, z9y8x7w6v5u4
Create Date: 2026-09-25

Both parent branches have already applied their own schema changes. This
revision only joins their histories so ``alembic upgrade head`` is unambiguous.
"""

revision = "d0e1f2a3b4c5"
down_revision = ("a9b0c1d2e3f4", "z9y8x7w6v5u4")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
