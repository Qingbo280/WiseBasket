"""Offline presentation contract; no database writes or provider calls."""
from copy import deepcopy
from dataclasses import replace

import pytest

from services.api.app.schemas import PantryFoodResponse, RecipeSuggestionResponse
from services.api.app.services.recipe_quantities import PantryQuantity
from services.api.app.services.recipe_quantity_summary import (
    RecipeQuantityIngredientInput as Ingredient, summarize_recipe_quantities,
)
from services.api.app.services.recipe_readiness import build_recipe_readiness


def food(food_id="chicken", name="Chicken breast"):
    return PantryFoodResponse(canonical_food_id=food_id, name=name, name_ms=None, category="protein")


def summary(*ingredients, adults=2, children=0):
    return summarize_recipe_quantities(2, adults, children, ingredients)


def chicken(amount=100):
    stock = (PantryQuantity("UNKNOWN", None),) if amount is None else (PantryQuantity("KNOWN", amount),)
    return Ingredient("chicken", True, 500, stock)


def test_present_is_not_sufficient_and_shortfall_is_actionable():
    result = build_recipe_readiness(summary(chicken()), {"chicken": food()}, {"chicken"})
    assert result.status == "INSUFFICIENT_QUANTITY"
    assert result.all_required_ingredients_available
    assert not result.all_required_quantities_sufficient
    issue = result.issues[0]
    assert (issue.required_quantity_kg, issue.available_quantity_kg, issue.shortfall_quantity_kg) == (0.5, 0.1, 0.4)
    assert issue.message_en == "Chicken breast: need 400 g more."


def test_enough_required_stock_is_ready_even_if_optional_salt_is_missing():
    quantities = summary(chicken(800), Ingredient("salt", False, None, ()))
    result = build_recipe_readiness(quantities, {"chicken": food()}, {"chicken"})
    assert result.status == "READY"
    assert result.all_required_quantities_sufficient
    assert result.issues == []


def test_have_without_amount_requires_confirmation_not_an_invented_shortfall():
    result = build_recipe_readiness(summary(chicken(None)), {"chicken": food()}, {"chicken"})
    assert result.status == "CHECK_QUANTITIES"
    assert result.message_en == "All required ingredients are available. Please confirm quantities."
    assert result.issues[0].reason == "AMOUNT_UNKNOWN"
    assert result.issues[0].shortfall_quantity_kg is None


def test_noncomparable_substitute_uses_actual_name_but_never_original_cut_grams():
    # Even a contradictory known quantity must not cross the conversion boundary.
    result = build_recipe_readiness(summary(chicken(900)), {"chicken": food("SF006", "Whole chicken")},
                                    {"chicken"}, frozenset({"chicken"}))
    assert result.status == "CHECK_QUANTITIES"
    issue = result.issues[0]
    assert issue.recipe_food_id == "chicken"
    assert issue.food.canonical_food_id == "SF006"
    assert issue.reason == "SUBSTITUTION_CONVERSION_UNAVAILABLE"
    assert issue.required_quantity_kg is issue.available_quantity_kg is issue.shortfall_quantity_kg is None
    assert issue.message_en.startswith("Whole chicken:")


def test_mixed_shortfalls_and_unknowns_are_both_returned_in_recipe_order():
    quantities = summary(chicken(), Ingredient("rice", True, 160, (PantryQuantity("UNKNOWN", None),)))
    result = build_recipe_readiness(quantities, {"chicken": food(), "rice": food("rice", "Rice")}, {"chicken", "rice"})
    assert quantities.quantity_status == "UNKNOWN"  # Existing API field remains unchanged.
    assert result.status == "INSUFFICIENT_QUANTITY"
    assert [issue.status for issue in result.issues] == ["INSUFFICIENT", "UNKNOWN"]


def test_missing_ingredient_remains_distinct_from_an_unmeasured_owned_ingredient():
    quantities = summary(chicken(None))
    result = build_recipe_readiness(quantities, {"chicken": food()}, set())
    assert result.status == "MISSING_INGREDIENTS"
    assert not result.all_required_ingredients_available
    assert result.issues[0].status == "MISSING"
    assert result.issues[0].shortfall_quantity_kg is None


@pytest.mark.parametrize("base", [None, 0])
def test_unreviewed_or_zero_recipe_amount_never_reports_ready(base):
    quantities = summary(Ingredient("chicken", True, None, (PantryQuantity("KNOWN", 800),)))
    quantities = replace(quantities, ingredients=(replace(quantities.ingredients[0], required_quantity_g=base),))
    result = build_recipe_readiness(quantities, {"chicken": food()}, {"chicken"})
    assert result.status == "CHECK_QUANTITIES"
    assert result.issues[0].status == "NOT_TRACKED"


def test_partial_known_stock_does_not_claim_a_definite_shortfall():
    quantities = summary(Ingredient("chicken", True, 500,
                                   (PantryQuantity("KNOWN", 100), PantryQuantity("UNKNOWN", None))))
    result = build_recipe_readiness(quantities, {"chicken": food()}, {"chicken"})
    assert result.status == "CHECK_QUANTITIES"
    assert result.issues[0].available_quantity_kg == 0.1
    assert result.issues[0].shortfall_quantity_kg is None


def test_household_scaling_and_read_only_determinism():
    quantities = summary(chicken(100), adults=2, children=2)
    before = deepcopy(quantities)
    result = build_recipe_readiness(quantities, {"chicken": food()}, {"chicken"})
    assert result.issues[0].required_quantity_kg == 0.75
    assert result.issues[0].shortfall_quantity_kg == 0.65
    assert quantities == before
    assert result == build_recipe_readiness(quantities, {"chicken": food()}, {"chicken"})


@pytest.mark.parametrize("required_g,available_g,label", [(500, 499.9, "1 g"), (2000, 800, "1.2 kg")])
def test_copy_is_readable_without_zeroing_small_shortfalls(required_g, available_g, label):
    quantities = summary(Ingredient("chicken", True, required_g, (PantryQuantity("KNOWN", available_g),)))
    result = build_recipe_readiness(quantities, {"chicken": food()}, {"chicken"})
    assert result.issues[0].message_en == f"Chicken breast: need {label} more."
    assert result.issues[0].shortfall_quantity_kg == (required_g - available_g) / 1000


def test_empty_or_incomplete_quantity_data_never_claims_ready():
    quantities = summary()
    assert build_recipe_readiness(quantities, {}, set()).status == "CHECK_QUANTITIES"
    result = build_recipe_readiness(quantities, {"chicken": food()}, {"chicken"})
    assert result.status == "CHECK_QUANTITIES"
    assert result.issues[0].reason == "RECIPE_AMOUNT_UNREVIEWED"


def test_legacy_schema_callers_can_omit_readiness():
    response = RecipeSuggestionResponse(recipe_id="test", name="Test", description=None,
        available_ingredients=[], missing_required_ingredients=[], required_match_count=0,
        required_ingredient_count=0, ingredient_count=0)
    assert response.readiness is None
