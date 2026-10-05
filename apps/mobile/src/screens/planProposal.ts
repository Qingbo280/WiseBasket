import type { ImageSourcePropType } from 'react-native';
import type { FoodInfo, PlanRequest, PlanResponse } from '../api/plannerTypes';
import type { PlannerPantryStockItem } from '../services/pantryApi';
import { foodImageUriForBackendId } from '../data/foodAssetManifest.ts';
import { purchaseQuantity } from '../services/purchaseQuantity.ts';
import type { BasketDraftItem, BasketProposal, BasketProposalItem, BasketProposalRecommendation, BasketRecipeOpportunity } from './basketContent';
import type { PlanDraft, PlanningLocation } from './planFlowContent';
import {
  foodMatchesGlutenKeywords,
  foodMatchesRestrictionText,
} from './planQuestionThreeContent.ts';
import type { PlanQuestionTwoRestrictionId } from './planQuestionTwoContent';

/**
 * Maps the plan questionnaire draft onto the real backend planner contract
 * (POST /api/v2/plans through the mobile adapter). No synthetic defaults beyond explicit
 * product decisions: 7-day weekly planning cycle, no store lock, GPS fix
 * preferred over the stated area.
 */

const WEEKLY_PLANNING_DAYS = 7 as const;
const RECIPE_OPPORTUNITY_LIMIT = 3 as const;

function targetMealsForDraft(planDraft: PlanDraft): number {
  if (planDraft.selectedMealId === null) {
    throw new Error('Choose a weekly meal range before building the plan.');
  }
  if (planDraft.selectedMealId === 'other') {
    return planDraft.customMealCount ?? WEEKLY_PLANNING_DAYS;
  }
  if (planDraft.selectedMealId === '10-14') return 10;
  if (planDraft.selectedMealId === '6-9') return 6;
  return 3;
}

const ALLERGY_BY_RESTRICTION: Partial<Record<PlanQuestionTwoRestrictionId, string>> = {
  dairy: 'dairy',
  eggs: 'egg',
  peanuts: 'peanut',
};

const PATTERN_BY_RESTRICTION: Partial<Record<PlanQuestionTwoRestrictionId, 'no-pork'>> = {
  pork: 'no-pork',
};

function mealsAtHomeForDraft(planDraft: PlanDraft): PlanRequest['meals_at_home'] {
  if (planDraft.selectedMealId === null) return null;
  if (planDraft.selectedMealId === 'other') {
    const count = planDraft.customMealCount;
    if (count === null) return null;
    if (count >= 10) return 'most_days_multiple';
    if (count >= 3) return 'once_daily';
    return 'few_times_week';
  }

  switch (planDraft.selectedMealId) {
    case '10-14':
      return 'most_days_multiple';
    case '6-9':
      return 'once_daily';
    case '3-5':
      return 'few_times_week';
    default:
      return null;
  }
}

function basketItemGrams(item: BasketDraftItem): number | null {
  const unit = item.unit.trim().toLowerCase();
  if (unit === 'kg') return item.suggestedQuantity * 1000;
  if (unit === 'g' || unit === 'gram' || unit === 'grams') return item.suggestedQuantity;
  return null;
}

function basketMinimumPurchaseKg(
  item: BasketDraftItem,
  food: FoodInfo | undefined,
): number | null {
  const exactPurchaseKg = item.minimumPurchaseKg;
  if (typeof exactPurchaseKg === 'number' && Number.isFinite(exactPurchaseKg) && exactPurchaseKg > 0) {
    return exactPurchaseKg;
  }
  const directGrams = basketItemGrams(item);
  if (directGrams !== null && directGrams > 0) return directGrams / 1000;
  if (!food?.pack_grams || food.pack_grams <= 0) return null;

  const packLabelMatch = /^(\d+(?:[.,]\d+)?)\s*(.+)$/.exec(food.pack_label.trim());
  const quantityPerPack = packLabelMatch
    ? Number.parseFloat(packLabelMatch[1].replace(',', '.'))
    : 1;
  const labelUnit = packLabelMatch?.[2].trim().toLowerCase();
  const itemUnit = item.unit.trim().toLowerCase();
  const packCount = labelUnit === itemUnit && quantityPerPack > 0
    ? Math.ceil(item.suggestedQuantity / quantityPerPack)
    : 1;
  return (food.pack_grams * packCount) / 1000;
}

export function planRequestFromDraft(
  planDraft: PlanDraft,
  usualProductIds: readonly string[],
  catalogFoods: readonly FoodInfo[] = [],
  selectedFoodIds: readonly string[] = usualProductIds,
  pantryStock: readonly PlannerPantryStockItem[] = [],
  basketDraft: readonly BasketDraftItem[] = [],
  pinnedFoodIds: readonly string[] = [],
): PlanRequest {
  const allergies: string[] = [];
  const dietaryPatterns: ('no-pork')[] = [];

  planDraft.selectedRestrictions.forEach((restriction) => {
    const allergy = ALLERGY_BY_RESTRICTION[restriction];
    if (allergy) {
      allergies.push(allergy);
      return;
    }
    const pattern = PATTERN_BY_RESTRICTION[restriction];
    if (pattern) {
      dietaryPatterns.push(pattern);
    }
  });

  // Q2 toggles without a database exclusion code (2026-09-11: both are now
  // ACTIVE in the questionnaire) become HARD solver excludes resolved against
  // the live catalogue, so the planner can never quietly buy a food the user
  // watched disappear from Q3:
  //   - 'gluten'  -> canonical-name grain keywords (wheat/flour/bread/...)
  //   - 'other'   -> free-text tokens matched against food names
  // Code-backed restrictions (pork/peanuts/dairy/eggs) flow via allergies /
  // dietary_patterns above and are NOT duplicated here.
  const excludes: string[] = [];
  const filterGluten = planDraft.selectedRestrictions.includes('gluten');
  const filterCustom =
    planDraft.selectedRestrictions.includes('other')
    && planDraft.customRestriction.trim().length > 0;
  if (filterGluten || filterCustom) {
    catalogFoods.forEach((food) => {
      const name = food.name || '';
      if ((filterGluten && foodMatchesGlutenKeywords(name))
        || (filterCustom && foodMatchesRestrictionText(name, planDraft.customRestriction))) {
        excludes.push(food.food_id);
      }
    });
  }
  basketDraft
    .filter((item) => item.choice === 'skip')
    .forEach((item) => excludes.push(item.productId));

  const preferenceScores: Record<string, number> = {};
  usualProductIds.forEach((foodId) => {
    preferenceScores[foodId] = 0.5;
  });

  // 2026-09-16 user rule (worth-Add loop fix): habit_picks must mirror the
  // user's CURRENTLY endorsed picks, not the frozen Q3 tick list - a tick
  // the user skipped leaves the demote domain, and a worth-considering item
  // they flipped back to Need (or manually added) joins it. The solver's
  // >4-protein demote trigger and demote domain then match what the user
  // actually stands behind: a re-post no longer re-demotes a protein the
  // user just added back, and a skipped tick no longer drags the trigger.
  const usualSet = new Set(usualProductIds);
  const skippedUsualIds = new Set(
    basketDraft
      .filter((item) => item.choice === 'skip' && usualSet.has(item.productId))
      .map((item) => item.productId),
  );
  const habitPicks = [
    ...usualProductIds.filter((id) => !skippedUsualIds.has(id)),
    ...basketDraft
      .filter((item) => item.choice === 'need' && !usualSet.has(item.productId))
      .map((item) => item.productId),
  ];

  const skippedIds = new Set(
    basketDraft.filter((item) => item.choice === 'skip').map((item) => item.productId),
  );
  const haveIds = basketDraft
    .filter((item) => item.choice === 'have')
    .map((item) => item.productId);
  const endorsedFoodIds = [...new Set([
    ...selectedFoodIds.filter((foodId) => !skippedIds.has(foodId)),
    ...haveIds,
  ])];

  const pantryByFoodId = new Map(pantryStock.map((item) => [item.food_id, item.grams]));
  const catalogByFoodId = new Map(catalogFoods.map((food) => [food.food_id, food]));
  basketDraft
    .filter((item) => item.choice === 'have')
    .forEach((item) => {
      const grams = basketItemGrams(item)
        ?? ((basketMinimumPurchaseKg(item, catalogByFoodId.get(item.productId)) ?? 0) * 1000);
      if (grams !== null && grams > 0) {
        pantryByFoodId.set(item.productId, Math.max(pantryByFoodId.get(item.productId) ?? 0, grams));
      }
    });

  const location: PlanningLocation | null = planDraft.planningLocation;
  const endorsedSet = new Set(endorsedFoodIds);
  const minimumPurchaseQuantities = basketDraft.flatMap((item) => {
    if (item.choice !== 'need' || !endorsedSet.has(item.productId)
      || (item.source === 'usual' && item.protectedQuantity !== true)) return [];
    const food = catalogByFoodId.get(item.productId);
    const purchaseKg = basketMinimumPurchaseKg(item, food);
    if (purchaseKg === null || purchaseKg <= 0) return [];
    return [{ food_id: item.productId, purchase_kg: purchaseKg }];
  });
  return {
    budget_rm: planDraft.weeklyBudget ?? 0,
    target_meals: targetMealsForDraft(planDraft),
    days: WEEKLY_PLANNING_DAYS,
    adults: planDraft.adults,
    children: planDraft.children,
    allergies,
    dislikes: [],
    excludes,
    locks: [],
    dietary_patterns: dietaryPatterns,
    iron_bioavailability: '10pct',
    preference_scores: preferenceScores,
    habit_picks: habitPicks,
    // 2026-09-14 user decision: the shopping list is solved within the user's
    // FINAL selected set only (round 1 = the Q3 ticks at 90% of budget, worth-
    // considering recommendations complement them opt-in). Empty (no ticks) =
    // legacy whole-catalogue solve, unchanged.
    selected_food_ids: endorsedFoodIds,
    minimum_purchase_quantities: minimumPurchaseQuantities,
    fixed_purchase_quantities: [],
    // A1 (2026-09-17): the previously-shown week-plan need set rides as
    // pinned picks so a curated re-solve cannot evaporate them (bug8).
    pinned_food_ids: [...pinnedFoodIds],
    habit_adjustments: {},
    store_id: null,
    location_state: location?.state ?? null,
    location_district: location?.district ?? null,
    location_lat: location?.latitude ?? null,
    location_lon: location?.longitude ?? null,
    meals_at_home: mealsAtHomeForDraft(planDraft),
    shopping_rhythm: null,
    // W10 (I2 Phase 2 A2): confirmed pantry stock as zero-cost grams; empty
    // = plan from scratch (backend regression-locked identical behaviour).
    pantry_stock: [...pantryByFoodId].map(([food_id, grams]) => ({ food_id, grams })),
  };
}

function isGramUnit(unit: string): boolean {
  return ['g', 'gram', 'grams'].includes(unit.trim().toLowerCase());
}

/** Display one purchasable unit as a normalized total. */
function singlePackDisplay(packLabelRaw: string): { suggestedQuantity: number; unit: string } {
  let label = packLabelRaw.trim();
  let approx = false;
  if (label.startsWith('+-')) {
    approx = true;
    label = label.slice(2).trim();
  }
  const match = /^(\d+(?:[.,]\d+)?)\s*(.+)$/.exec(label);
  if (match) {
    const per = Number.parseFloat(match[1].replace(',', '.'));
    const labelUnit = match[2].trim();
    if (isGramUnit(labelUnit)) {
      return { suggestedQuantity: per / 1000, unit: 'kg' };
    }
    return {
      suggestedQuantity: Number.isInteger(per) ? per : Math.round(per * 100) / 100,
      unit: labelUnit,
    };
  }
  if (approx) return { suggestedQuantity: 1, unit: `约 ${label}` };
  return { suggestedQuantity: 1, unit: packLabelRaw || 'pack' };
}

function proposalItemFromPlanItem(item: PlanResponse['items'][number]): BasketProposalItem {
  const uri = foodImageUriForBackendId(item.food_id);
  const imageSource: ImageSourcePropType | null = uri ? { uri } : null;

  // 2026-09-14 user feedback: quantities read as TOTALS - by-weight fresh
  // meat as a weight, pack items multiplied out ("3 biji", never "3 1 biji")
  // - mirroring the backend's display_quantity totals rule.
  // 2026-09-16 user rule: every gram-denominated quantity displays as kg
  // ("0.5 kg", "1.2 kg"); ml/L/biji stay as-is.
  const byWeight = item.by_weight === true;
  const purchaseGrams = item.purchase_g;
  const minimumPurchaseKg = typeof purchaseGrams === 'number'
    && Number.isFinite(purchaseGrams)
    && purchaseGrams > 0
    ? purchaseGrams / 1000
    : undefined;
  if (byWeight) {
    return {
      productId: item.food_id,
      name: item.name,
      imageSource,
      suggestedQuantity: item.grams / 1000,
      unit: 'kg',
      ...(minimumPurchaseKg !== undefined ? { minimumPurchaseKg } : {}),
      defaultChoice: 'need',
    };
  }
  const packCount = item.packs > 0 ? item.packs : 1;
  // 2026-09-16 user rule: "+-" pack labels are approximate-weight packs
  // (wet market). The number is real, so they multiply out like any gram
  // label ("2 × +-450g" -> "0.9 kg"); a "+-" label without a leading
  // number cannot be multiplied and reads "约 <label>".
  const rawLabel = (item.pack_label || '').trim();
  let label = rawLabel;
  let approx = false;
  if (label.startsWith('+-')) {
    approx = true;
    label = label.slice(2).trim();
  }
  const labelMatch = /^(\d+(?:[.,]\d+)?)\s*(.+)$/.exec(label);
  if (labelMatch) {
    const per = Number.parseFloat(labelMatch[1].replace(',', '.'));
    const total = per * packCount;
    const labelUnit = labelMatch[2].trim();
    if (isGramUnit(labelUnit)) {
      return {
        productId: item.food_id,
        name: item.name,
        imageSource,
        suggestedQuantity: total / 1000,
        unit: 'kg',
        ...(minimumPurchaseKg !== undefined ? { minimumPurchaseKg } : {}),
        defaultChoice: 'need',
      };
    }
    return {
      productId: item.food_id,
      name: item.name,
      imageSource,
      suggestedQuantity: Number.isInteger(total) ? total : Math.round(total * 100) / 100,
      unit: labelUnit,
      ...(minimumPurchaseKg !== undefined ? { minimumPurchaseKg } : {}),
      defaultChoice: 'need',
    };
  }
  if (approx) {
    return {
      productId: item.food_id,
      name: item.name,
      imageSource,
      suggestedQuantity: packCount,
      unit: `约 ${label}`,
      ...(minimumPurchaseKg !== undefined ? { minimumPurchaseKg } : {}),
      defaultChoice: 'need',
    };
  }
  return {
    productId: item.food_id,
    name: item.name,
    imageSource,
    suggestedQuantity: packCount,
    // 2026-09-14 user rule: the final list never displays the generic
    // "item" unit - an unlabeled pack reads "pack".
    unit: item.pack_label || 'pack',
    ...(minimumPurchaseKg !== undefined ? { minimumPurchaseKg } : {}),
    defaultChoice: 'need',
  };
}

// Product rule (2026-09-13, usual-basket page split; numbers re-confirmed by
// the user 2026-09-14, per-category count scaled by household size
// 2026-09-15: solo households keep at most 2 per category, everyone else 3;
// the cap applies only when they ticked MORE than 4 in that category) and
// AT MOST the table kind cap IN TOTAL. Everything else lands in "Worth
// considering": the overflow picks plus the backend's per-category
// recommendations (2 per category on top of any overflow).
const OVERFLOW_CAP_THRESHOLD = 4;
// 2026-09-15 user decision: one person cooks 1-2 dishes per category, not 3.
function weekPlanPicksPerCategory(persons = 2): number {
  return persons <= HOUSEHOLD_BASKET_RULES_TABLE[0][0] ? 2 : 3;
}
const FILLED_CATEGORY_MIN = 3;
const FILLER_REASON = 'Affordable and nutritious - rounds out this category.';
const SOLVER_EXTRA_REASON = 'Part of your nutritionally balanced week.';
const overflowPickReason = (persons = 2) =>
  `One of your usual picks (beyond the ${weekPlanPicksPerCategory(persons)} planned in this category).`;
const DROPPED_PICK_REASON = 'One of your usual picks.';

// 2026-09-15 user decision (save-money batch): the WHOLE weekly-basket rule
// set keyed by household size is ONE explicit hard-coded table - purchase
// floors, fresh-seasoning floors AND basket variety - not a formula.
// Mirrors portions.HOUSEHOLD_BASKET_RULES_TABLE exactly (children weigh 0.6
// of an adult). Rows are (upToEffectivePersons, packFloorG, freshSeasoningG,
// kindFloor, kindCap); the FIRST row whose bucket covers the household wins.
// 2026-09-16 W5: solo kind caps raised to 12/15 (1A coverage bottleneck).
const HOUSEHOLD_BASKET_RULES_TABLE: ReadonlyArray<readonly [number, number, number, number, number]> = [
  [1.25, 250, 100, 6, 12],     // 1 adult alone: solo week - small lines, more kinds
  [1.75, 400, 150, 8, 15],     // 1 adult + 1 small child
  [99.0, 1000, 250, 10, 15],   // 2+ adults: original 2026-09-14 family rules
];
function basketRulesRow(persons = 2): readonly [number, number, number, number, number] {
  for (const row of HOUSEHOLD_BASKET_RULES_TABLE) {
    if (persons <= row[0]) return row;
  }
  return HOUSEHOLD_BASKET_RULES_TABLE[HOUSEHOLD_BASKET_RULES_TABLE.length - 1];
}
function packPurchaseFloorG(persons = 2): number {
  return basketRulesRow(persons)[1];
}

// 2026-09-16 user decision: staples ALWAYS win the carbohydrate week-plan
// slots. Keyword list mirrors portions.CONVENTIONAL_STAPLE_KEYWORDS (the
// backend's single source of truth - keep in sync): a solver response order
// that lists yellow noodles / flour ahead of rice must never push the rice
// into "Worth considering".
const CONVENTIONAL_STAPLE_KEYWORDS = [
  'rice', 'noodle', 'bread', 'pasta', 'bihun',
  'vermicelli', 'kuey teow', 'porridge',
];
function isConventionalStapleItem(category: string, name: string): boolean {
  if (category !== 'carbohydrate' && category !== 'staples') return false;
  const n = (name || '').toLowerCase();
  return CONVENTIONAL_STAPLE_KEYWORDS.some((k) => n.includes(k));
}
function basketKindCap(persons = 2): number {
  return basketRulesRow(persons)[4];
}
// 2026-09-15 mirror of portions.py is_fresh_seasoning (extended 2026-09-16:
// shallot / curry leaves / lime): ginger/garlic/fresh turmeric/galangal/
// lemongrass/fresh chili (vegetables AND fruit categories - lime moved into
// the seasoning bucket) are weighed loose at the wet market and floor at the
// table fresh-seasoning g (100 g at 1 adult, 250 g family), not the universal
// pack floor.
const FRESH_SEASONING_NAME_KEYWORDS = [
  'ginger',
  'garlic',
  'turmeric',
  'galangal',
  'lemongrass',
  'chili',
  'shallot',
  'curry leaf',
  'curry leaves',
  'lime',
];
function purchaseFloorGFor(food: FoodInfo | undefined, persons = 2): number {
  // 2026-09-16 PM proposal: the backend serves a curated per-food solo
  // weekly floor (week_floors.csv, code-side); the household floor scales
  // linearly by effective persons. Missing value -> household-size table.
  if (food?.week_floor_g_per_person != null && food.week_floor_g_per_person > 0) {
    return Math.max(1, Math.round(food.week_floor_g_per_person * persons));
  }
  if (
    food &&
    (food.category === 'vegetables' || food.category === 'fruit') &&
    FRESH_SEASONING_NAME_KEYWORDS.some((k) => (food.name || '').toLowerCase().includes(k))
  ) {
    return basketRulesRow(persons)[2];
  }
  return packPurchaseFloorG(persons);
}

const FOOD_CATEGORIES = ['carbohydrate', 'protein', 'vegetables', 'fruit', 'other'] as const;

function catalogItemFromFood(food: FoodInfo, reason: string) {
  const uri = foodImageUriForBackendId(food.food_id);
  const packDisplay = singlePackDisplay(food.pack_label || 'pack');
  return {
    productId: food.food_id,
    name: food.name,
    imageSource: uri ? { uri } : null,
    suggestedQuantity: packDisplay.suggestedQuantity,
    unit: packDisplay.unit,
    defaultChoice: 'need' as const,
    reason,
  };
}

/**
 * 2026-09-14 user rule: when the solver proves the selection cannot build a
 * basket (INFEASIBLE, empty items), the review basket still needs a usable
 * display list. The capped pipeline inside createPlanBasketProposal handles
 * this via isCatalogFallback, so callers only need to commit the proposal.
 */

/**
 * Turn a real planner response into the basket proposal consumed by the
 * basket screens. Purchased items and recommendations both come from the
 * backend response; catalogue data only supplies recommendation display data.
 *
 * V2 includes all purchased recipe ingredients in the week plan and groups
 * recipe add-ons into complete bundles. The older response keeps its existing
 * category-cap behavior until its migration is complete.
 */
export function createPlanBasketProposal(
  planResult: PlanResponse,
  catalogFoods: readonly FoodInfo[] = [],
  usualProductIds: readonly string[] = [],
  explicitlyAddedIds: readonly string[] = [],
): BasketProposal {
  const catalogById = new Map(catalogFoods.map((food) => [food.food_id, food]));
  if (planResult.planner_version === 'recipe-first-v2') {
    const planItemById = new Map(planResult.items.map((item) => [item.food_id, item]));
    const unpricedIds = new Set(planResult.unpriced_food_ids ?? []);
    const deferredSelections = (planResult.unselected_picks ?? [])
      .filter((productId) => !unpricedIds.has(productId))
      .map((productId) => ({ productId, name: catalogById.get(productId)?.name ?? productId }));
    // The backend's purchased recipe ingredients complete the user's partial
    // selection; they belong in the week plan and its basket total.
    const persons = (planResult.adults ?? 2) + 0.6 * (planResult.children ?? 0);
    const meals = planResult.requested_meals ?? 7;
    const selectedIds = [...new Set(usualProductIds)];
    const selectedCounts = new Map<string, number>();
    selectedIds.forEach((foodId) => {
      const category = catalogById.get(foodId)?.category ?? 'other';
      selectedCounts.set(category, (selectedCounts.get(category) ?? 0) + 1);
    });
    // A long usual-food list expresses preferences. The recipe purchases are
    // the Week plan; unpriced preferences cannot be budgeted automatically.
    const overSelected = selectedIds.length > Math.min(15, Math.max(8, meals + 5))
      || (selectedCounts.get('protein') ?? 0) > 3
      || (selectedCounts.get('carbohydrate') ?? 0) > 3
      || (selectedCounts.get('vegetables') ?? 0) > 4;
    const explicitIds = new Set(explicitlyAddedIds);
    const orderedUnpricedIds = [...new Set([
      ...selectedIds.filter((foodId) => unpricedIds.has(foodId)),
      ...unpricedIds,
    ])];
    const unpricedUsuals = orderedUnpricedIds.flatMap((productId): BasketProposalItem[] => {
      if (overSelected && !explicitIds.has(productId)) return [];
      if (planItemById.has(productId)) return [];
      const food = catalogById.get(productId);
      if (!food) return [];
      const displayed = applyOptimisticAddQuantity({
        ...catalogItemFromFood(food, ''), source: 'usual', choice: 'need',
      }, catalogFoods, persons);
      return [displayed];
    });
    const usuals = [...planResult.items.map(proposalItemFromPlanItem), ...unpricedUsuals];
    const selectedSet = new Set(usuals.map((item) => item.productId));
    // A recipe opportunity is one actionable bundle. An ingredient row on
    // its own cannot promise that a multi-ingredient recipe is cookable.
    const recipeOpportunities = (planResult.recipe_opportunities ?? [])
      .slice(0, RECIPE_OPPORTUNITY_LIMIT)
      .flatMap((opportunity): BasketRecipeOpportunity[] => {
        const missing = opportunity.missing_ingredients.filter(
          (ingredient) => !selectedSet.has(ingredient.food_id),
        );
        if (missing.length === 0) return [];
        const items = missing.flatMap((ingredient): BasketProposalItem[] => {
          const food = catalogById.get(ingredient.food_id);
          if (!food) return [];
          const display = purchaseQuantity(ingredient.purchase_kg, ingredient.purchase_units, food);
          return [{
            ...catalogItemFromFood(food, `Needed for ${opportunity.recipe_name}.`),
            suggestedQuantity: display.quantity,
            unit: display.unit,
            minimumPurchaseKg: ingredient.purchase_kg,
          }];
        });
        if (items.length !== missing.length) return [];
        return [{
          recipeId: opportunity.recipe_id,
          name: opportunity.recipe_name,
          estimatedCostRm: opportunity.estimated_cost_rm,
          items,
        }];
      });
    // Keep the original food-row UI. Each missing ingredient is shown once;
    // adding any row linked to a recipe accepts its complete bundle.
    const recommendedIds = new Set<string>();
    const recipeRecommendations = recipeOpportunities.flatMap((opportunity) =>
      opportunity.items.flatMap((item): BasketProposalRecommendation[] => {
        if (recommendedIds.has(item.productId)) return [];
        recommendedIds.add(item.productId);
        return [{
          ...item,
          recipeId: opportunity.recipeId,
          reason: `Needed for ${opportunity.name}.`,
          angle: 'recipe_pairing',
        }];
      }));
    const deferredRecommendations = (overSelected ? [] : deferredSelections).flatMap(({ productId }): BasketProposalRecommendation[] => {
      if (selectedSet.has(productId) || recommendedIds.has(productId)) return [];
      const food = catalogById.get(productId);
      if (!food) return [];
      recommendedIds.add(productId);
      return [{ ...catalogItemFromFood(food, 'Chosen for this week; no purchased recipe used it.'), angle: 'your_picks' }];
    });
    if (recipeOpportunities.length === 0) {
      const fallback = (planResult.food_fallback_suggestions ?? [])
        .filter((item) => !selectedSet.has(item.food_id) && !planItemById.has(item.food_id))
        .flatMap((item): BasketProposalRecommendation[] => {
          const food = catalogById.get(item.food_id);
          if (!food) return [];
          const display = purchaseQuantity(item.purchase_kg, item.purchase_units, food);
          return [{
            ...catalogItemFromFood(food, `Estimated add-on RM${item.estimated_cost_rm.toFixed(2)}; fits your remaining budget.`),
            suggestedQuantity: display.quantity,
            unit: display.unit,
            minimumPurchaseKg: item.purchase_kg,
            budgetFallback: true,
            needsSpace: item.requires_swap === true,
          }];
        });
      return { usuals, recommendations: [...deferredRecommendations, ...fallback], recipeOpportunities, deferredSelections };
    }
    return {
      usuals,
      recommendations: [...deferredRecommendations, ...recipeRecommendations],
      recipeOpportunities,
      deferredSelections,
    };
  }
  // 2026-09-15: purchase floors scale by household size (1 person = half).
  const persons = (planResult.adults ?? 2) + 0.6 * (planResult.children ?? 0);

  const suggestionRecommendations = (excludedIds: ReadonlySet<string>) => {
    const taken = new Set<string>(excludedIds);
    return planResult.suggestions.flatMap((suggestion) => {
      const productId = suggestion.related_food_ids.find(
        (foodId) => !plannedIds.has(foodId) && !taken.has(foodId) && catalogById.has(foodId),
      );
      if (!productId) return [];

      taken.add(productId);
      const food = catalogById.get(productId)!;
      return [{
        ...catalogItemFromFood(food, suggestion.body || suggestion.title),
      }];
    });
  };

  const pickIds = [...new Set(usualProductIds)];

  /**
   * One purchase unit of a pack, displayed as a TOTAL (2026-09-17 v5-6a):
   * "1kg" -> 1 kg (never "1 1kg"), "345ml" -> 345 ml, "10 biji" -> 10 biji,
   * "+-450g" -> 0.45 kg. Mirrors the multiplied-out totals rule of
   * proposalItemFromPlanItem with packCount = 1.
   */
  if (pickIds.length === 0) {
    return {
      usuals: planResult.items.map(proposalItemFromPlanItem),
      recommendations: suggestionRecommendations(new Set()),
    };
  }

  // 2026-09-14 user rule (applies to EVERY path incl. failed solves): when
  // the solver returns no basket items (INFEASIBLE narrow domain), run the
  // SAME capped pipeline over the user's picks using catalogue display data
  // - >4-per-category keeps 3, the week plan caps at the household-size
  //   table kind cap (9 solo / 12 at 1A1C / 15 family), and every
  //   overflow pick lands in "Worth considering", never all 44+ picks dumped
  //   into the week plan. Quantities follow the table purchase floor too
  //   (user rule, restated 2026-09-14, tabled 2026-09-15: EVERY line totals
  //   >= the household floor):
  // pack_grams known -> ceil(1000/pack) packs; unknown -> 1 pack, grams 0.
  const isCatalogFallback = planResult.items.length === 0;
  const isOverloadedSelection = pickIds.length > 30;
  // 2026-09-17 (Step 2, A3): a curated response is the solver's OWN curation
  // of the user's ticks - re-applying the week-plan caps here would wrongly
  // push solver-selected picks back into worth considering. The caps only
  // make sense for the presence-floor (non-curated) journey and the
  // catalogue fallback.
  const isCurated = planResult.curated_selection === true && !isCatalogFallback;
  const fallbackPacksFor = (food: FoodInfo): { packs: number; grams: number } => {
    const packG = food.pack_grams && food.pack_grams > 0 ? food.pack_grams : null;
    if (!packG) return { packs: 1, grams: 0 };
    const packs = Math.max(1, Math.ceil(purchaseFloorGFor(food, persons) / packG));
    return { packs, grams: packs * packG };
  };
  const planItems: PlanResponse['items'] = isCatalogFallback
    ? pickIds.flatMap((foodId): PlanResponse['items'][number][] => {
      const food = catalogById.get(foodId);
      if (!food) return [];
      const { packs, grams } = fallbackPacksFor(food);
      const pricePer100 = food.price_rm_per_100g ?? 0;
      return [{
        food_id: food.food_id,
        name: food.name,
        name_ms: food.name_ms,
        category: food.category,
        grams,
        cost_rm: Math.round(pricePer100 * grams * 100) / 100,
        price_rm_per_100g: pricePer100,
        price_is_estimated: food.price_is_estimated ?? false,
        packs,
        pack_label: food.pack_label || '',
        display_quantity: '',
        by_weight: false,
        estimated_consumption_g: null,
        substitutes: [],
      }];
    })
    : planResult.items;
  const plannedIds = new Set(planItems.map((item) => item.food_id));

  // 2026-09-14: when the backend supplies worth-considering recommendations
  // (LLM-picked, hard-constrained, bilingual curated tags) they take over the
  // recommendation section; the local filler/suggestion ranking further down
  // stays as the fallback for older payloads without the field.
  const worthItems = planResult.worth_considering ?? [];
  const pickCountByCategory = new Map<string, number>();
  const worthRecommendationFromItem = (w: NonNullable<PlanResponse['worth_considering']>[number]): BasketProposalRecommendation => {
    const uri = foodImageUriForBackendId(w.food_id);
    // 2026-09-14 user feedback: recommendations must carry REAL purchase
    // units, never the generic "item". Backend-supplied pack info wins;
    // the live catalogue's pack_label is the fallback for older payloads.
    // By-weight recs quote one 250 g counter unit (matching est_cost_rm),
    // displayed as kg (2026-09-16 user rule).
    const catalogFood = catalogById.get(w.food_id);
    const packLabel = (w.pack_label ?? catalogFood?.pack_label ?? '').trim();
    const byWeight = w.by_weight === true;
    const packDisplay = singlePackDisplay(packLabel);
    return {
      productId: w.food_id,
      name: w.name,
      imageSource: uri ? { uri } : null,
      suggestedQuantity: byWeight ? 0.25 : packDisplay.suggestedQuantity,
      unit: byWeight ? 'kg' : packDisplay.unit,
      defaultChoice: 'need',
      // Curated bilingual tag pair + one-unit estimated cost; never LLM prose.
      reason: `${w.reason_en} · ${w.reason_ms} — ~RM${w.est_cost_rm.toFixed(2)}`,
      angle: w.angle,
    };
  };

  const pickSet = new Set(pickIds);
  const planItemById = new Map(planItems.map((item) => [item.food_id, item]));
  const categoryOf = (foodId: string): string => {
    const planItem = planItemById.get(foodId);
    if (planItem && planItem.category) return planItem.category;
    return catalogById.get(foodId)?.category ?? 'other';
  };

  // Per-category week-plan cap: only categories where the user ticked MORE
  // than 4 picks are capped at 3; 4 or fewer all stay in the week plan.
  // On top of that the WHOLE week plan is capped at the household-size
  // table kind cap (user rule 2026-09-14, tabled 2026-09-15, W5 revised
  // 2026-09-16: 12 foods solo, 15 at 1A1C, 15 family): once the total is
  // reached, further picks overflow into "Worth considering" just like
  // per-category overflow.
  const weekPlanTotalMax = basketKindCap(persons);
  pickIds.forEach((foodId) => {
    const category = categoryOf(foodId);
    pickCountByCategory.set(category, (pickCountByCategory.get(category) ?? 0) + 1);
  });
  const weekPlanCap = (category: string): number => {
    const count = pickCountByCategory.get(category) ?? 0;
    if (isOverloadedSelection && ['carbohydrate', 'protein', 'vegetables'].includes(category)) {
      return Math.min(count, 3);
    }
    return count > OVERFLOW_CAP_THRESHOLD
      ? weekPlanPicksPerCategory(persons)
      : count;
  };
  const canKeepPickInWeekPlan = (category: string, taken: number): boolean =>
    (!isOverloadedSelection && isCurated)
    || (taken < weekPlanCap(category) && weekPlanTotal < weekPlanTotalMax);

  const usuals: BasketProposalItem[] = [];
  const considered: BasketProposalRecommendation[] = [];
  const listedIds = new Set<string>();
  const categoryListed = new Map<string, number>();
  const bump = (foodId: string, category: string) => {
    listedIds.add(foodId);
    categoryListed.set(category, (categoryListed.get(category) ?? 0) + 1);
  };

  // 1a) 2026-09-16 user rule: STAPLES FIRST - within the carbohydrate class
  //     the rice/noodle/bread family always takes the week-plan slots before
  //     flour-type carbs, whatever order the solver response lists them in.
  const weekPlanTaken = new Map<string, number>();
  let weekPlanTotal = 0;
  planItems.forEach((item) => {
    if (!pickSet.has(item.food_id)) return;
    const category = categoryOf(item.food_id);
    if (!isConventionalStapleItem(category, item.name)) return;
    const taken = weekPlanTaken.get(category) ?? 0;
    if (canKeepPickInWeekPlan(category, taken)) {
      weekPlanTaken.set(category, taken + 1);
      weekPlanTotal += 1;
      usuals.push(proposalItemFromPlanItem(item));
      bump(item.food_id, category);
    }
  });

  // 1b) Week plan: the user's picks in solver order, capped per category AND
  //     in total (both caps overflow into "Worth considering", never
  //     vanish). Staple carbs already took their slots in pass 1a.
  //     (Curated response: no caps - the solver already curated.)
  planItems.forEach((item) => {
    if (!pickSet.has(item.food_id) || listedIds.has(item.food_id)) return;
    const category = categoryOf(item.food_id);
    const taken = weekPlanTaken.get(category) ?? 0;
    if (canKeepPickInWeekPlan(category, taken)) {
      weekPlanTaken.set(category, taken + 1);
      weekPlanTotal += 1;
      usuals.push(proposalItemFromPlanItem(item));
      bump(item.food_id, category);
    }
  });

  // 2) The solver's other basket items: not user picks, still worth seeing.
  //    (Never in the catalogue-fallback path: fallback items ARE the picks.)
  //    Skipped when the backend supplied worth-considering picks (the solve
  //    domain is the user's selection, so non-pick basket items cannot exist).
  //    Step 2 (2026-09-16): a solver basket item that IS a user pick landed
  //    here because the client caps overflowed it - its reason is the
  //    backend's curated advantage tag (pick_reasons) when supplied, not the
  //    generic solver-extra copy.
  if (!isCatalogFallback && worthItems.length === 0) {
    planItems.forEach((item) => {
      if (listedIds.has(item.food_id)) return;
      const tagReason = planResult.pick_reasons?.[item.food_id];
      const reason = (pickSet.has(item.food_id) && tagReason)
        ? `${tagReason.en} · ${tagReason.ms}`
        : SOLVER_EXTRA_REASON;
      considered.push({ ...proposalItemFromPlanItem(item), reason });
      bump(item.food_id, categoryOf(item.food_id));
    });
  }

  // 3) Backend worth-considering recommendations (opt-in), before the user's
  //    own overflow/dropped picks so the curated suggestions lead the section.
  if (worthItems.length > 0) {
    worthItems.forEach((w) => {
      if (listedIds.has(w.food_id)) return;
      considered.push(worthRecommendationFromItem(w));
      bump(w.food_id, w.category);
    });
  }

  // 3) Overflow / dropped picks: everything the user ticked that is not in
  //    the week plan (beyond-cap picks keep their solver/catalogue display
  //    quantities, picks with no data at all are skipped silently).
  //    Step 2 (2026-09-16): the reason is the backend's curated bilingual
  //    advantage tag (pick_reasons) when supplied - the hardcoded overflow
  //    copy is the fallback for older payloads only. Curated drops
  //    (unselected_picks) are rendered by the backend's own budget_fit worth
  //    items, so they are skipped here (never duplicated).
  const unselectedSet = new Set(planResult.unselected_picks ?? []);
  pickIds.forEach((foodId) => {
    if (listedIds.has(foodId) || unselectedSet.has(foodId)) return;
    const planItem = planItemById.get(foodId);
    const catalogFood = catalogById.get(foodId);
    if (!planItem && !catalogFood) return;
    const category = categoryOf(foodId);
    const overCap = (pickCountByCategory.get(category) ?? 0) > OVERFLOW_CAP_THRESHOLD;
    const tagReason = planResult.pick_reasons?.[foodId];
    const pickReason = tagReason ? `${tagReason.en} · ${tagReason.ms}` : null;
    considered.push(planItem
      ? { ...proposalItemFromPlanItem(planItem), reason: pickReason ?? (overCap ? overflowPickReason(persons) : DROPPED_PICK_REASON) }
      : catalogItemFromFood(catalogFood!, pickReason ?? DROPPED_PICK_REASON));
    bump(foodId, category);
  });

  // 2026-09-16 user decision (worth section order): nutrient gaps first,
  // then the user's OWN picks (demoted budget_fit + overflow picks),
  // then recipe pairings, then health upgrades. Array.sort is stable, so
  // within-group order (backend order / pick order) is kept.
  if (worthItems.length > 0) {
    const groupOf = (rec: BasketProposalRecommendation): number => {
      if (rec.angle === 'budget_fit' || pickSet.has(rec.productId)) return 1;
      if (rec.angle === 'nutrient_gap') return 0;
      if (rec.angle === 'recipe_pairing') return 2;
      if (rec.angle === 'health_upgrade') return 3;
      return 4;
    };
    considered.sort((a, b) => groupOf(a) - groupOf(b));
  }

  // 4) Fillers: bring every food category to at least 3 listed items with
  //    cheap (real-priced first, then lowest RM/100g) catalogue foods. The
  //    catalogue payload carries no nutrient columns, so price is the
  //    available "cheap and nutritious" proxy; ranking is deterministic.
  //    (Worth-considering mode replaces this local heuristic entirely.)
  if (worthItems.length === 0) {
    FOOD_CATEGORIES.forEach((category) => {
      const fillers = catalogFoods
        .filter((food) => food.category === category
          && !listedIds.has(food.food_id)
          && food.price_available
          && (food.price_rm_per_100g ?? 0) > 0)
        .sort((a, b) => {
          const realA = a.price_is_estimated ? 1 : 0;
          const realB = b.price_is_estimated ? 1 : 0;
          if (realA !== realB) return realA - realB;
          return (a.price_rm_per_100g ?? Infinity) - (b.price_rm_per_100g ?? Infinity);
        });
      for (const food of fillers) {
        if ((categoryListed.get(category) ?? 0) >= FILLED_CATEGORY_MIN) break;
        considered.push(catalogItemFromFood(food, FILLER_REASON));
        bump(food.food_id, category);
      }
    });
  }

  // 5) Healthier picks from the backend suggestions (deduped against all of
  //    the above). (Worth-considering mode: the backend's curated picks
  //    already cover this role; only the fallback path appends them.)
  if (worthItems.length === 0) {
    suggestionRecommendations(listedIds).forEach((rec) => {
      if (!listedIds.has(rec.productId)) {
        considered.push(rec);
        bump(rec.productId, categoryOf(rec.productId));
      }
    });
  }

  return { usuals, recommendations: considered };
}

/**
 * 2026-09-15 user rule: accepting a "Worth considering" item (or manually
 * adding a catalogue food) must put it into the week plan IMMEDIATELY at the
 * purchase floor - the 500 ms debounce + backend re-solve
 * round trip no longer gates visibility. Quantity fine-tuning is deferred to
 * the next removal-triggered re-solve or the confirm-time forced re-solve.
 *
 * Display mirrors the catalogue-fallback floor: pack foods at
 * ceil(floor / pack_grams) packs multiplied out ("20 biji", "1200 g",
 * "1000 ml"), by-weight counter items (unit 'g') at the floor grams (1000 g,
 * fresh seasonings 250 g - see purchaseFloorGFor), and foods without
 * pack data keep their catalogue placeholder (the re-solve replaces it).
 */
export function applyOptimisticAddQuantity(
  item: BasketDraftItem,
  catalogFoods: readonly FoodInfo[] = [],
  persons = 2,
): BasketDraftItem {
  if (item.recipeBundle && item.minimumPurchaseKg) return item;
  const food = catalogFoods.find((candidate) => candidate.food_id === item.productId);
  const floorG = purchaseFloorGFor(food, persons);
  // By-weight worth items quote one counter unit at the floor, in kg
  // (2026-09-16 user rule: gram-denominated quantities display as kg).
  if (item.unit === 'kg' || item.unit === 'g') {
    const minimumPurchaseKg = item.budgetFallback && item.minimumPurchaseKg
      ? item.minimumPurchaseKg
      : Math.max(floorG / 1000, item.minimumPurchaseKg ?? 0);
    return {
      ...item,
      suggestedQuantity: minimumPurchaseKg,
      unit: 'kg',
      minimumPurchaseKg,
    };
  }
  const packG = food?.pack_grams && food.pack_grams > 0 ? food.pack_grams : null;
  if (!packG) return item;
  const packs = Math.max(1, Math.ceil(floorG / packG));
  const minimumPurchaseKg = (packs * packG) / 1000;
  // 2026-09-16 user rule: "+-" approximate-weight packs multiply out like
  // any gram label ("+-450g" x 2 -> "0.9 kg"); non-numeric "+-" labels
  // read "约 <label>".
  let floorLabel = (food?.pack_label || '').trim();
  let approx = false;
  if (floorLabel.startsWith('+-')) {
    approx = true;
    floorLabel = floorLabel.slice(2).trim();
  }
  const labelMatch = /^(\d+(?:[.,]\d+)?)\s*(.+)$/.exec(floorLabel);
  if (labelMatch) {
    const per = Number.parseFloat(labelMatch[1].replace(',', '.'));
    const total = per * packs;
    const labelUnit = labelMatch[2].trim();
    if (isGramUnit(labelUnit)) {
      return {
        ...item,
        suggestedQuantity: total / 1000,
        unit: 'kg',
        minimumPurchaseKg,
      };
    }
    return {
      ...item,
      suggestedQuantity: Number.isInteger(total) ? total : Math.round(total * 100) / 100,
      unit: labelUnit,
      minimumPurchaseKg,
    };
  }
  if (approx) {
    return {
      ...item,
      suggestedQuantity: packs,
      unit: `约 ${floorLabel}`,
      minimumPurchaseKg,
    };
  }
  return {
    ...item,
    suggestedQuantity: packs,
    unit: food?.pack_label || 'pack',
    minimumPurchaseKg,
  };
}
