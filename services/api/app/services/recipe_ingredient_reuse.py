"""Reviewed, directed pantry alternatives for ingredient slots in 35 recipes.

Shopping-diversity families are intentionally not used here: sharing a food
family does not prove cooking equivalence or comparable purchased mass.
"""

from __future__ import annotations

from dataclasses import dataclass

from .recipe_quantities import PantryQuantity


CHICKEN_RECIPES = frozenset({
    "malay-chicken-soup", "malaysian-chicken-curry-with-rice",
    "soy-sauce-chicken-with-rice", "tomato-chicken-with-rice",
    "turmeric-chicken-with-rice",
})
PRAWN_RECIPES = frozenset({
    "bihun-goreng", "garlic-prawn-stir-fry", "tofu-prawn-stir-fry",
})
COCONUT_MILK_RECIPES = frozenset({
    "egg-potato-curry-with-rice", "malaysian-chicken-curry-with-rice",
})
SERVED_RICE_RECIPES = frozenset({
    "dhal-curry-with-rice", "egg-potato-curry-with-rice",
    "garlic-prawn-stir-fry", "malay-chicken-soup",
    "malaysian-chicken-curry-with-rice", "onion-omelette",
    "potato-onion-stir-fry", "red-tilapia-soy-with-rice",
    "sambal-eggplant-with-rice", "sardine-sambal-with-rice",
    "soy-sauce-chicken-with-rice", "soy-sauce-eggs-with-rice",
    "soy-sauce-mackerel-with-rice", "squid-soy-stir-fry",
    "tofu-cabbage-stir-fry", "tofu-prawn-stir-fry",
    "tomato-chicken-with-rice", "tomato-egg-stir-fry",
    "tomato-tofu-with-rice", "turmeric-chicken-with-rice",
})

CHICKEN_CUTS = ("SF006", "SF013", "SF014", "SF015", "SF016", "SF017")


@dataclass(frozen=True)
class ReusedIngredient:
    required_food_id: str
    pantry_food_id: str
    # Whole/bone-in/boneless chicken and coconut milks need a reviewed edible
    # yield or concentration conversion before claiming quantity sufficiency.
    purchase_mass_comparable: bool


def _approved_alternatives(recipe_id: str, required_food_id: str) -> tuple[tuple[str, ...], bool]:
    if recipe_id in CHICKEN_RECIPES and required_food_id in ("SF006", "SF014"):
        return CHICKEN_CUTS, False
    if recipe_id in PRAWN_RECIPES and required_food_id == "SF022":
        return ("SF022", "SF036"), True
    if recipe_id in COCONUT_MILK_RECIPES and required_food_id == "SF102":
        return ("SF102", "SF103"), False
    if recipe_id in SERVED_RICE_RECIPES and required_food_id == "SF110":
        return ("SF110", "SF113"), True
    return (), False


def resolve_reused_ingredients(
    recipe_id: str,
    required_food_ids: tuple[str, ...],
    pantry_food_ids: set[str],
    excluded_food_ids: set[str] | frozenset[str] = frozenset(),
    *,
    measured_pantry_food_ids: frozenset[str] = frozenset(),
) -> dict[str, ReusedIngredient]:
    """Pick one owned SKU per slot, preferring a measured compatible food.

    The result is keyed by the recipe's original ingredient ID, so a pantry
    with multiple equivalent SKUs can never inflate ingredient counts. A
    measured non-comparable substitute still has UNKNOWN usable quantity.
    """
    available = pantry_food_ids - excluded_food_ids
    measured = measured_pantry_food_ids & available
    matches: dict[str, ReusedIngredient] = {}
    for food_id in required_food_ids:
        if food_id in measured:
            continue
        alternatives, comparable = _approved_alternatives(recipe_id, food_id)
        substitute = next((candidate for candidate in alternatives
                           if candidate != food_id and candidate in measured), None)
        if substitute is None and food_id in available:
            continue
        if substitute is None:
            substitute = next((candidate for candidate in alternatives
                               if candidate != food_id and candidate in available), None)
        if substitute is not None:
            matches[food_id] = ReusedIngredient(food_id, substitute, comparable)
    return matches


def reused_pantry_quantities(
    reused: ReusedIngredient,
    pantry_quantities_by_food: dict[str, list[PantryQuantity]],
) -> tuple[PantryQuantity, ...]:
    """Never compare non-equivalent raw kilograms as recipe sufficiency."""
    if not reused.purchase_mass_comparable:
        return (PantryQuantity(quantity_status="UNKNOWN", quantity_g=None),)
    return tuple(pantry_quantities_by_food.get(reused.pantry_food_id, ()))
