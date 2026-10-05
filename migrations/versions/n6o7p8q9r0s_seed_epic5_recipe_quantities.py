# Seed approved base servings and required quantities for Epic 5 curated recipes.
# Revision ID: n6o7p8q9r0s
# Revises: m5n6o7p8q9r
# Create Date: 2026-09-14
from alembic import op


revision = "n6o7p8q9r0s"
down_revision = "m5n6o7p8q9r"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Approved initial recipe quantities for two adult-equivalent servings.
    op.execute(
        """
        update recipe_catalog
        set base_servings = 2
        where recipe_id in (
            'chicken-kangkung-stir-fry',
            'egg-fried-rice',
            'tofu-kangkung-stir-fry'
        )
        """
    )
    op.execute(
        """
        update recipe_catalog_ingredient
        set base_quantity_g = case
            when recipe_id = 'chicken-kangkung-stir-fry' and canonical_food_id = 'SF006' then 300
            when recipe_id = 'chicken-kangkung-stir-fry' and canonical_food_id = 'SF074' then 200
            when recipe_id = 'chicken-kangkung-stir-fry' and canonical_food_id = 'SF110' then 160
            when recipe_id = 'egg-fried-rice' and canonical_food_id = 'SF018' then 100
            when recipe_id = 'egg-fried-rice' and canonical_food_id = 'SF110' then 160
            when recipe_id = 'tofu-kangkung-stir-fry' and canonical_food_id = 'SF107' then 300
            when recipe_id = 'tofu-kangkung-stir-fry' and canonical_food_id = 'SF074' then 200
            else base_quantity_g
        end
        where (recipe_id, canonical_food_id) in (
            ('chicken-kangkung-stir-fry', 'SF006'),
            ('chicken-kangkung-stir-fry', 'SF074'),
            ('chicken-kangkung-stir-fry', 'SF110'),
            ('egg-fried-rice', 'SF018'),
            ('egg-fried-rice', 'SF110'),
            ('tofu-kangkung-stir-fry', 'SF107'),
            ('tofu-kangkung-stir-fry', 'SF074')
        )
        """
    )


def downgrade() -> None:
    op.execute(
        """
        update recipe_catalog
        set base_servings = null
        where recipe_id in (
            'chicken-kangkung-stir-fry',
            'egg-fried-rice',
            'tofu-kangkung-stir-fry'
        )
        """
    )
    op.execute(
        """
        update recipe_catalog_ingredient
        set base_quantity_g = null
        where (recipe_id, canonical_food_id) in (
            ('chicken-kangkung-stir-fry', 'SF006'),
            ('chicken-kangkung-stir-fry', 'SF074'),
            ('chicken-kangkung-stir-fry', 'SF110'),
            ('egg-fried-rice', 'SF018'),
            ('egg-fried-rice', 'SF110'),
            ('tofu-kangkung-stir-fry', 'SF107'),
            ('tofu-kangkung-stir-fry', 'SF074')
        )
        """
    )
