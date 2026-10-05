# Epic 5 deterministic recipe substitution contract.
from services.api.app.services.recipe_substitutions import suggest_recipe_substitutions


def test_recipe_substitution_uses_only_an_approved_available_same_role_food():
    # Given water spinach is missing but the household has spinach.
    suggestions = suggest_recipe_substitutions(
        required_quantity_status_by_food={"SF074": "UNKNOWN"},
        pantry_food_ids={"SF062"},
        excluded_food_ids=set(),
    )

    # When deterministic substitution candidates are selected.
    # Then the approved spinach swap is suggested with its stored rationale.
    assert len(suggestions) == 1
    assert suggestions[0].rule_id == "water-spinach-to-spinach"
    assert suggestions[0].original_food_id == "SF074"
    assert suggestions[0].substitute_food_id == "SF062"


def test_recipe_substitution_does_not_replace_an_unmeasured_ingredient_already_in_pantry():
    # Given water spinach exists but its amount is not measured.
    suggestions = suggest_recipe_substitutions(
        required_quantity_status_by_food={"SF074": "UNKNOWN"},
        pantry_food_ids={"SF074", "SF062"},
        excluded_food_ids=set(),
    )

    # When substitutions are evaluated.
    # Then the system does not assume a swap is needed.
    assert suggestions == ()


def test_recipe_substitution_never_offers_an_excluded_candidate():
    # Given spinach is available but excluded by the household's restrictions.
    suggestions = suggest_recipe_substitutions(
        required_quantity_status_by_food={"SF074": "UNKNOWN"},
        pantry_food_ids={"SF062"},
        excluded_food_ids={"SF062"},
    )

    # When substitutions are evaluated.
    # Then no unsafe candidate is returned.
    assert suggestions == ()


def test_recipe_substitution_does_not_create_unapproved_food_pairs():
    # Given an unrelated pantry food is available.
    suggestions = suggest_recipe_substitutions(
        required_quantity_status_by_food={"SF074": "UNKNOWN"},
        pantry_food_ids={"SF110"},
        excluded_food_ids=set(),
    )

    # When substitutions are evaluated.
    # Then the system does not invent a rice-for-vegetable replacement.
    assert suggestions == ()
