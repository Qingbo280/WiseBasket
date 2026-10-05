from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_CEILING

from packages.optimizer.wisebasket_optimizer.v2.calculations import PantryStock, PurchaseOption
from packages.optimizer.wisebasket_optimizer.v2.domain import (
    CookingStep, IngredientRole, MealType, QuantityBasis, RecipeIngredient,
    ReviewedRecipe, ReviewStatus,
)


BASELINE_VERSION = "b40-pilot-v1"
ROTATING_VEGETABLE_IDS = ("SF057", "SF072", "SF062", "SF077")  # potato, tomato, spinach, carrot
BASELINE_FOOD_IDS = frozenset({
    "SF006", "SF018", "SF055", "SF057", "SF062", "SF072", "SF077",
    "SF110",
})


@dataclass(frozen=True)
class BaselineScenario:
    scenario_id: str
    name: str
    reference_budget_rm: Decimal
    # Catalog IDs and raw purchase kg, not serving sizes.
    purchase_targets: tuple[tuple[str, Decimal], ...]
    reference_meals: int
    min_meals: int = 3
    max_meals: int = 14


SCENARIOS = (
    BaselineScenario("solo", "One adult", Decimal("100"), (
        ("SF110", Decimal("2")), ("SF006", Decimal("0.5")),
        ("SF018", Decimal("0.58")),
    ), reference_meals=5, max_meals=6),
    BaselineScenario("single-parent", "One adult with children", Decimal("100"), (
        ("SF110", Decimal("2")), ("SF006", Decimal("1")),
        ("SF018", Decimal("0.58")), ("SF055", Decimal("1")),
    ), reference_meals=6),
    BaselineScenario("small-family", "Two adults, up to one child", Decimal("150"), (
        ("SF110", Decimal("2")), ("SF006", Decimal("1")),
        ("SF018", Decimal("0.58")), ("SF055", Decimal("1")),
    ), reference_meals=6),
    BaselineScenario("larger-family", "Two adults with two or three children", Decimal("200"), (
        ("SF110", Decimal("2")), ("SF006", Decimal("1.5")),
        ("SF018", Decimal("1.16")), ("SF055", Decimal("1")),
    ), reference_meals=9),
)


def match_scenario(adults: int, children: int, meals: int) -> BaselineScenario | None:
    if adults < 1 or meals < 3 or meals > 14:
        return None
    if adults == 1 and children == 0:
        scenario = SCENARIOS[0]
    elif adults == 1 and 1 <= children <= 3:
        scenario = SCENARIOS[1]
    elif adults == 2 and 0 <= children <= 1:
        scenario = SCENARIOS[2]
    elif adults == 2 and 2 <= children <= 3:
        scenario = SCENARIOS[3]
    else:
        return None
    return scenario if scenario.min_meals <= meals <= scenario.max_meals else None


def _pilot_meal(recipe_id: str, name: str, protein: str, vegetable: str) -> ReviewedRecipe:
    protein_kg = Decimal("0.15") if protein == "SF006" else Decimal("0.116")
    ingredients = (
        RecipeIngredient(protein, protein_kg, IngredientRole.MAIN_PROTEIN),
        RecipeIngredient("SF110", Decimal("0.16"), IngredientRole.STAPLE),
        RecipeIngredient(vegetable, Decimal("0.20"), IngredientRole.MAIN_VEGETABLE),
    )
    return ReviewedRecipe(
        recipe_id=f"b40-pilot-{recipe_id}", name=name,
        meal_type=MealType.COMPLETE_MEAL, base_servings=Decimal("2"),
        version=1, review_status=ReviewStatus.PILOT, optimizer_eligible=True,
        quantity_basis=QuantityBasis.RAW_EDIBLE_KG,
        ingredients=ingredients,
        steps=(
            CookingStep(1, "Cook rice thoroughly.", frozenset({"SF110"})),
            CookingStep(2, "Cook protein thoroughly and cook the vegetable; serve with rice.",
                        frozenset({protein, vegetable})),
        ),
        max_weekly_occurrences=3,
    )


PILOT_MEALS = (
    _pilot_meal("chicken-cabbage", "Chicken, cabbage and rice", "SF006", "SF055"),
    _pilot_meal("chicken-potato", "Chicken, potato and rice", "SF006", "SF057"),
    _pilot_meal("chicken-tomato", "Chicken, tomato and rice", "SF006", "SF072"),
    _pilot_meal("chicken-carrot", "Chicken, carrot and rice", "SF006", "SF077"),
    _pilot_meal("chicken-spinach", "Chicken, spinach and rice", "SF006", "SF062"),
    _pilot_meal("egg-cabbage", "Egg, cabbage and rice", "SF018", "SF055"),
    _pilot_meal("egg-tomato", "Egg, tomato and rice", "SF018", "SF072"),
    _pilot_meal("egg-potato", "Egg, potato and rice", "SF018", "SF057"),
    _pilot_meal("egg-spinach", "Egg, spinach and rice", "SF018", "SF062"),
    _pilot_meal("egg-carrot", "Egg, carrot and rice", "SF018", "SF077"),
)


@dataclass(frozen=True)
class PreparedBaseline:
    scenario: BaselineScenario
    recipes: tuple[ReviewedRecipe, ...]
    minimum_purchase_kg: dict[str, Decimal]
    minimum_recipe_occurrences_by_food_id: dict[str, int]


def prepare_baseline(
    scenario: BaselineScenario,
    purchase_options: tuple[PurchaseOption, ...],
    safe_food_ids: set[str],
    pantry: tuple[PantryStock, ...],
    budget_rm: Decimal,
    week: int | None,
    meals: int,
    household_servings: Decimal,
) -> PreparedBaseline | None:
    """Use only safe, observed-price foods and leave budget headroom for meals."""
    options = {option.food_id: option for option in purchase_options
               if not option.price_is_estimated}
    usable = set(options) & safe_food_ids
    if "SF110" not in usable or not ({"SF006", "SF018"} & usable):
        return None
    meal_scale = min(Decimal("1"), Decimal(meals) / Decimal(scenario.reference_meals))
    targets = {food_id: quantity * meal_scale for food_id, quantity in scenario.purchase_targets
               if food_id in usable}
    # Rotate one vegetable in every profile, a second for 13-14 meals.
    offset = ((date.today().isocalendar().week if week is None else week) - 1) % len(ROTATING_VEGETABLE_IDS)
    for food_id in ROTATING_VEGETABLE_IDS[offset:] + ROTATING_VEGETABLE_IDS[:offset]:
        if food_id in usable:
            targets[food_id] = Decimal("1")
            break
    target_veg_count = 1 if scenario.scenario_id == "solo" else 2
    if len({food_id for food_id in targets if food_id in {"SF055", *ROTATING_VEGETABLE_IDS}}) < target_veg_count:
        return None
    # The menu uses exactly the vegetables in the basket. A third vegetable
    # gives at least five distinct recipes for a 13-14 meal request.
    if meals >= 13:
        for food_id in ROTATING_VEGETABLE_IDS[offset + 1:] + ROTATING_VEGETABLE_IDS[:offset + 1]:
            if food_id in usable and food_id not in targets:
                targets[food_id] = Decimal("1")
                break
    allowed_veg = set(targets) & {"SF055", *ROTATING_VEGETABLE_IDS}
    recipes = tuple(recipe for recipe in PILOT_MEALS
                    if all(ingredient.food_id in usable for ingredient in recipe.ingredients)
                    and any(ingredient.role is IngredientRole.MAIN_VEGETABLE
                            and ingredient.food_id in allowed_veg for ingredient in recipe.ingredients))
    if sum(recipe.max_weekly_occurrences for recipe in recipes) < meals:
        return None
    stock: dict[str, Decimal] = {}
    for item in pantry:
        if item.status == "CONFIRMED" and item.quantity_kg is not None:
            stock[item.food_id] = stock.get(item.food_id, Decimal("0")) + item.quantity_kg
    minima = {}
    for food_id, target in targets.items():
        needed = max(Decimal("0"), target - stock.get(food_id, Decimal("0")))
        if needed:
            unit = options[food_id].unit_kg
            minima[food_id] = (needed / unit).to_integral_value(rounding=ROUND_CEILING) * unit
    minimum_cost = sum((quantity * options[food_id].price_rm_per_kg
                        for food_id, quantity in minima.items()), Decimal("0"))
    # Keep baseline essentials inside the same 60% week-plan allocation as
    # the general solver; the reserved 20% remains available for add-ons.
    if minimum_cost > budget_rm * Decimal("0.60"):
        return None
    # A rigid equal split can push every vegetable just over a full pack.
    # Keep each vegetable in the menu, but allow the solver to put the extra
    # meals on one of them when that saves a whole purchase pack.
    even_share = meals // len(allowed_veg)
    minimum_occurrences = {}
    for food_id in allowed_veg:
        per_meal_demands = [
            ingredient.quantity_kg * household_servings / recipe.base_servings
            for recipe in recipes for ingredient in recipe.ingredients
            if ingredient.food_id == food_id and ingredient.role is IngredientRole.MAIN_VEGETABLE
        ]
        if not per_meal_demands:
            return None
        per_meal_kg = max(per_meal_demands)
        first_pack_meals = int(options[food_id].unit_kg / per_meal_kg)
        minimum_occurrences[food_id] = max(1, min(even_share, first_pack_meals))
    minimum_occurrences.update({food_id: 1 for food_id in {"SF006", "SF018"} & usable})
    return PreparedBaseline(scenario, recipes, minima, minimum_occurrences)
