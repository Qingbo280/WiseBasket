import asyncio

from sqlalchemy import func, select

from services.api.app.db import (
    AsyncSessionLocal,
    FoodSafetyProfile,
    RecipeCatalog,
    RecipeCatalogIngredient,
    RecipeCookingStep,
    RecipeCookingStepFood,
    engine,
)


def run_db(coro):
    async def runner():
        try:
            return await coro
        finally:
            await engine.dispose()

    return asyncio.run(runner())


def test_recipe_v2_draft_metadata_is_backfilled():
    async def check():
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(
                    func.count(RecipeCatalog.recipe_id),
                    func.count(RecipeCatalog.recipe_id).filter(
                        RecipeCatalog.meal_type == "COMPLETE_MEAL"
                    ),
                    func.count(RecipeCatalog.recipe_id).filter(
                        RecipeCatalog.optimizer_eligible.is_(True)
                    ),
                ).where(RecipeCatalog.active.is_(True))
            )
            total, complete, enabled = result.one()
            assert total == 35
            assert complete == 14
            assert enabled == 14

            missing_governance = await db.scalar(
                select(func.count(RecipeCatalog.recipe_id)).where(
                    RecipeCatalog.active.is_(True),
                    (
                        RecipeCatalog.recipe_version.is_(None)
                        | RecipeCatalog.review_status.is_(None)
                        | RecipeCatalog.quantity_basis.is_(None)
                        | RecipeCatalog.max_weekly_occurrences.is_(None)
                    ),
                )
            )
            assert missing_governance == 0

    run_db(check())


def test_every_recipe_ingredient_has_a_draft_role():
    async def check():
        async with AsyncSessionLocal() as db:
            missing_roles = await db.scalar(
                select(func.count(RecipeCatalogIngredient.recipe_ingredient_id)).where(
                    RecipeCatalogIngredient.ingredient_role.is_(None)
                )
            )
            assert missing_roles == 0

    run_db(check())


def test_full_recipe_set_is_reviewed_and_complete_meals_are_enabled():
    async def check():
        async with AsyncSessionLocal() as db:
            enabled = await db.scalar(
                select(func.count(RecipeCatalog.recipe_id)).where(
                    RecipeCatalog.optimizer_eligible.is_(True)
                )
            )
            approved_complete = await db.scalar(
                select(func.count(RecipeCatalog.recipe_id)).where(
                    RecipeCatalog.meal_type == "COMPLETE_MEAL",
                    RecipeCatalog.review_status == "APPROVED",
                    RecipeCatalog.review_source.is_not(None),
                )
            )
            approved = await db.scalar(
                select(func.count(RecipeCatalog.recipe_id)).where(
                    RecipeCatalog.review_status == "APPROVED",
                    RecipeCatalog.review_source.is_not(None),
                )
            )
            component_enabled = await db.scalar(
                select(func.count(RecipeCatalog.recipe_id)).where(
                    RecipeCatalog.optimizer_component_eligible.is_(True)
                )
            )
            assert enabled == 14
            assert component_enabled == 21
            assert approved_complete == 14
            assert approved == 35

    run_db(check())


def test_enabled_recipe_required_ingredients_are_linked_to_steps():
    async def check():
        async with AsyncSessionLocal() as db:
            required = (
                await db.execute(
                    select(
                        RecipeCatalogIngredient.recipe_id,
                        RecipeCatalogIngredient.canonical_food_id,
                    )
                    .join(
                        RecipeCatalog,
                        RecipeCatalog.recipe_id == RecipeCatalogIngredient.recipe_id,
                    )
                    .where(
                        RecipeCatalog.optimizer_eligible.is_(True),
                        RecipeCatalogIngredient.required.is_(True),
                    )
                )
            ).all()
            linked = set(
                (
                    await db.execute(
                        select(
                            RecipeCookingStep.recipe_id,
                            RecipeCookingStepFood.canonical_food_id,
                        ).join(
                            RecipeCookingStep,
                            RecipeCookingStep.recipe_cooking_step_id
                            == RecipeCookingStepFood.recipe_cooking_step_id,
                        )
                    )
                ).all()
            )
            assert set(required) <= linked

    run_db(check())


def test_enabled_recipe_foods_have_approved_safety_profiles():
    async def check():
        async with AsyncSessionLocal() as db:
            food_ids = set(
                (
                    await db.execute(
                        select(RecipeCatalogIngredient.canonical_food_id)
                        .join(
                            RecipeCatalog,
                            RecipeCatalog.recipe_id
                            == RecipeCatalogIngredient.recipe_id,
                        )
                        .where(RecipeCatalog.optimizer_eligible.is_(True))
                        .distinct()
                    )
                ).scalars()
            )
            approved = set(
                (
                    await db.execute(
                        select(FoodSafetyProfile.canonical_food_id).where(
                            FoodSafetyProfile.review_status == "APPROVED",
                            FoodSafetyProfile.review_source.is_not(None),
                        )
                    )
                ).scalars()
            )
            assert food_ids <= approved

    run_db(check())


def test_reviewed_essentials_preserve_staple_roles_and_classify_every_ingredient():
    async def check():
        async with AsyncSessionLocal() as db:
            role_counts = dict(
                (
                    await db.execute(
                        select(
                            RecipeCatalogIngredient.ingredient_role,
                            func.count(RecipeCatalogIngredient.recipe_ingredient_id),
                        ).group_by(RecipeCatalogIngredient.ingredient_role)
                    )
                ).all()
            )
            # f2/g3 review promotes 85 original optional + 15 legacy seasoning
            # rows. Main-food roles and meal/component classifications stay fixed.
            assert role_counts == {
                "COOKING_ESSENTIAL": 134,
                "MAIN_PROTEIN": 26,
                "MAIN_VEGETABLE": 34,
                "OPTIONAL": 40,
                "SEASONING": 5,
                "STAPLE": 28,
            }

            meal_type_counts = dict(
                (
                    await db.execute(
                        select(
                            RecipeCatalog.meal_type,
                            func.count(RecipeCatalog.recipe_id),
                        ).group_by(RecipeCatalog.meal_type)
                    )
                ).all()
            )
            assert meal_type_counts == {
                "COMPLETE_MEAL": 14,
                "MAIN_DISH": 11,
                "SIDE": 10,
            }

            rows = (
                await db.execute(
                    select(
                        RecipeCatalogIngredient.recipe_id,
                        RecipeCatalogIngredient.canonical_food_id,
                        RecipeCatalogIngredient.ingredient_role,
                        RecipeCatalogIngredient.required,
                    ).where(
                        RecipeCatalogIngredient.recipe_id.in_((
                            "french-bean-garlic-stir-fry",
                            "dhal-curry-with-rice",
                            "egg-potato-curry-with-rice",
                            "malay-chicken-soup",
                            "turmeric-chicken-with-rice",
                        )),
                        RecipeCatalogIngredient.canonical_food_id.in_((
                            "SF057", "SF069", "SF133", "SF134", "SF135",
                        )),
                    )
                )
            ).all()
            by_pair = {
                (row.recipe_id, row.canonical_food_id): (
                    row.ingredient_role,
                    row.required,
                )
                for row in rows
            }

            assert by_pair[("dhal-curry-with-rice", "SF057")] == ("STAPLE", True)
            assert by_pair[("egg-potato-curry-with-rice", "SF057")] == ("STAPLE", True)
            assert by_pair[("malay-chicken-soup", "SF057")] == ("STAPLE", True)
            assert by_pair[("dhal-curry-with-rice", "SF135")] == ("COOKING_ESSENTIAL", True)
            assert by_pair[("egg-potato-curry-with-rice", "SF133")] == ("COOKING_ESSENTIAL", True)
            assert by_pair[("malay-chicken-soup", "SF134")] == ("COOKING_ESSENTIAL", True)
            assert by_pair[("turmeric-chicken-with-rice", "SF135")] == ("COOKING_ESSENTIAL", True)
            assert by_pair[("french-bean-garlic-stir-fry", "SF069")] == ("COOKING_ESSENTIAL", True)

    run_db(check())
