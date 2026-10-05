"""backfill edible-yield conversions from trusted price observations

Revision ID: 2f4a1b8c9d00
Revises: c247125c677d
Create Date: 2026-09-06 18:15:00.000000

The live serving path resolves edible-basis prices from current
unit_conversion rows. Some environments already carry evidenced
food_price_observation.edible_yield_fraction values loaded by the
PriceCatcher data pipeline, but lack matching EDIBLE_YIELD conversion rows.
This migration promotes the latest valid value per canonical food into the
current conversion table so the resolver can serve those foods without
falling back to stale stored edible prices.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2f4a1b8c9d00"
down_revision: Union[str, Sequence[str], None] = "c247125c677d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EVIDENCE_NOTE = (
    "Backfilled from existing food_price_observation.edible_yield_fraction; "
    "latest valid observed value per canonical food at migration time."
)


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            insert into unit_conversion (
                canonical_food_id,
                conversion_type,
                source_unit,
                target_unit,
                factor,
                edible_yield_fraction,
                production_eligible,
                evidence_note
            )
            select
                latest.canonical_food_id,
                'EDIBLE_YIELD',
                'purchase_mass',
                'edible_mass',
                null,
                latest.edible_yield_fraction,
                true,
                :evidence_note
            from (
                select distinct on (fpo.canonical_food_id)
                    fpo.canonical_food_id,
                    fpo.edible_yield_fraction
                from food_price_observation fpo
                where fpo.canonical_food_id is not null
                  and fpo.quality_status in ('PASS', 'WARN')
                  and fpo.edible_yield_fraction is not null
                  and fpo.edible_yield_fraction > 0
                  and fpo.edible_yield_fraction <= 1
                order by
                    fpo.canonical_food_id,
                    fpo.observed_date desc,
                    fpo.price_observation_id desc
            ) latest
            where not exists (
                select 1
                from unit_conversion uc
                where uc.canonical_food_id = latest.canonical_food_id
                  and uc.conversion_type = 'EDIBLE_YIELD'
                  and uc.production_eligible = true
                  and uc.edible_yield_fraction is not null
            )
            """
        ).bindparams(evidence_note=EVIDENCE_NOTE)
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            delete from unit_conversion
            where conversion_type = 'EDIBLE_YIELD'
              and production_eligible = true
              and evidence_note = :evidence_note
            """
        ).bindparams(evidence_note=EVIDENCE_NOTE)
    )
