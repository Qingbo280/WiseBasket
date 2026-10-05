"""Join the cumulative Epic 5/6 branch with the latest develop history.

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5, 2fa9158bd5be
Create Date: 2026-09-25

Both parent revisions are no-DDL merges of the same receipt and catalogue
histories. Keeping both published revisions intact lets either deployment
history upgrade to one unambiguous head.
"""

revision = "e1f2a3b4c5d6"
down_revision = ("d0e1f2a3b4c5", "2fa9158bd5be")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
