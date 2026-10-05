# Epic 5 household-scaled recipe quantity response contract.
from services.api.app.services.recipe_quantities import PantryQuantity
from services.api.app.services.recipe_quantity_summary import (
    RecipeQuantityIngredientInput,
    recipe_quantity_rank,
    summarize_recipe_quantities,
)


def test_recipe_quantity_summary_scales_for_adults_and_children():
    # Given a two-serving chicken recipe and a household with two adults and two children.
    summary = summarize_recipe_quantities(
        base_servings=2,
        adult_count=2,
        child_count=2,
        ingredients=(
            RecipeQuantityIngredientInput(
                canonical_food_id="SF006",
                required=True,
                base_quantity_g=300,
                pantry_quantities=(PantryQuantity("KNOWN", 400, "RECEIPT"),),
            ),
        ),
    )

    # When the household recipe response is calculated.
    # Then it requires 450g and reports the 50g shortfall without deducting stock.
    ingredient = summary.ingredients[0]
    assert summary.base_servings == 2
    assert summary.household_servings == 3
    assert summary.quantity_status == "INSUFFICIENT"
    assert summary.is_quantity_sufficient is False
    assert summary.required_quantity_sufficient_count == 0
    assert ingredient.required_quantity_g == 450
    assert ingredient.available_quantity_g == 400
    assert ingredient.quantity_status == "INSUFFICIENT"
    assert ingredient.shortfall_quantity_g == 50
    assert ingredient.remaining_quantity_g == 0


def test_recipe_quantity_summary_never_assumes_unmeasured_pantry_stock_is_sufficient():
    # Given a recipe ingredient exists in the pantry without a measured quantity.
    summary = summarize_recipe_quantities(
        base_servings=2,
        adult_count=2,
        child_count=0,
        ingredients=(
            RecipeQuantityIngredientInput(
                canonical_food_id="SF110",
                required=True,
                base_quantity_g=160,
                pantry_quantities=(PantryQuantity("UNKNOWN", None, "MANUAL"),),
            ),
        ),
    )

    # When recipe quantity sufficiency is calculated.
    # Then the amount remains unknown instead of being invented as sufficient.
    ingredient = summary.ingredients[0]
    assert summary.is_quantity_sufficient is False
    assert summary.quantity_status == "UNKNOWN"
    assert ingredient.quantity_status == "UNKNOWN"
    assert ingredient.available_quantity_g is None
    assert ingredient.shortfall_quantity_g is None


def test_recipe_quantity_summary_marks_unreviewed_recipe_quantities_as_not_tracked():
    # Given a required ingredient has no approved base gram quantity yet.
    summary = summarize_recipe_quantities(
        base_servings=2,
        adult_count=1,
        child_count=0,
        ingredients=(
            RecipeQuantityIngredientInput(
                canonical_food_id="SF056",
                required=True,
                base_quantity_g=None,
                pantry_quantities=(),
            ),
        ),
    )

    # When the response is built.
    # Then it explicitly reports NOT_TRACKED rather than a made-up estimate.
    ingredient = summary.ingredients[0]
    assert summary.is_quantity_sufficient is None
    assert summary.quantity_status == "NOT_TRACKED"
    assert ingredient.quantity_status == "NOT_TRACKED"
    assert ingredient.required_quantity_g is None


def test_recipe_quantity_ranking_prioritizes_cookable_recipes_without_hiding_others():
    # Given recipe quantity states from a confirmed household pantry.
    statuses = ("UNKNOWN", "SUFFICIENT", "NOT_TRACKED", "INSUFFICIENT")

    # When suggestion ranking is calculated.
    ranked_statuses = sorted(statuses, key=recipe_quantity_rank)

    # Then a cookable recipe is first, followed by actionable shortfalls and unknown amounts.
    assert ranked_statuses == ["SUFFICIENT", "INSUFFICIENT", "UNKNOWN", "NOT_TRACKED"]
