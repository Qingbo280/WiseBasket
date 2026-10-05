import assert from 'node:assert/strict';
import test from 'node:test';

import {
  adaptPlannerV2Response,
  toPlannerV2Request,
} from './plannerV2Adapter.ts';
import { createPlanBasketProposal } from '../screens/planProposal.ts';
import { buildBasketDraft } from '../screens/basketContent.ts';

const legacyRequest = {
  budget_rm: 150,
  target_meals: 10,
  days: 7,
  adults: 1,
  children: 2,
  allergies: ['egg'],
  dislikes: [],
  excludes: ['SF999'],
  locks: [],
  dietary_patterns: ['no-pork'],
  iron_bioavailability: '10pct',
  preference_scores: { SF002: 0.5, SF006: 0.5 },
  habit_picks: ['SF002', 'SF006'],
  selected_food_ids: ['SF002', 'SF006'],
  habit_adjustments: {},
  store_id: null,
  location_state: null,
  location_district: null,
  location_lat: null,
  location_lon: null,
  meals_at_home: 'most_days_multiple',
  shopping_rhythm: null,
  pantry_stock: [
    { food_id: 'SF110', grams: 1000 },
    { food_id: 'SF018', grams: 300 },
  ],
  minimum_purchase_quantities: [
    { food_id: 'SF006', purchase_kg: 0.25 },
  ],
};

test('maps the existing questionnaire request to the recipe-first V2 contract', () => {
  assert.deepEqual(toPlannerV2Request(legacyRequest), {
    household: { adults: 1, children: 2 },
    budget_rm: 150,
    target_meals: 10,
    pantry: [
      { food_id: 'SF110', quantity_kg: 1, status: 'CONFIRMED' },
      { food_id: 'SF018', quantity_kg: 0.3, status: 'CONFIRMED' },
    ],
    preferences: [
      { food_id: 'SF002', score: 10 },
      { food_id: 'SF006', score: 10 },
    ],
    minimum_purchase_quantities: [
      { food_id: 'SF006', purchase_kg: 0.25 },
    ],
    fixed_purchase_quantities: [],
    selected_food_ids: ['SF002', 'SF006'],
    excluded_food_ids: ['SF999'],
    dietary_patterns: ['NO_PORK'],
    allergens: ['EGG'],
    purchase_policy: { preferred_oil_food_ids: [] },
  });
});

test('selected cooking oils constrain V2 oil purchase without locking pantry stock', () => {
  const request = { ...legacyRequest, selected_food_ids: ['SF123', 'SF122', 'SF120', 'SF123'] };
  assert.deepEqual(toPlannerV2Request(request).purchase_policy, {
    preferred_oil_food_ids: ['SF120', 'SF123'],
  });
});

test('adapts a V2 shortfall into the current basket model using purchase quantities', () => {
  const response = {
    planner_version: 'recipe-first-v2',
    portion_policy_version: 'adult-1-child-0.5-v1',
    child_portion_factor: 0.5,
    quantity_basis: 'RAW_EDIBLE_KG',
    outcome: {
      status: 'SHORTFALL',
      requested_meals: 10,
      supported_meals: 3,
      deferred_meals: 7,
      error_codes: ['MISSING_PRICE'],
      minimum_additional_budget_rm: null,
      estimated_total_cost_rm: 7.99,
      missing_price_food_ids: ['SF006'],
    },
    recipes: [{ recipe_id: 'tomato-egg', name: 'Tomato Egg Stir-Fry', occurrences: 3, household_servings: 2 }],
    shopping_items: [
      { food_id: 'SF072', demand_kg: 0.462, pantry_used_kg: 0, shortage_kg: 0.462, purchase_units: 1, purchase_kg: 1, surplus_kg: 0.538, estimated_cost_rm: 7.99, price_is_estimated: true },
      { food_id: 'SF018', demand_kg: 0.3, pantry_used_kg: 0.3, shortage_kg: 0, purchase_units: 0, purchase_kg: 0, surplus_kg: 0, estimated_cost_rm: 0, price_is_estimated: false },
    ],
    allocations: [
      { recipe_id: 'tomato-egg', food_id: 'SF072', demand_kg: 0.462, pantry_used_kg: 0, purchase_allocated_kg: 0.462 },
    ],
    recipe_opportunities: [{
      recipe_id: 'onion-omelette',
      recipe_name: 'Onion Omelette',
      additional_meals: 3,
      estimated_cost_rm: 1.2,
      missing_ingredients: [{
        food_id: 'SF056', quantity_kg: 0.1, purchase_units: 1, purchase_kg: 0.2,
        estimated_cost_rm: 1.2, recipe_reuse_count: 2,
      }],
    }],
    food_fallback_suggestions: [{
      food_id: 'SF022', group: 'protein', purchase_units: 1,
      purchase_kg: 1, estimated_cost_rm: 33.5,
    }],
    substitutions: [],
    nutrition: { energy_coverage: 0.7, protein_coverage: 0.8, calcium_coverage: 0.6, missing_food_ids: [] },
    quality: { preference_score: 0, pantry_used_kg: 0.3, purchase_surplus_kg: 0.538, purchased_food_count: 1, recipe_variety: 1 },
    exact_total_cost_rm: 7.99,
    displayed_total_cost_rm: 7.99,
    remaining_budget_rm: 142.01,
    safety_missing_food_ids: [],
  };
  const catalog = [
    { food_id: 'SF072', name: 'tomato', name_ms: 'tomato', category: 'vegetables', pack_label: '1 kg' },
    { food_id: 'SF018', name: 'egg', name_ms: 'telur', category: 'protein', pack_label: '10 biji' },
  ];

  const adapted = adaptPlannerV2Response(response, legacyRequest, catalog);

  assert.equal(adapted.planner_version, 'recipe-first-v2');
  assert.equal(adapted.status, 'INFEASIBLE');
  assert.equal(adapted.total_cost_rm, 7.99);
  assert.equal(adapted.exact_total_cost_rm, 7.99);
  assert.equal(adapted.items.length, 1, 'fully pantry-covered foods are not shopping lines');
  assert.deepEqual(
    {
      food_id: adapted.items[0].food_id,
      name: adapted.items[0].name,
      grams: adapted.items[0].grams,
      packs: adapted.items[0].packs,
      cost_rm: adapted.items[0].cost_rm,
      stock_g: adapted.items[0].stock_g,
      purchase_g: adapted.items[0].purchase_g,
    },
    { food_id: 'SF072', name: 'tomato', grams: 1000, packs: 1, cost_rm: 7.99, stock_g: 0, purchase_g: 1000 },
  );
  assert.match(adapted.infeasibility_reason, /3 of 10 meals/);
  assert.deepEqual(adapted.recipes, response.recipes);
  assert.deepEqual(adapted.recipe_allocations, response.allocations);
  assert.deepEqual(adapted.recipe_opportunities, response.recipe_opportunities);
  assert.deepEqual(adapted.food_fallback_suggestions, response.food_fallback_suggestions);
  assert.equal(adapted.items[0].price_is_estimated, true);

  const overBudget = adaptPlannerV2Response({
    ...response,
    outcome: { ...response.outcome, status: 'FULL_PLAN' },
    displayed_total_cost_rm: 151,
  }, legacyRequest, catalog);
  assert.equal(overBudget.status, 'INFEASIBLE');
  assert.match(overBudget.infeasibility_reason, /above your RM 150\.00 weekly budget/);
});

test('keeps the catalogue piece unit for purchased egg trays', () => {
  const response = {
    planner_version: 'recipe-first-v2',
    outcome: { status: 'FULL_PLAN', requested_meals: 1, supported_meals: 1, deferred_meals: 0, error_codes: [], missing_price_food_ids: [] },
    recipes: [],
    shopping_items: [{
      food_id: 'SF018', demand_kg: 0.7, pantry_used_kg: 0, shortage_kg: 0.7,
      purchase_units: 2, purchase_kg: 1.1, surplus_kg: 0.4,
      estimated_cost_rm: 12, price_is_estimated: false,
    }],
    allocations: [], recipe_opportunities: [], food_fallback_suggestions: [],
    substitutions: [], nutrition: null,
    quality: { preference_score: 0, pantry_used_kg: 0, purchase_surplus_kg: 0.4, purchased_food_count: 1, recipe_variety: 1 },
    exact_total_cost_rm: 12, displayed_total_cost_rm: 12, remaining_budget_rm: 138,
    safety_missing_food_ids: [],
  };
  const catalog = [{ food_id: 'SF018', name: 'chicken egg', name_ms: 'telur ayam', category: 'protein', pack_grams: 550, pack_label: '10 biji' }];

  const [egg] = adaptPlannerV2Response(response, legacyRequest, catalog).items;
  assert.equal(egg.pack_label, '10 biji');
  assert.equal(egg.packs, 2);
  assert.equal(egg.display_quantity, '20 biji');
  assert.equal(egg.grams, 1100, 'mass stays available for the optimizer and pricing');
});

test('planner purchase quantities reach the Week plan draft in kg and biji', () => {
  const response = {
    planner_version: 'recipe-first-v2',
    outcome: { status: 'FULL_PLAN', requested_meals: 1, supported_meals: 1, deferred_meals: 0, error_codes: [], missing_price_food_ids: [] },
    recipes: [], allocations: [], recipe_opportunities: [], food_fallback_suggestions: [],
    shopping_items: [
      { food_id: 'SF002', demand_kg: 0.25, pantry_used_kg: 0, purchase_units: 40, purchase_kg: 1, estimated_cost_rm: 30, price_is_estimated: false },
      { food_id: 'SF018', demand_kg: 0.6, pantry_used_kg: 0, purchase_units: 2, purchase_kg: 1.1, estimated_cost_rm: 12, price_is_estimated: false },
    ],
    nutrition: null,
    exact_total_cost_rm: 42, displayed_total_cost_rm: 42, remaining_budget_rm: 108,
  };
  const catalog = [
    { food_id: 'SF002', name: 'beef', category: 'protein', sold_by_weight: true },
    { food_id: 'SF018', name: 'chicken egg', category: 'protein', pack_grams: 550, pack_label: '10 biji' },
  ];
  const plan = adaptPlannerV2Response(response, legacyRequest, catalog);
  const draft = buildBasketDraft(createPlanBasketProposal(plan, catalog, ['SF002', 'SF018']));

  assert.deepEqual(draft.map(({ name, suggestedQuantity, unit }) => [name, suggestedQuantity, unit]), [
    ['beef', 1, 'kg'], ['chicken egg', 20, 'biji'],
  ]);
});

test('an unpriced selected food stays in the Week plan without changing the priced total', () => {
  const response = {
    planner_version: 'recipe-first-v2', unpriced_food_ids: ['SF106'],
    outcome: { status: 'FULL_PLAN', requested_meals: 1, supported_meals: 1, deferred_meals: 0, error_codes: [], missing_price_food_ids: [] },
    recipes: [], allocations: [], recipe_opportunities: [], food_fallback_suggestions: [],
    shopping_items: [{
      food_id: 'SF110', demand_kg: 0.2, pantry_used_kg: 0, purchase_units: 1,
      purchase_kg: 2, estimated_cost_rm: 7, price_is_estimated: false,
    }],
    nutrition: null, exact_total_cost_rm: 7, displayed_total_cost_rm: 7, remaining_budget_rm: 93,
  };
  const catalog = [
    { food_id: 'SF110', name: 'rice', category: 'carbohydrate', pack_grams: 2000, pack_label: '2 kg' },
    { food_id: 'SF106', name: 'tempeh', category: 'protein', pack_grams: 250, pack_label: '250 g', week_floor_g_per_person: 250, price_available: false },
  ];
  const request = { ...legacyRequest, adults: 2, children: 0, budget_rm: 100, selected_food_ids: ['SF110', 'SF106'] };
  const plan = adaptPlannerV2Response(response, request, catalog);
  const draft = buildBasketDraft(createPlanBasketProposal(plan, catalog, request.selected_food_ids));

  assert.equal(plan.total_cost_rm, 7);
  assert.deepEqual(draft.map(({ productId, suggestedQuantity, unit }) => [productId, suggestedQuantity, unit]), [
    ['SF110', 2, 'kg'], ['SF106', 0.5, 'kg'],
  ]);
});

test('reports weekly choices omitted by the recipe plan while counting pantry-covered choices', () => {
  const request = { ...legacyRequest, selected_food_ids: ['rice', 'noodles', 'egg'] };
  const response = {
    planner_version: 'recipe-first-v2',
    outcome: { status: 'FULL_PLAN', requested_meals: 1, supported_meals: 1, deferred_meals: 0, error_codes: [], missing_price_food_ids: [] },
    recipes: [], allocations: [], recipe_opportunities: [], substitutions: [], nutrition: null,
    shopping_items: [
      { food_id: 'rice', demand_kg: 1, pantry_used_kg: 0, purchase_units: 1, purchase_kg: 1, estimated_cost_rm: 4, price_is_estimated: false },
      { food_id: 'egg', demand_kg: 0.3, pantry_used_kg: 0.3, purchase_units: 0, purchase_kg: 0, estimated_cost_rm: 0, price_is_estimated: false },
    ],
    quality: { preference_score: 0, pantry_used_kg: 0.3, purchase_surplus_kg: 0, purchased_food_count: 1, recipe_variety: 1 },
    exact_total_cost_rm: 4, displayed_total_cost_rm: 4, remaining_budget_rm: 146,
    safety_missing_food_ids: [],
  };

  const plan = adaptPlannerV2Response(response, request, []);
  assert.deepEqual(plan.unselected_picks, ['noodles']);
});
