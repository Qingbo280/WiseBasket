# Controlled dietary and allergen safety tests with optional request inputs.
from decimal import Decimal as D

from packages.optimizer.tests_v2.test_optimizer import meal, options
from packages.optimizer.tests_v2.test_substitution_optimizer import beef_meal
from packages.optimizer.wisebasket_optimizer.v2.calculations import PurchaseOption
from packages.optimizer.wisebasket_optimizer.v2.domain import (
    CookingStep,
    IngredientRole,
    RecipeIngredient,
    ReviewStatus,
    SubstitutionRule,
)
from packages.optimizer.wisebasket_optimizer.v2.safety import FoodSafety
from services.api.app.planner_v2_service import PlannerV2Catalog, create_plan_v2
from services.api.app.schemas import PlannerV2CreateRequest


def request(**changes):
    values = {
        "household": {"adults": 1, "children": 0},
        "budget_rm": D("20"),
        "target_meals": 1,
    }
    values.update(changes)
    return PlannerV2CreateRequest(**values)


def safe(food_id, vegetarian=True, vegan=True, pork=False, allergens=()):
    return FoodSafety(food_id, vegetarian, vegan, pork, frozenset(allergens))


def common_safety():
    return tuple(safe(food) for food in ("rice", "carrot", "oil"))


def test_no_selected_pattern_or_allergen_requires_no_safety_metadata():
    catalog = PlannerV2Catalog(
        recipes=(meal("chicken"),),
        purchase_options=options(chicken="10"),
    )
    response = create_plan_v2(request(), catalog)
    assert response.outcome.status == "FULL_PLAN"
    assert response.safety_missing_food_ids == []


def test_optional_vegetarian_pattern_filters_meat_recipes():
    catalog = PlannerV2Catalog(
        recipes=(meal("chicken-meal"), meal("tofu-meal", "tofu")),
        purchase_options=options(chicken="10", tofu="2"),
        food_safety=common_safety() + (
            safe("chicken", vegetarian=False, vegan=False),
            safe("tofu"),
        ),
    )
    response = create_plan_v2(request(dietary_patterns=["VEGETARIAN"]), catalog)
    assert response.outcome.status == "FULL_PLAN"
    assert [recipe.recipe_id for recipe in response.recipes] == ["tofu-meal"]


def test_vegan_pattern_excludes_egg_and_dairy():
    catalog = PlannerV2Catalog(
        recipes=(meal("egg-meal", "egg"), meal("tofu-meal", "tofu")),
        purchase_options=options(egg="3", tofu="2"),
        food_safety=common_safety() + (
            safe("egg", vegetarian=True, vegan=False, allergens=("EGG",)),
            safe("tofu"),
        ),
    )
    response = create_plan_v2(request(dietary_patterns=["VEGAN"]), catalog)
    assert [recipe.recipe_id for recipe in response.recipes] == ["tofu-meal"]


def test_allergen_on_optional_ingredient_rejects_the_whole_recipe():
    base = meal("egg-optional")
    ingredients = base.ingredients + (
        RecipeIngredient("egg", D("0.050"), IngredientRole.SEASONING, required=False),
    )
    recipe = type(base)(
        base.recipe_id, base.name, base.meal_type, base.base_servings, base.version,
        base.review_status, base.optimizer_eligible, base.quantity_basis, ingredients,
        base.steps + (CookingStep(2, "Optionally add egg.", frozenset({"egg"})),),
        base.max_weekly_occurrences,
    )
    catalog = PlannerV2Catalog(
        recipes=(recipe,),
        purchase_options=options(chicken="10"),
        food_safety=common_safety() + (
            safe("chicken", vegetarian=False, vegan=False),
            safe("egg", vegetarian=True, vegan=False, allergens=("EGG",)),
        ),
    )
    response = create_plan_v2(request(allergens=["EGG"]), catalog)
    assert response.outcome.status == "SHORTFALL"
    assert "RESTRICTIONS_TOO_LIMITING" in response.outcome.error_codes


def test_allergen_cannot_reenter_through_a_substitution():
    rule = SubstitutionRule(
        "beef-to-tofu", "beef", "tofu", D("1"), IngredientRole.MAIN_PROTEIN,
        recipe_ids=frozenset({"beef-rice"}), review_status=ReviewStatus.APPROVED,
    )
    catalog = PlannerV2Catalog(
        recipes=(beef_meal(),),
        purchase_options=(
            PurchaseOption("tofu", D("0.1"), D("2")),
            *options()[0:3],
        ),
        substitution_rules=(rule,),
        food_safety=common_safety() + (
            safe("beef", vegetarian=False, vegan=False),
            safe("tofu", allergens=("SOY",)),
        ),
    )
    response = create_plan_v2(request(allergens=["SOY"]), catalog)
    assert response.outcome.status == "SHORTFALL"
    assert response.substitutions == []
    assert all(item.food_id != "tofu" for item in response.shopping_items)


def test_selected_restriction_with_missing_metadata_fails_closed():
    catalog = PlannerV2Catalog(
        recipes=(meal("chicken"),),
        purchase_options=options(chicken="10"),
    )
    response = create_plan_v2(request(dietary_patterns=["VEGETARIAN"]), catalog)
    assert response.outcome.status == "SHORTFALL"
    assert "MISSING_SAFETY_METADATA" in response.outcome.error_codes
    assert response.safety_missing_food_ids == ["carrot", "chicken", "oil", "rice"]
