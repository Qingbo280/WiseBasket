"""correct SF022/SF024/SF025 stale bootstrap identity

Revision ID: e7a2c9f04b18
Revises: b3f7a1c2d4e5
Create Date: 2026-09-06 00:00:00.000000

Migration a7c9d2e1f604 seeded SF022/SF024/SF025 as apple/pork loin (lean)/
shrimp (medium) via `INSERT ... ON CONFLICT DO NOTHING` -- placeholder values
that never actually reached the authoritative production database (whose
real source_food_mapping, food_nutrition, and food_alias rows for these
three IDs have always, exclusively, referenced white bread, Indian mackerel,
and tomato respectively -- confirmed by direct inspection before writing
this migration; there is no orphaned apple/pork/shrimp data anywhere to
worry about). No later migration ever corrected canonical_food itself.

This migration is UPDATE-only (never INSERT/DELETE) and touches only
canonical_food.canonical_name / canonical_name_ms for these three rows. It
fails closed: if a row's current value is neither the known-stale value nor
the known-correct value, that row is left untouched and the migration
raises rather than guessing -- protecting a database that may already hold
some other, unanticipated value from being silently overwritten. SF023 is
deliberately not touched: its English identity ("potato") already matches
across every source; the Malay-spelling difference ("kentang" vs. "ubi
kentang") is a display variation, not a material identity error, and is
out of scope for this repair.

See docs/data_food_integrity/canonical_identity/ for the full audit trail.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e7a2c9f04b18"
down_revision: Union[str, Sequence[str], None] = "b3f7a1c2d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (canonical_food_id, known_stale_name, known_stale_name_ms, correct_name, correct_name_ms)
CORRECTIONS = [
    ("SF022", "apple", "epal", "white bread", "roti putih"),
    ("SF024", "pork loin (lean)", "daging babi", "indian mackerel", "ikan kembung"),
    ("SF025", "shrimp (medium)", "udang", "tomato", "tomato"),
]

# Post-rebuild (2026-09) identities for the same IDs, per the Data-team
# 201-food namespace. A database already holding one of these is in the new
# world where the stale/correct dichotomy above is moot -- a governed no-op,
# not an unexpected identity.
NEW_NAMESPACE_IDENTITY = {
    "SF022": "white prawn",
    "SF024": "spanish mackerel",
    "SF025": "indian mackerel",
}


def apply_corrections(bind, corrections=CORRECTIONS) -> None:
    """Core, directly-testable fail-closed correction logic (see module
    docstring). Raises RuntimeError -- which the caller's transaction turns
    into a rollback -- on any row holding a third, unrecognised identity."""
    for food_id, stale_name, stale_name_ms, correct_name, correct_name_ms in corrections:
        row = bind.execute(
            sa.text(
                "select canonical_name, canonical_name_ms from canonical_food "
                "where canonical_food_id = :fid"
            ),
            {"fid": food_id},
        ).fetchone()
        if row is None:
            # Nothing to correct on a database that never had this row at all
            # (e.g. a partial/older schema) -- not this migration's concern.
            continue
        current_name, current_name_ms = row
        if current_name == correct_name:
            # Already correct (the normal case for the real authoritative
            # database, which never actually held the stale value) -- no-op.
            continue
        if current_name == NEW_NAMESPACE_IDENTITY.get(food_id):
            # Already re-identified by the 2026-09 namespace rebuild -- the
            # stale/correct pair above predates the new namespace and must
            # not overwrite it. Governed no-op.
            continue
        if current_name != stale_name:
            raise RuntimeError(
                f"UNEXPECTED_IDENTITY: {food_id}.canonical_name is {current_name!r}, which is "
                f"neither the known-stale value ({stale_name!r}) nor the known-correct value "
                f"({correct_name!r}). Refusing to overwrite an identity this migration does not "
                f"recognise -- investigate before proceeding."
            )
        bind.execute(
            sa.text(
                "update canonical_food set canonical_name = :name, "
                "canonical_name_ms = :name_ms, updated_at = now() "
                "where canonical_food_id = :fid"
            ),
            {"name": correct_name, "name_ms": correct_name_ms, "fid": food_id},
        )


def revert_corrections(bind, corrections=CORRECTIONS) -> None:
    """Only reverts rows this migration itself would have changed."""
    for food_id, stale_name, stale_name_ms, correct_name, correct_name_ms in corrections:
        row = bind.execute(
            sa.text(
                "select canonical_name from canonical_food where canonical_food_id = :fid"
            ),
            {"fid": food_id},
        ).fetchone()
        if row is None or row[0] != correct_name:
            continue
        bind.execute(
            sa.text(
                "update canonical_food set canonical_name = :name, "
                "canonical_name_ms = :name_ms, updated_at = now() "
                "where canonical_food_id = :fid"
            ),
            {"name": stale_name, "name_ms": stale_name_ms, "fid": food_id},
        )


def upgrade() -> None:
    bind = op.get_bind()
    # 2026-09 namespace rebuild: on a database seeded with the new namespace
    # (SF201 present), the pre-rebuild identities this migration repairs no
    # longer exist -- the whole correction is a governed no-op there.
    if bind.execute(sa.text("SELECT 1 FROM canonical_food WHERE canonical_food_id = 'SF201'")).fetchone():
        return
    apply_corrections(bind)


def downgrade() -> None:
    bind = op.get_bind()
    # Namespace rebuild: upgrade was a no-op on new-namespace databases;
    # reverting would corrupt the new identities -- skip symmetrically.
    if bind.execute(sa.text("SELECT 1 FROM canonical_food WHERE canonical_food_id = 'SF201'")).fetchone():
        return
    revert_corrections(bind)
