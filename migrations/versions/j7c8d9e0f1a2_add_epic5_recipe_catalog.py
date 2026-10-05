# Add the curated Epic 5 recipe catalogue and initial Malaysian recipe data.
# Revision ID: j7c8d9e0f1a2
# Revises: i6b7c8d9e0f1
# Create Date: 2026-09-13
from alembic import op
import sqlalchemy as sa


revision = "j7c8d9e0f1a2"
down_revision = "i6b7c8d9e0f1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "recipe_catalog",
        sa.Column("recipe_id", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("recipe_id"),
    )
    op.create_table(
        "recipe_catalog_ingredient",
        sa.Column("recipe_ingredient_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("recipe_id", sa.String(length=80), nullable=False),
        sa.Column("canonical_food_id", sa.String(length=32), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.CheckConstraint("display_order > 0", name="ck_recipe_catalog_ingredient_order_positive"),
        sa.ForeignKeyConstraint(["canonical_food_id"], ["canonical_food.canonical_food_id"]),
        sa.ForeignKeyConstraint(["recipe_id"], ["recipe_catalog.recipe_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("recipe_ingredient_id"),
        sa.UniqueConstraint("recipe_id", "canonical_food_id", name="uq_recipe_catalog_ingredient_food"),
        sa.UniqueConstraint("recipe_id", "display_order", name="uq_recipe_catalog_ingredient_order"),
    )
    op.create_table(
        "recipe_cooking_step",
        sa.Column("recipe_cooking_step_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("recipe_id", sa.String(length=80), nullable=False),
        sa.Column("step_number", sa.Integer(), nullable=False),
        sa.Column("instruction", sa.Text(), nullable=False),
        sa.CheckConstraint("step_number > 0", name="ck_recipe_cooking_step_number_positive"),
        sa.ForeignKeyConstraint(["recipe_id"], ["recipe_catalog.recipe_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("recipe_cooking_step_id"),
        sa.UniqueConstraint("recipe_id", "step_number", name="uq_recipe_cooking_step_order"),
    )

    recipe_catalog = sa.table(
        "recipe_catalog",
        sa.column("recipe_id", sa.String),
        sa.column("name", sa.String),
        sa.column("description", sa.Text),
        sa.column("active", sa.Boolean),
    )
    ingredient = sa.table(
        "recipe_catalog_ingredient",
        sa.column("recipe_id", sa.String),
        sa.column("canonical_food_id", sa.String),
        sa.column("required", sa.Boolean),
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
            {"recipe_id": "chicken-kangkung-stir-fry", "name": "Chicken & Kangkung Stir-fry", "description": "A quick stir-fry that makes practical use of chicken, kangkung and rice.", "active": True},
            {"recipe_id": "egg-fried-rice", "name": "Egg Fried Rice", "description": "A simple fried-rice meal using eggs and rice.", "active": True},
            {"recipe_id": "tofu-kangkung-stir-fry", "name": "Tofu & Kangkung Stir-fry", "description": "A simple vegetable-forward tofu stir-fry.", "active": True},
        ],
    )
    # Ingredient canonical_food_id values are the current 201-namespace IDs
    # (SF110 rice, SF018 chicken egg, SF074 water spinach, SF006 whole chicken,
    # SF107 tofu, SF056 onion, SF069 garlic, SF077 carrot) - the old 72-space
    # IDs collide with completely different foods and must never be used here.
    op.bulk_insert(
        ingredient,
        [
            {"recipe_id": "chicken-kangkung-stir-fry", "canonical_food_id": "SF006", "required": True, "display_order": 1},
            {"recipe_id": "chicken-kangkung-stir-fry", "canonical_food_id": "SF074", "required": True, "display_order": 2},
            {"recipe_id": "chicken-kangkung-stir-fry", "canonical_food_id": "SF110", "required": True, "display_order": 3},
            {"recipe_id": "chicken-kangkung-stir-fry", "canonical_food_id": "SF056", "required": False, "display_order": 4},
            {"recipe_id": "chicken-kangkung-stir-fry", "canonical_food_id": "SF069", "required": False, "display_order": 5},
            {"recipe_id": "egg-fried-rice", "canonical_food_id": "SF018", "required": True, "display_order": 1},
            {"recipe_id": "egg-fried-rice", "canonical_food_id": "SF110", "required": True, "display_order": 2},
            {"recipe_id": "egg-fried-rice", "canonical_food_id": "SF056", "required": False, "display_order": 3},
            {"recipe_id": "egg-fried-rice", "canonical_food_id": "SF077", "required": False, "display_order": 4},
            {"recipe_id": "tofu-kangkung-stir-fry", "canonical_food_id": "SF107", "required": True, "display_order": 1},
            {"recipe_id": "tofu-kangkung-stir-fry", "canonical_food_id": "SF074", "required": True, "display_order": 2},
            {"recipe_id": "tofu-kangkung-stir-fry", "canonical_food_id": "SF056", "required": False, "display_order": 3},
            {"recipe_id": "tofu-kangkung-stir-fry", "canonical_food_id": "SF069", "required": False, "display_order": 4},
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


def downgrade() -> None:
    op.drop_table("recipe_cooking_step")
    op.drop_table("recipe_catalog_ingredient")
    op.drop_table("recipe_catalog")
