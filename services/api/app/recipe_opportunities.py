from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING

from packages.optimizer.wisebasket_optimizer.v2.calculations import (
    Household,
    PantryStock,
    PurchaseOption,
)
from packages.optimizer.wisebasket_optimizer.v2.domain import IngredientRole, ReviewedRecipe
from packages.optimizer.wisebasket_optimizer.v2.oil_equivalence import OIL_FOOD_IDS, OIL_GROUP, oil_group
from services.api.app.schemas import (
    PlannerV2OpportunityIngredientResponse,
    PlannerV2RecipeOpportunityResponse,
)


@dataclass(frozen=True)
class OpportunityIngredient:
    food_id: str
    quantity_kg: Decimal
    purchase_units: int
    purchase_kg: Decimal
    estimated_cost_rm: Decimal
    price_is_estimated: bool
    purchase_priority: int


@dataclass(frozen=True)
class RecipeOpportunity:
    recipe: ReviewedRecipe
    ingredients: tuple[OpportunityIngredient, ...]
    estimated_cost_rm: Decimal


PURCHASE_PRIORITY_BY_ROLE = {
    IngredientRole.MAIN_PROTEIN: 0,
    IngredientRole.STAPLE: 1,
    IngredientRole.MAIN_VEGETABLE: 2,
    IngredientRole.SUPPORTING_VEGETABLE: 2,
    IngredientRole.COOKING_ESSENTIAL: 3,
    IngredientRole.SEASONING: 4,
    IngredientRole.OPTIONAL: 5,
}
OPPORTUNITY_LIMIT = 3

# Closely substitutable raw-protein forms should not be introduced together.
# They remain distinct catalogue SKUs for pricing and explicit user choices,
# but Worth considering treats them as alternatives: someone who already has
# chicken leg does not need whole chicken and thigh suggested alongside it.
INTRODUCTION_FAMILY_BY_FOOD_ID = {
    "SF003": "fresh_lamb",  # mutton/lamb with bone
    "SF004": "fresh_lamb",  # boneless mutton/lamb
    "SF005": "fresh_lamb",  # lamb leg with bone
    "SF006": "fresh_chicken",  # whole chicken
    "SF008": "fresh_pork",  # pork belly (SF009 pork (lean & fat) BLOCKED 2026-09-30: same food)
    "SF010": "fresh_pork",  # pork ribs
    "SF011": "fresh_pork",  # lean pork
    "SF013": "fresh_chicken",  # chicken whole leg
    "SF014": "fresh_chicken",  # chicken thigh
    "SF015": "fresh_chicken",  # chicken drumstick
    "SF016": "fresh_chicken",  # chicken wing
    "SF017": "fresh_chicken",  # chicken breast
    "SF022": "fresh_prawn",  # white prawn
    "SF023": "red_snapper",  # red snapper
    "SF028": "red_snapper",  # red snapper head
    "SF032": "pomfret",  # white pomfret
    "SF035": "tilapia",  # red tilapia
    "SF036": "fresh_prawn",  # tiger prawn
    "SF049": "tilapia",  # black tilapia
    "SF050": "pomfret",  # black pomfret
    "SF075": "capsicum",  # red capsicum
    "SF085": "capsicum",  # green capsicum
    "SF086": "capsicum",  # yellow capsicum
    "SF102": "coconut_milk",  # boxed coconut milk
    "SF103": "coconut_milk",  # fresh coconut milk
    "SF120": "cooking_oil",  # cooking oil (bottle)
    "SF121": "cooking_oil",  # corn oil
    "SF123": "cooking_oil",  # cooking oil (packet)
}


def ingredient_purchase_priority(role: IngredientRole) -> int:
    return PURCHASE_PRIORITY_BY_ROLE[role]


def select_diverse_opportunities(
    ranked: list[RecipeOpportunity],
    available_food_ids: set[str],
) -> tuple[RecipeOpportunity, ...]:
    chosen_by_family: dict[str, set[str]] = {}
    for food_id in available_food_ids:
        family = INTRODUCTION_FAMILY_BY_FOOD_ID.get(food_id)
        if family:
            chosen_by_family.setdefault(family, set()).add(food_id)

    selected = []
    for candidate in ranked:
        oil_top_up_already_suggested = any(
            ingredient.food_id in OIL_FOOD_IDS
            for prior in selected for ingredient in prior.ingredients
        )
        candidate_by_family: dict[str, set[str]] = {}
        for ingredient in candidate.ingredients:
            family = INTRODUCTION_FAMILY_BY_FOOD_ID.get(ingredient.food_id)
            if family:
                candidate_by_family.setdefault(family, set()).add(ingredient.food_id)

        conflicts = any(
            len(food_ids) > 1
            or (
                family in chosen_by_family
                and not food_ids <= chosen_by_family[family]
                # Existing equivalent oil may be insufficient; allow one
                # replenishment suggestion without introducing another oil SKU.
                and (family != "cooking_oil" or oil_top_up_already_suggested)
            )
            for family, food_ids in candidate_by_family.items()
        )
        if conflicts:
            continue

        selected.append(candidate)
        for family, food_ids in candidate_by_family.items():
            chosen_by_family.setdefault(family, set()).update(food_ids)
        if len(selected) >= OPPORTUNITY_LIMIT:
            break
    return tuple(selected)


def confirmed_pantry_quantities(pantry: tuple[PantryStock, ...]) -> dict[str, Decimal]:
    quantities: dict[str, Decimal] = {}
    for item in pantry:
        if item.status == "CONFIRMED":
            quantities[item.food_id] = quantities.get(item.food_id, Decimal("0")) + item.quantity_kg
    return quantities


def recipe_reuse_counts(
    recipes: tuple[ReviewedRecipe, ...],
    available_food_ids: set[str],
    selected_food_ids: set[str],
    excluded_food_ids: frozenset[str],
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for recipe in recipes:
        required_food_ids = {
            ingredient.food_id
            for ingredient in recipe.ingredients
            if ingredient.required
        }
        if not {oil_group(food_id) for food_id in required_food_ids} & {
            oil_group(food_id) for food_id in available_food_ids
        }:
            continue
        if required_food_ids & excluded_food_ids:
            continue
        selected_groups = {oil_group(food_id) for food_id in selected_food_ids}
        for food_id in required_food_ids:
            if oil_group(food_id) in selected_groups:
                continue
            counts[food_id] = counts.get(food_id, 0) + 1
    return counts


def opportunity_candidates(
    recipes: tuple[ReviewedRecipe, ...],
    household: Household,
    selected_food_ids: set[str],
    pantry: tuple[PantryStock, ...],
    purchase_options: tuple[PurchaseOption, ...],
    excluded_food_ids: frozenset[str],
    budget_rm: Decimal,
    anchor_food_ids: set[str] | None = None,
) -> tuple[RecipeOpportunity, ...]:
    pantry_quantities = confirmed_pantry_quantities(pantry)
    available_food_ids = (
        selected_food_ids | set(pantry_quantities) | (anchor_food_ids or set())
    )
    if not available_food_ids:
        return ()

    options_by_food_id = {option.food_id: option for option in purchase_options}
    pantry_by_group: dict[str, Decimal] = {}
    for food_id, quantity in pantry_quantities.items():
        group = oil_group(food_id)
        pantry_by_group[group] = pantry_by_group.get(group, Decimal("0")) + quantity
    candidates = []
    for recipe in recipes:
        required = tuple(ingredient for ingredient in recipe.ingredients if ingredient.required)
        required_food_ids = {ingredient.food_id for ingredient in required}
        if not {oil_group(food_id) for food_id in required_food_ids} & {
            oil_group(food_id) for food_id in available_food_ids
        }:
            continue
        if required_food_ids & excluded_food_ids:
            continue

        scale = household.servings / recipe.base_servings
        missing = []
        complete_bundle = True
        processed_groups: set[str] = set()
        for ingredient in required:
            group = oil_group(ingredient.food_id)
            if group in processed_groups:
                continue
            processed_groups.add(group)
            if any(oil_group(food_id) == group for food_id in selected_food_ids):
                continue
            demand = sum(
                (part.quantity_kg * scale for part in required if oil_group(part.food_id) == group),
                Decimal("0"),
            )
            shortage = max(
                Decimal("0"),
                demand - pantry_by_group.get(group, Decimal("0")),
            )
            if shortage == 0:
                continue
            candidate_options = (
                [options_by_food_id[food_id] for food_id in sorted(OIL_FOOD_IDS) if food_id in options_by_food_id]
                if group == OIL_GROUP else [options_by_food_id[ingredient.food_id]]
                if ingredient.food_id in options_by_food_id else []
            )
            candidate_options = [option for option in candidate_options if not option.price_is_estimated]
            option = min(
                candidate_options,
                key=lambda candidate: (
                    int((shortage / (candidate.unit_kg * candidate.edible_yield)).to_integral_value(rounding=ROUND_CEILING))
                    * candidate.unit_kg * candidate.price_rm_per_kg,
                    candidate.food_id,
                ),
                default=None,
            )
            if option is None:
                complete_bundle = False
                break
            purchase_units = int(
                (shortage / (option.unit_kg * option.edible_yield)).to_integral_value(
                    rounding=ROUND_CEILING,
                )
            )
            purchase_kg = option.unit_kg * purchase_units
            missing.append(OpportunityIngredient(
                food_id=option.food_id,
                quantity_kg=shortage,
                purchase_units=purchase_units,
                purchase_kg=purchase_kg,
                estimated_cost_rm=purchase_kg * option.price_rm_per_kg,
                price_is_estimated=option.price_is_estimated,
                purchase_priority=ingredient_purchase_priority(ingredient.role),
            ))

        if not complete_bundle or not missing:
            continue
        estimated_cost = sum(
            (ingredient.estimated_cost_rm for ingredient in missing),
            Decimal("0"),
        )
        if estimated_cost > budget_rm:
            continue
        candidates.append(RecipeOpportunity(
            recipe=recipe,
            ingredients=tuple(sorted(
                missing,
                key=lambda item: (item.purchase_priority, item.food_id),
            )),
            estimated_cost_rm=estimated_cost,
        ))
    return tuple(candidates)


def build_recipe_opportunities(
    recipes: tuple[ReviewedRecipe, ...],
    household: Household,
    selected_food_ids: set[str],
    pantry: tuple[PantryStock, ...],
    purchase_options: tuple[PurchaseOption, ...],
    excluded_food_ids: frozenset[str],
    budget_rm: Decimal,
    anchor_food_ids: set[str] | None = None,
) -> list[PlannerV2RecipeOpportunityResponse]:
    pantry_quantities = confirmed_pantry_quantities(pantry)
    available_food_ids = (
        selected_food_ids | set(pantry_quantities) | (anchor_food_ids or set())
    )
    reuse_counts = recipe_reuse_counts(
        recipes=recipes,
        available_food_ids=available_food_ids,
        selected_food_ids=selected_food_ids,
        excluded_food_ids=excluded_food_ids,
    )
    candidates = opportunity_candidates(
        recipes=recipes,
        household=household,
        selected_food_ids=selected_food_ids,
        pantry=pantry,
        purchase_options=purchase_options,
        excluded_food_ids=excluded_food_ids,
        budget_rm=budget_rm,
        anchor_food_ids=anchor_food_ids,
    )
    ranked = sorted(
        candidates,
        key=lambda candidate: (
            len(candidate.ingredients),
            min(item.purchase_priority for item in candidate.ingredients),
            -sum(reuse_counts.get(item.food_id, 0) for item in candidate.ingredients),
            -candidate.recipe.max_weekly_occurrences,
            candidate.estimated_cost_rm,
            candidate.recipe.recipe_id,
        ),
    )
    selected_candidates = select_diverse_opportunities(ranked, available_food_ids)
    # Each tile can be added separately, but treat the visible set as one
    # combined budget commitment so accepting several tiles cannot overspend.
    budgeted_candidates = []
    committed_rm = Decimal("0")
    for candidate in selected_candidates:
        if committed_rm + candidate.estimated_cost_rm > budget_rm:
            continue
        budgeted_candidates.append(candidate)
        committed_rm += candidate.estimated_cost_rm
    return [
        PlannerV2RecipeOpportunityResponse(
            recipe_id=candidate.recipe.recipe_id,
            recipe_name=candidate.recipe.name,
            # The bundle is priced for one household occurrence, so its label
            # must promise exactly one additional meal rather than the recipe's
            # weekly occurrence ceiling.
            additional_meals=1,
            estimated_cost_rm=float(candidate.estimated_cost_rm),
            missing_ingredients=[
                PlannerV2OpportunityIngredientResponse(
                    food_id=item.food_id,
                    quantity_kg=float(item.quantity_kg),
                    purchase_units=item.purchase_units,
                    purchase_kg=float(item.purchase_kg),
                    estimated_cost_rm=float(item.estimated_cost_rm),
                    recipe_reuse_count=reuse_counts.get(item.food_id, 0),
                    price_is_estimated=item.price_is_estimated,
                    purchase_priority=item.purchase_priority,
                )
                for item in sorted(
                    candidate.ingredients,
                    key=lambda ingredient: (
                        ingredient.purchase_priority,
                        -reuse_counts.get(ingredient.food_id, 0),
                        ingredient.estimated_cost_rm,
                        ingredient.food_id,
                    ),
                )
            ],
        )
        for candidate in budgeted_candidates
    ]
