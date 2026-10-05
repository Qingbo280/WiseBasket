# Remove the three curated Epic 5 seed recipes from the production catalogue.
# Revision ID: o7p8q9r0s1t2
# Revises: n6o7p8q9r0s
# Create Date: 2026-09-15
#
# The Epic 5 recipe catalogue is now supplied by the collected 35-recipe
# dataset (team data handoff 2026-09-15), superseding the three hand-written
# seed recipes from j7c8d9e0f1a2/n6o7p8q9r0s. The seeds remain available as
# test-owned fixtures (tests/epic5/conftest.py). This delete is idempotent:
# databases where the seeds were already removed manually (UAT yamabiko,
# cleaned 2026-09-15) simply no-op.
from alembic import op
import sqlalchemy as sa


revision = "o7p8q9r0s1t2"
down_revision = "n6o7p8q9r0s"
branch_labels = None
depends_on = None

SEED_RECIPE_IDS = (
    "chicken-kangkung-stir-fry",
    "egg-fried-rice",
    "tofu-kangkung-stir-fry",
)


def upgrade() -> None:
    # Children first, explicitly, so the delete does not rely on the FK
    # cascade being present; then the catalogue rows themselves.
    op.execute(
        """
        delete from recipe_catalog_ingredient
        where recipe_id in (
            'chicken-kangkung-stir-fry',
            'egg-fried-rice',
            'tofu-kangkung-stir-fry'
        )
        """
    )
    op.execute(
        """
        delete from recipe_cooking_step
        where recipe_id in (
            'chicken-kangkung-stir-fry',
            'egg-fried-rice',
            'tofu-kangkung-stir-fry'
        )
        """
    )
    op.execute(
        """
        delete from recipe_catalog
        where recipe_id in (
            'chicken-kangkung-stir-fry',
            'egg-fried-rice',
            'tofu-kangkung-stir-fry'
        )
        """
    )


def downgrade() -> None:
    # Restore the exact seed data of j7c8d9e0f1a2 (rows) + n6o7p8q9r0s
    # (base_servings=2 and required-gram quantities).
    recipe_catalog = sa.table(
        "recipe_catalog",
        sa.column("recipe_id", sa.String),
        sa.column("name", sa.String),
        sa.column("description", sa.Text),
        sa.column("active", sa.Boolean),
        sa.column("base_servings", sa.Integer),
    )
    ingredient = sa.table(
        "recipe_catalog_ingredient",
        sa.column("recipe_id", sa.String),
        sa.column("canonical_food_id", sa.String),
        sa.column("required", sa.Boolean),
        sa.column("base_quantity_g", sa.Numeric),
        sa.column("display_order", sa.Integer),
    )
    cooking_step = sa.table(
        "recipe_cooking_step",
        sa.column("recipe_id", sa.String),
        sa.column("step_number", sa.Integer),
        sa.column("instruction", sa.Text),
    )
    op.bulk_insert(
        recipe_catalog,
        [
            {"recipe_id": "chicken-kangkung-stir-fry", "name": "Chicken & Kangkung Stir-fry", "description": "A quick stir-fry that makes practical use of chicken, kangkung and rice.", "active": True, "base_servings": 2},
            {"recipe_id": "egg-fried-rice", "name": "Egg Fried Rice", "description": "A simple fried-rice meal using eggs and rice.", "active": True, "base_servings": 2},
            {"recipe_id": "tofu-kangkung-stir-fry", "name": "Tofu & Kangkung Stir-fry", "description": "A simple vegetable-forward tofu stir-fry.", "active": True, "base_servings": 2},
        ],
    )
    op.bulk_insert(
        ingredient,
        [
            {"recipe_id": "chicken-kangkung-stir-fry", "canonical_food_id": "SF006", "required": True, "base_quantity_g": 300, "display_order": 1},
            {"recipe_id": "chicken-kangkung-stir-fry", "canonical_food_id": "SF074", "required": True, "base_quantity_g": 200, "display_order": 2},
            {"recipe_id": "chicken-kangkung-stir-fry", "canonical_food_id": "SF110", "required": True, "base_quantity_g": 160, "display_order": 3},
            {"recipe_id": "chicken-kangkung-stir-fry", "canonical_food_id": "SF056", "required": False, "base_quantity_g": None, "display_order": 4},
            {"recipe_id": "chicken-kangkung-stir-fry", "canonical_food_id": "SF069", "required": False, "base_quantity_g": None, "display_order": 5},
            {"recipe_id": "egg-fried-rice", "canonical_food_id": "SF018", "required": True, "base_quantity_g": 100, "display_order": 1},
            {"recipe_id": "egg-fried-rice", "canonical_food_id": "SF110", "required": True, "base_quantity_g": 160, "display_order": 2},
            {"recipe_id": "egg-fried-rice", "canonical_food_id": "SF056", "required": False, "base_quantity_g": None, "display_order": 3},
            {"recipe_id": "egg-fried-rice", "canonical_food_id": "SF077", "required": False, "base_quantity_g": None, "display_order": 4},
            {"recipe_id": "tofu-kangkung-stir-fry", "canonical_food_id": "SF107", "required": True, "base_quantity_g": 300, "display_order": 1},
            {"recipe_id": "tofu-kangkung-stir-fry", "canonical_food_id": "SF074", "required": True, "base_quantity_g": 200, "display_order": 2},
            {"recipe_id": "tofu-kangkung-stir-fry", "canonical_food_id": "SF056", "required": False, "base_quantity_g": None, "display_order": 3},
            {"recipe_id": "tofu-kangkung-stir-fry", "canonical_food_id": "SF069", "required": False, "base_quantity_g": None, "display_order": 4},
        ],
    )
    op.bulk_insert(
        cooking_step,
        [
            {"recipe_id": "chicken-kangkung-stir-fry", "step_number": 1, "instruction": "Wash the chicken and kangkung."},
            {"recipe_id": "chicken-kangkung-stir-fry", "step_number": 2, "instruction": "Stir-fry chicken until it is cooked through."},
            {"recipe_id": "chicken-kangkung-stir-fry", "step_number": 3, "instruction": "Add kangkung and any preferred seasoning, then stir-fry for 2 to 3 minutes."},
            {"recipe_id": "chicken-kangkung-stir-fry", "step_number": 4, "instruction": "Serve with rice."},
            {"recipe_id": "egg-fried-rice", "step_number": 1, "instruction": "Scramble the eggs in a hot pan."},
            {"recipe_id": "egg-fried-rice", "step_number": 2, "instruction": "Add rice and stir-fry until heated through."},
            {"recipe_id": "egg-fried-rice", "step_number": 3, "instruction": "Add any preferred vegetables or seasoning, then serve."},
            {"recipe_id": "tofu-kangkung-stir-fry", "step_number": 1, "instruction": "Pan-fry tofu until lightly golden."},
            {"recipe_id": "tofu-kangkung-stir-fry", "step_number": 2, "instruction": "Add kangkung, then stir-fry until tender."},
            {"recipe_id": "tofu-kangkung-stir-fry", "step_number": 3, "instruction": "Add any preferred vegetables or seasoning and serve."},
        ],
    )
