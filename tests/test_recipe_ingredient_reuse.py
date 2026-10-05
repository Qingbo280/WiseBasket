"""Reviewed recipe-slot alternatives never erase catalogue SKU distinctions."""

from collections import defaultdict

from migrations.versions.p3q4r5s6t7u8_seed_epic5_35_recipe_collection import INGREDIENTS
from services.api.app.services.recipe_ingredient_reuse import (
    CHICKEN_RECIPES, COCONUT_MILK_RECIPES, PRAWN_RECIPES,
    SERVED_RICE_RECIPES, resolve_reused_ingredients, reused_pantry_quantities,
)
from services.api.app.services.recipe_matching import Recipe, RecipeIngredient, match_recipe
from services.api.app.services.recipe_quantities import PantryQuantity


def test_reviewed_scope_matches_the_seed_and_not_arbitrary_future_recipes():
    recipes_by_food: dict[str, set[str]] = defaultdict(set)
    for recipe_id, food_id, required, _, _ in INGREDIENTS:
        if required:
            recipes_by_food[food_id].add(recipe_id)
    assert recipes_by_food["SF006"] | recipes_by_food["SF014"] == CHICKEN_RECIPES
    assert recipes_by_food["SF022"] == PRAWN_RECIPES
    assert recipes_by_food["SF102"] == COCONUT_MILK_RECIPES
    assert recipes_by_food["SF110"] == SERVED_RICE_RECIPES
    assert resolve_reused_ingredients("unreviewed-chicken-recipe", ("SF014",), {"SF006"}) == {}


def test_whole_chicken_satisfies_curry_thigh_presence_once_without_claiming_enough():
    reused = resolve_reused_ingredients(
        "malaysian-chicken-curry-with-rice", ("SF014",), {"SF006", "SF017"},
    )
    assert reused["SF014"].pantry_food_id == "SF006"  # reviewed deterministic order
    assert reused["SF014"].purchase_mass_comparable is False
    recipe = Recipe("malaysian-chicken-curry-with-rice", "Chicken Curry",
                    (RecipeIngredient("SF014"),))
    matched = match_recipe(recipe, {"SF006", "SF017"} | reused.keys())
    assert matched.required_match_count == 1
    assert matched.required_ingredient_count == 1
    assert matched.available_food_ids == ("SF014",)
    assert matched.missing_food_ids == ()
    quantities = reused_pantry_quantities(reused["SF014"], {
        "SF006": [PantryQuantity("KNOWN", 2000)],
    })
    assert quantities == (PantryQuantity("UNKNOWN", None),)


def test_measured_chicken_leg_beats_unknown_exact_and_unknown_whole_chicken():
    measured = frozenset({"SF013"})
    for recipe_id, required_id in (
        ("malaysian-chicken-curry-with-rice", "SF014"),
        ("soy-sauce-chicken-with-rice", "SF006"),
    ):
        reused = resolve_reused_ingredients(
            recipe_id, (required_id,), {"SF006", "SF013"},
            measured_pantry_food_ids=measured,
        )[required_id]
        assert reused.pantry_food_id == "SF013"
        assert reused_pantry_quantities(reused, {
            "SF013": [PantryQuantity("KNOWN", 1000)],
        }) == (PantryQuantity("UNKNOWN", None),)


def test_measured_exact_still_wins_and_excluded_measured_cut_cannot_be_reused():
    recipe_id = "soy-sauce-chicken-with-rice"
    assert resolve_reused_ingredients(
        recipe_id, ("SF006",), {"SF006", "SF013"},
        measured_pantry_food_ids=frozenset({"SF006", "SF013"}),
    ) == {}
    assert resolve_reused_ingredients(
        recipe_id, ("SF006",), {"SF006", "SF013"}, {"SF013"},
        measured_pantry_food_ids=frozenset({"SF013"}),
    ) == {}


def test_exact_chicken_wins_and_exclusions_and_non_food_forms_do_not_match():
    recipe_id = "malaysian-chicken-curry-with-rice"
    assert resolve_reused_ingredients(recipe_id, ("SF014",), {"SF014", "SF006"}) == {}
    assert resolve_reused_ingredients(recipe_id, ("SF014",), {"SF006"}, {"SF006"}) == {}
    assert resolve_reused_ingredients(recipe_id, ("SF014",), {"SF007"}) == {}
    assert resolve_reused_ingredients(recipe_id, ("SF014",), {"SF016"})["SF014"].pantry_food_id == "SF016"


def test_prawn_and_rice_purchase_mass_can_be_compared_but_dried_or_glutinous_cannot():
    prawn = resolve_reused_ingredients("garlic-prawn-stir-fry", ("SF022",), {"SF036"})["SF022"]
    rice = resolve_reused_ingredients("garlic-prawn-stir-fry", ("SF110",), {"SF113"})["SF110"]
    assert prawn.purchase_mass_comparable and rice.purchase_mass_comparable
    assert reused_pantry_quantities(prawn, {"SF036": [PantryQuantity("KNOWN", 300)]}) == (
        PantryQuantity("KNOWN", 300),
    )
    assert resolve_reused_ingredients("garlic-prawn-stir-fry", ("SF022",), {"SF052"}) == {}
    assert resolve_reused_ingredients("garlic-prawn-stir-fry", ("SF110",), {"SF112"}) == {}


def test_fresh_coconut_milk_matches_presence_but_not_boxed_volume_sufficiency():
    reused = resolve_reused_ingredients(
        "malaysian-chicken-curry-with-rice", ("SF102",), {"SF103"},
    )["SF102"]
    assert reused.purchase_mass_comparable is False
    assert reused_pantry_quantities(reused, {"SF103": [PantryQuantity("KNOWN", 500)]}) == (
        PantryQuantity("UNKNOWN", None),
    )
    assert resolve_reused_ingredients("malaysian-chicken-curry-with-rice", ("SF102",), {"SF104"}) == {}
