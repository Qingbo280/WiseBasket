from collections.abc import Callable, Iterable
from decimal import Decimal

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from packages.optimizer.wisebasket_optimizer.v2.calculations import PurchaseOption
from packages.optimizer.wisebasket_optimizer.v2.domain import (
    CookingStep,
    IngredientRole,
    MealType,
    QuantityBasis,
    RecipeIngredient,
    ReviewedRecipe,
    ReviewStatus,
    SubstitutionRule,
)
from packages.optimizer.wisebasket_optimizer.v2.nutrition import FoodNutrition as V2FoodNutrition
from packages.optimizer.wisebasket_optimizer.v2.safety import FoodSafety
from services.api.app.db import (
    CanonicalFood,
    FoodAllergen,
    FoodNutrition,
    FoodSafetyProfile,
    RecipeCatalog,
    RecipeCatalogIngredient,
    RecipeCookingStep,
    RecipeCookingStepFood,
    RecipeSubstitutionRule,
    RecipeSubstitutionScope,
)
from services.api.app.planner_v2_routes import CatalogUnavailableError
from services.api.app.planner_v2_service import PlannerV2Catalog
from services.api.app.budget_food_fallback import FOOD_FALLBACK_IDS
from services.api.app.weekly_baselines import BASELINE_FOOD_IDS
from services.api.app.recipe_combinations import build_complete_meal_candidates
from services.api.app.schemas import PlannerV2CreateRequest
from services.api.app.services.representative_price import (
    fetch_current_purchase_masses_batch,
    resolve_food_prices,
)
from packages.optimizer.wisebasket_optimizer.v2.oil_equivalence import OIL_FOOD_IDS


GRAMS_PER_KG = Decimal("1000")
PRICE_100G_TO_KG = Decimal("10")
BY_WEIGHT_PURCHASE_STEP_G = Decimal("25")


def purchase_unit_kg(
    purchase_mode: str,
    pack_sizes: list[tuple[Decimal, str | None]],
) -> Decimal:
    if purchase_mode == "BY_WEIGHT":
        return BY_WEIGHT_PURCHASE_STEP_G / GRAMS_PER_KG
    if purchase_mode != "FIXED_PACK":
        raise CatalogUnavailableError(f"Unsupported purchase mode {purchase_mode!r}.")
    if not pack_sizes:
        raise CatalogUnavailableError("Fixed-pack food has no registered pack size.")
    return min(Decimal(pack[0]) for pack in pack_sizes) / GRAMS_PER_KG


async def load_purchase_modes(
    db: AsyncSession,
    food_ids: list[str],
) -> dict[str, str]:
    if not food_ids:
        return {}
    rows = (
        await db.execute(
            select(CanonicalFood.canonical_food_id, CanonicalFood.purchase_mode)
            .where(CanonicalFood.canonical_food_id.in_(food_ids))
        )
    ).all()
    return {food_id: purchase_mode for food_id, purchase_mode in rows}


class DatabasePlannerV2CatalogProvider:
    def __init__(self, session_factory: Callable[[], AsyncSession]):
        self.session_factory = session_factory

    async def get_catalog(self, payload: PlannerV2CreateRequest) -> PlannerV2Catalog:
        minimum_purchase_food_ids = {
            item.food_id for item in payload.minimum_purchase_quantities
        }
        try:
            async with self.session_factory() as db:
                return await load_planner_v2_catalog(
                    db,
                    additional_food_ids=minimum_purchase_food_ids | BASELINE_FOOD_IDS,
                )
        except CatalogUnavailableError:
            raise
        except Exception as error:
            raise CatalogUnavailableError(
                "The reviewed planner catalogue could not be loaded."
            ) from error


async def load_planner_v2_catalog(
    db: AsyncSession,
    additional_food_ids: Iterable[str] = (),
) -> PlannerV2Catalog:
    recipes = await load_reviewed_recipes(db)
    recipe_food_ids = {
        ingredient.food_id
        for recipe in recipes
    for ingredient in recipe.ingredients
    }
    # Additional oil options remain subject to the same live catalogue,
    # trusted-price and reviewed-safety loaders as direct ingredients.
    active_oils = set((await db.scalars(
        select(CanonicalFood.canonical_food_id).where(
            CanonicalFood.canonical_food_id.in_(OIL_FOOD_IDS),
            CanonicalFood.status == "ACTIVE",
        )
    )).all())
    active_fallback_foods = set((await db.scalars(
        select(CanonicalFood.canonical_food_id).where(
            CanonicalFood.canonical_food_id.in_(FOOD_FALLBACK_IDS),
            CanonicalFood.status == "ACTIVE",
            CanonicalFood.catalog_eligible.is_(True),
        )
    )).all())
    food_ids = sorted(recipe_food_ids | active_oils | active_fallback_foods | set(additional_food_ids))
    purchase_options = await load_purchase_options(db, food_ids)
    nutrition = await load_food_nutrition(db, food_ids)
    safety = await load_food_safety(db, food_ids)
    substitutions = await load_substitution_rules(db)
    return PlannerV2Catalog(
        recipes=recipes,
        purchase_options=purchase_options,
        food_nutrition=nutrition,
        substitution_rules=substitutions,
        food_safety=safety,
    )


async def load_reviewed_recipes(db: AsyncSession) -> tuple[ReviewedRecipe, ...]:
    recipe_rows = (
        await db.execute(
            select(RecipeCatalog)
            .where(
                RecipeCatalog.active.is_(True),
                RecipeCatalog.review_status == "APPROVED",
                or_(
                    RecipeCatalog.optimizer_eligible.is_(True),
                    RecipeCatalog.optimizer_component_eligible.is_(True),
                ),
            )
            .order_by(RecipeCatalog.recipe_id)
        )
    ).scalars().all()
    recipe_ids = [row.recipe_id for row in recipe_rows]
    if not recipe_ids:
        return ()

    ingredient_rows = (
        await db.execute(
            select(RecipeCatalogIngredient)
            .where(RecipeCatalogIngredient.recipe_id.in_(recipe_ids))
            .order_by(
                RecipeCatalogIngredient.recipe_id,
                RecipeCatalogIngredient.display_order,
            )
        )
    ).scalars().all()
    ingredients_by_recipe: dict[str, list[RecipeIngredient]] = {}
    for row in ingredient_rows:
        if row.base_quantity_g is None and not row.required:
            continue
        if row.base_quantity_g is None or row.ingredient_role is None:
            raise CatalogUnavailableError(
                f"Approved recipe {row.recipe_id} has incomplete ingredient data."
            )
        ingredients_by_recipe.setdefault(row.recipe_id, []).append(
            RecipeIngredient(
                food_id=row.canonical_food_id,
                quantity_kg=Decimal(row.base_quantity_g) / GRAMS_PER_KG,
                role=IngredientRole(row.ingredient_role),
                required=row.required,
            )
        )

    step_rows = (
        await db.execute(
            select(RecipeCookingStep)
            .where(RecipeCookingStep.recipe_id.in_(recipe_ids))
            .order_by(RecipeCookingStep.recipe_id, RecipeCookingStep.step_number)
        )
    ).scalars().all()
    step_ids = [row.recipe_cooking_step_id for row in step_rows]
    food_ids_by_step: dict[int, set[str]] = {}
    if step_ids:
        link_rows = (
            await db.execute(
                select(
                    RecipeCookingStepFood.recipe_cooking_step_id,
                    RecipeCookingStepFood.canonical_food_id,
                ).where(RecipeCookingStepFood.recipe_cooking_step_id.in_(step_ids))
            )
        ).all()
        for step_id, food_id in link_rows:
            food_ids_by_step.setdefault(step_id, set()).add(food_id)

    steps_by_recipe: dict[str, list[CookingStep]] = {}
    for row in step_rows:
        steps_by_recipe.setdefault(row.recipe_id, []).append(
            CookingStep(
                step_number=row.step_number,
                instruction=row.instruction,
                food_ids=frozenset(food_ids_by_step.get(row.recipe_cooking_step_id, set())),
            )
        )

    recipes = []
    for row in recipe_rows:
        if any(value is None for value in (
            row.base_servings,
            row.meal_type,
            row.recipe_version,
            row.quantity_basis,
            row.max_weekly_occurrences,
        )):
            raise CatalogUnavailableError(
                f"Approved recipe {row.recipe_id} has incomplete governance data."
            )
        recipes.append(
            ReviewedRecipe(
                recipe_id=row.recipe_id,
                name=row.name,
                meal_type=MealType(row.meal_type),
                base_servings=Decimal(row.base_servings),
                version=row.recipe_version,
                review_status=ReviewStatus(row.review_status),
                optimizer_eligible=row.optimizer_eligible,
                quantity_basis=QuantityBasis(row.quantity_basis),
                ingredients=tuple(ingredients_by_recipe.get(row.recipe_id, ())),
                steps=tuple(steps_by_recipe.get(row.recipe_id, ())),
                max_weekly_occurrences=row.max_weekly_occurrences,
            )
        )
    return build_complete_meal_candidates(tuple(recipes))


async def load_purchase_options(
    db: AsyncSession,
    food_ids: list[str],
) -> tuple[PurchaseOption, ...]:
    # V2 uses labelled package weight directly: a 300 g pack supplies 300 g
    # unless an approved yield explicitly says otherwise.
    default_yield = Decimal("1")
    prices = await resolve_food_prices(
        db,
        food_ids,
        default_edible_yield=default_yield,
    )
    masses = await fetch_current_purchase_masses_batch(db, food_ids)
    purchase_modes = await load_purchase_modes(db, food_ids)
    options = []
    for food_id in food_ids:
        price = prices.get(food_id)
        pack_sizes = masses.get(food_id)
        if price is None or not pack_sizes:
            continue
        purchase_mode = purchase_modes.get(food_id)
        if purchase_mode is None:
            continue
        options.append(
            PurchaseOption(
                food_id=food_id,
                unit_kg=purchase_unit_kg(purchase_mode, pack_sizes),
                price_rm_per_kg=(
                    Decimal(str(price.price_rm_per_100g_purchase)) * PRICE_100G_TO_KG
                ),
                edible_yield=default_yield,
                price_is_estimated=price.price_is_estimated,
            )
        )
    return tuple(options)


async def load_food_nutrition(
    db: AsyncSession,
    food_ids: list[str],
) -> tuple[V2FoodNutrition, ...]:
    if not food_ids:
        return ()
    rows = (
        await db.execute(
            select(FoodNutrition)
            .where(
                FoodNutrition.canonical_food_id.in_(food_ids),
                FoodNutrition.is_current.is_(True),
                FoodNutrition.quality_status == "PASS",
            )
            .order_by(FoodNutrition.canonical_food_id, FoodNutrition.nutrition_id.desc())
        )
    ).scalars().all()
    current_by_food = {}
    for row in rows:
        current_by_food.setdefault(row.canonical_food_id, row)

    nutrition = []
    for food_id in food_ids:
        row = current_by_food.get(food_id)
        if row is None:
            continue
        scale = GRAMS_PER_KG / Decimal(row.basis_g)
        values = tuple(
            Decimal(value or 0) * scale
            for value in (row.energy_kcal, row.protein_g, row.calcium_mg)
        )
        if values == (Decimal("0"), Decimal("0"), Decimal("0")):
            continue
        nutrition.append(V2FoodNutrition(food_id, *values))
    return tuple(nutrition)


async def load_food_safety(
    db: AsyncSession,
    food_ids: list[str],
) -> tuple[FoodSafety, ...]:
    if not food_ids:
        return ()
    profile_rows = (
        await db.execute(
            select(FoodSafetyProfile)
            .where(
                FoodSafetyProfile.canonical_food_id.in_(food_ids),
                FoodSafetyProfile.review_status == "APPROVED",
                FoodSafetyProfile.allergen_assessment_complete.is_(True),
            )
            .order_by(FoodSafetyProfile.canonical_food_id)
        )
    ).scalars().all()
    allergen_rows = (
        await db.execute(
            select(FoodAllergen.canonical_food_id, FoodAllergen.allergen_code)
            .where(FoodAllergen.canonical_food_id.in_(food_ids))
            .order_by(FoodAllergen.canonical_food_id, FoodAllergen.allergen_code)
        )
    ).all()
    allergens_by_food: dict[str, set[str]] = {}
    for food_id, allergen in allergen_rows:
        allergens_by_food.setdefault(food_id, set()).add(allergen)
    return tuple(
        FoodSafety(
            food_id=row.canonical_food_id,
            vegetarian=row.vegetarian,
            vegan=row.vegan,
            contains_pork=row.contains_pork,
            allergens=frozenset(allergens_by_food.get(row.canonical_food_id, set())),
        )
        for row in profile_rows
    )


async def load_substitution_rules(db: AsyncSession) -> tuple[SubstitutionRule, ...]:
    rule_rows = (
        await db.execute(
            select(RecipeSubstitutionRule)
            .where(
                RecipeSubstitutionRule.active.is_(True),
                RecipeSubstitutionRule.review_status == "APPROVED",
            )
            .order_by(RecipeSubstitutionRule.rule_id)
        )
    ).scalars().all()
    rule_ids = [row.rule_id for row in rule_rows]
    scopes_by_rule: dict[str, set[str]] = {}
    if rule_ids:
        scope_rows = (
            await db.execute(
                select(RecipeSubstitutionScope.rule_id, RecipeSubstitutionScope.recipe_id)
                .where(RecipeSubstitutionScope.rule_id.in_(rule_ids))
            )
        ).all()
        for rule_id, recipe_id in scope_rows:
            scopes_by_rule.setdefault(rule_id, set()).add(recipe_id)
    return tuple(
        SubstitutionRule(
            rule_id=row.rule_id,
            original_food_id=row.original_food_id,
            substitute_food_id=row.substitute_food_id,
            quantity_ratio=Decimal(row.quantity_ratio),
            role=IngredientRole(row.ingredient_role),
            recipe_ids=frozenset(scopes_by_rule.get(row.rule_id, set())),
            review_status=ReviewStatus(row.review_status),
            version=row.version,
        )
        for row in rule_rows
    )
