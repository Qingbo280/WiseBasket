"""add retail item_group/item_category to source_food_mapping.

Revision ID: d5e6f7a8b9c0
Revises: 2f4a1b8c9d00
Create Date: 2026-09-09

App-side item search (name / spec / price by item) needs the Data team's
item classification columns from lookup_item_FINAL.csv. The 493 namespace-
migration mappings are already imported; this migration only widens the
table and backfills the two columns from the same bundled JSON data.

Idempotent: ADD COLUMN IF NOT EXISTS + deterministic UPDATE from JSON.
Downgrade drops the columns.
"""
from pathlib import Path
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d5e6f7a8b9c0"
down_revision: Union[str, Sequence[str], None] = "2f4a1b8c9d00"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def upgrade() -> None:
    bind = op.get_bind()
    if not bind.execute(sa.text("SELECT to_regclass('public.source_food_mapping')")).scalar():
        return
    bind.execute(sa.text("ALTER TABLE source_food_mapping ADD COLUMN IF NOT EXISTS item_group VARCHAR(80)"))
    bind.execute(sa.text("ALTER TABLE source_food_mapping ADD COLUMN IF NOT EXISTS item_category VARCHAR(80)"))

    import json

    mappings = json.loads((DATA_DIR / "new_source_mappings_493.json").read_text(encoding="utf-8"))
    for m in mappings:
        bind.execute(sa.text(
            "UPDATE source_food_mapping SET item_group = :g, item_category = :c "
            "WHERE source_system = :s AND source_dataset_version = :v AND source_food_id = :fid"
        ), {"g": m["item_group"], "c": m["item_category"],
            "s": m["source_system"], "v": m["source_dataset_version"], "fid": m["source_food_id"]})


def downgrade() -> None:
    bind = op.get_bind()
    if not bind.execute(sa.text("SELECT to_regclass('public.source_food_mapping')")).scalar():
        return
    bind.execute(sa.text("ALTER TABLE source_food_mapping DROP COLUMN IF EXISTS item_category"))
    bind.execute(sa.text("ALTER TABLE source_food_mapping DROP COLUMN IF EXISTS item_group"))
