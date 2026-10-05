# Curated, deterministic substitution candidates for Epic 5 recipe cooking.
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RecipeSubstitutionRule:
    rule_id: str
    original_food_id: str
    substitute_food_id: str
    reason: str


@dataclass(frozen=True)
class RecipeSubstitutionSuggestion:
    rule_id: str
    original_food_id: str
    substitute_food_id: str
    reason: str


# These are deliberately narrow, reviewed same-role swaps. A later AI layer
# may rank or explain these candidates, but it must not create new food pairs.
APPROVED_RECIPE_SUBSTITUTION_RULES = (
    RecipeSubstitutionRule(
        rule_id="water-spinach-to-spinach",
        original_food_id="SF074",
        substitute_food_id="SF062",
        reason="Spinach can replace water spinach in a quick stir-fry.",
    ),
    RecipeSubstitutionRule(
        rule_id="whole-chicken-to-chicken-breast",
        original_food_id="SF006",
        substitute_food_id="SF017",
        reason="Chicken breast is a direct chicken alternative for this stir-fry.",
    ),
)


def suggest_recipe_substitutions(
    required_quantity_status_by_food: dict[str, str],
    pantry_food_ids: set[str],
    excluded_food_ids: set[str],
) -> tuple[RecipeSubstitutionSuggestion, ...]:
    suggestions = []
    for rule in APPROVED_RECIPE_SUBSTITUTION_RULES:
        original_status = required_quantity_status_by_food.get(rule.original_food_id)
        original_is_missing = rule.original_food_id not in pantry_food_ids
        original_is_insufficient = original_status == "INSUFFICIENT"
        substitute_is_allowed = rule.substitute_food_id not in excluded_food_ids
        if (original_is_missing or original_is_insufficient) and (
            rule.substitute_food_id in pantry_food_ids and substitute_is_allowed
        ):
            suggestions.append(
                RecipeSubstitutionSuggestion(
                    rule_id=rule.rule_id,
                    original_food_id=rule.original_food_id,
                    substitute_food_id=rule.substitute_food_id,
                    reason=rule.reason,
                )
            )
    return tuple(suggestions)
