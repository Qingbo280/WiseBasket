# Database-free application boundary for the recipe-first planner.
from dataclasses import dataclass, replace
from decimal import Decimal, ROUND_CEILING

from packages.optimizer.wisebasket_optimizer.v2.calculations import (
    Household,
    PantryStock,
    PurchaseOption,
)
from packages.optimizer.wisebasket_optimizer.v2.domain import (
    IngredientRole,
    ReviewedRecipe,
    SubstitutionRule,
    assess_recipe,
    assess_substitution,
)
from packages.optimizer.wisebasket_optimizer.v2.nutrition import (
    FoodNutrition,
    household_nutrition_targets,
)
from packages.optimizer.wisebasket_optimizer.v2.optimizer import (
    FoodPreference,
    OptimizationResult,
    PREMIUM_PROTEIN_BUDGET_SHARE,
    PREMIUM_PROTEIN_PRICE_RM_PER_KG,
    optimize_recipe_plan,
)
from packages.optimizer.wisebasket_optimizer.v2.safety import (
    FoodSafety,
    resolve_safety_exclusions,
)
from packages.optimizer.wisebasket_optimizer.v2.oil_equivalence import OIL_FOOD_IDS, oil_group
from packages.optimizer.wisebasket_optimizer.week_floors import load_week_floors
from services.api.app.planner_v2_response import build_plan_v2_outcome
from services.api.app.budget_food_fallback import build_budget_food_fallback, rotating_week_plan_priorities
from services.api.app.recipe_opportunities import build_recipe_opportunities
from services.api.app.weekly_baselines import (
    BASELINE_VERSION, BASELINE_FOOD_IDS, match_scenario, prepare_baseline,
)
from services.api.app.schemas import (
    PlannerV2AllocationResponse,
    PlannerV2AppliedSubstitutionResponse,
    PlannerV2CreateRequest,
    PlannerV2NutritionResponse,
    PlannerV2OutcomeResponse,
    PlannerV2PlanResponse,
    PlannerV2QualityResponse,
    PlannerV2RecipeResponse,
    PlannerV2ShoppingItemResponse,
)


PLANNING_BUDGET_SHARE = Decimal("0.60")
WORTH_CONSIDERING_BUDGET_SHARE = Decimal("0.20")
CORE_TOP_UP_ROLE_PRIORITY = {
    IngredientRole.MAIN_PROTEIN: 0,
    IngredientRole.STAPLE: 1,
    IngredientRole.MAIN_VEGETABLE: 2,
    IngredientRole.SUPPORTING_VEGETABLE: 2,
}


def selection_is_overloaded(
    selected_food_ids: set[str],
    recipes: tuple[ReviewedRecipe, ...],
    target_meals: int,
) -> bool:
    """Treat a long habit list as recipe anchors, not a buy-everything goal."""
    if len(selected_food_ids) > min(15, max(8, target_meals + 5)):
        return True
    core_ids = {role: set() for role in (
        IngredientRole.STAPLE, IngredientRole.MAIN_PROTEIN, IngredientRole.MAIN_VEGETABLE,
    )}
    for recipe in recipes:
        for ingredient in recipe.ingredients:
            if ingredient.required and ingredient.food_id in selected_food_ids and ingredient.role in core_ids:
                core_ids[ingredient.role].add(ingredient.food_id)
    return (
        len(core_ids[IngredientRole.STAPLE]) > 3
        or len(core_ids[IngredientRole.MAIN_PROTEIN]) > 3
        or len(core_ids[IngredientRole.MAIN_VEGETABLE]) > 4
    )


def top_up_existing_core_foods(
    result: OptimizationResult,
    recipes: tuple[ReviewedRecipe, ...],
    purchase_options: tuple[PurchaseOption, ...],
    target_budget_rm: Decimal,
) -> OptimizationResult:
    """Spend useful headroom on existing meal cores, never new ingredients."""
    roles_by_food_id: dict[str, int] = {}
    for recipe in recipes:
        if result.occurrences.get(recipe.recipe_id, 0) <= 0:
            continue
        for ingredient in recipe.ingredients:
            priority = CORE_TOP_UP_ROLE_PRIORITY.get(ingredient.role)
            if ingredient.required and priority is not None:
                roles_by_food_id[ingredient.food_id] = min(
                    priority,
                    roles_by_food_id.get(ingredient.food_id, priority),
                )

    options_by_food_id = {option.food_id: option for option in purchase_options}
    items = dict(result.calculation.items)
    initial_units = {
        food_id: item.purchase_units
        for food_id, item in items.items()
        if item.purchase_units > 0
    }
    added_units = {food_id: 0 for food_id in initial_units}
    exact_cost_rm = result.calculation.exact_cost_rm
    premium_budget_rm = target_budget_rm * PREMIUM_PROTEIN_BUDGET_SHARE
    premium_spend_rm = sum((
        item.exact_cost_rm
        for food_id, item in items.items()
        if roles_by_food_id.get(food_id) == CORE_TOP_UP_ROLE_PRIORITY[IngredientRole.MAIN_PROTEIN]
        and food_id in options_by_food_id
        and options_by_food_id[food_id].price_rm_per_kg >= PREMIUM_PROTEIN_PRICE_RM_PER_KG
    ), Decimal("0"))
    candidates = sorted(
        (
            food_id
            for food_id in initial_units
            if food_id in roles_by_food_id
            and food_id in options_by_food_id
            and not options_by_food_id[food_id].price_is_estimated
        ),
        key=lambda food_id: (roles_by_food_id[food_id], food_id),
    )

    while True:
        changed = False
        for food_id in candidates:
            if added_units[food_id] >= initial_units[food_id]:
                continue
            item = items[food_id]
            option = options_by_food_id[food_id]
            extra_edible_kg = option.unit_kg * option.edible_yield
            extra_cost_rm = option.unit_kg * option.price_rm_per_kg
            if item.edible_surplus_kg + extra_edible_kg > item.demand_kg:
                continue
            if exact_cost_rm + extra_cost_rm > target_budget_rm:
                continue
            is_premium_protein = (
                roles_by_food_id[food_id]
                == CORE_TOP_UP_ROLE_PRIORITY[IngredientRole.MAIN_PROTEIN]
                and option.price_rm_per_kg >= PREMIUM_PROTEIN_PRICE_RM_PER_KG
            )
            if is_premium_protein and premium_spend_rm + extra_cost_rm > premium_budget_rm:
                continue
            items[food_id] = replace(
                item,
                purchase_units=item.purchase_units + 1,
                purchase_kg=item.purchase_kg + option.unit_kg,
                edible_surplus_kg=item.edible_surplus_kg + extra_edible_kg,
                exact_cost_rm=item.exact_cost_rm + extra_cost_rm,
            )
            exact_cost_rm += extra_cost_rm
            if is_premium_protein:
                premium_spend_rm += extra_cost_rm
            added_units[food_id] += 1
            changed = True
        if not changed:
            break

    if exact_cost_rm == result.calculation.exact_cost_rm:
        return result
    calculation = replace(
        result.calculation,
        items=items,
        exact_cost_rm=exact_cost_rm,
    )
    quality = replace(
        result.quality,
        purchase_surplus_kg=sum(
            (item.edible_surplus_kg for item in items.values()),
            Decimal("0"),
        ),
    )
    return replace(result, calculation=calculation, quality=quality)


def remaining_basket_stock(
    pantry: tuple[PantryStock, ...],
    result: OptimizationResult,
) -> tuple[PantryStock, ...]:
    """Return confirmed pantry plus purchase surplus left after the week plan."""
    quantities: dict[str, Decimal] = {}
    for item in pantry:
        if item.status == "CONFIRMED" and item.quantity_kg is not None:
            quantities[item.food_id] = (
                quantities.get(item.food_id, Decimal("0")) + item.quantity_kg
            )
    for food_id, item in result.calculation.items.items():
        quantities[food_id] = max(
            Decimal("0"),
            quantities.get(food_id, Decimal("0"))
            - item.pantry_used_kg
            + item.edible_surplus_kg,
        )
    return tuple(
        PantryStock(food_id, quantity_kg, "CONFIRMED")
        for food_id, quantity_kg in sorted(quantities.items())
        if quantity_kg > 0
    )


@dataclass(frozen=True)
class PlannerV2Catalog:
    recipes: tuple[ReviewedRecipe, ...]
    purchase_options: tuple[PurchaseOption, ...]
    food_nutrition: tuple[FoodNutrition, ...] = ()
    substitution_rules: tuple[SubstitutionRule, ...] = ()
    food_safety: tuple[FoodSafety, ...] = ()


class CatalogValidationError(ValueError):
    def __init__(self, issues: tuple[str, ...]):
        self.issues = tuple(sorted(set(issues)))
        super().__init__("; ".join(self.issues))


def duplicate_identity_issues(records, identity, label: str) -> list[str]:
    seen = set()
    duplicates = set()
    for record in records:
        value = identity(record)
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return [f"DUPLICATE_{label}_ID:{value}" for value in sorted(duplicates)]


def validate_planner_v2_catalog(catalog: PlannerV2Catalog) -> PlannerV2Catalog:
    # Reject malformed provider data before it can reach the solver.
    if not isinstance(catalog, PlannerV2Catalog):
        raise CatalogValidationError(("INVALID_CATALOG_TYPE",))

    issues = []
    issues.extend(duplicate_identity_issues(
        catalog.recipes, lambda record: record.recipe_id, "RECIPE",
    ))
    issues.extend(duplicate_identity_issues(
        catalog.purchase_options, lambda record: record.food_id, "PURCHASE_OPTION",
    ))
    issues.extend(duplicate_identity_issues(
        catalog.food_nutrition, lambda record: record.food_id, "FOOD_NUTRITION",
    ))
    issues.extend(duplicate_identity_issues(
        catalog.food_safety, lambda record: record.food_id, "FOOD_SAFETY",
    ))
    issues.extend(duplicate_identity_issues(
        catalog.substitution_rules, lambda record: record.rule_id, "SUBSTITUTION_RULE",
    ))

    recipes_by_id = {}
    for recipe in catalog.recipes:
        recipes_by_id.setdefault(recipe.recipe_id, recipe)
        assessment = assess_recipe(recipe)
        if not assessment.optimizer_eligible:
            reasons = ",".join(assessment.reasons)
            issues.append(f"RECIPE_NOT_ELIGIBLE:{recipe.recipe_id}:{reasons}")

    known_food_ids = {
        ingredient.food_id
        for recipe in catalog.recipes
        for ingredient in recipe.ingredients
    }
    known_food_ids.update(option.food_id for option in catalog.purchase_options)
    known_food_ids.update(profile.food_id for profile in catalog.food_nutrition)
    known_food_ids.update(record.food_id for record in catalog.food_safety)

    for rule in catalog.substitution_rules:
        missing_food_ids = sorted({
            rule.original_food_id,
            rule.substitute_food_id,
        } - known_food_ids)
        for food_id in missing_food_ids:
            issues.append(
                f"SUBSTITUTION_REFERENCES_UNKNOWN_FOOD:{rule.rule_id}:{food_id}"
            )

        unknown_recipe_ids = sorted(rule.recipe_ids - recipes_by_id.keys())
        for recipe_id in unknown_recipe_ids:
            issues.append(
                f"SUBSTITUTION_REFERENCES_UNKNOWN_RECIPE:{rule.rule_id}:{recipe_id}"
            )
        if missing_food_ids or unknown_recipe_ids:
            continue

        candidate_recipes = (
            tuple(recipes_by_id[recipe_id] for recipe_id in sorted(rule.recipe_ids))
            if rule.recipe_ids
            else tuple(recipes_by_id.values())
        )
        assessments = tuple(
            (recipe, assess_substitution(rule, recipe))
            for recipe in candidate_recipes
        )
        if rule.recipe_ids:
            for recipe, assessment in assessments:
                if not assessment.allowed:
                    reasons = ",".join(assessment.reasons)
                    issues.append(
                        f"SUBSTITUTION_INVALID_FOR_RECIPE:{rule.rule_id}:"
                        f"{recipe.recipe_id}:{reasons}"
                    )
        elif not any(assessment.allowed for _, assessment in assessments):
            issues.append(f"SUBSTITUTION_NOT_APPLICABLE:{rule.rule_id}")

    if issues:
        raise CatalogValidationError(tuple(issues))
    return catalog


def create_plan_v2(
    payload: PlannerV2CreateRequest,
    catalog: PlannerV2Catalog,
    planning_week: int | None = None,
) -> PlannerV2PlanResponse:
    validate_planner_v2_catalog(catalog)
    selected_food_ids = set(payload.selected_food_ids)
    recipes = catalog.recipes
    if selected_food_ids:
        selected_groups = {oil_group(food_id) for food_id in selected_food_ids}
        recipes = tuple(
            recipe
            for recipe in recipes
            if selected_groups & {oil_group(ingredient.food_id) for ingredient in recipe.ingredients}
        )
    household = Household(
        adults=payload.household.adults,
        children=payload.household.children,
    )
    pantry = tuple(
        PantryStock(item.food_id, item.quantity_kg, item.status)
        for item in payload.pantry
    )
    preferences = tuple(
        FoodPreference(item.food_id, item.score)
        for item in payload.preferences
    )
    minimum_purchase_kg = {
        item.food_id: item.purchase_kg
        for item in payload.minimum_purchase_quantities
    }
    fixed_purchase_kg = {
        item.food_id: item.purchase_kg
        for item in payload.fixed_purchase_quantities
    }
    planning_budget_rm = payload.budget_rm * PLANNING_BUDGET_SHARE
    purchase_options_by_food_id = {
        option.food_id: option for option in catalog.purchase_options
    }
    # Keep selected foods with no recent DB price in the basket response, but
    # do not give the optimizer an unpriceable minimum or count it as RM 0.
    # The client displays these IDs as "No recent price" and excludes them
    # from the priced subtotal until a purchase quote exists.
    unpriced_food_ids = sorted(
        (selected_food_ids | set(minimum_purchase_kg) | set(fixed_purchase_kg))
        - set(purchase_options_by_food_id)
    )
    for food_id in unpriced_food_ids:
        minimum_purchase_kg.pop(food_id, None)
        fixed_purchase_kg.pop(food_id, None)
    nutrition_targets = household_nutrition_targets(
        household,
        payload.target_meals,
    )
    catalogue_food_ids = {
        ingredient.food_id
        for recipe in catalog.recipes
        for ingredient in recipe.ingredients
    } | {
        food_id
        for rule in catalog.substitution_rules
        for food_id in (rule.original_food_id, rule.substitute_food_id)
    }
    catalogue_food_ids |= {
        option.food_id for option in catalog.purchase_options if option.food_id in OIL_FOOD_IDS
    } | {
        item.food_id for item in pantry if item.food_id in OIL_FOOD_IDS
    }
    catalogue_food_ids |= BASELINE_FOOD_IDS & set(purchase_options_by_food_id)
    safety = resolve_safety_exclusions(
        food_ids=catalogue_food_ids,
        records=catalog.food_safety,
        dietary_patterns=payload.dietary_patterns,
        allergens=payload.allergens,
        explicit_exclusions=payload.excluded_food_ids,
    )
    unpriced_food_ids = [food_id for food_id in unpriced_food_ids if food_id not in safety.excluded_food_ids]
    reviewed_oils = {record.food_id for record in catalog.food_safety if record.food_id in OIL_FOOD_IDS}
    allowed_oils = reviewed_oils - safety.excluded_food_ids
    preferred_oils = frozenset(payload.purchase_policy.preferred_oil_food_ids)
    available_options = tuple(
        option for option in catalog.purchase_options
        if option.food_id not in OIL_FOOD_IDS
        or (option.food_id in allowed_oils and (not preferred_oils or option.food_id in preferred_oils))
    )
    solver_options = (
        tuple(option for option in available_options if option.food_id in fixed_purchase_kg)
        if fixed_purchase_kg else available_options
    )
    scenario = match_scenario(payload.household.adults, payload.household.children, payload.target_meals)
    baseline = (
        prepare_baseline(
            scenario, available_options,
            {record.food_id for record in catalog.food_safety} - safety.excluded_food_ids,
            pantry, payload.budget_rm, planning_week, payload.target_meals,
            household.servings,
        )
        if scenario is not None and not fixed_purchase_kg else None
    )
    if baseline is not None:
        recipes = baseline.recipes
        for food_id, quantity in baseline.minimum_purchase_kg.items():
            minimum_purchase_kg[food_id] = max(minimum_purchase_kg.get(food_id, Decimal("0")), quantity)
    # The four pilot baskets already set their own household purchase targets.
    # Otherwise, a food selected by the recipe solver must be bought in a
    # useful weekly amount. This is conditional: a floor must not force every
    # candidate recipe ingredient into the basket. Explicit accepted amounts
    # keep their own minimum (including smaller recipe and budget add-ons).
    effective_persons = Decimal(payload.household.adults) + Decimal("0.6") * payload.household.children
    weekly_floors = load_week_floors()
    conditional_purchase_floor_kg = {
        option.food_id: Decimal(weekly_floors[option.food_id]) * effective_persons / Decimal("1000")
        for option in available_options
        if baseline is None
        and option.food_id in weekly_floors
        and option.food_id not in OIL_FOOD_IDS
        and option.food_id not in minimum_purchase_kg
        and option.food_id not in fixed_purchase_kg
    }
    accepted_purchase_cost_rm = sum((
        (
            quantity_kg / purchase_options_by_food_id[food_id].unit_kg
        ).to_integral_value(rounding=ROUND_CEILING)
        * purchase_options_by_food_id[food_id].unit_kg
        * purchase_options_by_food_id[food_id].price_rm_per_kg
        for food_id, quantity_kg in minimum_purchase_kg.items()
        if food_id in purchase_options_by_food_id
    ), Decimal("0"))
    # Explicitly accepted basket minima can use reserved budget headroom;
    # otherwise the week plan stays within its 60% share.
    optimizer_budget_rm = (
        max(payload.budget_rm, accepted_purchase_cost_rm)
        if accepted_purchase_cost_rm > planning_budget_rm
        else planning_budget_rm
    )
    if selected_food_ids:
        weekly_priorities = (
            frozenset() if selection_is_overloaded(selected_food_ids, recipes, payload.target_meals)
            else frozenset(selected_food_ids)
        )
    else:
        weekly_priorities = rotating_week_plan_priorities(
            budget_rm=payload.budget_rm,
            purchase_options=available_options,
            food_safety=catalog.food_safety,
            excluded_food_ids=safety.excluded_food_ids,
            recipe_food_ids={ingredient.food_id for recipe in recipes for ingredient in recipe.ingredients if ingredient.required},
            week=planning_week,
        )
    safe_pantry = tuple(item for item in pantry if item.food_id not in safety.excluded_food_ids)
    def solve(budget_rm: Decimal, minimum_occurrences: dict[str, int] | None) -> OptimizationResult:
        return optimize_recipe_plan(
            household=household,
            recipes=recipes,
            pantry=safe_pantry,
            purchase_options=solver_options,
            budget_rm=budget_rm,
            target_meals=payload.target_meals,
            excluded_food_ids=safety.excluded_food_ids,
            nutrition_targets=nutrition_targets,
            food_nutrition=catalog.food_nutrition,
            food_preferences=preferences,
            substitution_rules=catalog.substitution_rules,
            preferred_oil_food_ids=preferred_oils,
            minimum_purchase_kg=minimum_purchase_kg,
            fixed_purchase_kg=fixed_purchase_kg,
            conditional_purchase_floor_kg=conditional_purchase_floor_kg,
            priority_food_ids=weekly_priorities,
            allow_pilot_recipes=baseline is not None,
            minimum_recipe_occurrences_by_food_id=minimum_occurrences,
        )

    minimum_occurrences = (
        baseline.minimum_recipe_occurrences_by_food_id if baseline is not None else None
    )
    try:
        result = solve(optimizer_budget_rm, minimum_occurrences)
    except RuntimeError as error:
        if baseline is None or "model could not be solved" not in str(error):
            raise
        result = None
    if result is None:
        # Relax recipe rotation constraints, but keep the same spending cap.
        result = solve(optimizer_budget_rm, None)
    if not fixed_purchase_kg and baseline is None:
        result = top_up_existing_core_foods(
            result=result,
            recipes=recipes,
            purchase_options=available_options,
            target_budget_rm=planning_budget_rm,
        )
    recipes_by_id = {recipe.recipe_id: recipe for recipe in recipes}
    nutrition = None
    if result.nutrition is not None:
        nutrition = PlannerV2NutritionResponse(
            energy_coverage=float(result.nutrition.energy_coverage),
            protein_coverage=float(result.nutrition.protein_coverage),
            calcium_coverage=float(result.nutrition.calcium_coverage),
            missing_food_ids=list(result.nutrition.missing_food_ids),
        )
    exact_total = result.calculation.exact_cost_rm
    opportunity_pantry = remaining_basket_stock(safe_pantry, result)
    opportunity_anchor_food_ids = selected_food_ids | {
        food_id
        for food_id, item in result.calculation.items.items()
        if item.purchase_units > 0
    }
    outcome = build_plan_v2_outcome(result)
    if safety.missing_food_ids and outcome.status == "SHORTFALL":
        outcome_data = outcome.model_dump()
        outcome_data["error_codes"].append("MISSING_SAFETY_METADATA")
        outcome = PlannerV2OutcomeResponse(**outcome_data)
    recipe_opportunities = build_recipe_opportunities(
        recipes=catalog.recipes,
        household=household,
        selected_food_ids=selected_food_ids,
        anchor_food_ids=opportunity_anchor_food_ids,
        pantry=opportunity_pantry,
        purchase_options=available_options,
        excluded_food_ids=safety.excluded_food_ids,
        budget_rm=min(
            payload.budget_rm * WORTH_CONSIDERING_BUDGET_SHARE,
            max(Decimal("0"), payload.budget_rm - exact_total),
        ),
    )
    food_fallback_suggestions = []
    if not recipe_opportunities:
        food_fallback_suggestions = build_budget_food_fallback(
            budget_rm=payload.budget_rm,
            basket_cost_rm=exact_total,
            purchase_options=available_options,
            food_safety=catalog.food_safety,
            dietary_patterns=payload.dietary_patterns,
            allergens=payload.allergens,
            excluded_food_ids=payload.excluded_food_ids,
            basket_food_ids={
                food_id for food_id, item in result.calculation.items.items()
                if item.purchase_units > 0
            },
            selected_food_ids=selected_food_ids,
            purchase_floor_persons=Decimal(payload.household.adults) + Decimal("0.6") * payload.household.children,
            suggestion_budget_rm=min(
                payload.budget_rm * WORTH_CONSIDERING_BUDGET_SHARE,
                max(Decimal("0"), payload.budget_rm - exact_total),
            ),
            week=planning_week,
        )
    return PlannerV2PlanResponse(
        planner_version="recipe-first-v2",
        baseline_id=baseline.scenario.scenario_id if baseline is not None else None,
        baseline_version=BASELINE_VERSION if baseline is not None else None,
        baseline_status="PILOT" if baseline is not None else None,
        unpriced_food_ids=unpriced_food_ids,
        portion_policy_version="adult-1-child-0.5-v1",
        child_portion_factor=float(household.child_portion_factor),
        quantity_basis="RAW_EDIBLE_KG",
        outcome=outcome,
        recipes=[
            PlannerV2RecipeResponse(
                recipe_id=recipe_id,
                name=recipes_by_id[recipe_id].name,
                occurrences=occurrences,
                household_servings=float(household.servings),
            )
            for recipe_id, occurrences in result.occurrences.items()
        ],
        shopping_items=[
            PlannerV2ShoppingItemResponse(
                food_id=item.food_id,
                demand_kg=float(item.demand_kg),
                pantry_used_kg=float(item.pantry_used_kg),
                shortage_kg=float(item.shortage_kg),
                purchase_units=item.purchase_units,
                purchase_kg=float(item.purchase_kg),
                surplus_kg=float(item.edible_surplus_kg),
                estimated_cost_rm=float(item.exact_cost_rm),
                price_is_estimated=(
                    purchase_options_by_food_id[item.food_id].price_is_estimated
                    if item.purchase_units > 0
                    else False
                ),
            )
            for item in result.calculation.items.values()
        ],
        allocations=[
            PlannerV2AllocationResponse(
                recipe_id=allocation.recipe_id,
                food_id=allocation.food_id,
                demand_kg=float(allocation.demand_kg),
                pantry_used_kg=float(allocation.pantry_used_kg),
                purchase_allocated_kg=float(allocation.purchase_allocated_kg),
                pantry_source_food_ids=list(allocation.pantry_source_food_ids),
                purchase_source_food_id=allocation.purchase_source_food_id,
            )
            for allocation in result.calculation.allocations
        ],
        recipe_opportunities=recipe_opportunities,
        food_fallback_suggestions=food_fallback_suggestions,
        substitutions=[
            PlannerV2AppliedSubstitutionResponse(
                rule_id=item.rule_id,
                recipe_id=item.recipe_id,
                original_food_id=item.original_food_id,
                substitute_food_id=item.substitute_food_id,
                occurrences=item.occurrences,
                original_quantity_kg=float(item.original_quantity_kg),
                substitute_quantity_kg=float(item.substitute_quantity_kg),
            )
            for item in result.substitutions
        ],
        nutrition=nutrition,
        quality=PlannerV2QualityResponse(
            preference_score=result.quality.preference_score,
            pantry_used_kg=float(result.quality.pantry_used_kg),
            purchase_surplus_kg=float(result.quality.purchase_surplus_kg),
            purchased_food_count=result.quality.purchased_food_count,
            recipe_variety=result.quality.recipe_variety,
        ),
        exact_total_cost_rm=float(exact_total),
        displayed_total_cost_rm=float(result.calculation.total_cost_rm),
        remaining_budget_rm=float(max(Decimal("0"), payload.budget_rm - exact_total)),
        safety_missing_food_ids=list(safety.missing_food_ids),
    )
