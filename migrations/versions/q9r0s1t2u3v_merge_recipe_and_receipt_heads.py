"""Merge recipe-seed cleanup and receipt/pantry migration heads.

Revision ID: q9r0s1t2u3v
Revises: o7p8q9r0s1t2, p8q9r0s1t2u
Create Date: 2026-09-16

Both parent revisions contain independent, already-required schema/data work.
This merge revision intentionally performs no DDL; it restores one Alembic
head so deployment can safely use ``alembic upgrade head``.
"""

from typing import Sequence, Union


revision: str = "q9r0s1t2u3v"
down_revision: Union[str, Sequence[str], None] = ("o7p8q9r0s1t2", "p8q9r0s1t2u")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Join independent migration branches without schema changes."""


def downgrade() -> None:
    """Split the Alembic graph back to its two parent revisions."""
