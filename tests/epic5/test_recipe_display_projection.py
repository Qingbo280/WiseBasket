"""The existing Recipe UI receives the real pantry SKU, not a renamed recipe SKU."""

import asyncio
from types import SimpleNamespace as Row
from unittest.mock import AsyncMock, patch

from services.api.app.main import (
    build_recipe_quantity_summary,
    get_recipe_detail,
    list_recipe_suggestions,
    recipe_detail_ingredient_response,
    recipe_suggestion_response,
)
from services.api.app.services.recipe_ingredient_reuse import resolve_reused_ingredients


def _food(food_id: str, name: str):
    return Row(canonical_food_id=food_id, canonical_name=name,
               canonical_name_ms=None, category="protein")


def _recipe_response(pantry_rows: tuple[tuple[str, float | None, str | None], ...]):
    recipe = Row(recipe_id="malaysian-chicken-curry-with-rice", name="Chicken Curry",
                 description=None, base_servings=2)
    ingredient = Row(canonical_food_id="SF014", required=True, base_quantity_g=250)
    thigh = _food("SF014", "chicken thigh")
    whole = _food("SF006", "whole chicken")
    pantry_ids = {food_id for food_id, _, _ in pantry_rows}
    pantry_items = tuple(
        Row(canonical_food_id=food_id, quantity=quantity, unit=unit, source="MANUAL")
        for food_id, quantity, unit in pantry_rows
    )
    reused = resolve_reused_ingredients(recipe.recipe_id, ("SF014",), pantry_ids)
    summary = build_recipe_quantity_summary(
        recipe, ((ingredient, thigh),), Row(adults=2, children=0), pantry_items, reused,
    )
    reused_foods = {"SF006": whole} if reused else {}
    suggestion = recipe_suggestion_response(
        recipe, ((ingredient, thigh),), pantry_ids, summary, reused, reused_foods,
    )
    detail_ingredient = recipe_detail_ingredient_response(
        ingredient, thigh, summary.ingredients[0], reused, reused_foods,
    )
    return suggestion, detail_ingredient


def test_owned_whole_chicken_projects_its_real_id_in_list_and_detail():
    suggestion, detail = _recipe_response((("SF006", 2.0, "kg"),))
    assert [(food.canonical_food_id, food.name) for food in suggestion.available_ingredients] == [
        ("SF006", "whole chicken"),
    ]
    assert suggestion.missing_required_ingredients == []
    assert suggestion.required_match_count == 1
    assert suggestion.matched_alternatives == {"SF014": "SF006"}
    assert (detail.food.canonical_food_id, detail.food.name) == ("SF006", "whole chicken")
    assert detail.required_quantity_kg is None  # thigh grams are not whole-chicken grams
    assert detail.quantity_status == "UNKNOWN"
    assert detail.is_quantity_sufficient is False


def test_no_chicken_preserves_the_recipe_thigh_for_display_and_need_it():
    suggestion, detail = _recipe_response(())
    assert suggestion.available_ingredients == []
    assert [(food.canonical_food_id, food.name) for food in suggestion.missing_required_ingredients] == [
        ("SF014", "chicken thigh"),
    ]
    assert suggestion.required_match_count == 0
    assert suggestion.matched_alternatives == {}
    assert (detail.food.canonical_food_id, detail.food.name) == ("SF014", "chicken thigh")
    assert detail.required_quantity_kg == 0.25


def test_exact_thigh_remains_the_display_when_both_cuts_are_owned():
    suggestion, detail = _recipe_response((("SF014", 0.25, "kg"), ("SF006", 1.0, "kg")))
    assert [food.canonical_food_id for food in suggestion.available_ingredients] == ["SF014"]
    assert suggestion.matched_alternatives == {}
    assert detail.food.canonical_food_id == "SF014"
    assert detail.is_quantity_sufficient is True


def test_list_and_detail_endpoints_return_the_same_owned_substitute():
    recipe = Row(recipe_id="malaysian-chicken-curry-with-rice", name="Chicken Curry",
                 description=None, base_servings=2, active=True)
    ingredient = Row(recipe_id=recipe.recipe_id, canonical_food_id="SF014",
                     required=True, base_quantity_g=250, ingredient_role="MAIN_PROTEIN")
    thigh = _food("SF014", "chicken thigh")
    whole = _food("SF006", "whole chicken")
    pantry = Row(canonical_food_id="SF006", status="AVAILABLE", quantity=2.0,
                 unit="kg", source="MANUAL")

    class FakeDb:
        async def get(self, model, key):
            return recipe

        async def scalars(self, query):
            name = query.column_descriptions[0]["name"]
            values = {"PantryItem": [pantry], "RecipeCatalog": [recipe],
                      "CanonicalFood": [whole], "instruction": ["Cook chicken."]}[name]
            return Row(all=lambda: values)

        async def execute(self, query):
            return Row(all=lambda: [(ingredient, thigh)])

    async def check():
        db = FakeDb()
        with patch("services.api.app.main.find_owned_household",
                   AsyncMock(return_value=Row(adults=2, children=0))), \
             patch("services.api.app.main._resolve_excluded_food_ids",
                   AsyncMock(return_value=set())):
            listed = await list_recipe_suggestions(
                1, exclusions=[], use_semantic=False, gluten_free=False,
                custom_restriction="", planned_food_ids=None, advice=False, current_user=None, db=db,
            )
            detail = await get_recipe_detail(
                1, recipe.recipe_id, exclusions=[], gluten_free=False,
                custom_restriction="", current_user=None, db=db,
            )
        assert [food.canonical_food_id for food in listed[0].available_ingredients] == ["SF006"]
        assert [food.canonical_food_id for food in detail.available_ingredients] == ["SF006"]
        assert [item.food.canonical_food_id for item in detail.ingredients] == ["SF006"]
        assert detail.ingredients[0].required_quantity_kg is None
        assert detail.matched_alternatives == {"SF014": "SF006"}
        assert detail.readiness == listed[0].readiness
        assert detail.readiness.status == "CHECK_QUANTITIES"
        assert detail.readiness.all_required_ingredients_available
        assert not detail.readiness.all_required_quantities_sufficient
        issue = detail.readiness.issues[0]
        assert issue.recipe_food_id == "SF014"
        assert issue.food.canonical_food_id == "SF006"
        assert issue.reason == "SUBSTITUTION_CONVERSION_UNAVAILABLE"
        assert issue.required_quantity_kg is None
        assert issue.shortfall_quantity_kg is None
        assert detail.model_dump(mode="json")["readiness"]["issues"][0]["food"]["name"] == "whole chicken"

    asyncio.run(check())


def test_list_and_detail_prefer_measured_leg_to_unknown_whole_chicken():
    recipe = Row(recipe_id="malaysian-chicken-curry-with-rice", name="Chicken Curry",
                 description=None, base_servings=2, active=True)
    ingredient = Row(recipe_id=recipe.recipe_id, canonical_food_id="SF014",
                     required=True, base_quantity_g=250, ingredient_role="MAIN_PROTEIN")
    thigh = _food("SF014", "chicken thigh")
    leg = _food("SF013", "chicken whole leg")
    pantry = [
        Row(canonical_food_id="SF006", status="AVAILABLE", quantity=None,
            unit=None, source="MANUAL"),
        Row(canonical_food_id="SF013", status="AVAILABLE", quantity=1.0,
            unit="kg", source="MANUAL"),
    ]

    class FakeDb:
        async def get(self, model, key):
            return recipe

        async def scalars(self, query):
            name = query.column_descriptions[0]["name"]
            values = {"PantryItem": pantry, "RecipeCatalog": [recipe],
                      "CanonicalFood": [leg], "instruction": ["Cook chicken."]}[name]
            return Row(all=lambda: values)

        async def execute(self, query):
            return Row(all=lambda: [(ingredient, thigh)])

    async def check():
        db = FakeDb()
        with patch("services.api.app.main.find_owned_household",
                   AsyncMock(return_value=Row(adults=2, children=2))), \
             patch("services.api.app.main._resolve_excluded_food_ids",
                   AsyncMock(return_value=set())):
            listed = await list_recipe_suggestions(
                1, exclusions=[], use_semantic=False, gluten_free=False,
                custom_restriction="", planned_food_ids=None, advice=False, current_user=None, db=db,
            )
            detail = await get_recipe_detail(
                1, recipe.recipe_id, exclusions=[], gluten_free=False,
                custom_restriction="", current_user=None, db=db,
            )
        assert listed[0].matched_alternatives == {"SF014": "SF013"}
        assert listed[0].available_ingredients[0].canonical_food_id == "SF013"
        assert detail.ingredients[0].food.canonical_food_id == "SF013"
        assert detail.readiness.status == "CHECK_QUANTITIES"
        assert detail.ingredients[0].is_quantity_sufficient is False
        assert detail.ingredients[0].required_quantity_kg is None

    asyncio.run(check())
