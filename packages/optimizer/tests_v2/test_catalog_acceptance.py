# Controlled catalogue acceptance tests without database access.
from dataclasses import replace
from decimal import Decimal as D

import pytest

from packages.optimizer.tests_v2.test_optimizer import meal, options
from packages.optimizer.tests_v2.test_substitution_optimizer import chicken_rule
from packages.optimizer.wisebasket_optimizer.v2.calculations import PurchaseOption
from packages.optimizer.wisebasket_optimizer.v2.domain import ReviewStatus
from packages.optimizer.wisebasket_optimizer.v2.nutrition import FoodNutrition
from packages.optimizer.wisebasket_optimizer.v2.safety import FoodSafety
from services.api.app.planner_v2_service import (
    CatalogValidationError,
    PlannerV2Catalog,
    validate_planner_v2_catalog,
)


def valid_catalog():
    return PlannerV2Catalog(
        recipes=(meal("chicken-meal"),),
        purchase_options=options(chicken="10"),
    )


def issues_for(catalog):
    with pytest.raises(CatalogValidationError) as captured:
        validate_planner_v2_catalog(catalog)
    return captured.value.issues


def test_valid_catalogue_passes_without_transformation():
    catalog = valid_catalog()
    assert validate_planner_v2_catalog(catalog) is catalog


def test_empty_catalogue_is_valid_and_left_for_no_eligible_recipe_outcome():
    catalog = PlannerV2Catalog((), ())
    assert validate_planner_v2_catalog(catalog) is catalog


def test_duplicate_catalogue_identities_fail_closed():
    base = valid_catalog()
    nutrition = FoodNutrition("chicken", D("1000"), D("100"), D("10"))
    safety = FoodSafety("chicken", False, False, False)
    rule = replace(
        chicken_rule(recipe_ids=frozenset({"chicken-meal"})),
        rule_id="chicken-to-tofu",
        original_food_id="chicken",
        substitute_food_id="tofu",
    )
    catalog = PlannerV2Catalog(
        recipes=(base.recipes[0], base.recipes[0]),
        purchase_options=(
            base.purchase_options[0],
            base.purchase_options[0],
            *base.purchase_options[1:],
            PurchaseOption("tofu", D("0.1"), D("2")),
        ),
        food_nutrition=(nutrition, nutrition),
        substitution_rules=(rule, rule),
        food_safety=(safety, safety),
    )

    assert issues_for(catalog) == (
        "DUPLICATE_FOOD_NUTRITION_ID:chicken",
        "DUPLICATE_FOOD_SAFETY_ID:chicken",
        "DUPLICATE_PURCHASE_OPTION_ID:rice",
        "DUPLICATE_RECIPE_ID:chicken-meal",
        "DUPLICATE_SUBSTITUTION_RULE_ID:chicken-to-tofu",
    )


def test_noneligible_recipe_is_invalid_provider_data():
    draft = meal("draft", status=ReviewStatus.DRAFT)
    catalog = PlannerV2Catalog((draft,), options(chicken="10"))
    assert issues_for(catalog) == ("RECIPE_NOT_ELIGIBLE:draft:NOT_APPROVED",)


def test_broken_substitution_references_are_reported():
    catalog = valid_catalog()
    unknown_recipe = chicken_rule(recipe_ids=frozenset({"missing-recipe"}))
    unknown_food = replace(
        chicken_rule(recipe_ids=frozenset({"chicken-meal"})),
        rule_id="chicken-to-unknown",
        original_food_id="chicken",
        substitute_food_id="unknown-food",
    )
    broken = replace(
        catalog,
        substitution_rules=(unknown_recipe, unknown_food),
    )

    assert issues_for(broken) == (
        "SUBSTITUTION_REFERENCES_UNKNOWN_FOOD:beef-to-chicken:beef",
        "SUBSTITUTION_REFERENCES_UNKNOWN_FOOD:chicken-to-unknown:unknown-food",
        "SUBSTITUTION_REFERENCES_UNKNOWN_RECIPE:beef-to-chicken:missing-recipe",
    )


def test_missing_optional_metadata_is_disclosed_later_not_rejected_here():
    assert validate_planner_v2_catalog(valid_catalog())


@pytest.mark.parametrize("factory", [
    lambda: PurchaseOption("rice", D("0"), D("1")),
    lambda: PurchaseOption("rice", D("1"), D("0")),
    lambda: PurchaseOption("rice", D("1"), D("1"), D("1.1")),
])
def test_invalid_purchase_records_cannot_enter_the_catalogue(factory):
    with pytest.raises(ValueError):
        factory()
