"""Pure matching contract for code-less Q2 recipe restrictions."""

from services.api.app.services.recipe_restrictions import (
    food_matches_gluten_keywords,
    food_matches_restriction_text,
    recipe_matches_name_restrictions,
)


def test_gluten_keyword_matches_wheat_not_glutinous_rice():
    assert food_matches_gluten_keywords("Whole Wheat Flour")
    assert food_matches_gluten_keywords("Noodles")
    assert not food_matches_gluten_keywords("Glutinous rice")
    assert not food_matches_gluten_keywords("White rice")


def test_other_text_uses_same_three_letter_tokens_as_plan():
    assert food_matches_restriction_text("Fresh Squid", "seafood, squid")
    assert food_matches_restriction_text("Peanut Butter", "no peanuts")
    assert food_matches_restriction_text("Chicken egg", "avoid eggs")
    assert not food_matches_restriction_text("Squid", "no a")
    assert not food_matches_restriction_text("Egg", "seafood, squid")


def test_any_optional_ingredient_blocks_list_and_detail():
    # The caller passes every ingredient, not only required ones.
    names = ["Rice", "Egg", "Wheat flour"]
    assert recipe_matches_name_restrictions(names, gluten_free=True)
    assert recipe_matches_name_restrictions(names, custom_restriction="wheat")
    assert not recipe_matches_name_restrictions(names, custom_restriction="seafood")
