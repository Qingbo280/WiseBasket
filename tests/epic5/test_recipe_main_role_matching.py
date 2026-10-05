"""Main-role recipe matching: additive suggestion fields and basics_only pantry.

Oil/salt are COOKING_ESSENTIAL/SEASONING and must never inflate recipe
matches: a pantry holding only cooking oil is "basics_only" and receives
unlock suggestions instead of 30+ oil-boosted stir-fries floating to the top.
"""
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch


def _food(food_id, name=None):
    return SimpleNamespace(
        canonical_food_id=food_id,
        canonical_name=name or food_id,
        canonical_name_ms=None,
        category="test",
    )


def _recipe(recipe_id, name, ingredients):
    """ingredients: (food_id, required, role, grams) tuples."""
    recipe = SimpleNamespace(
        recipe_id=recipe_id, name=name, description=None, base_servings=2,
    )
    rows = [
        (
            SimpleNamespace(
                recipe_id=recipe_id,
                canonical_food_id=food_id,
                required=required,
                base_quantity_g=grams,
                ingredient_role=role,
            ),
            _food(food_id),
        )
        for food_id, required, role, grams in ingredients
    ]
    return recipe, rows


# Tomato-egg stir-fry: egg/tomato/rice are mains, oil is COOKING_ESSENTIAL,
# sugar/salt are optional seasonings (mirrors the real curated recipe).
TOMATO_EGG = (
    ("SF018", True, "MAIN_PROTEIN", 100),
    ("SF0TO", True, "MAIN_VEGETABLE", 200),
    ("SF110", True, "STAPLE", 160),
    ("SF120", True, "COOKING_ESSENTIAL", 20),
    ("SFSUG", False, "SEASONING", 10),
    ("SFSAL", False, "SEASONING", 5),
)
EGG_SOUP = (
    ("SF018", True, "MAIN_PROTEIN", 100),
    ("SF120", True, "COOKING_ESSENTIAL", 10),
)
GARLIC_BROCCOLI = (
    ("SF0BR", True, "MAIN_VEGETABLE", 300),
    ("SF0GA", True, "SEASONING", 16),
    ("SF120", True, "COOKING_ESSENTIAL", 20),
)


def _world(recipes_with_rows, pantry_food_ids):
    recipes = [recipe for recipe, _ in recipes_with_rows]
    all_rows = [
        (ingredient, food)
        for _, rows in recipes_with_rows
        for ingredient, food in rows
    ]
    pantry = [
        SimpleNamespace(canonical_food_id=food_id, quantity=None, unit=None, source="MANUAL")
        for food_id in pantry_food_ids
    ]

    async def scalars(query):
        selected = query.column_descriptions[0]["name"]
        values = pantry if selected == "PantryItem" else recipes
        return SimpleNamespace(all=lambda: values)

    async def execute(query):
        return SimpleNamespace(all=lambda: all_rows)

    return SimpleNamespace(scalars=scalars, execute=execute)


async def _suggestions(db, prices=None, planned_food_ids=None, advice=False):
    from services.api.app.main import list_recipe_suggestions

    with patch("services.api.app.main.find_owned_household",
               AsyncMock(return_value=SimpleNamespace(adults=1, children=0))), \
         patch("services.api.app.main._resolve_excluded_food_ids", AsyncMock(return_value=set())), \
         patch("services.api.app.main.load_estimated_prices_rm",
               AsyncMock(return_value=prices or {})):
        return await list_recipe_suggestions(
            1, exclusions=[], use_semantic=False, gluten_free=False,
            custom_restriction="", planned_food_ids=planned_food_ids,
            advice=advice, current_user=None, db=db,
        )


class MainRoleSuggestionFieldTests(unittest.IsolatedAsyncioTestCase):
    async def test_can_make_true_and_oil_missing_but_not_missing_main(self):
        # Pantry owns egg+tomato+rice but no oil: every main ingredient is
        # present, so can_make is True. Oil stays honestly listed under
        # missing_required_ingredients but never under missing_main.
        recipes = [_recipe("tomato-egg", "Tomato Egg Stir-Fry", TOMATO_EGG)]
        db = _world(recipes, {"SF018", "SF0TO", "SF110"})
        result = await _suggestions(db)
        suggestion = next(item for item in result if item.recipe_id == "tomato-egg")
        self.assertEqual(suggestion.main_ingredient_count, 3)
        self.assertEqual(suggestion.main_match_count, 3)
        self.assertTrue(suggestion.can_make)
        missing_required = {food.canonical_food_id for food in suggestion.missing_required_ingredients}
        missing_main = {food.canonical_food_id for food in suggestion.missing_main_ingredients}
        self.assertIn("SF120", missing_required)
        self.assertNotIn("SF120", missing_main)
        self.assertEqual(missing_main, set())
        self.assertEqual(suggestion.pantry_state, "ok")
        self.assertIsNone(suggestion.unlock_suggestions)

    async def test_oil_only_pantry_degrades_to_fewest_missing_first(self):
        # Never-empty semantics: an oil-only pantry has no main match
        # anywhere, so the zero-main filter degrades to the full eligible
        # set. pantry_state stays basics_only and the existing
        # fewest-missing ordering floats one-purchase-away dishes to the top.
        recipes = [
            _recipe("tomato-egg", "Tomato Egg Stir-Fry", TOMATO_EGG),
            _recipe("egg-soup", "Egg Drop Soup", EGG_SOUP),
            _recipe("broccoli", "Garlic Broccoli", GARLIC_BROCCOLI),
        ]
        db = _world(recipes, {"SF120"})
        result = await _suggestions(db)
        self.assertEqual(len(result), 3)
        for suggestion in result:
            self.assertEqual(suggestion.main_match_count, 0)
            self.assertFalse(suggestion.can_make)
            self.assertEqual(suggestion.pantry_state, "basics_only")
        missing_counts = [
            item.required_ingredient_count - item.required_match_count for item in result
        ]
        self.assertEqual(missing_counts, sorted(missing_counts))
        # The single-main dishes (one missing main) lead the degraded list.
        self.assertEqual(result[0].recipe_id, "egg-soup")
        self.assertEqual(
            [food.canonical_food_id for food in result[0].missing_main_ingredients],
            ["SF018"],
        )
        # Deterministic across runs.
        second = await _suggestions(db)
        self.assertEqual(
            [item.model_dump() for item in result],
            [item.model_dump() for item in second],
        )

    def test_unlock_suggestions_are_deterministic_for_a_basics_only_pantry(self):
        # The unlock computation still runs for basics_only pantries; exercise
        # it directly since the (empty) suggestions list cannot carry it.
        from services.api.app.main import recipe_unlock_suggestions

        recipes = [
            _recipe("tomato-egg", "Tomato Egg Stir-Fry", TOMATO_EGG),
            _recipe("egg-soup", "Egg Drop Soup", EGG_SOUP),
            _recipe("broccoli", "Garlic Broccoli", GARLIC_BROCCOLI),
        ]
        eligible = [(recipe, rows, {}) for recipe, rows in recipes]
        unlocks = recipe_unlock_suggestions(eligible)
        by_id = {item.canonical_food_id: item for item in unlocks}
        # Egg is a main ingredient in two recipes, so it leads the list.
        self.assertEqual(unlocks[0].canonical_food_id, "SF018")
        self.assertEqual(by_id["SF018"].recipes_unlocked, 2)
        self.assertEqual(
            by_id["SF018"].sample_recipe_names,
            ["Egg Drop Soup", "Tomato Egg Stir-Fry"],
        )
        self.assertGreaterEqual(by_id["SF0BR"].recipes_unlocked, 1)
        self.assertEqual(
            [item.model_dump() for item in unlocks],
            [item.model_dump() for item in recipe_unlock_suggestions(eligible)],
        )

    async def test_empty_pantry_degrades_to_full_eligible_set(self):
        recipes = [_recipe("tomato-egg", "Tomato Egg Stir-Fry", TOMATO_EGG)]
        db = _world(recipes, set())
        result = await _suggestions(db)
        self.assertEqual([item.recipe_id for item in result], ["tomato-egg"])
        self.assertEqual(result[0].pantry_state, "basics_only")
        self.assertEqual(result[0].main_match_count, 0)

    async def test_available_main_ingredients_follow_curated_order(self):
        # Pantry owns egg+rice but not tomato: available_main_ingredients
        # lists the owned mains in curated display_order, missing_main lists
        # the rest, and oil appears in neither.
        recipes = [_recipe("tomato-egg", "Tomato Egg Stir-Fry", TOMATO_EGG)]
        db = _world(recipes, {"SF018", "SF110"})
        result = await _suggestions(db)
        suggestion = result[0]
        self.assertEqual(
            [food.canonical_food_id for food in suggestion.available_main_ingredients],
            ["SF018", "SF110"],
        )
        self.assertEqual(
            [food.canonical_food_id for food in suggestion.missing_main_ingredients],
            ["SF0TO"],
        )
        self.assertFalse(suggestion.can_make)

    async def test_zero_main_recipe_ranks_last_when_another_main_matches(self):
        # Every eligible recipe is listed; ranking alone keeps the matched
        # tomato-egg ahead of the zero-match broccoli stir-fry.
        recipes = [
            _recipe("tomato-egg", "Tomato Egg Stir-Fry", TOMATO_EGG),
            _recipe("broccoli", "Garlic Broccoli", GARLIC_BROCCOLI),
        ]
        db = _world(recipes, {"SF018"})
        result = await _suggestions(db)
        self.assertEqual([item.recipe_id for item in result], ["tomato-egg", "broccoli"])
        suggestion = result[0]
        self.assertEqual(suggestion.main_match_count, 1)
        self.assertGreater(suggestion.main_ingredient_count, 1)
        self.assertFalse(suggestion.can_make)
        self.assertEqual(suggestion.pantry_state, "ok")
        self.assertIsNone(suggestion.unlock_suggestions)
        self.assertEqual(result[1].main_match_count, 0)
        self.assertEqual(result[1].pantry_state, "ok")

    async def test_available_main_ingredients_empty_when_no_main_owned(self):
        # Zero owned mains means the recipe only appears via the basics_only
        # fallback, with an empty available_main_ingredients list.
        recipes = [_recipe("broccoli", "Garlic Broccoli", GARLIC_BROCCOLI)]
        db = _world(recipes, {"SF120"})
        result = await _suggestions(db)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].available_main_ingredients, [])
        self.assertEqual(
            [food.canonical_food_id for food in result[0].missing_main_ingredients],
            ["SF0BR"],
        )

    async def test_main_match_against_oil_expanded_pantry(self):
        # Owning any equivalent oil ID must still leave the pantry
        # basics_only: oil expansion never creates a main match, and the
        # never-empty fallback then returns the degraded full set.
        from packages.optimizer.wisebasket_optimizer.v2.oil_equivalence import OIL_FOOD_IDS

        oil_id = sorted(OIL_FOOD_IDS)[0]
        recipes = [_recipe("broccoli", "Garlic Broccoli", GARLIC_BROCCOLI)]
        db = _world(recipes, {oil_id})
        result = await _suggestions(db)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].main_match_count, 0)
        self.assertEqual(result[0].pantry_state, "basics_only")


GARLIC_SPINACH = (
    ("SF0SP", True, "MAIN_VEGETABLE", 250),
    ("SF0GA", True, "SEASONING", 16),
    ("SF120", True, "COOKING_ESSENTIAL", 20),
)
RICE_PORRIDGE = (
    ("SF110", True, "STAPLE", 160),
    ("SF120", True, "COOKING_ESSENTIAL", 10),
)


def _eligible(recipes):
    return [(recipe, rows, {}) for recipe, rows in recipes]


class ZeroMainFilterSemanticsTests(unittest.IsolatedAsyncioTestCase):
    async def test_rice_staple_counts_as_a_normal_main_ingredient(self):
        # Pinned product decision: rice (STAPLE) is a real main ingredient.
        # A rice-only pantry is NOT basics_only; rice dishes stay listed.
        recipes = [
            _recipe("tomato-egg", "Tomato Egg Stir-Fry", TOMATO_EGG),
            _recipe("porridge", "Rice Porridge", RICE_PORRIDGE),
            _recipe("broccoli", "Garlic Broccoli", GARLIC_BROCCOLI),
        ]
        db = _world(recipes, {"SF110"})
        result = await _suggestions(db)
        # Every eligible recipe is listed; rice-matching dishes lead, the
        # zero-match broccoli stir-fry ranks last.
        self.assertEqual(
            [item.recipe_id for item in result],
            ["porridge", "tomato-egg", "broccoli"],
        )
        self.assertEqual(result[0].main_match_count, 1)
        self.assertEqual(result[-1].main_match_count, 0)
        self.assertTrue(all(item.pantry_state == "ok" for item in result))
        self.assertTrue(all(item.unlock_suggestions is None for item in result))
        self.assertTrue(all(item.quick_win_suggestions is None for item in result))
        self.assertTrue(all(item.planned_unlock_summary is None for item in result))

    async def test_planned_hit_ranks_tier_two_without_claiming_ownership(self):
        # Three-tier contract with planned ids: tomato-egg has a planned main
        # (egg) but no pantry main, so it is tier 2 — after the pantry-matched
        # broccoli, before the untouched porridge. Planned foods never count
        # as pantry matches.
        recipes = [
            _recipe("tomato-egg", "Tomato Egg Stir-Fry", TOMATO_EGG),
            _recipe("broccoli", "Garlic Broccoli", GARLIC_BROCCOLI),
            _recipe("porridge", "Rice Porridge", RICE_PORRIDGE),
        ]
        db = _world(recipes, {"SF0BR"})
        result = await _suggestions(db, planned_food_ids=["SF018"])
        self.assertEqual(
            [item.recipe_id for item in result],
            ["broccoli", "tomato-egg", "porridge"],
        )
        planned_hit = result[1]
        self.assertEqual(planned_hit.main_match_count, 0)
        self.assertEqual(planned_hit.required_match_count, 0)
        self.assertTrue(all(item.pantry_state == "ok" for item in result))


class BasicsOnlyAdviceLayerTests(unittest.TestCase):
    """The three basics-only advice layers, exercised at the computation
    layer: the bare-list response is empty in basics_only, so these payloads
    currently have no item to ride on (documented in main.py)."""

    def setUp(self):
        self.recipes = [
            _recipe("tomato-egg", "Tomato Egg Stir-Fry", TOMATO_EGG),
            _recipe("egg-soup", "Egg Drop Soup", EGG_SOUP),
            _recipe("broccoli", "Garlic Broccoli", GARLIC_BROCCOLI),
            _recipe("spinach", "Garlic Spinach", GARLIC_SPINACH),
            _recipe("porridge", "Rice Porridge", RICE_PORRIDGE),
        ]

    def test_quick_win_lists_single_main_dishes_by_price(self):
        from services.api.app.main import recipe_quick_win_suggestions

        prices = {"SF018": 1.20, "SF0BR": 0.50}  # SF0SP/SF110 unpriced -> last
        wins = recipe_quick_win_suggestions(_eligible(self.recipes), prices)
        # tomato-egg has three mains and never qualifies. Priced first
        # (cheapest wins), unpriced last with a food_id tiebreak.
        self.assertEqual(
            [item.canonical_food_id for item in wins],
            ["SF0BR", "SF018", "SF0SP", "SF110"],
        )
        by_id = {item.canonical_food_id: item for item in wins}
        self.assertEqual(by_id["SF0BR"].recipe_id, "broccoli")
        self.assertEqual(by_id["SF0BR"].recipe_name, "Garlic Broccoli")
        self.assertEqual(by_id["SF0BR"].estimated_price_rm, 0.50)
        self.assertIsNone(by_id["SF0SP"].estimated_price_rm)
        # Deterministic across runs.
        self.assertEqual(
            [item.model_dump() for item in wins],
            [item.model_dump() for item in recipe_quick_win_suggestions(_eligible(self.recipes), prices)],
        )

    def test_unlock_tiebreak_chain_role_then_price(self):
        from services.api.app.main import recipe_unlock_suggestions

        # SF018 and SF110 each appear in two recipes; the count tie breaks
        # by role priority (protein < staple) regardless of price. The
        # single-recipe vegetables then order by price, unpriced last.
        prices = {"SF0SP": 0.10, "SF018": 9.99, "SF0BR": 0.50}
        unlocks = recipe_unlock_suggestions(_eligible(self.recipes), prices)
        self.assertEqual(
            [item.canonical_food_id for item in unlocks],
            ["SF018", "SF110", "SF0SP", "SF0BR", "SF0TO"],
        )
        by_id = {item.canonical_food_id: item for item in unlocks}
        self.assertEqual(by_id["SF018"].ingredient_role, "MAIN_PROTEIN")
        self.assertEqual(by_id["SF018"].estimated_price_rm, 9.99)
        self.assertEqual(by_id["SF110"].ingredient_role, "STAPLE")
        self.assertIsNone(by_id["SF110"].estimated_price_rm)

    def test_planned_unlock_summary_counts_dishes_with_planned_mains(self):
        from services.api.app.main import planned_unlock_summary

        summary = planned_unlock_summary(_eligible(self.recipes), ["SF018"])
        self.assertIsNotNone(summary)
        self.assertEqual(summary.dishes_count, 2)  # tomato-egg + egg-soup
        self.assertEqual(
            summary.sample_recipe_names, ["Egg Drop Soup", "Tomato Egg Stir-Fry"],
        )
        self.assertEqual(summary.planned_main_food_ids, ["SF018"])
        self.assertIsNone(planned_unlock_summary(_eligible(self.recipes), []))
        self.assertIsNone(planned_unlock_summary(_eligible(self.recipes), ["SF120"]))
        # Deterministic across runs.
        self.assertEqual(
            summary.model_dump(),
            planned_unlock_summary(_eligible(self.recipes), ["SF018"]).model_dump(),
        )


class AdviceOptInWrapperTests(unittest.IsolatedAsyncioTestCase):
    async def test_default_response_stays_the_bare_list(self):
        recipes = [_recipe("tomato-egg", "Tomato Egg Stir-Fry", TOMATO_EGG)]
        db = _world(recipes, {"SF018"})
        result = await _suggestions(db)
        self.assertIsInstance(result, list)
        self.assertEqual(result[0].recipe_id, "tomato-egg")

    async def test_advice_wrapper_with_a_normal_pantry(self):
        recipes = [_recipe("tomato-egg", "Tomato Egg Stir-Fry", TOMATO_EGG)]
        db = _world(recipes, {"SF018", "SF0TO", "SF110"})
        result = await _suggestions(db, advice=True)
        self.assertNotIsInstance(result, list)
        self.assertEqual([item.recipe_id for item in result.suggestions], ["tomato-egg"])
        self.assertEqual(result.pantry_state, "ok")
        self.assertIsNone(result.quick_win_suggestions)
        self.assertIsNone(result.unlock_suggestions)
        self.assertIsNone(result.planned_unlock_summary)
        # Item-level duplicated fields stay in place inside suggestions.
        self.assertEqual(result.suggestions[0].pantry_state, "ok")

    async def test_advice_wrapper_carries_basics_only_layers_on_the_fallback_list(self):
        recipes = [
            _recipe("tomato-egg", "Tomato Egg Stir-Fry", TOMATO_EGG),
            _recipe("egg-soup", "Egg Drop Soup", EGG_SOUP),
            _recipe("broccoli", "Garlic Broccoli", GARLIC_BROCCOLI),
        ]
        db = _world(recipes, {"SF120"})
        prices = {"SF018": 1.20, "SF0BR": 0.50}
        result = await _suggestions(db, prices=prices, planned_food_ids=["SF018"], advice=True)
        # Never-empty semantics: the degraded full set rides the wrapper too.
        self.assertEqual(len(result.suggestions), 3)
        self.assertEqual(result.pantry_state, "basics_only")
        self.assertTrue(
            all(item.pantry_state == "basics_only" for item in result.suggestions)
        )
        # Layer 1: single-main dishes, price ascending. egg-soup and broccoli
        # qualify; tomato-egg (three mains) never does.
        self.assertEqual(
            [item.canonical_food_id for item in result.quick_win_suggestions],
            ["SF0BR", "SF018"],
        )
        self.assertEqual(result.quick_win_suggestions[0].recipe_name, "Garlic Broccoli")
        # Layer 2: same source as the item-level payload, egg leads on count.
        self.assertEqual(result.unlock_suggestions[0].canonical_food_id, "SF018")
        self.assertEqual(result.unlock_suggestions[0].recipes_unlocked, 2)
        # Layer 3: the planned egg unlocks two dishes.
        self.assertIsNotNone(result.planned_unlock_summary)
        self.assertEqual(result.planned_unlock_summary.dishes_count, 2)
        self.assertEqual(result.planned_unlock_summary.planned_main_food_ids, ["SF018"])
        # Top-level payloads are lifted from the exact same computations.
        from services.api.app.main import (
            planned_unlock_summary,
            recipe_quick_win_suggestions,
            recipe_unlock_suggestions,
        )
        eligible = [(recipe, rows, {}) for recipe, rows in recipes]
        self.assertEqual(
            [item.model_dump() for item in result.quick_win_suggestions],
            [item.model_dump() for item in recipe_quick_win_suggestions(eligible, prices)],
        )
        self.assertEqual(
            [item.model_dump() for item in result.unlock_suggestions],
            [item.model_dump() for item in recipe_unlock_suggestions(eligible, prices)],
        )
        self.assertEqual(
            result.planned_unlock_summary.model_dump(),
            planned_unlock_summary(eligible, ["SF018"]).model_dump(),
        )

    async def test_advice_wrapper_with_rice_only_pantry_stays_ok(self):
        # Rice (STAPLE) is a normal main ingredient: no basics_only advice.
        recipes = [
            _recipe("porridge", "Rice Porridge", RICE_PORRIDGE),
            _recipe("broccoli", "Garlic Broccoli", GARLIC_BROCCOLI),
        ]
        db = _world(recipes, {"SF110"})
        result = await _suggestions(db, advice=True)
        self.assertEqual(result.pantry_state, "ok")
        # Full ranked list: the rice dish leads, the zero-match broccoli
        # stir-fry ranks last, no basics_only advice.
        self.assertEqual(
            [item.recipe_id for item in result.suggestions], ["porridge", "broccoli"],
        )
        self.assertEqual(result.suggestions[-1].main_match_count, 0)
        self.assertIsNone(result.quick_win_suggestions)
        self.assertIsNone(result.unlock_suggestions)
        self.assertIsNone(result.planned_unlock_summary)

class NoTruncationTests(unittest.IsolatedAsyncioTestCase):
    async def test_all_eligible_recipes_returned_without_truncation(self):
        # No total cap and family overflow demotes instead of dropping: a
        # 12-recipe world returns all 12 even with an oil-only pantry, and
        # the five egg dishes all stay visible.
        recipes = [
            _recipe(f"egg-{index}", f"Egg Dish {index}", EGG_SOUP) for index in range(5)
        ] + [
            _recipe("tomato-egg", "Tomato Egg Stir-Fry", TOMATO_EGG),
            _recipe("broccoli", "Garlic Broccoli", GARLIC_BROCCOLI),
            _recipe("spinach", "Garlic Spinach", GARLIC_SPINACH),
            _recipe("porridge", "Rice Porridge", RICE_PORRIDGE),
            _recipe("veg-1", "Long Beans", GARLIC_BROCCOLI),
            _recipe("veg-2", "Mustard Greens", GARLIC_BROCCOLI),
            _recipe("veg-3", "Cauliflower", GARLIC_BROCCOLI),
        ]
        db = _world(recipes, {"SF120"})
        result = await _suggestions(db)
        self.assertEqual(len(result), 12)
        self.assertTrue(all(item.pantry_state == "basics_only" for item in result))
        egg_ids = [item.recipe_id for item in result if item.recipe_id.startswith("egg-")]
        self.assertEqual(len(egg_ids), 5)
        # Family overflow demotes to the tier tail, in original order.
        self.assertEqual(egg_ids, [f"egg-{index}" for index in range(5)])


class FamilyDemotionStaysInTierTests(unittest.IsolatedAsyncioTestCase):
    async def test_family_overflow_sinks_to_tier_tail_never_across_tiers(self):
        # Key no-truncation contract: the 4th egg dish (family overflow) sinks
        # to the END of tier 1 — after the accepted egg dishes but still
        # BEFORE every tier-2 (planned) dish. Demotion never crosses tiers.
        recipes = [
            _recipe(f"egg-{index}", f"Egg Dish {index}", EGG_SOUP) for index in range(4)
        ] + [
            _recipe("chicken-rice", "Chicken Rice", (
                ("SF006", True, "MAIN_PROTEIN", 200),
                ("SF110", True, "STAPLE", 160),
                ("SF120", True, "COOKING_ESSENTIAL", 20),
            )),
            _recipe("broccoli", "Garlic Broccoli", GARLIC_BROCCOLI),
        ]
        db = _world(recipes, {"SF018"})
        result = await _suggestions(db, planned_food_ids=["SF006"])
        ids = [item.recipe_id for item in result]
        self.assertEqual(len(ids), 6)
        # Three accepted egg dishes lead tier 1, the overflow egg dish sits at
        # the tier-1 tail, then the planned chicken dish (tier 2), then the
        # untouched broccoli (tier 3).
        self.assertEqual(ids, ["egg-0", "egg-1", "egg-2", "egg-3", "chicken-rice", "broccoli"])
        self.assertLess(ids.index("egg-3"), ids.index("chicken-rice"))
        self.assertTrue(all(item.pantry_state == "ok" for item in result))
        # Deterministic across runs.
        second = await _suggestions(db, planned_food_ids=["SF006"])
        self.assertEqual(ids, [item.recipe_id for item in second])
