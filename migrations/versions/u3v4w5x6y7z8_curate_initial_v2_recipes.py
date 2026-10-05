"""Curate the first safety-reviewed recipe-first V2 catalogue slice.

Revision ID: u3v4w5x6y7z8
Revises: t2u3v4w5x6y7
Create Date: 2026-09-21
"""

from alembic import op
import sqlalchemy as sa
from datetime import UTC, datetime


revision = "u3v4w5x6y7z8"
down_revision = "t2u3v4w5x6y7"
branch_labels = None
depends_on = None


REVIEW_SOURCE = "WISEBASKET_CURATED_V2_INITIAL_SET_2026_09_21"

ENABLED_RECIPES = (
    "dhal-curry-with-rice",
    "egg-potato-curry-with-rice",
    "malay-chicken-soup",
    "onion-omelette",
    "tomato-egg-stir-fry",
    "turmeric-chicken-with-rice",
)

STEP_FOOD_LINKS = (
    ("dhal-curry-with-rice", 1, "SF124"),
    ("dhal-curry-with-rice", 1, "SF057"),
    ("dhal-curry-with-rice", 1, "SF072"),
    ("dhal-curry-with-rice", 2, "SF135"),
    ("dhal-curry-with-rice", 4, "SF110"),
    ("egg-potato-curry-with-rice", 1, "SF018"),
    ("egg-potato-curry-with-rice", 3, "SF057"),
    ("egg-potato-curry-with-rice", 3, "SF072"),
    ("egg-potato-curry-with-rice", 2, "SF133"),
    ("egg-potato-curry-with-rice", 4, "SF102"),
    ("egg-potato-curry-with-rice", 5, "SF110"),
    ("malay-chicken-soup", 2, "SF006"),
    ("malay-chicken-soup", 3, "SF057"),
    ("malay-chicken-soup", 3, "SF077"),
    ("malay-chicken-soup", 2, "SF134"),
    ("malay-chicken-soup", 5, "SF110"),
    ("onion-omelette", 1, "SF018"),
    ("onion-omelette", 2, "SF056"),
    ("onion-omelette", 4, "SF110"),
    ("tomato-egg-stir-fry", 1, "SF018"),
    ("tomato-egg-stir-fry", 3, "SF072"),
    ("tomato-egg-stir-fry", 4, "SF110"),
    ("turmeric-chicken-with-rice", 1, "SF014"),
    ("turmeric-chicken-with-rice", 4, "SF084"),
    ("turmeric-chicken-with-rice", 4, "SF077"),
    ("turmeric-chicken-with-rice", 5, "SF110"),
    ("turmeric-chicken-with-rice", 1, "SF135"),
)

# Food identity review for every required and optional food in the six enabled
# recipes. Values are vegetarian, vegan and contains_pork respectively.
SAFETY_PROFILES = (
    ("SF006", False, False, False),
    ("SF014", False, False, False),
    ("SF018", True, False, False),
    ("SF056", True, True, False),
    ("SF057", True, True, False),
    ("SF058", True, True, False),
    ("SF064", True, True, False),
    ("SF069", True, True, False),
    ("SF071", True, True, False),
    ("SF072", True, True, False),
    ("SF077", True, True, False),
    ("SF084", True, True, False),
    ("SF102", True, True, False),
    ("SF110", True, True, False),
    ("SF118", True, True, False),
    ("SF120", True, True, False),
    ("SF124", True, True, False),
    ("SF133", True, True, False),
    ("SF134", True, True, False),
    ("SF135", True, True, False),
    ("SF136", True, True, False),
    ("SF148", True, True, False),
    ("SF151", True, True, False),
)

ALLERGENS = (("SF018", "EGG"),)


def upgrade() -> None:
    reviewed_at = datetime.now(UTC)
    op.add_column("recipe_catalog", sa.Column("review_source", sa.String(120)))
    op.add_column(
        "recipe_substitution_rule",
        sa.Column("review_source", sa.String(120)),
    )
    op.add_column(
        "food_safety_profile",
        sa.Column("review_source", sa.String(120)),
    )

    op.drop_constraint(
        "ck_recipe_catalog_optimizer_governance",
        "recipe_catalog",
        type_="check",
    )
    op.create_check_constraint(
        "ck_recipe_catalog_optimizer_governance",
        "recipe_catalog",
        "not optimizer_eligible or (active and base_servings > 0 and "
        "meal_type = 'COMPLETE_MEAL' and recipe_version is not null and "
        "review_status = 'APPROVED' and quantity_basis = 'RAW_EDIBLE_KG' and "
        "max_weekly_occurrences > 0 and (reviewed_by is not null or review_source is not null) "
        "and reviewed_at is not null)",
    )

    op.drop_constraint(
        "ck_recipe_substitution_approval_attribution",
        "recipe_substitution_rule",
        type_="check",
    )
    op.create_check_constraint(
        "ck_recipe_substitution_approval_attribution",
        "recipe_substitution_rule",
        "review_status <> 'APPROVED' or ((reviewed_by is not null or review_source is not null) "
        "and reviewed_at is not null)",
    )

    op.drop_constraint(
        "ck_food_safety_approval_complete",
        "food_safety_profile",
        type_="check",
    )
    op.create_check_constraint(
        "ck_food_safety_approval_complete",
        "food_safety_profile",
        "review_status <> 'APPROVED' or (vegetarian is not null and vegan is not null "
        "and contains_pork is not null and allergen_assessment_complete "
        "and (reviewed_by is not null or review_source is not null) and reviewed_at is not null)",
    )

    connection = op.get_bind()
    step_food = sa.table(
        "recipe_cooking_step_food",
        sa.column("recipe_cooking_step_id", sa.Integer()),
        sa.column("canonical_food_id", sa.String()),
    )
    cooking_step = sa.table(
        "recipe_cooking_step",
        sa.column("recipe_cooking_step_id", sa.Integer()),
        sa.column("recipe_id", sa.String()),
        sa.column("step_number", sa.Integer()),
    )
    for recipe_id, step_number, food_id in STEP_FOOD_LINKS:
        step_id = connection.execute(
            sa.select(cooking_step.c.recipe_cooking_step_id).where(
                cooking_step.c.recipe_id == recipe_id,
                cooking_step.c.step_number == step_number,
            )
        ).scalar_one()
        connection.execute(
            step_food.insert().values(
                recipe_cooking_step_id=step_id,
                canonical_food_id=food_id,
            )
        )

    safety = sa.table(
        "food_safety_profile",
        sa.column("canonical_food_id", sa.String()),
        sa.column("vegetarian", sa.Boolean()),
        sa.column("vegan", sa.Boolean()),
        sa.column("contains_pork", sa.Boolean()),
        sa.column("allergen_assessment_complete", sa.Boolean()),
        sa.column("review_status", sa.String()),
        sa.column("version", sa.Integer()),
        sa.column("review_source", sa.String()),
        sa.column("reviewed_at", sa.DateTime(timezone=True)),
    )
    connection.execute(
        safety.insert(),
        [
            {
                "canonical_food_id": food_id,
                "vegetarian": vegetarian,
                "vegan": vegan,
                "contains_pork": contains_pork,
                "allergen_assessment_complete": True,
                "review_status": "APPROVED",
                "version": 1,
                "review_source": REVIEW_SOURCE,
                "reviewed_at": reviewed_at,
            }
            for food_id, vegetarian, vegan, contains_pork in SAFETY_PROFILES
        ],
    )

    allergen = sa.table(
        "food_allergen",
        sa.column("canonical_food_id", sa.String()),
        sa.column("allergen_code", sa.String()),
    )
    connection.execute(
        allergen.insert(),
        [
            {"canonical_food_id": food_id, "allergen_code": code}
            for food_id, code in ALLERGENS
        ],
    )

    recipe = sa.table(
        "recipe_catalog",
        sa.column("recipe_id", sa.String()),
        sa.column("review_status", sa.String()),
        sa.column("optimizer_eligible", sa.Boolean()),
        sa.column("review_source", sa.String()),
        sa.column("reviewed_at", sa.DateTime(timezone=True)),
    )
    connection.execute(
        recipe.update()
        .where(recipe.c.recipe_id.in_(ENABLED_RECIPES))
        .values(
            review_status="APPROVED",
            optimizer_eligible=True,
            review_source=REVIEW_SOURCE,
            reviewed_at=sa.func.now(),
        )
    )


def downgrade() -> None:
    connection = op.get_bind()
    recipe = sa.table(
        "recipe_catalog",
        sa.column("recipe_id", sa.String()),
        sa.column("review_status", sa.String()),
        sa.column("optimizer_eligible", sa.Boolean()),
        sa.column("reviewed_at", sa.DateTime(timezone=True)),
    )
    connection.execute(
        recipe.update()
        .where(recipe.c.recipe_id.in_(ENABLED_RECIPES))
        .values(
            review_status="DRAFT",
            optimizer_eligible=False,
            reviewed_at=None,
        )
    )

    food_ids = tuple(profile[0] for profile in SAFETY_PROFILES)
    op.execute(
        sa.text("DELETE FROM food_allergen WHERE canonical_food_id IN :food_ids").bindparams(
            sa.bindparam("food_ids", expanding=True, value=food_ids)
        )
    )
    op.execute(
        sa.text(
            "DELETE FROM food_safety_profile WHERE canonical_food_id IN :food_ids"
        ).bindparams(sa.bindparam("food_ids", expanding=True, value=food_ids))
    )

    step_ids = connection.execute(
        sa.text(
            "SELECT recipe_cooking_step_id FROM recipe_cooking_step "
            "WHERE recipe_id IN :recipe_ids"
        ).bindparams(
            sa.bindparam("recipe_ids", expanding=True, value=ENABLED_RECIPES)
        )
    ).scalars()
    op.execute(
        sa.text(
            "DELETE FROM recipe_cooking_step_food WHERE recipe_cooking_step_id IN :step_ids"
        ).bindparams(sa.bindparam("step_ids", expanding=True, value=tuple(step_ids)))
    )

    op.drop_constraint(
        "ck_food_safety_approval_complete",
        "food_safety_profile",
        type_="check",
    )
    op.create_check_constraint(
        "ck_food_safety_approval_complete",
        "food_safety_profile",
        "review_status <> 'APPROVED' or (vegetarian is not null and vegan is not null "
        "and contains_pork is not null and allergen_assessment_complete "
        "and reviewed_by is not null and reviewed_at is not null)",
    )
    op.drop_constraint(
        "ck_recipe_substitution_approval_attribution",
        "recipe_substitution_rule",
        type_="check",
    )
    op.create_check_constraint(
        "ck_recipe_substitution_approval_attribution",
        "recipe_substitution_rule",
        "review_status <> 'APPROVED' or (reviewed_by is not null and reviewed_at is not null)",
    )
    op.drop_constraint(
        "ck_recipe_catalog_optimizer_governance",
        "recipe_catalog",
        type_="check",
    )
    op.create_check_constraint(
        "ck_recipe_catalog_optimizer_governance",
        "recipe_catalog",
        "not optimizer_eligible or (active and base_servings > 0 and "
        "meal_type = 'COMPLETE_MEAL' and recipe_version is not null and "
        "review_status = 'APPROVED' and quantity_basis = 'RAW_EDIBLE_KG' and "
        "max_weekly_occurrences > 0 and reviewed_by is not null and reviewed_at is not null)",
    )
    op.drop_column("food_safety_profile", "review_source")
    op.drop_column("recipe_substitution_rule", "review_source")
    op.drop_column("recipe_catalog", "review_source")
