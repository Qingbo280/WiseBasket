"""bridge orphaned database revision

Revision ID: c247125c677d
Revises: f19b6d84c3a7
Create Date: 2026-09-06 18:20:00.000000

UAT reported this Alembic revision in alembic_version, but the matching
migration file is not present in current develop or reachable Git history.
Keep the revision graph connected so existing databases can upgrade from
their recorded state, and fresh databases can still pass through this
revision deterministically.
"""
from __future__ import annotations

from typing import Sequence, Union


revision: str = "c247125c677d"
down_revision: Union[str, Sequence[str], None] = "f19b6d84c3a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
