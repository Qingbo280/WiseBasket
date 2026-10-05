"""Backfill deterministic V2 draft metadata for the curated recipes.

Revision ID: t2u3v4w5x6y7
Revises: s1t2u3v4w5x6
Create Date: 2026-09-21
"""

from alembic import op


revision = "t2u3v4w5x6y7"
down_revision = "s1t2u3v4w5x6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # These fields are structural defaults, not human approval. Recipes stay
    # DRAFT and optimizer_eligible remains false until step and safety review.
    op.execute(
        """
        UPDATE recipe_catalog
        SET recipe_version = COALESCE(recipe_version, 1),
            review_status = COALESCE(review_status, 'DRAFT'),
            quantity_basis = COALESCE(quantity_basis, 'RAW_EDIBLE_KG'),
            max_weekly_occurrences = COALESCE(max_weekly_occurrences, 3)
        WHERE active
        """
    )

    # Required ingredient roles derive only from existing canonical categories.
    # Optional rows remain OPTIONAL so they can never block a counted meal.
    op.execute(
        """
        UPDATE recipe_catalog_ingredient AS ingredient
        SET ingredient_role = CASE
            WHEN NOT ingredient.required THEN 'OPTIONAL'
            WHEN food.category = 'protein' THEN 'MAIN_PROTEIN'
            WHEN food.category = 'carbohydrate' THEN 'STAPLE'
            WHEN food.category = 'vegetables' THEN 'MAIN_VEGETABLE'
            ELSE 'COOKING_ESSENTIAL'
        END
        FROM canonical_food AS food
        WHERE food.canonical_food_id = ingredient.canonical_food_id
          AND ingredient.ingredient_role IS NULL
        """
    )

    # COMPLETE_MEAL is deliberately strict: a required protein, staple and
    # vegetable must all exist. Remaining recipes stay available as dishes or
    # sides in the catalogue but cannot count toward V2's meal target.
    op.execute(
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
        END
        WHERE recipe.active AND recipe.meal_type IS NULL
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE recipe_catalog_ingredient
        SET ingredient_role = NULL
        """
    )
    op.execute(
        """
        UPDATE recipe_catalog
        SET meal_type = NULL,
            recipe_version = NULL,
            review_status = NULL,
            quantity_basis = NULL,
            max_weekly_occurrences = NULL
        WHERE NOT optimizer_eligible
        """
    )
