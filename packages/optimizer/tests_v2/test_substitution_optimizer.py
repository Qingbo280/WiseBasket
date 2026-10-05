# Controlled substitution decisions using reviewed rules and synthetic data.
from decimal import Decimal as D

from packages.optimizer.wisebasket_optimizer.v2.calculations import (
    Household,
    PantryStock,
    PurchaseOption,
)
from packages.optimizer.wisebasket_optimizer.v2.domain import (
    CookingStep,
    IngredientRole,
    MealType,
    QuantityBasis,
    RecipeIngredient,
    ReviewStatus,
    ReviewedRecipe,
    SubstitutionRule,
)
from packages.optimizer.wisebasket_optimizer.v2.optimizer import optimize_recipe_plan


def beef_meal(cap=3):
    ingredients = (
        RecipeIngredient("beef", D("0.100"), IngredientRole.MAIN_PROTEIN),
        RecipeIngredient("rice", D("0.100"), IngredientRole.STAPLE),
        RecipeIngredient("carrot", D("0.100"), IngredientRole.MAIN_VEGETABLE),
        RecipeIngredient("oil", D("0.010"), IngredientRole.COOKING_ESSENTIAL),
    )
    return ReviewedRecipe(
        "beef-rice", "Beef Rice", MealType.COMPLETE_MEAL, D("1"), 1,
        ReviewStatus.APPROVED, True, QuantityBasis.RAW_EDIBLE_KG,
        ingredients,
        (CookingStep(1, "Cook.", frozenset(i.food_id for i in ingredients)),),
        cap,
    )


def chicken_rule(**changes):
    values = dict(
        rule_id="beef-to-chicken",
        original_food_id="beef",
        substitute_food_id="chicken",
        quantity_ratio=D("1.2"),
        role=IngredientRole.MAIN_PROTEIN,
        recipe_ids=frozenset({"beef-rice"}),
        review_status=ReviewStatus.APPROVED,
        version=1,
    )
    values.update(changes)
    return SubstitutionRule(**values)


def common_options():
    return (
        PurchaseOption("chicken", D("0.010"), D("10")),
        PurchaseOption("rice", D("0.100"), D("1")),
        PurchaseOption("carrot", D("0.100"), D("1")),
        PurchaseOption("oil", D("0.010"), D("1")),
    )


def test_approved_substitute_can_make_an_unpriced_original_recipe_feasible():
    result = optimize_recipe_plan(
        Household(1, 0), (beef_meal(),), (), common_options(), D("10"), 1,
        substitution_rules=(chicken_rule(),),
    )
    assert result.status == "FULL_PLAN"
    assert result.occurrences == {"beef-rice": 1}
    assert len(result.substitutions) == 1
    applied = result.substitutions[0]
    assert applied.rule_id == "beef-to-chicken"
    assert applied.occurrences == 1
    assert applied.original_quantity_kg == D("0.100")
    assert applied.substitute_quantity_kg == D("0.1200")
    assert "chicken" in result.calculation.items
    assert "beef" not in result.calculation.items


def test_original_and_substitute_occurrences_share_the_recipe_cap():
    pantry = (PantryStock("beef", D("0.100")),)
    result = optimize_recipe_plan(
        Household(1, 0), (beef_meal(cap=2),), pantry, common_options(), D("10"), 2,
        substitution_rules=(chicken_rule(),),
    )
    assert result.occurrences == {"beef-rice": 2}
    assert result.substitutions[0].occurrences == 1
    assert result.calculation.items["beef"].pantry_used_kg == D("0.100")
    assert result.calculation.items["chicken"].demand_kg == D("0.1200")


def test_draft_reverse_scoped_and_excluded_substitutes_fail_closed():
    cases = (
        (chicken_rule(review_status=ReviewStatus.DRAFT), set(), "RULE_NOT_APPROVED"),
        (SubstitutionRule("reverse", "chicken", "beef", D("1"),
            IngredientRole.MAIN_PROTEIN, review_status=ReviewStatus.APPROVED),
            set(), "ORIGINAL_NOT_IN_RECIPE"),
        (chicken_rule(recipe_ids=frozenset({"another-recipe"})), set(), "RULE_NOT_FOR_RECIPE"),
        (chicken_rule(), {"chicken"}, "SUBSTITUTE_EXCLUDED"),
    )
    for rule, exclusions, reason in cases:
        result = optimize_recipe_plan(
            Household(1, 0), (beef_meal(),), (), common_options(), D("10"), 1,
            excluded_food_ids=exclusions,
            substitution_rules=(rule,),
        )
        assert result.meal_count == 0
        assert result.substitutions == ()
        assert reason in result.rejected_substitutions[("beef-rice", rule.rule_id)].reasons


def test_substitution_result_is_deterministic():
    inputs = dict(
        household=Household(1, 0), recipes=(beef_meal(),), pantry=(),
        purchase_options=common_options(), budget_rm=D("10"), target_meals=2,
        substitution_rules=(chicken_rule(),),
    )
    assert optimize_recipe_plan(**inputs) == optimize_recipe_plan(**inputs)


def test_original_is_kept_when_substitution_does_not_improve_the_plan():
    equal_cost_rule = chicken_rule(quantity_ratio=D("1"))
    equal_options = (
        PurchaseOption("beef", D("0.010"), D("12")),
        PurchaseOption("chicken", D("0.010"), D("12")),
        *common_options()[1:],
    )
    result = optimize_recipe_plan(
        Household(1, 0), (beef_meal(),), (), equal_options, D("10"), 1,
        substitution_rules=(equal_cost_rule,),
    )
    assert result.occurrences == {"beef-rice": 1}
    assert result.substitutions == ()
    assert "beef" in result.calculation.items
