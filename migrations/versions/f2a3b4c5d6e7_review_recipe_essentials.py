"""Correct essential ingredients in the reviewed 35-recipe collection.

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-09-29

The 125 optional rows were reviewed against all 35 cooking methods. Promote
the 85 ingredients explicitly required to execute those methods (cooking
oil, aromatics, mustard seeds, and bihun's dried chili), with conservative
two-serving minimums. The other 40 adjustable seasonings and extra vegetables
remain optional. Butter-fried spinach and steamed egg have no cooking oil.
"""

from alembic import op
import sqlalchemy as sa


revision = "f2a3b4c5d6e7"
down_revision = "e1f2a3b4c5d6"
branch_labels = None
depends_on = None

OIL_RECIPE_IDS = (
    "bihun-goreng",
    "cabbage-mamak-stir-fry",
    "cauliflower-stir-fry",
    "dhal-curry-with-rice",
    "egg-potato-curry-with-rice",
    "french-bean-garlic-stir-fry",
    "garlic-broccoli-stir-fry",
    "garlic-long-beans",
    "garlic-prawn-stir-fry",
    "long-bean-egg-stir-fry",
    "maggi-goreng",
    "malay-chicken-soup",
    "malaysian-chicken-curry-with-rice",
    "mee-goreng",
    "mixed-vegetable-stir-fry",
    "mustard-greens-stir-fry",
    "okra-eggplant-stir-fry",
    "onion-omelette",
    "potato-onion-stir-fry",
    "red-tilapia-soy-with-rice",
    "sambal-eggplant-with-rice",
    "sardine-sambal-with-rice",
    "soy-sauce-chicken-with-rice",
    "soy-sauce-eggs-with-rice",
    "soy-sauce-mackerel-with-rice",
    "squid-soy-stir-fry",
    "tofu-cabbage-stir-fry",
    "tofu-prawn-stir-fry",
    "tomato-chicken-with-rice",
    "tomato-egg-stir-fry",
    "tomato-tofu-with-rice",
    "turmeric-chicken-with-rice",
    "winged-bean-stir-fry",
)

ESSENTIAL_BASE_G = {
    "SF120": 10,  # cooking oil, minimum for frying/sauteing two servings
    "SF069": 9,   # garlic; matches the reviewed garlic stir-fries' 9-12 g
    "SF056": 110, # onion; matches the reviewed omelette/stir-fry quantities
    "SF071": 10,  # ginger
    "SF054": 30,  # shallot
    "SF148": 2,   # mustard seeds for tempering
    "SF060": 5,   # dried chili in bihun goreng only
}

# Exact reviewed optional rows. Downgrade must not touch garlic/onion rows
# that were already required and happen to share one of the new quantities.
PROMOTION_RECIPE_IDS = {
    "SF120": OIL_RECIPE_IDS,
    "SF069": (
        "bihun-goreng", "cabbage-mamak-stir-fry", "cauliflower-stir-fry",
        "dhal-curry-with-rice", "egg-potato-curry-with-rice",
        "long-bean-egg-stir-fry", "maggi-goreng", "malay-chicken-soup",
        "mee-goreng", "mixed-vegetable-stir-fry", "mustard-greens-stir-fry",
        "okra-eggplant-stir-fry", "potato-onion-stir-fry",
        "red-tilapia-soy-with-rice", "sardine-sambal-with-rice",
        "soy-sauce-chicken-with-rice", "soy-sauce-eggs-with-rice",
        "soy-sauce-mackerel-with-rice", "squid-soy-stir-fry",
        "tofu-cabbage-stir-fry", "tomato-chicken-with-rice",
        "turmeric-chicken-with-rice", "winged-bean-stir-fry",
    ),
    "SF056": (
        "bihun-goreng", "dhal-curry-with-rice", "egg-potato-curry-with-rice",
        "maggi-goreng", "malay-chicken-soup",
        "malaysian-chicken-curry-with-rice", "red-tilapia-soy-with-rice",
        "soy-sauce-chicken-with-rice", "soy-sauce-eggs-with-rice",
        "soy-sauce-mackerel-with-rice", "squid-soy-stir-fry",
        "tomato-chicken-with-rice", "turmeric-chicken-with-rice",
    ),
    "SF071": (
        "bihun-goreng", "egg-potato-curry-with-rice",
        "garlic-prawn-stir-fry", "malay-chicken-soup",
        "red-tilapia-soy-with-rice", "soy-sauce-chicken-with-rice",
        "tofu-prawn-stir-fry", "tomato-chicken-with-rice",
    ),
    "SF054": (
        "cabbage-mamak-stir-fry", "garlic-long-beans",
        "long-bean-egg-stir-fry", "mee-goreng",
        "mixed-vegetable-stir-fry",
    ),
    "SF148": ("cabbage-mamak-stir-fry", "dhal-curry-with-rice"),
    "SF060": ("bihun-goreng",),
}


def _ingredient():
    return sa.table(
        "recipe_catalog_ingredient",
        sa.column("recipe_id", sa.String()),
        sa.column("canonical_food_id", sa.String()),
        sa.column("required", sa.Boolean()),
        sa.column("base_quantity_g", sa.Numeric()),
        sa.column("ingredient_role", sa.String()),
    )


def upgrade() -> None:
    ingredient = _ingredient()
    for food_id, quantity_g in ESSENTIAL_BASE_G.items():
        recipe_ids = PROMOTION_RECIPE_IDS[food_id]
        op.get_bind().execute(
            ingredient.update()
            .where(
                ingredient.c.recipe_id.in_(recipe_ids),
                ingredient.c.canonical_food_id == food_id,
                ingredient.c.required.is_(False),
                ingredient.c.base_quantity_g.is_(None),
            )
            .values(required=True, base_quantity_g=quantity_g,
                    ingredient_role="COOKING_ESSENTIAL")
        )


def downgrade() -> None:
    ingredient = _ingredient()
    for food_id, quantity_g in ESSENTIAL_BASE_G.items():
        recipe_ids = PROMOTION_RECIPE_IDS[food_id]
        op.get_bind().execute(
            ingredient.update()
            .where(
                ingredient.c.recipe_id.in_(recipe_ids),
                ingredient.c.canonical_food_id == food_id,
                ingredient.c.required.is_(True),
                ingredient.c.base_quantity_g == quantity_g,
                ingredient.c.ingredient_role == "COOKING_ESSENTIAL",
            )
            .values(required=False, base_quantity_g=None, ingredient_role="OPTIONAL")
        )
