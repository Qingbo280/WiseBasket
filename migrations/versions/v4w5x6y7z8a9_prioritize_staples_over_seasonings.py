"""Apply reviewed staple-first metadata to the 35-recipe catalogue.

Revision ID: v4w5x6y7z8a9
Revises: u3v4w5x6y7z8
Create Date: 2026-09-21
"""

from alembic import op
import sqlalchemy as sa


revision = "v4w5x6y7z8a9"
down_revision = "u3v4w5x6y7z8"
branch_labels = None
depends_on = None


REVIEW_SOURCE = "WISEBASKET_35_RECIPE_STAPLE_FIRST_REVIEW_2026_09_21"
PREVIOUS_REVIEW_SOURCE = "WISEBASKET_CURATED_V2_INITIAL_SET_2026_09_21"

COMPLETE_MEALS = (
    "bihun-goreng",
    "dhal-curry-with-rice",
    "egg-potato-curry-with-rice",
    "maggi-goreng",
    "malay-chicken-soup",
    "mee-goreng",
    "onion-omelette",
    "sardine-sambal-with-rice",
    "soy-sauce-mackerel-with-rice",
    "tofu-cabbage-stir-fry",
    "tomato-chicken-with-rice",
    "tomato-egg-stir-fry",
    "tomato-tofu-with-rice",
    "turmeric-chicken-with-rice",
)

MAIN_DISHES = (
    "garlic-prawn-stir-fry",
    "long-bean-egg-stir-fry",
    "malaysian-chicken-curry-with-rice",
    "potato-onion-stir-fry",
    "red-tilapia-soy-with-rice",
    "sambal-eggplant-with-rice",
    "soy-sauce-chicken-with-rice",
    "soy-sauce-eggs-with-rice",
    "squid-soy-stir-fry",
    "steamed-egg",
    "tofu-prawn-stir-fry",
)

SIDES = (
    "cabbage-mamak-stir-fry",
    "cauliflower-stir-fry",
    "french-bean-garlic-stir-fry",
    "garlic-broccoli-stir-fry",
    "garlic-long-beans",
    "garlic-spinach-stir-fry",
    "mixed-vegetable-stir-fry",
    "mustard-greens-stir-fry",
    "okra-eggplant-stir-fry",
    "winged-bean-stir-fry",
)

ALL_RECIPES = tuple(sorted((*COMPLETE_MEALS, *MAIN_DISHES, *SIDES)))

ROLE_FOOD_IDS = {
    "STAPLE": ("SF057", "SF109", "SF110", "SF159", "SF161"),
    "MAIN_PROTEIN": (
        "SF006", "SF014", "SF018", "SF022", "SF024", "SF035", "SF042",
        "SF107", "SF124", "SF156",
    ),
    "MAIN_VEGETABLE": (
        "SF055", "SF056", "SF062", "SF063", "SF067", "SF068", "SF072",
        "SF073", "SF077", "SF079", "SF081", "SF082", "SF084",
    ),
    "COOKING_ESSENTIAL": ("SF102", "SF129", "SF130", "SF131", "SF132", "SF170"),
}

# These rows add flavour but must not block a meal or outrank staple foods.
# The classification is recipe-specific so substantial onion remains a main
# vegetable while small amounts of garlic, chili and powdered spices do not.
SEASONING_ROWS = (
    ("cabbage-mamak-stir-fry", "SF135"),
    ("dhal-curry-with-rice", "SF135"),
    ("egg-potato-curry-with-rice", "SF133"),
    ("french-bean-garlic-stir-fry", "SF069"),
    ("garlic-broccoli-stir-fry", "SF069"),
    ("garlic-long-beans", "SF069"),
    ("garlic-long-beans", "SF058"),
    ("garlic-prawn-stir-fry", "SF069"),
    ("garlic-spinach-stir-fry", "SF069"),
    ("malay-chicken-soup", "SF134"),
    ("malaysian-chicken-curry-with-rice", "SF133"),
    ("potato-onion-stir-fry", "SF135"),
    ("sambal-eggplant-with-rice", "SF052"),
    ("sardine-sambal-with-rice", "SF139"),
    ("sardine-sambal-with-rice", "SF098"),
    ("soy-sauce-eggs-with-rice", "SF118"),
    ("soy-sauce-mackerel-with-rice", "SF118"),
    ("tomato-chicken-with-rice", "SF135"),
    ("tomato-tofu-with-rice", "SF118"),
    ("turmeric-chicken-with-rice", "SF135"),
)


def set_meal_type(recipe_ids: tuple[str, ...], meal_type: str) -> None:
    recipe = sa.table(
        "recipe_catalog",
        sa.column("recipe_id", sa.String()),
        sa.column("meal_type", sa.String()),
        sa.column("recipe_version", sa.Integer()),
        sa.column("review_source", sa.String()),
    )
    op.get_bind().execute(
        recipe.update()
        .where(recipe.c.recipe_id.in_(recipe_ids))
        .values(
            meal_type=meal_type,
            recipe_version=2,
            review_source=REVIEW_SOURCE,
        )
    )


def upgrade() -> None:
    connection = op.get_bind()
    ingredient = sa.table(
        "recipe_catalog_ingredient",
        sa.column("recipe_id", sa.String()),
        sa.column("canonical_food_id", sa.String()),
        sa.column("base_quantity_g", sa.Numeric()),
        sa.column("required", sa.Boolean()),
        sa.column("ingredient_role", sa.String()),
    )

    # Reapply every role deterministically rather than preserving the generic
    # category backfill. Optional catalogue rows stay non-gating.
    connection.execute(
        ingredient.update()
        .where(ingredient.c.recipe_id.in_(ALL_RECIPES))
        .values(ingredient_role="OPTIONAL", required=False)
    )
    for role, food_ids in ROLE_FOOD_IDS.items():
        connection.execute(
            ingredient.update()
            .where(
                ingredient.c.recipe_id.in_(ALL_RECIPES),
                ingredient.c.canonical_food_id.in_(food_ids),
                ingredient.c.base_quantity_g.is_not(None),
            )
            .values(ingredient_role=role, required=True)
        )
    for recipe_id, food_id in SEASONING_ROWS:
        connection.execute(
            ingredient.update()
            .where(
                ingredient.c.recipe_id == recipe_id,
                ingredient.c.canonical_food_id == food_id,
            )
            .values(ingredient_role="SEASONING", required=False)
        )

    set_meal_type(COMPLETE_MEALS, "COMPLETE_MEAL")
    set_meal_type(MAIN_DISHES, "MAIN_DISH")
    set_meal_type(SIDES, "SIDE")


def downgrade() -> None:
    # Restore the deterministic category-based draft state created by t2.
    op.execute(
        sa.text(
            """
            UPDATE recipe_catalog_ingredient AS ingredient
            SET required = ingredient.base_quantity_g IS NOT NULL,
                ingredient_role = CASE
                    WHEN ingredient.base_quantity_g IS NULL THEN 'OPTIONAL'
                    WHEN food.category = 'protein' THEN 'MAIN_PROTEIN'
                    WHEN food.category = 'carbohydrate' THEN 'STAPLE'
                    WHEN food.category = 'vegetables' THEN 'MAIN_VEGETABLE'
                    ELSE 'COOKING_ESSENTIAL'
                END
            FROM canonical_food AS food
            WHERE food.canonical_food_id = ingredient.canonical_food_id
              AND ingredient.recipe_id IN :recipe_ids
            """
        ).bindparams(sa.bindparam("recipe_ids", expanding=True, value=ALL_RECIPES))
    )
    op.execute(
        sa.text(
            """
            UPDATE recipe_catalog AS recipe
            SET meal_type = CASE
                WHEN EXISTS (
                    SELECT 1 FROM recipe_catalog_ingredient i
                    WHERE i.recipe_id = recipe.recipe_id
                      AND i.required AND i.ingredient_role = 'MAIN_PROTEIN'
                ) AND EXISTS (
                    SELECT 1 FROM recipe_catalog_ingredient i
                    WHERE i.recipe_id = recipe.recipe_id
                      AND i.required AND i.ingredient_role = 'STAPLE'
                ) AND EXISTS (
                    SELECT 1 FROM recipe_catalog_ingredient i
                    WHERE i.recipe_id = recipe.recipe_id
                      AND i.required AND i.ingredient_role = 'MAIN_VEGETABLE'
                ) THEN 'COMPLETE_MEAL'
                WHEN EXISTS (
                    SELECT 1 FROM recipe_catalog_ingredient i
                    WHERE i.recipe_id = recipe.recipe_id
                      AND i.required
                      AND i.ingredient_role IN ('MAIN_PROTEIN', 'STAPLE')
                ) THEN 'MAIN_DISH'
                ELSE 'SIDE'
            END,
            recipe_version = 1,
            review_source = CASE
                WHEN recipe_id IN :enabled_recipes THEN :previous_source
                ELSE NULL
            END
            WHERE recipe_id IN :recipe_ids
            """
        ).bindparams(
            sa.bindparam("recipe_ids", expanding=True, value=ALL_RECIPES),
            sa.bindparam(
                "enabled_recipes",
                expanding=True,
                value=(
                    "dhal-curry-with-rice",
                    "egg-potato-curry-with-rice",
                    "malay-chicken-soup",
                    "onion-omelette",
                    "tomato-egg-stir-fry",
                    "turmeric-chicken-with-rice",
                ),
            ),
            sa.bindparam("previous_source", value=PREVIOUS_REVIEW_SOURCE),
        )
    )
