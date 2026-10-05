# Controlled recipe-governance tests: no database and no network.
from decimal import Decimal as D

import pytest

from packages.optimizer.wisebasket_optimizer.v2.domain import (
    CookingStep,
    IngredientRole,
    MealType,
    QuantityBasis,
    RecipeIngredient,
    ReviewStatus,
    ReviewedRecipe,
    SubstitutionRule,
    assess_recipe,
    assess_substitution,
)


def complete_recipe(**overrides):
    values = dict(
        recipe_id="turmeric-chicken-rice",
        name="Turmeric Chicken with Rice",
        meal_type=MealType.COMPLETE_MEAL,
        base_servings=D("2"),
        version=1,
        review_status=ReviewStatus.APPROVED,
        optimizer_eligible=True,
        quantity_basis=QuantityBasis.RAW_EDIBLE_KG,
        ingredients=(
            RecipeIngredient("chicken", D("0.300"), IngredientRole.MAIN_PROTEIN),
            RecipeIngredient("rice", D("0.160"), IngredientRole.STAPLE),
            RecipeIngredient("long-beans", D("0.100"), IngredientRole.MAIN_VEGETABLE),
            RecipeIngredient("oil", D("0.010"), IngredientRole.COOKING_ESSENTIAL),
            RecipeIngredient("garlic", D("0.005"), IngredientRole.SEASONING, required=False),
        ),
        steps=(
            CookingStep(1, "Cook the rice.", frozenset({"rice"})),
            CookingStep(2, "Cook chicken and long beans in oil.", frozenset({"chicken", "long-beans", "oil"})),
            CookingStep(3, "Add garlic if desired and serve.", frozenset({"garlic"})),
        ),
        max_weekly_occurrences=3,
    )
    values.update(overrides)
    return ReviewedRecipe(**values)


def test_approved_complete_meal_is_countable():
    result = assess_recipe(complete_recipe())
    assert result.optimizer_eligible
    assert result.counts_as_meal
    assert result.reasons == ()


@pytest.mark.parametrize(("changes", "reason"), [
    ({"review_status": ReviewStatus.DRAFT}, "NOT_APPROVED"),
    ({"optimizer_eligible": False}, "OPTIMIZER_DISABLED"),
    ({"meal_type": MealType.SIDE}, "NOT_COMPLETE_MEAL"),
    ({"quantity_basis": QuantityBasis.PURCHASE_KG}, "UNSUPPORTED_QUANTITY_BASIS"),
])
def test_governance_failures_prevent_counting(changes, reason):
    result = assess_recipe(complete_recipe(**changes))
    assert not result.optimizer_eligible
    assert not result.counts_as_meal
    assert reason in result.reasons


@pytest.mark.parametrize(("missing_food", "reason"), [
    ("chicken", "MISSING_MAIN_PROTEIN"),
    ("rice", "MISSING_STAPLE"),
    ("long-beans", "MISSING_MAIN_VEGETABLE"),
])
def test_complete_meal_requires_three_core_roles(missing_food, reason):
    base = complete_recipe()
    recipe = complete_recipe(ingredients=tuple(i for i in base.ingredients if i.food_id != missing_food),
        steps=tuple(CookingStep(s.step_number, s.instruction, s.food_ids - {missing_food}) for s in base.steps))
    result = assess_recipe(recipe)
    assert reason in result.reasons
    assert not result.counts_as_meal


def test_cooking_essential_cannot_be_optional():
    base = complete_recipe()
    ingredients = tuple(
        RecipeIngredient(i.food_id, i.quantity_kg, i.role, False) if i.food_id == "oil" else i
        for i in base.ingredients
    )
    result = assess_recipe(complete_recipe(ingredients=ingredients))
    assert "OPTIONAL_COOKING_ESSENTIAL" in result.reasons


def test_every_required_ingredient_must_appear_in_structured_steps():
    base = complete_recipe()
    steps = tuple(CookingStep(s.step_number, s.instruction, s.food_ids - {"oil"}) for s in base.steps)
    result = assess_recipe(complete_recipe(steps=steps))
    assert result.unused_required_food_ids == ("oil",)
    assert "REQUIRED_INGREDIENT_NOT_IN_STEPS" in result.reasons


def test_excluded_food_makes_recipe_ineligible():
    result = assess_recipe(complete_recipe(), excluded_food_ids={"chicken"})
    assert result.excluded_food_ids == ("chicken",)
    assert "CONTAINS_EXCLUDED_FOOD" in result.reasons


def test_steps_must_be_contiguous_and_only_reference_recipe_foods():
    base = complete_recipe()
    bad = complete_recipe(steps=(
        CookingStep(1, "Cook.", frozenset({"rice"})),
        CookingStep(3, "Invent.", frozenset({"not-an-ingredient"})),
    ))
    result = assess_recipe(bad)
    assert "NONCONTIGUOUS_STEPS" in result.reasons
    assert "STEP_REFERENCES_UNKNOWN_FOOD" in result.reasons


def test_directional_reviewed_substitution_is_accepted_for_matching_recipe_role():
    rule = SubstitutionRule("chicken-to-tofu", "chicken", "tofu", D("0.8"),
        IngredientRole.MAIN_PROTEIN, recipe_ids=frozenset({"turmeric-chicken-rice"}),
        review_status=ReviewStatus.APPROVED, version=1)
    result = assess_substitution(rule, complete_recipe())
    assert result.allowed
    assert result.substitute_quantity(D("0.300")) == D("0.2400")


@pytest.mark.parametrize(("rule", "reason"), [
    (SubstitutionRule("reverse", "tofu", "chicken", D("1"), IngredientRole.MAIN_PROTEIN,
        review_status=ReviewStatus.APPROVED), "ORIGINAL_NOT_IN_RECIPE"),
    (SubstitutionRule("wrong-role", "chicken", "spinach", D("1"), IngredientRole.MAIN_VEGETABLE,
        review_status=ReviewStatus.APPROVED), "ROLE_MISMATCH"),
    (SubstitutionRule("draft", "chicken", "tofu", D("1"), IngredientRole.MAIN_PROTEIN), "RULE_NOT_APPROVED"),
])
def test_substitutions_fail_closed(rule, reason):
    result = assess_substitution(rule, complete_recipe())
    assert not result.allowed
    assert reason in result.reasons


def test_excluded_substitute_and_wrong_recipe_scope_are_rejected():
    rule = SubstitutionRule("chicken-to-tofu", "chicken", "tofu", D("1"),
        IngredientRole.MAIN_PROTEIN, recipe_ids=frozenset({"another-recipe"}),
        review_status=ReviewStatus.APPROVED)
    result = assess_substitution(rule, complete_recipe(), excluded_food_ids={"tofu"})
    assert result.reasons == ("RULE_NOT_FOR_RECIPE", "SUBSTITUTE_EXCLUDED")


def test_substitute_already_present_in_recipe_is_rejected():
    base = complete_recipe()
    recipe = complete_recipe(ingredients=base.ingredients + (
        RecipeIngredient("tofu", D("0.050"), IngredientRole.SEASONING, required=False),
    ))
    rule = SubstitutionRule(
        "chicken-to-tofu", "chicken", "tofu", D("1"),
        IngredientRole.MAIN_PROTEIN, review_status=ReviewStatus.APPROVED,
    )
    result = assess_substitution(rule, recipe)
    assert result.reasons == ("SUBSTITUTE_ALREADY_IN_RECIPE",)


@pytest.mark.parametrize("factory", [
    lambda: RecipeIngredient("rice", D("0"), IngredientRole.STAPLE),
    lambda: CookingStep(0, "Cook", frozenset()),
    lambda: CookingStep(1, "", frozenset()),
    lambda: complete_recipe(version=0),
    lambda: complete_recipe(max_weekly_occurrences=0),
    lambda: SubstitutionRule("bad", "a", "a", D("1"), IngredientRole.STAPLE),
    lambda: SubstitutionRule("bad", "a", "b", D("0"), IngredientRole.STAPLE),
])
def test_invalid_domain_records_are_rejected(factory):
    with pytest.raises(ValueError):
        factory()
