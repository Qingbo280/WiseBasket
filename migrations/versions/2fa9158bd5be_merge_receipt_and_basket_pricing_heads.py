"""merge receipt and basket pricing heads

Revision ID: 2fa9158bd5be
Revises: a9b0c1d2e3f4, z9y8x7w6v5u4
Create Date: 2026-09-24 23:23:35.801105

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2fa9158bd5be'
down_revision: Union[str, Sequence[str], None] = ('a9b0c1d2e3f4', 'z9y8x7w6v5u4')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
