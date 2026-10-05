"""add profile_data JSONB to user_profile

Stores the per-account app profile (household composition, budget, location,
restrictions, usual basket, habit adjustments) as a frontend-owned JSON blob
so a signed-in user never has to re-enter their details on a new device.

Revision ID: b3f7a1c2d4e5
Revises: a7c9d2e1f604
Create Date: 2026-08-30 02:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b3f7a1c2d4e5'
down_revision: Union[str, Sequence[str], None] = 'a7c9d2e1f604'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'user_profile',
        sa.Column('profile_data', sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('user_profile', 'profile_data')
