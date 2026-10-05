import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from services.api.app.services.recipe_matching import main_ingredient_priority


class RecipePantryRankingTests(unittest.TestCase):
    def test_main_ingredient_beats_seasoning_only_match(self):
        ingredients = (("broccoli", True, 300), ("garlic", True, 16))
        self.assertGreater(
            main_ingredient_priority(ingredients, {"broccoli"}),
            main_ingredient_priority(ingredients, {"garlic"}),
        )

    def test_have_without_quantity_counts_as_main_match(self):
        ingredients = (("egg", True, 100), ("rice", True, 160))
        self.assertEqual(main_ingredient_priority(ingredients, {"egg"}), (0.5, 1))

    def test_optional_ingredients_do_not_drive_priority(self):
        ingredients = (("egg", True, 100), ("oil", False, 200))
        self.assertEqual(main_ingredient_priority(ingredients, {"oil"}), (0, 0))

    def test_unmeasured_recipe_falls_back_to_required_ingredients(self):
        self.assertEqual(main_ingredient_priority((("egg", True, None),), {"egg"}), (1, 1))


class RecipeSuggestionEndpointTests(unittest.IsolatedAsyncioTestCase):
    async def test_badge_total_includes_optional_ingredients_without_changing_required_counts(self):
        from services.api.app.main import recipe_suggestion_response
        from services.api.app.services.recipe_quantity_summary import summarize_recipe_quantities

        for foods, pantry, expected in (
            ((('cauliflower', True), ('soy', True), ('garlic', False), ('carrot', False), ('oil', False)), {'oil'}, (1, 5, 0, 2)),
            ((('egg', True), ('soy', True), ('sugar', True), ('rice', True), ('onion', False), ('garlic', False), ('oil', False)), {'egg', 'oil'}, (2, 7, 1, 4)),
        ):
            rows = [(SimpleNamespace(canonical_food_id=food_id, required=required),
                     SimpleNamespace(canonical_food_id=food_id, canonical_name=food_id, canonical_name_ms=None, category='test'))
                    for food_id, required in foods]
            summary = summarize_recipe_quantities(None, 1, 0, ())
            result = recipe_suggestion_response(
                SimpleNamespace(recipe_id='test', name='Test', description=None), rows, pantry, summary,
            )
            self.assertEqual((len(result.available_ingredients), result.ingredient_count,
                              result.required_match_count, result.required_ingredient_count), expected)

    async def test_quantity_free_pantry_updates_endpoint_order_and_counts(self):
        from services.api.app.main import list_recipe_suggestions

        def recipe(recipe_id, name):
            return SimpleNamespace(recipe_id=recipe_id, name=name, description=None, base_servings=2)

        def row(food_id, grams):
            return (
                SimpleNamespace(canonical_food_id=food_id, required=True, base_quantity_g=grams),
                SimpleNamespace(canonical_food_id=food_id, canonical_name=food_id, canonical_name_ms=None, category="test"),
            )

        recipes = [recipe("broccoli", "Garlic Broccoli"), recipe("egg", "Z Egg Rice")]
        rows = {"broccoli": [row("broccoli", 300), row("garlic", 16)],
                "egg": [row("egg", 100), row("rice", 160)]}
        pantry = [SimpleNamespace(canonical_food_id=food_id, quantity=None, unit=None, source="MANUAL")
                  for food_id in ("garlic", "egg")]

        async def scalars(query):
            selected = query.column_descriptions[0]["name"]
            values = pantry if selected == "PantryItem" else recipes
            return SimpleNamespace(all=lambda: values)

        async def execute(query):
            pairs = []
            for recipe_id, recipe_rows in rows.items():
                for ingredient, food in recipe_rows:
                    ingredient.recipe_id = recipe_id
                    pairs.append((ingredient, food))
            return SimpleNamespace(all=lambda: pairs)

        with patch("services.api.app.main.find_owned_household", AsyncMock(return_value=SimpleNamespace(adults=1, children=0))), \
             patch("services.api.app.main._resolve_excluded_food_ids", AsyncMock(return_value=set())), \
             patch("services.api.app.main.recipe_ingredient_rows", AsyncMock(side_effect=lambda recipe_id, db: rows[recipe_id])), \
             patch("services.api.app.main.load_estimated_prices_rm", AsyncMock(return_value={})):
            # load_estimated_prices_rm is patched: the mock db cannot serve
            # the batch price SQL on the basics_only path (pantry cleared
            # below), and prices are irrelevant to this ordering guard.
            db = SimpleNamespace(scalars=scalars, execute=execute)
            result = await list_recipe_suggestions(
                1, exclusions=[], use_semantic=False, gluten_free=False,
                custom_restriction="", planned_food_ids=None, advice=False, current_user=None, db=db,
            )
            # Owning the egg main beats a recipe matching only garlic.
            # Its unknown amount still never counts as sufficient.
            self.assertEqual(result[0].recipe_id, "egg")
            egg = next(item for item in result if item.recipe_id == "egg")
            self.assertEqual(egg.required_match_count, 1)
            self.assertFalse(egg.is_quantity_sufficient)
            pantry.clear()
            result = await list_recipe_suggestions(
                1, exclusions=[], use_semantic=False, gluten_free=False,
                custom_restriction="", planned_food_ids=None, advice=False, current_user=None, db=db,
            )
            self.assertTrue(all(item.required_match_count == 0 for item in result))
