from decimal import Decimal

import pytest

from packages.optimizer.wisebasket_optimizer.v2.calculations import (
    Household,
    PurchaseOption,
)
from packages.optimizer.wisebasket_optimizer.v2.domain import (
    CookingStep,
    IngredientRole,
    MealType,
    QuantityBasis,
    RecipeIngredient,
    ReviewedRecipe,
    ReviewStatus,
)
from services.api.app.recipe_opportunities import build_recipe_opportunities


D = Decimal


def recipe(recipe_id: str, protein_id: str | None, vegetable_id: str | None) -> ReviewedRecipe:
    ingredients = [
        RecipeIngredient("SF110", D("0.1"), IngredientRole.STAPLE),
    ]
    if protein_id:
        ingredients.append(
            RecipeIngredient(protein_id, D("0.25"), IngredientRole.MAIN_PROTEIN)
        )
    if vegetable_id:
        ingredients.append(
            RecipeIngredient(vegetable_id, D("0.1"), IngredientRole.MAIN_VEGETABLE)
        )
    food_ids = frozenset(item.food_id for item in ingredients)
    return ReviewedRecipe(
        recipe_id=recipe_id,
        name=recipe_id.replace("-", " ").title(),
        meal_type=MealType.COMPLETE_MEAL,
        base_servings=D("1"),
        version=1,
        review_status=ReviewStatus.APPROVED,
        optimizer_eligible=True,
        quantity_basis=QuantityBasis.RAW_EDIBLE_KG,
        ingredients=tuple(ingredients),
        steps=(CookingStep(1, "Cook all ingredients.", food_ids),),
        max_weekly_occurrences=3,
    )


def option(food_id: str) -> PurchaseOption:
    return PurchaseOption(food_id, D("0.25"), D("10"), D("1"))


RECIPES = (
    recipe("whole-chicken-rice", "SF006", None),
    recipe("chicken-thigh-rice", "SF014", None),
    recipe("tomato-rice", None, "SF072"),
    recipe("cabbage-rice", None, "SF055"),
    recipe("potato-rice", None, "SF057"),
)
OPTIONS = tuple(
    option(food_id)
    for food_id in ("SF006", "SF013", "SF014", "SF055", "SF057", "SF072", "SF110")
)


def opportunities(selected_food_ids: set[str]):
    return build_recipe_opportunities(
        recipes=RECIPES,
        household=Household(1, 0),
        selected_food_ids=selected_food_ids,
        pantry=(),
        purchase_options=OPTIONS,
        excluded_food_ids=frozenset(),
        budget_rm=D("100"),
    )


def recommended_food_ids(result) -> set[str]:
    return {
        ingredient.food_id
        for opportunity in result
        for ingredient in opportunity.missing_ingredients
    }


def test_selected_chicken_cut_blocks_other_chicken_forms_from_opportunities():
    result = opportunities({"SF013", "SF110"})

    assert len(result) == 3
    assert not recommended_food_ids(result) & {"SF006", "SF014"}


def test_opportunities_introduce_at_most_one_chicken_form_when_none_is_selected():
    result = opportunities({"SF110"})

    assert len(result) == 3
    assert len(recommended_food_ids(result) & {"SF006", "SF014"}) == 1


@pytest.mark.parametrize(
    ("selected_id", "alternative_id"),
    [
        ("SF003", "SF004"),  # lamb cuts
        ("SF008", "SF010"),  # pork cuts
        ("SF022", "SF036"),  # prawn varieties
        ("SF023", "SF028"),  # red snapper / head
        ("SF032", "SF050"),  # pomfret colours
        ("SF035", "SF049"),  # tilapia colours
        ("SF075", "SF085"),  # capsicum colours
        ("SF102", "SF103"),  # coconut-milk formats
        ("SF120", "SF123"),  # cooking-oil formats
    ],
)
def test_selected_equivalent_food_blocks_alternative_purchase_form(
    selected_id: str,
    alternative_id: str,
):
    recipes = (
        recipe("equivalent-rice", alternative_id, None),
        recipe("tomato-rice", None, "SF072"),
        recipe("cabbage-rice", None, "SF055"),
        recipe("potato-rice", None, "SF057"),
    )
    options = tuple(
        option(food_id)
        for food_id in {
            selected_id, alternative_id, "SF055", "SF057", "SF072", "SF110"
        }
    )

    result = build_recipe_opportunities(
        recipes=recipes,
        household=Household(1, 0),
        selected_food_ids={selected_id, "SF110"},
        pantry=(),
        purchase_options=options,
        excluded_food_ids=frozenset(),
        budget_rm=D("100"),
    )

    assert len(result) == 3
    assert alternative_id not in recommended_food_ids(result)
