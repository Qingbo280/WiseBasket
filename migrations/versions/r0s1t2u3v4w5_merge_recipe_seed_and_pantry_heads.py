"""Merge the epic5 35-recipe seed head with the receipt/pantry merge head.

PR #199 (2026-09-17) added ``p3q4r5s6t7u8`` (seed the 35 curated Malaysian
recipes) parenting on ``o7p8q9r0s1t2``, but develop's single head had
already moved to the no-DDL merge revision ``q9r0s1t2u3v`` (which joins
``o7p8q9r0s1t2`` and ``p8q9r0s1t2u``). The merged graph therefore has TWO
heads (``q9r0s1t2u3v`` and ``p3q4r5s6t7u8``) and any ``alembic upgrade
head`` errors with "multiple heads".

This merge revision intentionally performs no DDL; it restores one
Alembic head so ``upgrade head`` works again. Same pattern as
``q9r0s1t2u3v_merge_recipe_and_receipt_heads``.

Revision ID: r0s1t2u3v4w5
Revises: q9r0s1t2u3v, p3q4r5s6t7u8
Create Date: 2026-09-17 14:30:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "r0s1t2u3v4w5"
down_revision: Union[str, Sequence[str], None] = (
    "q9r0s1t2u3v",
    "p3q4r5s6t7u8",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Join the two independent heads without schema or data changes."""
    pass


def downgrade() -> None:
    """Re-splitting heads is not meaningful; keep as a no-op."""
    pass
