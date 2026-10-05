import type { FoodInfo, PlanRequest, PlanResponse } from '../api/plannerTypes';
import { oilGroup } from './oilEquivalence.ts';
import { purchaseQuantity } from './purchaseQuantity.ts';

type PlannerV2Allergen = 'EGG' | 'MILK' | 'PEANUT' | 'TREE_NUT' | 'SOY' | 'WHEAT' | 'FISH' | 'SHELLFISH';
type PlannerV2DietaryPattern = 'VEGETARIAN' | 'VEGAN' | 'NO_PORK';

export interface PlannerV2Request {
  household: { adults: number; children: number };
  budget_rm: number;
  target_meals: number;
  pantry: { food_id: string; quantity_kg: number; status: 'CONFIRMED' }[];
  preferences: { food_id: string; score: number }[];
  minimum_purchase_quantities: { food_id: string; purchase_kg: number }[];
  fixed_purchase_quantities: { food_id: string; purchase_kg: number }[];
  selected_food_ids: string[];
  excluded_food_ids: string[];
  dietary_patterns: PlannerV2DietaryPattern[];
  allergens: PlannerV2Allergen[];
  purchase_policy: { preferred_oil_food_ids: string[] };
}

interface PlannerV2ShoppingItem {
  food_id: string;
  demand_kg: number;
  pantry_used_kg: number;
  shortage_kg: number;
  purchase_units: number;
  purchase_kg: number;
  surplus_kg: number;
  estimated_cost_rm: number;
  price_is_estimated: boolean;
}

interface PlannerV2Recipe {
  recipe_id: string;
  name: string;
  occurrences: number;
  household_servings: number;
}

interface PlannerV2Allocation {
  recipe_id: string;
  food_id: string;
  demand_kg: number;
  pantry_used_kg: number;
  purchase_allocated_kg: number;
  pantry_source_food_ids?: string[];
  purchase_source_food_id?: string | null;
}

interface PlannerV2RecipeOpportunity {
  recipe_id: string;
  recipe_name: string;
  additional_meals: number;
  estimated_cost_rm: number;
  missing_ingredients: {
    food_id: string;
    quantity_kg: number;
    purchase_units: number;
    purchase_kg: number;
    estimated_cost_rm: number;
    recipe_reuse_count: number;
    price_is_estimated: boolean;
    purchase_priority?: number;
  }[];
}

export interface PlannerV2Response {
  planner_version: 'recipe-first-v2';
  unpriced_food_ids?: string[];
  portion_policy_version: 'adult-1-child-0.5-v1';
  child_portion_factor: number;
  quantity_basis: 'RAW_EDIBLE_KG';
  outcome: {
    status: 'FULL_PLAN' | 'SHORTFALL';
    requested_meals: number;
    supported_meals: number;
    deferred_meals: number;
    error_codes: string[];
    minimum_additional_budget_rm: number | null;
    estimated_total_cost_rm: number;
    missing_price_food_ids: string[];
  };
  recipes: PlannerV2Recipe[];
  shopping_items: PlannerV2ShoppingItem[];
  allocations: PlannerV2Allocation[];
  recipe_opportunities?: PlannerV2RecipeOpportunity[];
  food_fallback_suggestions?: NonNullable<PlanResponse['food_fallback_suggestions']>;
  substitutions: unknown[];
  nutrition: {
    energy_coverage: number;
    protein_coverage: number;
    calcium_coverage: number;
    missing_food_ids: string[];
  } | null;
  quality: {
    preference_score: number;
    pantry_used_kg: number;
    purchase_surplus_kg: number;
    purchased_food_count: number;
    recipe_variety: number;
  };
  exact_total_cost_rm: number;
  displayed_total_cost_rm: number;
  remaining_budget_rm: number;
  safety_missing_food_ids: string[];
}

const ALLERGEN_MAP: Record<string, PlannerV2Allergen> = {
  dairy: 'MILK',
  egg: 'EGG',
  eggs: 'EGG',
  fish: 'FISH',
  gluten: 'WHEAT',
  milk: 'MILK',
  peanut: 'PEANUT',
  peanuts: 'PEANUT',
  shellfish: 'SHELLFISH',
  soy: 'SOY',
  tree_nut: 'TREE_NUT',
  wheat: 'WHEAT',
};

const DIETARY_PATTERN_MAP: Record<string, PlannerV2DietaryPattern> = {
  'no-pork': 'NO_PORK',
  no_pork: 'NO_PORK',
  vegan: 'VEGAN',
  vegetarian: 'VEGETARIAN',
};

function unique<T>(values: readonly T[]): T[] {
  return [...new Set(values)];
}

export function toPlannerV2Request(request: PlanRequest): PlannerV2Request {
  const preferenceIds = unique([
    ...request.habit_picks,
    ...request.selected_food_ids,
    ...Object.keys(request.preference_scores),
  ]);

  return {
    household: { adults: request.adults, children: request.children },
    budget_rm: request.budget_rm,
    target_meals: request.target_meals ?? request.days,
    pantry: (request.pantry_stock ?? [])
      .filter((item) => item.grams > 0)
      .map((item) => ({
        food_id: item.food_id,
        quantity_kg: item.grams / 1000,
        status: 'CONFIRMED' as const,
      })),
    preferences: preferenceIds.map((foodId) => ({ food_id: foodId, score: 10 })),
    minimum_purchase_quantities: request.minimum_purchase_quantities ?? [],
    fixed_purchase_quantities: request.fixed_purchase_quantities ?? [],
    selected_food_ids: unique(request.selected_food_ids),
    excluded_food_ids: unique(request.excludes),
    dietary_patterns: unique(request.dietary_patterns.flatMap((pattern) => {
      const mapped = DIETARY_PATTERN_MAP[pattern.toLowerCase()];
      return mapped ? [mapped] : [];
    })),
    allergens: unique(request.allergies.flatMap((allergen) => {
      const mapped = ALLERGEN_MAP[allergen.toLowerCase()];
      return mapped ? [mapped] : [];
    })),
    purchase_policy: {
      // Oil selections limit the brand we may purchase, not whether existing
      // equivalent oil stock can be consumed by the optimizer.
      preferred_oil_food_ids: unique(request.selected_food_ids.filter(
        (foodId) => oilGroup(foodId) === 'OIL_EQUIVALENT',
      )).sort(),
    },
  };
}

function categorySubtotals(items: PlanResponse['items']): PlanResponse['category_subtotals'] {
  const totals = new Map<string, { category: string; cost_rm: number; grams: number }>();
  items.forEach((item) => {
    const current = totals.get(item.category) ?? { category: item.category, cost_rm: 0, grams: 0 };
    current.cost_rm += item.cost_rm;
    current.grams += item.grams;
    totals.set(item.category, current);
  });
  return [...totals.values()].map((item) => ({
    ...item,
    cost_rm: Math.round(item.cost_rm * 100) / 100,
  }));
}

export function adaptPlannerV2Response(
  response: PlannerV2Response,
  request: PlanRequest,
  catalogFoods: readonly FoodInfo[],
): PlanResponse {
  const catalogById = new Map(catalogFoods.map((food) => [food.food_id, food]));
  const items: PlanResponse['items'] = response.shopping_items
    .filter((item) => item.purchase_units > 0 && item.purchase_kg > 0)
    .map((item) => {
      const food = catalogById.get(item.food_id);
      const grams = item.purchase_kg * 1000;
      const display = purchaseQuantity(item.purchase_kg, item.purchase_units, food);
      return {
        food_id: item.food_id,
        name: food?.name ?? item.food_id,
        name_ms: food?.name_ms ?? food?.name ?? item.food_id,
        category: food?.category ?? 'other',
        grams,
        cost_rm: item.estimated_cost_rm,
        price_rm_per_100g: grams > 0 ? item.estimated_cost_rm / (grams / 100) : 0,
        price_is_estimated: item.price_is_estimated,
        packs: item.purchase_units,
        pack_label: display.packLabel,
        display_quantity: display.displayQuantity,
        by_weight: food?.sold_by_weight === true,
        estimated_consumption_g: item.demand_kg * 1000,
        substitutes: [],
        stock_g: item.pantry_used_kg * 1000,
        purchase_g: grams,
      };
    });
  const includedFoodIds = new Set(response.shopping_items
    .filter((item) => item.purchase_units > 0 || item.pantry_used_kg > 0)
    .map((item) => item.food_id));
  const unselectedPicks = request.selected_food_ids.filter((foodId) => !includedFoodIds.has(foodId));
  const overBudget = response.displayed_total_cost_rm > request.budget_rm;
  const status = response.outcome.status === 'FULL_PLAN' && !overBudget
    ? 'FEASIBLE'
    : 'INFEASIBLE';
  const reason = overBudget
    ? `The selected foods cost RM ${response.displayed_total_cost_rm.toFixed(2)}, above your RM ${request.budget_rm.toFixed(2)} weekly budget.`
    : response.outcome.status === 'SHORTFALL'
      ? `The recipe planner can currently support ${response.outcome.supported_meals} of ${response.outcome.requested_meals} meals.`
      : null;

  return {
    planner_version: 'recipe-first-v2',
    unpriced_food_ids: response.unpriced_food_ids ?? [],
    unselected_picks: unselectedPicks,
    recipes: response.recipes,
    recipe_allocations: response.allocations,
    recipe_opportunities: response.recipe_opportunities ?? [],
    food_fallback_suggestions: response.food_fallback_suggestions ?? [],
    requested_meals: response.outcome.requested_meals,
    supported_meals: response.outcome.supported_meals,
    deferred_meals: response.outcome.deferred_meals,
    planner_error_codes: response.outcome.error_codes,
    missing_price_food_ids: response.outcome.missing_price_food_ids,
    status,
    budget_rm: request.budget_rm,
    adults: request.adults,
    children: request.children,
    days: request.days,
    explanation: reason,
    explanation_source: 'template',
    items,
    meal_plan: [],
    meal_plan_source: 'template',
    meal_plan_text: response.recipes.map((recipe) => `${recipe.name} × ${recipe.occurrences}`).join(', ') || null,
    meal_plan_text_source: 'template',
    category_subtotals: categorySubtotals(items),
    total_cost_rm: response.displayed_total_cost_rm,
    exact_total_cost_rm: response.exact_total_cost_rm,
    buffer_rm: response.remaining_budget_rm,
    nutrition_coverage: [],
    overall_coverage_pct: response.nutrition
      ? Math.round(Math.min(
        response.nutrition.energy_coverage,
        response.nutrition.protein_coverage,
        response.nutrition.calcium_coverage,
      ) * 10000) / 100
      : 0,
    gaps: [],
    estimated_price_items: 0,
    total_items: items.length,
    infeasibility_reason: reason,
    budget_block_message: null,
    min_budget_for_energy_rm: null,
    additional_budget_needed_rm: response.outcome.minimum_additional_budget_rm,
    days_coverable: null,
    applied_excludes: request.excludes,
    dropped_locks: [],
    data_version: response.planner_version,
    solve_time_ms: 0,
    price_context: null,
    store_comparison: [],
    recommended_store: null,
    store_comparison_scope: null,
    store_comparison_reason: 'no_prices_for_basket',
    resolved_location: null,
    savings_estimate: null,
    multi_store_plan: null,
    suggestions: [],
    worth_considering: [],
    habit_profile: null,
    plan_generation_id: `recipe-first-v2-${Date.now()}`,
  };
}
