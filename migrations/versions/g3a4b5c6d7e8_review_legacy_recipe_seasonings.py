"""Review the additional 20 optional rows introduced by the staple-first migration.

Revision ID: g3a4b5c6d7e8
Revises: f2a3b4c5d6e7

Restore 15 method-defining aromatics/spices to required, preserving their
already reviewed quantities. Keep chili, sugar and finishing lime optional.
Do not change meal types, optimizer eligibility, or catalogue identities.
"""
from alembic import op
import sqlalchemy as sa

revision = "g3a4b5c6d7e8"
down_revision = "f2a3b4c5d6e7"
branch_labels = None
depends_on = None

# Exact post-v4 rows and existing two-serving amounts. Guards preserve any
# subsequent recipe edits; rollback restores SEASONING, not generic OPTIONAL.
REVIEWED_ESSENTIALS = (
    ("cabbage-mamak-stir-fry", "SF135", 1),
    ("dhal-curry-with-rice", "SF135", 1),
    ("egg-potato-curry-with-rice", "SF133", 16),
    ("french-bean-garlic-stir-fry", "SF069", 9),
    ("garlic-broccoli-stir-fry", "SF069", 9),
    ("garlic-long-beans", "SF069", 12),
    ("garlic-prawn-stir-fry", "SF069", 12),
    ("garlic-spinach-stir-fry", "SF069", 12),
    ("malay-chicken-soup", "SF134", 6),
    ("malaysian-chicken-curry-with-rice", "SF133", 10),
    ("potato-onion-stir-fry", "SF135", 2),
    ("sambal-eggplant-with-rice", "SF052", 8),
    ("sardine-sambal-with-rice", "SF139", 30),
    ("tomato-chicken-with-rice", "SF135", 5),
    ("turmeric-chicken-with-rice", "SF135", 7),
)


def _update(*, required: bool) -> None:
    ingredient = sa.table(
        "recipe_catalog_ingredient",
        sa.column("recipe_id", sa.String()),
        sa.column("canonical_food_id", sa.String()),
        sa.column("required", sa.Boolean()),
        sa.column("base_quantity_g", sa.Numeric()),
        sa.column("ingredient_role", sa.String()),
    )
    for recipe_id, food_id, grams in REVIEWED_ESSENTIALS:
        op.get_bind().execute(ingredient.update().where(
            ingredient.c.recipe_id == recipe_id,
            ingredient.c.canonical_food_id == food_id,
            ingredient.c.base_quantity_g == grams,
            ingredient.c.required.is_(not required),
            ingredient.c.ingredient_role == ("SEASONING" if required else "COOKING_ESSENTIAL"),
        ).values(required=required,
                 ingredient_role="COOKING_ESSENTIAL" if required else "SEASONING"))


def upgrade() -> None:
    _update(required=True)


def downgrade() -> None:
    _update(required=False)
