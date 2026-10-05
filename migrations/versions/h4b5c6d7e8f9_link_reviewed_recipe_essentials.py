"""Link the 100 newly required ingredients to their actual cooking steps.

Revision ID: h4b5c6d7e8f9
Revises: g3a4b5c6d7e8

The old staple-first review linked only then-required foods. Record exactly
which links we insert so rollback never deletes pre-existing reviewed links.
Cooking instructions, order and UI remain unchanged.
"""
from alembic import op
import sqlalchemy as sa

revision = "h4b5c6d7e8f9"
down_revision = "g3a4b5c6d7e8"
branch_labels = None
depends_on = None

# Reviewed against the written methods. Oil is linked to the first frying
# step; garlic/spice links name the actual addition, not an arbitrary step.
STEP_FOODS = (
    ("bihun-goreng", 2, "SF056 SF060 SF069 SF071 SF120"),
    ("cabbage-mamak-stir-fry", 1, "SF054 SF069 SF120 SF148"),
    ("cabbage-mamak-stir-fry", 2, "SF135"),
    ("cauliflower-stir-fry", 1, "SF069 SF120"),
    ("dhal-curry-with-rice", 1, "SF069"),
    ("dhal-curry-with-rice", 2, "SF135"),
    ("dhal-curry-with-rice", 3, "SF056 SF120 SF148"),
    ("egg-potato-curry-with-rice", 2, "SF056 SF069 SF071 SF120 SF133"),
    ("french-bean-garlic-stir-fry", 1, "SF069 SF120"),
    ("garlic-broccoli-stir-fry", 1, "SF069 SF120"),
    ("garlic-long-beans", 1, "SF054 SF069 SF120"),
    ("garlic-prawn-stir-fry", 1, "SF069 SF071 SF120"),
    ("garlic-spinach-stir-fry", 1, "SF069"),
    ("long-bean-egg-stir-fry", 1, "SF054 SF069 SF120"),
    ("maggi-goreng", 2, "SF056 SF069 SF120"),
    ("malay-chicken-soup", 1, "SF056 SF069 SF071 SF120"),
    ("malay-chicken-soup", 2, "SF134"),
    ("malaysian-chicken-curry-with-rice", 1, "SF056 SF120 SF133"),
    ("mee-goreng", 1, "SF120"),
    ("mee-goreng", 3, "SF054 SF069"),
    ("mixed-vegetable-stir-fry", 1, "SF054 SF069 SF120"),
    ("mustard-greens-stir-fry", 1, "SF069 SF120"),
    ("okra-eggplant-stir-fry", 1, "SF069 SF120"),
    ("onion-omelette", 2, "SF120"),
    ("potato-onion-stir-fry", 1, "SF069 SF120"),
    ("potato-onion-stir-fry", 2, "SF135"),
    ("red-tilapia-soy-with-rice", 1, "SF120"),
    ("red-tilapia-soy-with-rice", 2, "SF056 SF069 SF071"),
    ("sambal-eggplant-with-rice", 1, "SF052 SF120"),
    ("sardine-sambal-with-rice", 2, "SF069 SF120"),
    ("sardine-sambal-with-rice", 3, "SF139"),
    ("soy-sauce-chicken-with-rice", 1, "SF120"),
    ("soy-sauce-chicken-with-rice", 2, "SF056 SF069 SF071"),
    ("soy-sauce-eggs-with-rice", 2, "SF056 SF069 SF120"),
    ("soy-sauce-mackerel-with-rice", 1, "SF056 SF069 SF120"),
    ("squid-soy-stir-fry", 1, "SF056 SF069 SF120"),
    ("tofu-cabbage-stir-fry", 1, "SF120"),
    ("tofu-cabbage-stir-fry", 2, "SF069"),
    ("tofu-prawn-stir-fry", 1, "SF071 SF120"),
    ("tomato-chicken-with-rice", 1, "SF135"),
    ("tomato-chicken-with-rice", 2, "SF120"),
    ("tomato-chicken-with-rice", 3, "SF056 SF069 SF071"),
    ("tomato-egg-stir-fry", 2, "SF120"),
    ("tomato-tofu-with-rice", 1, "SF120"),
    ("turmeric-chicken-with-rice", 1, "SF135"),
    ("turmeric-chicken-with-rice", 2, "SF120"),
    ("turmeric-chicken-with-rice", 3, "SF056 SF069"),
    ("winged-bean-stir-fry", 1, "SF069 SF120"),
)
JOURNAL = "_migration_h4_recipe_step_links"


def upgrade() -> None:
    journal = op.create_table(
        JOURNAL,
        sa.Column("recipe_cooking_step_id", sa.Integer(), primary_key=True),
        sa.Column("canonical_food_id", sa.String(32), primary_key=True),
    )
    connection = op.get_bind()
    for recipe_id, step_number, food_ids in STEP_FOODS:
        for food_id in food_ids.split():
            inserted = connection.execute(sa.text("""
                INSERT INTO recipe_cooking_step_food (recipe_cooking_step_id, canonical_food_id)
                SELECT step.recipe_cooking_step_id, :food_id
                FROM recipe_cooking_step AS step
                JOIN recipe_catalog_ingredient AS ingredient
                  ON ingredient.recipe_id=step.recipe_id
                 AND ingredient.canonical_food_id=:food_id AND ingredient.required
                WHERE step.recipe_id=:recipe_id AND step.step_number=:step_number
                ON CONFLICT DO NOTHING
                RETURNING recipe_cooking_step_id, canonical_food_id
            """), {"recipe_id": recipe_id, "step_number": step_number, "food_id": food_id}).mappings().all()
            if inserted:
                connection.execute(journal.insert(), [dict(row) for row in inserted])


def downgrade() -> None:
    op.execute(sa.text(f"""
        DELETE FROM recipe_cooking_step_food AS link USING {JOURNAL} AS added
        WHERE link.recipe_cooking_step_id=added.recipe_cooking_step_id
          AND link.canonical_food_id=added.canonical_food_id
    """))
    op.drop_table(JOURNAL)
