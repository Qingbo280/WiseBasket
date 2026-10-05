"""Name-based recipe exclusions matching the mobile planner's Q2 rules.

The authoritative hard-exclusion codes are resolved from the database.  These
two active Q2 choices have no database code, so they use the same deliberately
limited canonical-name matching as planQuestionThreeContent.ts and
planProposal.ts.  A recipe is rejected when *any* ingredient matches, whether
required or optional; otherwise the detail route could disclose a forbidden
ingredient after the list route filtered it.
"""
from __future__ import annotations

import re


GLUTEN_NAME_KEYWORDS = (
    "wheat", "flour", "bread", "noodle", "pasta", "oats",
    "spaghetti", "barley", "rye", "semolina", "gluten",
)


def food_matches_gluten_keywords(name: str) -> bool:
    normalized = name.strip().lower()
    return bool(normalized) and any(keyword in normalized for keyword in GLUTEN_NAME_KEYWORDS)


def food_matches_restriction_text(name: str, restriction_text: str) -> bool:
    normalized = name.strip().lower()
    if not normalized:
        return False
    tokens = (token for token in re.split(r"[^a-z]+", restriction_text.lower()) if len(token) >= 3)
    return any(
        token in normalized
        or (len(token) >= 4 and token.endswith("s") and not token.endswith("ss")
            and token[:-1] in normalized)
        for token in tokens
    )


def recipe_matches_name_restrictions(
    ingredient_names: list[str] | tuple[str, ...],
    *,
    gluten_free: bool = False,
    custom_restriction: str = "",
) -> bool:
    """True means the recipe must be hidden by both list and detail routes."""
    return any(
        (gluten_free and food_matches_gluten_keywords(name))
        or (custom_restriction and food_matches_restriction_text(name, custom_restriction))
        for name in ingredient_names
    )
