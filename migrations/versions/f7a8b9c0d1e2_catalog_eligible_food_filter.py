"""Catalogue eligibility tag: show only the curated real-data foods.

Team decision (2026-09-10): the app catalogue and the optimizer candidate set
are restricted to the 124 foods with real PriceCatcher price coverage that the
team curated in real_priced_foods.csv. Everything else - reference-price-only
foods (FAMA/e-commerce estimates), zero-transaction foods, and quality-gated
observations (e.g. SF048 gelama's RM0.01 dirty row) - stays in the database
but is hidden from users (catalogue endpoint) and from the planner
(optimizer candidate identity SQL).

Mechanism: a boolean tag on canonical_food, filtered in the two serving paths
(load_full_catalogue + CANDIDATE_IDENTITY_SQL). The tag is data-driven so the
team can flip individual foods with an UPDATE (or an admin toggle later)
without a code deploy. Newly inserted foods default to visible (True) so test
seeds and future data-pipeline inserts keep working; the backfill below hides
the non-curated 201-namespace rows.

The backfill is guarded to 201-namespace databases only (SF110 = rice exists):
legacy 72-id environments keep all their foods visible because none of the 124
curated ids exist there.

Revision: f7a8b9c0d1e2
Revises: e6f7a8b9c0d1
"""
from alembic import op
import sqlalchemy as sa

revision = "f7a8b9c0d1e2"
down_revision = "e6f7a8b9c0d1"

# Curated real-data food list (real_priced_foods.csv, 2026-09-10 screening).
CATALOG_ELIGIBLE_FOOD_IDS = (
    'SF110', 'SF111', 'SF112', 'SF057', 'SF109', 'SF117', 'SF159', 'SF161', 'SF195', 'SF006', 'SF013', 'SF014', 'SF015', 'SF016', 'SF017', 'SF018', 'SF001', 'SF002', 'SF003', 'SF004', 'SF005', 'SF008', 'SF009', 'SF023', 'SF024', 'SF025', 'SF027', 'SF028', 'SF030', 'SF032', 'SF034', 'SF035', 'SF022', 'SF036', 'SF037', 'SF039', 'SF042', 'SF043', 'SF046', 'SF050', 'SF052', 'SF053', 'SF124', 'SF125', 'SF126', 'SF127', 'SF128', 'SF156', 'SF168', 'SF176', 'SF180', 'SF184', 'SF055', 'SF059', 'SF062', 'SF081', 'SF082', 'SF072', 'SF063', 'SF073', 'SF084', 'SF067', 'SF074', 'SF087', 'SF077', 'SF056', 'SF054', 'SF069', 'SF065', 'SF058', 'SF061', 'SF064', 'SF060', 'SF066', 'SF070', 'SF071', 'SF079', 'SF080', 'SF068', 'SF085', 'SF083', 'SF098', 'SF088', 'SF089', 'SF090', 'SF091', 'SF092', 'SF094', 'SF095', 'SF096', 'SF100', 'SF097', 'SF101', 'SF118', 'SF119', 'SF120', 'SF121', 'SF122', 'SF123', 'SF102', 'SF103', 'SF104', 'SF105', 'SF129', 'SF130', 'SF131', 'SF132', 'SF133', 'SF134', 'SF135', 'SF136', 'SF137', 'SF138', 'SF139', 'SF148', 'SF151', 'SF154', 'SF155', 'SF166', 'SF170', 'SF171', 'SF172', 'SF174', 'SF175'
)


def upgrade() -> None:
    op.execute(
        """
        alter table canonical_food
            add column if not exists catalog_eligible boolean not null default true
        """
    )
    is_201_namespace = op.get_bind().execute(
        sa.text("select 1 from canonical_food where canonical_food_id = 'SF110'")
    ).scalar()
    if is_201_namespace:
        id_list = ", ".join(f"'{fid}'" for fid in CATALOG_ELIGIBLE_FOOD_IDS)
        op.get_bind().execute(
            sa.text(
                "update canonical_food set catalog_eligible = false "
                "where status = 'ACTIVE' and canonical_food_id not in ("
                + id_list + ")"
            )
        )


def downgrade() -> None:
    op.execute("alter table canonical_food drop column catalog_eligible")