"""Stable, quantity-aware Meal Ideas ordering and protein diversity."""
from __future__ import annotations

from collections import Counter
from fractions import Fraction


MAIN_ROLES = frozenset({
    "MAIN_PROTEIN", "STAPLE", "MAIN_VEGETABLE", "SUPPORTING_VEGETABLE",
})


def main_required_food_ids(rows) -> set[str]:
    """Required ingredients that count as a dish's main ingredients.

    A reviewed MAIN_ROLES role wins; rows with a NULL role fall back to the
    grams heuristic (required amounts >= 25% of the largest required amount),
    so small amounts of garlic/sauce never count. COOKING_ESSENTIAL (oil) and
    SEASONING never count, which keeps an oil-only pantry from inflating
    recipe matches.
    """
    required = [ingredient for ingredient, _ in rows if ingredient.required]
    largest_required_g = max(
        (float(getattr(ingredient, "base_quantity_g", None) or 0) for ingredient in required),
        default=0,
    )
    return {
        ingredient.canonical_food_id for ingredient in required
        if getattr(ingredient, "ingredient_role", None) in MAIN_ROLES
        or (
            getattr(ingredient, "ingredient_role", None) is None
            and (
                largest_required_g == 0
                or getattr(ingredient, "base_quantity_g", None) is None
                or float(ingredient.base_quantity_g) >= largest_required_g * 0.25
            )
        )
    }


def _ratio(numerator: int, denominator: int) -> Fraction:
    return Fraction(numerator, max(denominator, 1))


def rank_recipe_suggestions(
    entries: list[tuple[object, tuple, object]],
    limit: int | None = None,
    *,
    pantry_food_ids: frozenset[str] = frozenset(),
    planned_food_ids: frozenset[str] = frozenset(),
) -> list[object]:
    """Entries are (suggestion, ingredient rows, quantity summary).

    Every eligible recipe is returned (no total cap by default). Owned main
    ingredients lead the list even when their amounts are unknown. Unknown
    amounts never count as sufficient. Optional ingredients are excluded
    from every sufficiency denominator. Planned but unpurchased foods are
    only a secondary ordering hint.  They never enter pantry matching or
    quantity sufficiency.

    Protein-family diversity is a demotion, never a drop: a family
    contributes its first three dishes (five for reviewed substitutes once
    three exact SKUs are listed) at their natural position; overflow members
    are appended at the tail of THEIR OWN three-tier tier, so the pantry ->
    planned -> rest contract is never broken by family demotion.
    """
    def sort_key(entry):
        suggestion, rows, summary = entry
        required = [item for item in summary.ingredients if item.required]
        main_food_ids = main_required_food_ids(rows)
        main_pairs = [
            (item, ingredient) for item, (ingredient, _) in zip(summary.ingredients, rows)
            if item.required and ingredient.canonical_food_id in main_food_ids
        ]
        main_sufficient = sum(item.is_quantity_sufficient is True for item, _ in main_pairs)
        sufficient = sum(item.is_quantity_sufficient is True for item in required)
        matched_alternatives = getattr(suggestion, "matched_alternatives", {})
        main_present = sum(
            ingredient.canonical_food_id in pantry_food_ids
            or ingredient.canonical_food_id in matched_alternatives
            for _, ingredient in main_pairs
        )
        missing = suggestion.required_ingredient_count - suggestion.required_match_count
        planned_required = {
            ingredient.canonical_food_id for ingredient, _ in rows
            if ingredient.required and ingredient.canonical_food_id in planned_food_ids
        }
        planned_main = sum(ingredient.canonical_food_id in planned_required for _, ingredient in main_pairs)
        return (
            # Three-tier visibility contract (all eligible recipes listed):
            #   tier 1: pantry owns a main ingredient (What you have)
            #   tier 2: no pantry main, but the week plan (planned_food_ids)
            #           covers a required ingredient (Shopping list)
            #   tier 3: everything else
            # The first two keys pin the tiers strictly — the planned tier
            # only applies when the pantry owns no main, so a real pantry
            # match always beats a plan hint. All remaining keys only order
            # WITHIN a tier.
            # Pantry-owned mains take priority over a known-sufficient pantry
            # seasoning. The match ratio counts main-role ingredients only:
            # oil/salt are COOKING_ESSENTIAL/SEASONING, so a pantry holding
            # only cooking oil must not float every stir-fry to the top.
            # Recipes with no main-role required ingredient (all-seasoning)
            # fall back to the raw required ratio as a defensive default.
            -(main_present > 0),
            -(main_present == 0 and len(planned_required) > 0),
            -_ratio(main_present, len(main_pairs)) if main_pairs else -_ratio(
                suggestion.required_match_count, suggestion.required_ingredient_count),
            -_ratio(sufficient, len(required)),
            -_ratio(main_present, len(main_pairs)),
            -main_present,
            -_ratio(main_sufficient, len(main_pairs)),
            -main_sufficient,
            -_ratio(planned_main, len(main_pairs)),
            -_ratio(len(planned_required), len(required)),
            missing,
            -(suggestion.semantic_score or 0.0),
            suggestion.name.casefold(),
            suggestion.recipe_id,
        )

    accepted: list[tuple[tuple, object]] = []
    deferred: list[tuple[tuple, int, object]] = []
    family_counts: Counter[str] = Counter()
    exact_family_counts: Counter[str] = Counter()
    for sequence, entry in enumerate(sorted(entries, key=sort_key)):
        suggestion, rows, _ = entry
        matched_alternative_ids = set(getattr(suggestion, "matched_alternatives", {}))
        families = {
            _protein_family(ingredient.canonical_food_id, food)
            for ingredient, food in rows
            if ingredient.required and (
                getattr(ingredient, "ingredient_role", None) == "MAIN_PROTEIN"
                or (getattr(ingredient, "ingredient_role", None) is None and _known_protein_family(food) is not None)
            )
        }
        substituted_families = {
            _protein_family(ingredient.canonical_food_id, food)
            for ingredient, food in rows
            if ingredient.required and ingredient.canonical_food_id in matched_alternative_ids
            and (
                getattr(ingredient, "ingredient_role", None) == "MAIN_PROTEIN"
                or (getattr(ingredient, "ingredient_role", None) is None and _known_protein_family(food) is not None)
            )
        }
        # Three exact-SKU dishes may leave two places for reviewed protein
        # substitutes. Substitutes already represented in the first three do
        # not expand the quota and crowd out other meal ideas. Overflow is
        # demoted to the tail of its own tier, never dropped.
        over_quota = any(family_counts[family] >= (
            5 if family in substituted_families and exact_family_counts[family] >= 3 else 3
        )
               for family in families)
        if over_quota:
            deferred.append((sort_key(entry)[:2], sequence, suggestion))
            continue
        accepted.append((sort_key(entry)[:2], suggestion))
        family_counts.update(families)
        exact_family_counts.update(families - substituted_families)
    # Reassemble tier by tier: accepted members first, then the demoted
    # family overflow of the same tier in their original ranking order.
    merged: list[object] = []
    tiers = sorted({tier for tier, _ in accepted} | {tier for tier, _, _ in deferred})
    for tier in tiers:
        merged.extend(suggestion for entry_tier, suggestion in accepted if entry_tier == tier)
        merged.extend(
            suggestion
            for entry_tier, _, suggestion in sorted(
                (item for item in deferred if item[0] == tier), key=lambda item: item[1]
            )
        )
    return merged[:limit] if limit else merged


def _known_protein_family(food: object) -> str | None:
    # The reviewed ingredient role identifies the protein; its catalogue name
    # supplies a family until the catalogue has an explicit family column.
    names = f"{food.canonical_name} {food.canonical_name_ms or ''}".casefold()
    keywords = {
        # Catalogue SF018 is "chicken egg" / "telur ayam". The more
        # specific egg family must win before the animal-name match.
        "egg": ("egg", "telur", "蛋"),
        "chicken": ("chicken", "ayam", "鸡"),
        "fish": ("fish", "ikan", "鱼"),
        "beef": ("beef", "daging lembu", "牛"),
        "pork": ("pork", "babi", "猪"),
        "tofu": ("tofu", "tauhu", "豆腐"),
        "tempeh": ("tempeh", "tempe", "天贝"),
        "legume": ("dhal", "lentil", "kacang", "豆"),
    }
    for family, words in keywords.items():
        if any(word in names for word in words):
            return family
    return None


def _protein_family(food_id: str, food: object) -> str:
    return _known_protein_family(food) or food_id
