"""Close hard-exclusion mapping gaps found in the 2026-09-11 audit.

Audit (UAT DB, catalog-eligible foods vs restriction keywords) found 12
identity-exact gaps in hard_exclusion_food:

- NO_PORK: SF008 pork belly was unmapped (only SF009 pork lean & fat was).
- SHELLFISH: SF036 tiger prawn, SF037 flower crab, SF042 squid,
  SF052 dried shrimp, SF053 dried squid were unmapped (only SF022 white
  prawn and SF131 oyster sauce were).
- PEANUTS: SF172 peanut butter was unmapped (only SF127 peanuts was).
- MILK: SF166 sweetened condensed milk, SF168 cheese slices, SF170 butter
  were unmapped (only SF176 fresh / UHT milk was). The legacy "dairy"
  allergy tag maps to the MILK code, so all milk-derived products belong
  under it.

Not changed (deliberate):
- VEGETARIAN keeps its meat/seafood rows only; whether egg/dairy count as
  vegetarian is a product decision (ovo-vegetarian is common in Malaysia).
- Egg-/dairy-containing processed foods (e.g. egg noodles) are whole-food
  level mappings; ingredient-level tagging is out of scope.
- Coconut milk / soy milk are correctly NOT mapped to MILK.

Idempotent (ON CONFLICT DO NOTHING) and guarded by food existence so any
database state can take it safely.

Revision: g1a2b3c4d5e6
Revises: f7a8b9c0d1e2
Create Date: 2026-09-11
"""
from alembic import op

revision = "g1a2b3c4d5e6"
down_revision = "f7a8b9c0d1e2"
branch_labels = None
depends_on = None

# (exclusion_code, canonical_food_id, identity note)
GAP_ROWS = [
    ("NO_PORK", "SF008", "pork belly"),
    ("SHELLFISH", "SF036", "tiger prawn"),
    ("SHELLFISH", "SF037", "flower crab"),
    ("SHELLFISH", "SF042", "squid"),
    ("SHELLFISH", "SF052", "dried shrimp"),
    ("SHELLFISH", "SF053", "dried squid"),
    ("PEANUTS", "SF172", "peanut butter"),
    ("MILK", "SF166", "sweetened condensed milk"),
    ("MILK", "SF168", "cheese slices"),
    ("MILK", "SF170", "butter"),
]


def upgrade() -> None:
    for code, food_id, _note in GAP_ROWS:
        op.execute(
            f"""
            insert into hard_exclusion_food (exclusion_code, canonical_food_id)
            select '{code}', '{food_id}'
            where exists (select 1 from canonical_food where canonical_food_id = '{food_id}')
            on conflict do nothing
            """
        )


def downgrade() -> None:
    for code, food_id, _note in GAP_ROWS:
        op.execute(
            f"delete from hard_exclusion_food where exclusion_code = '{code}' and canonical_food_id = '{food_id}'"
        )
