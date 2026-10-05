# Bounded recipe selection with exact rational CP-SAT constraints.
from dataclasses import dataclass, replace
from decimal import Decimal, ROUND_CEILING
from fractions import Fraction
from functools import reduce
from math import ceil, gcd
from typing import Iterable, Mapping

from ortools.sat.python import cp_model

from .calculations import (
    CalculationResult,
    Household,
    Ingredient,
    PantryStock,
    PurchaseOption,
    Recipe,
    RecipeSelection,
    calculate_plan,
)
from .domain import (
    IngredientRole,
    RecipeAssessment,
    RecipeIngredient,
    ReviewedRecipe,
    SubstitutionAssessment,
    SubstitutionRule,
    assess_recipe,
    assess_substitution,
)
from .nutrition import (
    FoodNutrition,
    NutritionAssessment,
    NutritionTargets,
    assess_plan_nutrition,
)
from .oil_equivalence import OIL_FOOD_IDS, OIL_GROUP, oil_group


PREMIUM_PROTEIN_PRICE_RM_PER_KG = Decimal("25")
PREMIUM_PROTEIN_BUDGET_SHARE = Decimal("0.15")


def least_common_multiple(left: int, right: int) -> int:
    return left // gcd(left, right) * right


def integer_scale(values: Iterable[Fraction]) -> int:
    return reduce(least_common_multiple, (value.denominator for value in values), 1)


def decimal_fraction(value: Decimal) -> Fraction:
    return Fraction(value)


def require_positive_decimal(value: Decimal, label: str) -> None:
    if not isinstance(value, Decimal) or not value.is_finite() or value <= 0:
        raise ValueError(f"{label} must be a positive finite Decimal")


@dataclass(frozen=True)
class FoodPreference:
    food_id: str
    score: int

    def __post_init__(self) -> None:
        if not isinstance(self.food_id, str) or not self.food_id.strip():
            raise ValueError("Preference food id must be a nonempty string")
        if type(self.score) is not int or self.score == 0 or not -100 <= self.score <= 100:
            raise ValueError("Preference score must be a nonzero integer from -100 to 100")


@dataclass(frozen=True)
class QualityMetrics:
    preference_score: int
    pantry_used_kg: Decimal
    purchase_surplus_kg: Decimal
    purchased_food_count: int
    recipe_variety: int


@dataclass(frozen=True)
class AppliedSubstitution:
    rule_id: str
    recipe_id: str
    original_food_id: str
    substitute_food_id: str
    occurrences: int
    original_quantity_kg: Decimal
    substitute_quantity_kg: Decimal


@dataclass(frozen=True)
class RecipeVariant:
    variant_id: str
    recipe: ReviewedRecipe
    ingredients: tuple[RecipeIngredient, ...]
    substitution_rule: SubstitutionRule | None = None


@dataclass(frozen=True)
class OptimizationResult:
    status: str
    target_meals: int
    meal_count: int
    shortfall_meals: int
    occurrences: dict[str, int]
    calculation: CalculationResult
    rejected_recipes: dict[str, RecipeAssessment]
    nutrition: NutritionAssessment | None
    quality: QualityMetrics
    substitutions: tuple[AppliedSubstitution, ...]
    rejected_substitutions: dict[tuple[str, str], SubstitutionAssessment]
    reason_codes: tuple[str, ...]
    minimum_additional_budget_rm: Decimal | None
    missing_price_food_ids: tuple[str, ...]


def optimize_recipe_plan(
    household: Household,
    recipes: Iterable[ReviewedRecipe],
    pantry: Iterable[PantryStock],
    purchase_options: Iterable[PurchaseOption],
    budget_rm: Decimal,
    target_meals: int,
    excluded_food_ids: set[str] | frozenset[str] = frozenset(),
    nutrition_targets: NutritionTargets | None = None,
    food_nutrition: Iterable[FoodNutrition] = (),
    food_preferences: Iterable[FoodPreference] = (),
    substitution_rules: Iterable[SubstitutionRule] = (),
    minimum_purchase_kg: Mapping[str, Decimal] | None = None,
    fixed_purchase_kg: Mapping[str, Decimal] | None = None,
    conditional_purchase_floor_kg: Mapping[str, Decimal] | None = None,
    include_shortfall_diagnostics: bool = True,
    preferred_oil_food_ids: frozenset[str] = frozenset(),
    priority_food_ids: frozenset[str] = frozenset(),
    allow_pilot_recipes: bool = False,
    minimum_recipe_occurrences_by_food_id: Mapping[str, int] | None = None,
) -> OptimizationResult:
    # Select bounded whole recipe occurrences within a strict exact budget.
    # First maximize meals and pantry use. If nutrition targets exist, next
    # maximize capped linear coverage. Then minimize purchase cost; familiar
    # foods only break an equal-cost tie. This ordering keeps tight-budget
    # plans affordable instead of allowing preference to lock in dear food.
    require_positive_decimal(budget_rm, "Budget")
    if type(target_meals) is not int or target_meals <= 0:
        raise ValueError("Target meals must be a positive integer")
    if type(include_shortfall_diagnostics) is not bool:
        raise ValueError("Shortfall diagnostics flag must be boolean")

    recipes = tuple(recipes)
    pantry = tuple(pantry)
    purchase_options = tuple(purchase_options)
    food_nutrition = tuple(food_nutrition)
    food_preferences = tuple(food_preferences)
    substitution_rules = tuple(substitution_rules)
    if not preferred_oil_food_ids <= OIL_FOOD_IDS:
        raise ValueError("Preferred oils must belong to the reviewed oil group")
    if any(not isinstance(food_id, str) or not food_id.strip() for food_id in priority_food_ids):
        raise ValueError("Priority food ids must be nonempty strings")
    minimum_purchase_kg = dict(minimum_purchase_kg or {})
    fixed_purchase_kg = dict(fixed_purchase_kg or {})
    conditional_purchase_floor_kg = dict(conditional_purchase_floor_kg or {})
    minimum_recipe_occurrences_by_food_id = dict(minimum_recipe_occurrences_by_food_id or {})
    if any(type(count) is not int or count <= 0
           for count in minimum_recipe_occurrences_by_food_id.values()):
        raise ValueError("Minimum recipe occurrences must be positive integers")
    for food_id, quantity_kg in minimum_purchase_kg.items():
        if not isinstance(food_id, str) or not food_id.strip():
            raise ValueError("Minimum purchase food id must be a nonempty string")
        require_positive_decimal(quantity_kg, "Minimum purchase quantity")
    for food_id, quantity_kg in conditional_purchase_floor_kg.items():
        if not isinstance(food_id, str) or not food_id.strip():
            raise ValueError("Conditional purchase floor food id must be a nonempty string")
        require_positive_decimal(quantity_kg, "Conditional purchase floor")
    for food_id, quantity_kg in fixed_purchase_kg.items():
        if not isinstance(food_id, str) or not food_id.strip():
            raise ValueError("Fixed purchase food id must be a nonempty string")
        require_positive_decimal(quantity_kg, "Fixed purchase quantity")
        if quantity_kg < minimum_purchase_kg.get(food_id, Decimal("0")):
            raise ValueError("Fixed purchase quantity cannot be below its minimum")
    recipe_ids = [recipe.recipe_id for recipe in recipes]
    if len(set(recipe_ids)) != len(recipe_ids):
        raise ValueError("Recipe ids must be unique")
    option_ids = [option.food_id for option in purchase_options]
    if len(set(option_ids)) != len(option_ids):
        raise ValueError("Purchase options must be unique per food")
    nutrition_ids = [profile.food_id for profile in food_nutrition]
    if len(set(nutrition_ids)) != len(nutrition_ids):
        raise ValueError("Food nutrition records must be unique per food")
    preference_ids = [preference.food_id for preference in food_preferences]
    if len(set(preference_ids)) != len(preference_ids):
        raise ValueError("Food preferences must be unique per food")
    rule_ids = [rule.rule_id for rule in substitution_rules]
    if len(set(rule_ids)) != len(rule_ids):
        raise ValueError("Substitution rule ids must be unique")

    assessments = {
        recipe.recipe_id: assess_recipe(recipe, excluded_food_ids, allow_pilot=allow_pilot_recipes)
        for recipe in recipes
    }
    eligible = tuple(recipe for recipe in recipes if assessments[recipe.recipe_id].optimizer_eligible)
    rejected = {
        recipe_id: assessment
        for recipe_id, assessment in assessments.items()
        if not assessment.optimizer_eligible
    }
    variants = []
    rejected_substitutions = {}
    for recipe in eligible:
        variants.append(RecipeVariant(f"{recipe.recipe_id}::base", recipe, recipe.ingredients))
        for rule in substitution_rules:
            assessment = assess_substitution(rule, recipe, excluded_food_ids)
            if not assessment.allowed:
                rejected_substitutions[(recipe.recipe_id, rule.rule_id)] = assessment
                continue
            ingredients = tuple(
                RecipeIngredient(
                    rule.substitute_food_id,
                    ingredient.quantity_kg * rule.quantity_ratio,
                    ingredient.role,
                    ingredient.required,
                )
                if ingredient.food_id == rule.original_food_id
                else ingredient
                for ingredient in recipe.ingredients
            )
            variants.append(RecipeVariant(
                f"{recipe.recipe_id}::sub::{rule.rule_id}",
                recipe,
                ingredients,
                rule,
            ))
    variants = tuple(variants)

    confirmed_stock: dict[str, Fraction] = {}
    for stock in pantry:
        if stock.status == "CONFIRMED":
            confirmed_stock[stock.food_id] = (
                confirmed_stock.get(stock.food_id, Fraction(0))
                + decimal_fraction(stock.quantity_kg)
            )
    options_by_food = {option.food_id: option for option in purchase_options}
    missing_minimum_prices = (set(minimum_purchase_kg) | set(fixed_purchase_kg)) - set(options_by_food)
    if missing_minimum_prices:
        raise ValueError(
            "Missing trusted purchase option for "
            + ", ".join(sorted(missing_minimum_prices))
        )

    model = cp_model.CpModel()
    occurrence_vars: dict[str, cp_model.IntVar] = {}
    occurrence_bounds: dict[str, int] = {}
    demand_per_occurrence: dict[tuple[str, str], Fraction] = {}
    foods: set[str] = set()
    household_servings = decimal_fraction(household.servings)
    for variant in variants:
        recipe = variant.recipe
        upper_bound = min(recipe.max_weekly_occurrences, target_meals)
        occurrence_bounds[variant.variant_id] = upper_bound
        occurrence_vars[variant.variant_id] = model.NewIntVar(
            0, upper_bound, f"occ_{variant.variant_id}"
        )
        scale = household_servings / decimal_fraction(recipe.base_servings)
        for ingredient in variant.ingredients:
            if not ingredient.required:
                continue
            foods.add(ingredient.food_id)
            demand_per_occurrence[(variant.variant_id, ingredient.food_id)] = (
                decimal_fraction(ingredient.quantity_kg) * scale
            )
    foods.update(minimum_purchase_kg)
    foods.update(fixed_purchase_kg)
    for recipe in eligible:
        model.Add(
            sum(
                occurrence_vars[variant.variant_id]
                for variant in variants
                if variant.recipe.recipe_id == recipe.recipe_id
            )
            <= recipe.max_weekly_occurrences
        )
    for food_id, minimum_count in sorted(minimum_recipe_occurrences_by_food_id.items()):
        matching = [
            occurrence_vars[variant.variant_id] for variant in variants
            if any(ingredient.required and ingredient.food_id == food_id
                   for ingredient in variant.ingredients)
        ]
        if matching:
            model.Add(sum(matching) >= minimum_count)

    supply_keys = {oil_group(food_id) for food_id in foods}
    purchase_candidates = (foods - OIL_FOOD_IDS) | (OIL_FOOD_IDS if OIL_GROUP in supply_keys else frozenset())
    purchase_vars: dict[str, cp_model.IntVar] = {}
    purchase_bounds: dict[str, int] = {}
    edible_per_unit: dict[str, Fraction] = {}
    for food_id in sorted(purchase_candidates):
        if food_id in OIL_FOOD_IDS and preferred_oil_food_ids and food_id not in preferred_oil_food_ids:
            continue
        option = options_by_food.get(food_id)
        if option is None:
            continue
        edible = decimal_fraction(option.unit_kg) * decimal_fraction(option.edible_yield)
        edible_per_unit[food_id] = edible
        maximum_demand = sum(
            (
                demand * occurrence_bounds[variant_id]
                for (variant_id, demanded_food), demand in demand_per_occurrence.items()
                if oil_group(demanded_food) == oil_group(food_id)
            ),
            Fraction(0),
        )
        unit_numerator = maximum_demand.numerator * edible.denominator
        unit_denominator = maximum_demand.denominator * edible.numerator
        maximum_units = (unit_numerator + unit_denominator - 1) // unit_denominator
        minimum_units = int(
            (
                minimum_purchase_kg.get(food_id, Decimal("0"))
                / option.unit_kg
            ).to_integral_value(rounding=ROUND_CEILING)
        )
        conditional_floor_units = int(
            (
                conditional_purchase_floor_kg.get(food_id, Decimal("0"))
                / option.unit_kg
            ).to_integral_value(rounding=ROUND_CEILING)
        )
        fixed_kg = fixed_purchase_kg.get(food_id)
        fixed_units = None
        if fixed_kg is not None:
            exact_units = fixed_kg / option.unit_kg
            if exact_units != exact_units.to_integral_value():
                raise ValueError(f"Fixed purchase quantity must use whole purchase units: {food_id}")
            fixed_units = int(exact_units)
        maximum_units = max(maximum_units, minimum_units, conditional_floor_units, fixed_units or 0)
        purchase_vars[food_id] = model.NewIntVar(0, maximum_units, f"buy_{food_id}")
        if fixed_units is not None:
            model.Add(purchase_vars[food_id] == fixed_units)
        elif minimum_units:
            model.Add(purchase_vars[food_id] >= minimum_units)
        if conditional_floor_units > max(minimum_units, 1) and fixed_units is None:
            is_purchased = model.NewBoolVar(f"floor_buy_{food_id}")
            model.Add(purchase_vars[food_id] == 0).OnlyEnforceIf(is_purchased.Not())
            model.Add(purchase_vars[food_id] >= conditional_floor_units).OnlyEnforceIf(is_purchased)
        purchase_bounds[food_id] = maximum_units

    stock_by_group = {
        key: sum((amount for food_id, amount in confirmed_stock.items() if oil_group(food_id) == key), Fraction(0))
        for key in supply_keys
    }
    quantity_values = tuple(demand_per_occurrence.values()) + tuple(
        stock_by_group.values()
    ) + tuple(edible_per_unit.values())
    quantity_scale = integer_scale(quantity_values)
    demand_expressions = {}
    shortage_vars = {}
    surplus_vars = {}
    for food_id in sorted(supply_keys):
        demand_expression = sum(
            int(demand * quantity_scale) * occurrence_vars[variant_id]
            for (variant_id, demanded_food), demand in demand_per_occurrence.items()
            if oil_group(demanded_food) == food_id
        )
        demand_expressions[food_id] = demand_expression
        stock_integer = int(stock_by_group.get(food_id, Fraction(0)) * quantity_scale)
        maximum_demand = sum(
            int(demand * quantity_scale) * occurrence_bounds[variant_id]
            for (variant_id, demanded_food), demand in demand_per_occurrence.items()
            if oil_group(demanded_food) == food_id
        )
        shortage = model.NewIntVar(0, maximum_demand, f"shortage_{food_id}")
        model.AddMaxEquality(shortage, (demand_expression - stock_integer, 0))
        shortage_vars[food_id] = shortage
        group_purchase_ids = [candidate for candidate in purchase_vars if oil_group(candidate) == food_id]
        if group_purchase_ids:
            purchased = sum(
                int(edible_per_unit[candidate] * quantity_scale) * purchase_vars[candidate]
                for candidate in group_purchase_ids
            )
            model.Add(demand_expression <= stock_integer + purchased)
            maximum_surplus = sum(
                int(edible_per_unit[candidate] * quantity_scale) * purchase_bounds[candidate]
                for candidate in group_purchase_ids
            )
            surplus = model.NewIntVar(0, maximum_surplus, f"surplus_{food_id}")
            model.Add(surplus == purchased - shortage)
            surplus_vars[food_id] = surplus
        else:
            model.Add(demand_expression <= stock_integer)

    # Oil brands are substitutes, not separate shopping requirements. The
    # solver may buy one reviewed oil SKU at most; existing mixed stock remains usable.
    oil_used_vars = []
    for food_id in sorted(OIL_FOOD_IDS & purchase_vars.keys()):
        used = model.NewBoolVar(f"oil_used_{food_id}")
        model.Add(purchase_vars[food_id] <= purchase_bounds[food_id] * used)
        oil_used_vars.append(used)
    if oil_used_vars:
        model.Add(sum(oil_used_vars) <= 1)

    total_meals = sum(occurrence_vars.values())
    model.Add(total_meals <= target_meals)

    costs = {
        food_id: decimal_fraction(options_by_food[food_id].unit_kg)
        * decimal_fraction(options_by_food[food_id].price_rm_per_kg)
        for food_id in purchase_vars
    }
    cost_scale = integer_scale((*costs.values(), decimal_fraction(budget_rm)))
    cost_expression = sum(
        int(cost * cost_scale) * purchase_vars[food_id]
        for food_id, cost in costs.items()
    )
    model.Add(cost_expression <= int(decimal_fraction(budget_rm) * cost_scale))

    # B40 purchasing guard: premium MAIN_PROTEIN spend is one combined pool,
    # not 15% for every meat species. Affordable proteins can fill the other
    # meals while an explicitly preferred premium meat remains feasible in a
    # small quantity when it fits this allowance.
    main_protein_food_ids = {
        ingredient.food_id
        for variant in variants
        for ingredient in variant.ingredients
        if ingredient.required and ingredient.role == IngredientRole.MAIN_PROTEIN
    }
    premium_protein_food_ids = {
        food_id
        for food_id in purchase_vars
        if (
            food_id in main_protein_food_ids
            and options_by_food[food_id].price_rm_per_kg
            >= PREMIUM_PROTEIN_PRICE_RM_PER_KG
        )
    }
    if premium_protein_food_ids:
        premium_cost_expression = sum(
            int(costs[food_id] * cost_scale) * purchase_vars[food_id]
            for food_id in premium_protein_food_ids
        )
        premium_budget = (
            decimal_fraction(budget_rm)
            * decimal_fraction(PREMIUM_PROTEIN_BUDGET_SHARE)
        )
        # This guard curbs discretionary premium purchases. An explicit
        # basket minimum is already a user decision and must not make the
        # entire model infeasible before we can report its actual cost.
        mandatory_premium_cost = sum(
            costs[food_id] * ceil(
                decimal_fraction(minimum_purchase_kg.get(food_id, Decimal("0")))
                / decimal_fraction(options_by_food[food_id].unit_kg)
            )
            for food_id in premium_protein_food_ids
        )
        premium_budget = max(premium_budget, mandatory_premium_cost)
        model.Add(premium_cost_expression <= int(premium_budget * cost_scale))

    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 0
    validation_error = model.Validate()
    if validation_error:
        raise ValueError(f"Invalid recipe selection model: {validation_error}")

    def solve_and_fix(expression, maximize: bool, label: str) -> int:
        if maximize:
            model.Maximize(expression)
        else:
            model.Minimize(expression)
        stage_status = solver.Solve(model)
        if stage_status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            raise RuntimeError(f"{label} model could not be solved")
        best_value = int(solver.Value(expression))
        model.Add(expression == best_value)
        return best_value

    maximum_meals = solve_and_fix(total_meals, True, "Recipe selection")
    pantry_use_expression = sum(
        demand_expressions[food_id] - shortage_vars[food_id]
        for food_id in supply_keys
    )
    solve_and_fix(pantry_use_expression, True, "Pantry use")

    preference_by_food = {
        preference.food_id: preference.score for preference in food_preferences
    }
    preference_roles = {
        IngredientRole.MAIN_PROTEIN,
        IngredientRole.STAPLE,
        IngredientRole.MAIN_VEGETABLE,
        IngredientRole.SUPPORTING_VEGETABLE,
    }
    variant_preference_scores = {
        variant.variant_id: sum(
            preference_by_food.get(ingredient.food_id, 0)
            for ingredient in variant.ingredients
            if ingredient.required and ingredient.role in preference_roles
        )
        for variant in variants
    }
    preference_expression = sum(
        variant_preference_scores[variant.variant_id] * occurrence_vars[variant.variant_id]
        for variant in variants
    )
    nutrition_score = None
    if nutrition_targets is not None:
        nutrition_by_food = {profile.food_id: profile for profile in food_nutrition}
        target_values = (
            nutrition_targets.energy_kcal,
            nutrition_targets.protein_g,
            nutrition_targets.calcium_mg,
        )
        attribute_names = ("energy_kcal", "protein_g", "calcium_mg")
        coverage_vars = []
        for nutrient_index, (target, attribute_name) in enumerate(zip(target_values, attribute_names)):
            contributions: dict[str, Fraction] = {}
            for variant in variants:
                recipe_scale = household_servings / decimal_fraction(variant.recipe.base_servings)
                contribution = Fraction(0)
                for ingredient in variant.ingredients:
                    if not ingredient.required:
                        continue
                    profile = nutrition_by_food.get(ingredient.food_id)
                    if profile is not None:
                        contribution += (
                            decimal_fraction(ingredient.quantity_kg)
                            * recipe_scale
                            * decimal_fraction(getattr(profile, attribute_name))
                        )
                contributions[variant.variant_id] = contribution
            target_fraction = decimal_fraction(target)
            nutrient_scale = integer_scale((*contributions.values(), target_fraction))
            target_integer = int(target_fraction * nutrient_scale)
            amount_expression = sum(
                int(contributions[variant.variant_id] * nutrient_scale)
                * occurrence_vars[variant.variant_id]
                for variant in variants
            )
            coverage = model.NewIntVar(0, 10_000, f"coverage_{nutrient_index}")
            model.Add(coverage * target_integer <= amount_expression * 10_000)
            coverage_vars.append(coverage)
        nutrition_score = sum(coverage_vars)
        solve_and_fix(nutrition_score, True, "Nutrition scoring")

    # An explicit choice for this week takes priority over a cheaper recipe
    # when both plans meet the same meal and nutrition coverage within budget.
    # Count distinct foods, so repeating one chosen staple cannot outweigh
    # connecting another chosen food to an approved recipe.
    priority_used_vars = []
    for food_id in sorted(priority_food_ids):
        occurrences = sum(
            occurrence_vars[variant.variant_id]
            for variant in variants
            if any(ingredient.required and ingredient.food_id == food_id
                   for ingredient in variant.ingredients)
        )
        if isinstance(occurrences, int) and occurrences == 0:
            continue
        used = model.NewBoolVar(f"weekly_choice_{food_id}")
        model.Add(occurrences >= 1).OnlyEnforceIf(used)
        model.Add(occurrences == 0).OnlyEnforceIf(used.Not())
        priority_used_vars.append(used)
    if priority_used_vars:
        solve_and_fix(sum(priority_used_vars), True, "Weekly food choices")

    solve_and_fix(cost_expression, False, "Cost minimization")
    if food_preferences:
        solve_and_fix(preference_expression, True, "Food preference")
    surplus_expression = sum(surplus_vars.values())
    solve_and_fix(surplus_expression, False, "Surplus minimization")

    purchase_used_vars = {}
    for food_id, purchase_var in purchase_vars.items():
        used = model.NewBoolVar(f"purchase_used_{food_id}")
        model.Add(purchase_var >= 1).OnlyEnforceIf(used)
        model.Add(purchase_var == 0).OnlyEnforceIf(used.Not())
        purchase_used_vars[food_id] = used
    purchased_food_expression = sum(purchase_used_vars.values())
    solve_and_fix(purchased_food_expression, False, "Ingredient reuse")

    substitution_expression = sum(
        occurrence_vars[variant.variant_id]
        for variant in variants
        if variant.substitution_rule is not None
    )
    solve_and_fix(substitution_expression, False, "Original recipe preference")

    recipe_used_vars = {}
    for recipe in eligible:
        recipe_occurrences = sum(
            occurrence_vars[variant.variant_id]
            for variant in variants
            if variant.recipe.recipe_id == recipe.recipe_id
        )
        used = model.NewBoolVar(f"recipe_used_{recipe.recipe_id}")
        model.Add(recipe_occurrences >= 1).OnlyEnforceIf(used)
        model.Add(recipe_occurrences == 0).OnlyEnforceIf(used.Not())
        recipe_used_vars[recipe.recipe_id] = used
    variety_expression = sum(recipe_used_vars.values())
    solve_and_fix(variety_expression, True, "Recipe variety")

    selected_variants = {
        variant.variant_id: int(solver.Value(occurrence_vars[variant.variant_id]))
        for variant in variants
        if solver.Value(occurrence_vars[variant.variant_id]) > 0
    }
    selected = {
        recipe.recipe_id: sum(
            selected_variants.get(variant.variant_id, 0)
            for variant in variants
            if variant.recipe.recipe_id == recipe.recipe_id
        )
        for recipe in eligible
        if any(
            selected_variants.get(variant.variant_id, 0) > 0
            for variant in variants
            if variant.recipe.recipe_id == recipe.recipe_id
        )
    }
    calculation_recipes = {
        variant.variant_id: Recipe(
            variant.recipe.recipe_id,
            variant.recipe.base_servings,
            tuple(
                Ingredient(ingredient.food_id, ingredient.quantity_kg, ingredient.required)
                for ingredient in variant.ingredients
            ),
        )
        for variant in variants
    }
    selections = tuple(
        RecipeSelection(calculation_recipes[variant_id], occurrences)
        for variant_id, occurrences in selected_variants.items()
    )
    chosen_units = {food_id: int(solver.Value(var)) for food_id, var in purchase_vars.items()}
    calculation = calculate_plan(
        household, selections, pantry, purchase_options, budget_rm,
        minimum_purchase_kg=minimum_purchase_kg,
        purchase_units_by_food_id=chosen_units,
    )
    expected_cost = sum(
        Decimal(costs[food_id].numerator) / Decimal(costs[food_id].denominator) * units
        for food_id, units in chosen_units.items()
    )
    if calculation.exact_cost_rm != expected_cost:
        raise ValueError("Solver and shopping calculation disagree on exact cost")
    nutrition = None
    if nutrition_targets is not None:
        nutrition = assess_plan_nutrition(
            household,
            {
                variant.variant_id: replace(
                    variant.recipe,
                    recipe_id=variant.variant_id,
                    ingredients=variant.ingredients,
                )
                for variant in variants
            },
            selected_variants,
            nutrition_targets,
            food_nutrition,
        )
    quality = QualityMetrics(
        preference_score=sum(
            variant_preference_scores[variant_id] * occurrences
            for variant_id, occurrences in selected_variants.items()
        ),
        pantry_used_kg=sum(
            (item.pantry_used_kg for item in calculation.items.values()),
            Decimal("0"),
        ),
        purchase_surplus_kg=sum(
            (item.edible_surplus_kg for item in calculation.items.values()),
            Decimal("0"),
        ),
        purchased_food_count=sum(
            item.purchase_units > 0 for item in calculation.items.values()
        ),
        recipe_variety=len(selected),
    )
    applied_substitutions = tuple(
        AppliedSubstitution(
            variant.substitution_rule.rule_id,
            variant.recipe.recipe_id,
            variant.substitution_rule.original_food_id,
            variant.substitution_rule.substitute_food_id,
            selected_variants[variant.variant_id],
            next(
                ingredient.quantity_kg
                for ingredient in variant.recipe.ingredients
                if ingredient.food_id == variant.substitution_rule.original_food_id
            )
            * household.servings
            / variant.recipe.base_servings
            * selected_variants[variant.variant_id],
            next(
                ingredient.quantity_kg
                for ingredient in variant.ingredients
                if ingredient.food_id == variant.substitution_rule.substitute_food_id
            )
            * household.servings
            / variant.recipe.base_servings
            * selected_variants[variant.variant_id],
        )
        for variant in variants
        if variant.substitution_rule is not None and variant.variant_id in selected_variants
    )
    plan_status = "FULL_PLAN" if maximum_meals == target_meals else "SHORTFALL"
    reason_codes = ()
    minimum_additional_budget_rm = None
    missing_price_food_ids = ()
    if plan_status == "SHORTFALL":
        if include_shortfall_diagnostics:
            maximum_cost = sum(
                (
                    costs[food_id] * purchase_bounds[food_id]
                    for food_id in purchase_vars
                ),
                Fraction(0),
            )
            diagnostic_budget = max(
                budget_rm,
                Decimal(maximum_cost.numerator) / Decimal(maximum_cost.denominator),
            )
            diagnostic = optimize_recipe_plan(
                household=household,
                recipes=recipes,
                pantry=pantry,
                purchase_options=purchase_options,
                budget_rm=diagnostic_budget,
                target_meals=target_meals,
                excluded_food_ids=excluded_food_ids,
                nutrition_targets=nutrition_targets,
                food_nutrition=food_nutrition,
                food_preferences=food_preferences,
                substitution_rules=substitution_rules,
                minimum_purchase_kg=minimum_purchase_kg,
                fixed_purchase_kg=fixed_purchase_kg,
                conditional_purchase_floor_kg=conditional_purchase_floor_kg,
                include_shortfall_diagnostics=False,
                preferred_oil_food_ids=preferred_oil_food_ids,
                allow_pilot_recipes=allow_pilot_recipes,
                minimum_recipe_occurrences_by_food_id=minimum_recipe_occurrences_by_food_id,
            )
            if diagnostic.status == "FULL_PLAN":
                reason_codes = ("INSUFFICIENT_BUDGET",)
                additional = diagnostic.calculation.exact_cost_rm - budget_rm
                minimum_additional_budget_rm = additional.quantize(
                    Decimal("0.01"), rounding=ROUND_CEILING
                )
            else:
                reason_codes = diagnostic.reason_codes
                missing_price_food_ids = diagnostic.missing_price_food_ids
        else:
            reasons = []
            excluded_recipe_count = sum(
                "CONTAINS_EXCLUDED_FOOD" in assessment.reasons
                for assessment in rejected.values()
            )
            if not eligible:
                reasons.append(
                    "RESTRICTIONS_TOO_LIMITING"
                    if excluded_recipe_count
                    else "NO_ELIGIBLE_RECIPE"
                )
            else:
                if sum(recipe.max_weekly_occurrences for recipe in eligible) < target_meals:
                    reasons.append("RECIPE_LIMIT_REACHED")
                missing_price_foods = {
                    ingredient.food_id
                    for variant in variants
                    for ingredient in variant.ingredients
                    if ingredient.required and not any(
                        oil_group(option_id) == oil_group(ingredient.food_id)
                        for option_id in purchase_vars
                    )
                }
                if missing_price_foods:
                    reasons.append("MISSING_PRICE")
                    missing_price_food_ids = tuple(sorted(missing_price_foods))
                if excluded_recipe_count:
                    reasons.append("RESTRICTIONS_TOO_LIMITING")
                if not reasons:
                    reasons.append("TARGET_STRUCTURALLY_UNREACHABLE")
            reason_codes = tuple(reasons)
    return OptimizationResult(
        plan_status,
        target_meals,
        maximum_meals,
        target_meals - maximum_meals,
        selected,
        calculation,
        rejected,
        nutrition,
        quality,
        applied_substitutions,
        rejected_substitutions,
        reason_codes,
        minimum_additional_budget_rm,
        missing_price_food_ids,
    )
