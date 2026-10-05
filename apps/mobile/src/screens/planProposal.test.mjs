import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';

const source = fs.readFileSync(new URL('./planProposal.ts', import.meta.url), 'utf8');

test('maps questionnaire meals and manual area into the planner request', () => {
  assert.match(source, /case '6-9':\s*return 'once_daily'/);
  assert.match(source, /location_state: location\?\.state \?\? null/);
  assert.match(source, /location_district: location\?\.district \?\? null/);
  assert.match(source, /preferenceScores\[foodId\] = 0\.5/);
});

test('maps backend suggestions into the plan proposal recommendation section', () => {
  assert.match(source, /planResult\.suggestions\.flatMap/);
  assert.match(source, /suggestion\.related_food_ids\.find/);
  assert.match(source, /suggestion\.body \|\| suggestion\.title/);
  assert.match(source, /recommendations/);
});

import { applyOptimisticAddQuantity, createPlanBasketProposal, planRequestFromDraft } from './planProposal.ts';

const catalog = [
  { food_id: 'SF110', name: 'rice', name_ms: 'beras', category: 'carbohydrate', price_rm_per_100g: 0.34, price_is_estimated: false, price_available: true, pack_label: '2 kg' },
  { food_id: 'SF002', name: 'beef', name_ms: 'daging', category: 'protein', price_rm_per_100g: 3.5, price_is_estimated: false, price_available: true, pack_label: '250 g' },
  { food_id: 'SF018', name: 'egg', name_ms: 'telur', category: 'protein', price_rm_per_100g: 0.96, price_is_estimated: false, price_available: true, pack_label: '10 biji' },
  { food_id: 'SFS1', name: 'sardine', name_ms: 'sardin', category: 'protein', price_rm_per_100g: 2.2, price_is_estimated: false, price_available: true, pack_label: '425 g' },
  { food_id: 'SF062', name: 'spinach', name_ms: 'bayam', category: 'vegetables', price_rm_per_100g: 0.57, price_is_estimated: false, price_available: true, pack_label: '1kg' },
  { food_id: 'SF074', name: 'kangkung', name_ms: 'kangkung', category: 'vegetables', price_rm_per_100g: 0.65, price_is_estimated: false, price_available: true, pack_label: '1kg' },
  { food_id: 'SF088', name: 'guava', name_ms: 'jambu', category: 'fruit', price_rm_per_100g: 1.09, price_is_estimated: false, price_available: true, pack_label: '1kg' },
  { food_id: 'SF090', name: 'banana', name_ms: 'pisang', category: 'fruit', price_rm_per_100g: 0.97, price_is_estimated: false, price_available: true, pack_label: '1kg' },
  { food_id: 'SF055', name: 'cabbage', name_ms: 'kubis', category: 'vegetables', price_rm_per_100g: 0.68, price_is_estimated: false, price_available: true, pack_label: '1kg' },
  { food_id: 'SF089', name: 'watermelon', name_ms: 'tembikai', category: 'fruit', price_rm_per_100g: 0.66, price_is_estimated: false, price_available: true, pack_label: '1kg' },
  { food_id: 'SF200', name: 'cheap other', name_ms: 'other', category: 'other', price_rm_per_100g: 0.2, price_is_estimated: false, price_available: true, pack_label: '1kg' },
];
const food = (id, category) => ({ food_id: id, name: id, name_ms: id, category, grams: 500, cost_rm: 5, price_rm_per_100g: 1, price_is_estimated: false, packs: 1, pack_label: '1kg' });

test('recipe-first V2 does not invent recommendations when the API returns no recipe opportunities', () => {
  const plan = {
    planner_version: 'recipe-first-v2',
    recipes: [{ recipe_id: 'tomato-egg', name: 'Tomato Egg Stir-Fry', occurrences: 3 }],
    recipe_allocations: [
      { recipe_id: 'tomato-egg', food_id: 'SF072' },
      { recipe_id: 'tomato-egg', food_id: 'SF018' },
    ],
    items: [food('SF072', 'vegetables'), food('SF018', 'protein')],
    suggestions: [],
  };
  const proposal = createPlanBasketProposal(plan, catalog, ['SF072']);
  assert.deepEqual(proposal.usuals.map((item) => item.productId), ['SF072', 'SF018']);
  assert.deepEqual(proposal.recommendations, []);
});

test('recipe-first V2 uses the generated basket when the user picked no foods', () => {
  const plan = {
    planner_version: 'recipe-first-v2',
    items: [food('SF110', 'carbohydrate')],
    recipe_opportunities: [],
    food_fallback_suggestions: [{
      food_id: 'SF022', group: 'protein', purchase_units: 1,
      purchase_kg: 1, estimated_cost_rm: 33.5, requires_swap: false,
    }],
    suggestions: [],
  };
  const prawn = { food_id: 'SF022', name: 'prawn', name_ms: 'udang', category: 'protein', pack_label: '1 kg' };
  const proposal = createPlanBasketProposal(plan, [...catalog, prawn], []);
  assert.deepEqual(proposal.usuals.map((item) => item.productId), ['SF110']);
  assert.deepEqual(proposal.recommendations.map((item) => item.productId), ['SF022']);
});

test('recipe-first V2 keeps purchased staple, protein, and vegetables in the week plan after a partial selection', () => {
  const plan = {
    planner_version: 'recipe-first-v2',
    items: [food('SF110', 'carbohydrate'), food('SF018', 'protein'), food('SF062', 'vegetables')],
    recipes: [{ recipe_id: 'rice-egg-spinach', name: 'Rice, Egg and Spinach', occurrences: 3 }],
    recipe_opportunities: [], suggestions: [],
  };

  const proposal = createPlanBasketProposal(plan, catalog, ['SF110']);
  assert.deepEqual(proposal.usuals.map((item) => item.productId), ['SF110', 'SF018', 'SF062']);
  assert.deepEqual(proposal.recommendations, []);
});

test('a three-meal V2 plan does not turn dozens of unpriced usual picks into Need', () => {
  const proteinIds = Array.from({ length: 16 }, (_, index) => `protein-${index}`);
  const unpricedIds = ['oats', ...proteinIds];
  const foods = [
    ...catalog,
    { food_id: 'oats', name: 'oats', category: 'carbohydrate', pack_label: '1 kg', pack_grams: 1000 },
    ...proteinIds.map((foodId) => ({ food_id: foodId, name: foodId, category: 'protein', pack_label: '500 g', pack_grams: 500 })),
  ];
  const plan = {
    planner_version: 'recipe-first-v2', requested_meals: 3, adults: 2, children: 0,
    items: [food('SF110', 'carbohydrate'), food('SF006', 'protein'), food('SF055', 'vegetables')],
    unpriced_food_ids: unpricedIds,
    recipe_opportunities: [], suggestions: [],
  };
  const proposal = createPlanBasketProposal(plan, foods, ['SF110', 'SF006', 'SF055', ...unpricedIds]);
  assert.ok(proposal.usuals.length <= 8);
  assert.ok(proposal.usuals.filter((item) => proteinIds.includes(item.productId)).length <= 2);
  assert.equal(proposal.usuals.length, 3);
  assert.deepEqual(proposal.recommendations, []);

  const accepted = createPlanBasketProposal(plan, foods, ['SF110', 'SF006', 'SF055', ...unpricedIds], ['protein-15']);
  assert.ok(accepted.usuals.some((item) => item.productId === 'protein-15'));
});

test('recipe-first V2 exposes selected staples absent from the priced recipe plan for a user decision', () => {
  const noodles = { food_id: 'SF109', name: 'yellow noodles', name_ms: 'mi kuning', category: 'carbohydrate', pack_label: '450 g' };
  const plan = {
    planner_version: 'recipe-first-v2',
    items: [food('SF110', 'carbohydrate'), food('SF018', 'protein'), food('SF062', 'vegetables')],
    unselected_picks: ['SF109'],
    recipe_opportunities: [], suggestions: [],
  };

  const proposal = createPlanBasketProposal(plan, [...catalog, noodles], ['SF110', 'SF109']);
  assert.deepEqual(proposal.usuals.map((item) => item.productId), ['SF110', 'SF018', 'SF062']);
  assert.deepEqual(proposal.deferredSelections, [{ productId: 'SF109', name: 'yellow noodles' }]);
  assert.ok(proposal.recommendations.some((item) => item.productId === 'SF109'), 'a deferred choice remains visible in the original Worth considering rows');
});

test('recipe and rotating fallback suggestions show egg trays as biji', () => {
  const egg = { ...catalog.find((item) => item.food_id === 'SF018'), pack_grams: 550 };
  const base = {
    planner_version: 'recipe-first-v2', items: [food('SF110', 'carbohydrate')], suggestions: [],
  };
  const opportunity = createPlanBasketProposal({
    ...base,
    recipe_opportunities: [{
      recipe_id: 'egg-rice', recipe_name: 'Egg Rice', additional_meals: 1, estimated_cost_rm: 6,
      missing_ingredients: [{ food_id: 'SF018', quantity_kg: 0.3, purchase_units: 1, purchase_kg: 0.55, estimated_cost_rm: 6, recipe_reuse_count: 1 }],
    }],
  }, [...catalog, egg], ['SF110']);
  assert.equal(opportunity.recipeOpportunities[0].items[0].suggestedQuantity, 10);
  assert.equal(opportunity.recipeOpportunities[0].items[0].unit, 'biji');

  const fallback = createPlanBasketProposal({
    ...base,
    recipe_opportunities: [],
    food_fallback_suggestions: [{ food_id: 'SF018', group: 'protein', purchase_units: 1, purchase_kg: 0.55, estimated_cost_rm: 6 }],
  }, [...catalog, egg], ['SF110']);
  assert.equal(fallback.recommendations[0].suggestedQuantity, 10);
  assert.equal(fallback.recommendations[0].unit, 'biji');
});

test('recipe-first V2 shows reviewed budget foods only when no recipe opportunity matches', () => {
  const prawn = { food_id: 'SF022', name: 'white prawn', name_ms: 'udang', category: 'protein', pack_label: '1 kg' };
  const plan = {
    planner_version: 'recipe-first-v2',
    recipes: [],
    items: [food('SF110', 'carbohydrate')],
    suggestions: [],
    recipe_opportunities: [],
    food_fallback_suggestions: [{
      food_id: 'SF022', group: 'protein', purchase_units: 1,
      purchase_kg: 1, estimated_cost_rm: 33.5, requires_swap: true,
    }],
  };
  const proposal = createPlanBasketProposal(plan, [...catalog, prawn], ['SF110']);
  assert.deepEqual(proposal.recommendations.map((item) => item.productId), ['SF022']);
  assert.equal(proposal.recommendations[0].suggestedQuantity, 1);
  assert.equal(proposal.recommendations[0].needsSpace, true);
  assert.match(proposal.recommendations[0].reason, /RM33\.50/);

  plan.recipe_opportunities = [{
    recipe_id: 'prawn-meal', recipe_name: 'Prawn Meal', additional_meals: 1,
    estimated_cost_rm: 33.5,
    missing_ingredients: [{
      food_id: 'SF022', purchase_kg: 1, recipe_reuse_count: 1,
      purchase_priority: 0,
    }],
  }];
  const recipeProposal = createPlanBasketProposal(plan, [...catalog, prawn], ['SF110']);
  assert.equal(recipeProposal.recipeOpportunities[0].name, 'Prawn Meal');
  assert.equal(recipeProposal.recipeOpportunities[0].items[0].productId, 'SF022');
  assert.deepEqual(recipeProposal.recommendations.map((item) => item.productId), ['SF022']);
  assert.equal(recipeProposal.recommendations[0].recipeId, 'prawn-meal');

  plan.recipe_opportunities = [];
  plan.food_fallback_suggestions = [{
    food_id: 'SF109', group: 'carbohydrate', purchase_units: 1,
    purchase_kg: 0.45, estimated_cost_rm: 1.88,
  }];
  const noodles = { food_id: 'SF109', name: 'noodles', name_ms: 'mi', category: 'carbohydrate', pack_label: '450 g', pack_grams: 450 };
  const [noodleIdea] = createPlanBasketProposal(plan, [...catalog, noodles], ['SF110']).recommendations;
  const accepted = applyOptimisticAddQuantity({ ...noodleIdea, source: 'recommendation', choice: 'need' }, [...catalog, noodles], 3);
  assert.equal(accepted.suggestedQuantity, 0.45, 'accepting keeps the budget-sized pack amount');
  assert.equal(accepted.minimumPurchaseKg, 0.45);
});

test('recipe-first V2 ranks reusable opportunity ingredients without duplicating week-plan foods', () => {
  const plan = {
    planner_version: 'recipe-first-v2',
    recipes: [],
    recipe_allocations: [],
    recipe_opportunities: [
      {
        recipe_id: 'potato-curry', recipe_name: 'Potato Curry', additional_meals: 3,
        estimated_cost_rm: 4,
        missing_ingredients: [
          { food_id: 'SF133', purchase_kg: 0.1, recipe_reuse_count: 4, purchase_priority: 4 },
          { food_id: 'SF057', purchase_kg: 1, recipe_reuse_count: 2, purchase_priority: 0 },
        ],
      },
      {
        recipe_id: 'potato-soup', recipe_name: 'Potato Soup', additional_meals: 3,
        estimated_cost_rm: 5,
        missing_ingredients: [
          { food_id: 'SF057', purchase_kg: 1, recipe_reuse_count: 2, purchase_priority: 0 },
        ],
      },
    ],
    items: [food('SF110', 'carbohydrate'), food('SFS1', 'protein')],
    suggestions: [],
  };
  const opportunityCatalog = [
    ...catalog,
    { food_id: 'SF057', name: 'potato', name_ms: 'kentang', category: 'vegetables', pack_label: '1 kg' },
    { food_id: 'SF133', name: 'curry powder', name_ms: 'serbuk kari', category: 'other', pack_label: '100 g' },
  ];

  const proposal = createPlanBasketProposal(plan, opportunityCatalog, ['SF110']);

  assert.deepEqual(proposal.usuals.map((item) => item.productId), ['SF110', 'SFS1']);
  assert.deepEqual(proposal.recipeOpportunities.map((item) => item.name), ['Potato Curry', 'Potato Soup']);
  assert.deepEqual(proposal.recipeOpportunities[0].items.map((item) => item.productId), ['SF133', 'SF057']);
  assert.deepEqual(proposal.recipeOpportunities[1].items.map((item) => item.productId), ['SF057']);
  assert.deepEqual(proposal.recommendations.map((item) => item.productId), ['SF133', 'SF057']);
  assert.equal(proposal.recommendations[0].recipeId, 'potato-curry');
});

test('recipe-first V2 shows every missing ingredient from three recipe opportunities', () => {
  const ids = ['SF301', 'SF302', 'SF303', 'SF304', 'SF305'];
  const plan = {
    planner_version: 'recipe-first-v2',
    recipes: [],
    recipe_allocations: [],
    recipe_opportunities: [
      {
        recipe_id: 'recipe-1', recipe_name: 'Recipe 1', additional_meals: 1,
        estimated_cost_rm: 2,
        missing_ingredients: [
          { food_id: 'SF301', purchase_kg: 0.1, estimated_cost_rm: 1, recipe_reuse_count: 1, purchase_priority: 0, price_is_estimated: false },
          { food_id: 'SF302', purchase_kg: 0.1, estimated_cost_rm: 1, recipe_reuse_count: 2, purchase_priority: 2, price_is_estimated: false },
        ],
      },
      {
        recipe_id: 'recipe-2', recipe_name: 'Recipe 2', additional_meals: 1,
        estimated_cost_rm: 2,
        missing_ingredients: [
          { food_id: 'SF302', purchase_kg: 0.1, estimated_cost_rm: 1, recipe_reuse_count: 2, purchase_priority: 2, price_is_estimated: false },
          { food_id: 'SF303', purchase_kg: 0.1, estimated_cost_rm: 1, recipe_reuse_count: 1, purchase_priority: 1, price_is_estimated: false },
        ],
      },
      {
        recipe_id: 'recipe-3', recipe_name: 'Recipe 3', additional_meals: 1,
        estimated_cost_rm: 2,
        missing_ingredients: [
          { food_id: 'SF304', purchase_kg: 0.1, estimated_cost_rm: 1, recipe_reuse_count: 1, purchase_priority: 0, price_is_estimated: false },
          { food_id: 'SF305', purchase_kg: 0.1, estimated_cost_rm: 1, recipe_reuse_count: 1, purchase_priority: 4, price_is_estimated: false },
        ],
      },
    ],
    items: [food('SF110', 'carbohydrate')],
    suggestions: [],
  };
  const opportunityCatalog = [
    ...catalog,
    ...ids.map((foodId) => ({
      food_id: foodId,
      name: foodId,
      name_ms: foodId,
      category: 'vegetables',
      pack_label: '100 g',
    })),
  ];

  const proposal = createPlanBasketProposal(plan, opportunityCatalog, ['SF110']);

  assert.equal(proposal.recipeOpportunities.length, 3);
  assert.deepEqual(
    new Set(proposal.recipeOpportunities.flatMap((recipe) => recipe.items.map((item) => item.productId))),
    new Set(ids),
    'each recipe offers all its missing ingredients',
  );
  assert.equal(proposal.recipeOpportunities[0].items.length, 2);
  assert.equal(proposal.recipeOpportunities[1].items.length, 2);
});

test('multi-ingredient recipe suggestions remain complete add-on bundles', () => {
  const plan = {
    planner_version: 'recipe-first-v2', items: [food('SF110', 'carbohydrate')], suggestions: [],
    recipe_opportunities: [{
      recipe_id: 'egg-spinach-rice', recipe_name: 'Egg Spinach Rice', additional_meals: 1,
      estimated_cost_rm: 9,
      missing_ingredients: [
        { food_id: 'SF018', purchase_units: 1, purchase_kg: 0.55, estimated_cost_rm: 6, recipe_reuse_count: 1 },
        { food_id: 'SF062', purchase_units: 1, purchase_kg: 1, estimated_cost_rm: 3, recipe_reuse_count: 1 },
      ],
    }],
  };
  const egg = { ...catalog.find((item) => item.food_id === 'SF018'), pack_grams: 550 };
  const proposal = createPlanBasketProposal(plan, [...catalog, egg], ['SF110']);

  assert.equal(proposal.recipeOpportunities.length, 1);
  assert.equal(proposal.recipeOpportunities[0].name, 'Egg Spinach Rice');
  assert.deepEqual(proposal.recipeOpportunities[0].items.map((item) => item.productId), ['SF018', 'SF062']);
  assert.equal(proposal.recipeOpportunities[0].items[0].unit, 'biji');
  assert.deepEqual(proposal.recommendations.map((item) => item.productId), ['SF018', 'SF062']);
  const acceptedEgg = {
    ...proposal.recipeOpportunities[0].items[0],
    source: 'recommendation', choice: 'need', recipeBundle: true,
  };
  assert.deepEqual(
    { q: applyOptimisticAddQuantity(acceptedEgg, [...catalog, egg], 3).suggestedQuantity,
      unit: applyOptimisticAddQuantity(acceptedEgg, [...catalog, egg], 3).unit },
    { q: 10, unit: 'biji' },
  );
});

test('uses the lower bound of a meal range and the exact custom meal count for V2', () => {
  const draft = {
    selectedRestrictions: [],
    customRestriction: '',
    weeklyBudget: 150,
    adults: 1,
    children: 2,
    planningLocation: null,
    selectedMealId: '10-14',
    customMealCount: null,
  };
  assert.equal(planRequestFromDraft(draft, [], []).target_meals, 10);
  assert.equal(planRequestFromDraft({ ...draft, selectedMealId: 'other', customMealCount: 12 }, [], []).target_meals, 12);
});

test('sends skipped basket foods as hard V2 exclusions', () => {
  const draft = {
    selectedRestrictions: [],
    customRestriction: '',
    weeklyBudget: 150,
    adults: 1,
    children: 0,
    planningLocation: null,
    selectedMealId: '6-9',
    customMealCount: null,
  };
  const basket = [{ productId: 'SF006', name: 'chicken', imageSource: null, suggestedQuantity: 1, unit: 'kg', source: 'usual', choice: 'skip' }];
  assert.deepEqual(planRequestFromDraft(draft, ['SF006'], [], [], [], basket).excludes, ['SF006']);
});

test('sends Have items as selected pantry weight while Skip remains excluded', () => {
  const draft = {
    selectedRestrictions: [],
    customRestriction: '',
    weeklyBudget: 150,
    adults: 1,
    children: 0,
    planningLocation: null,
    selectedMealId: '6-9',
    customMealCount: null,
  };
  const basket = [
    { productId: 'SF018', name: 'egg', imageSource: null, suggestedQuantity: 0.3, unit: 'kg', source: 'usual', choice: 'have' },
    { productId: 'SF006', name: 'chicken', imageSource: null, suggestedQuantity: 1, unit: 'kg', source: 'usual', choice: 'skip' },
  ];
  const request = planRequestFromDraft(draft, ['SF018', 'SF006'], [], [], [], basket);
  assert.deepEqual(request.selected_food_ids, ['SF018']);
  assert.deepEqual(request.pantry_stock, [{ food_id: 'SF018', grams: 300 }]);
  assert.deepEqual(request.excludes, ['SF006']);
});

test('converts a Have egg tray in biji to its reviewed pack mass for pantry planning', () => {
  const draft = {
    selectedRestrictions: [], customRestriction: '', weeklyBudget: 150,
    adults: 1, children: 0, planningLocation: null,
    selectedMealId: '6-9', customMealCount: null,
  };
  const basket = [{
    productId: 'SF018', name: 'chicken egg', imageSource: null,
    suggestedQuantity: 10, unit: 'biji', source: 'usual', choice: 'have',
  }];
  const egg = { ...catalog.find((item) => item.food_id === 'SF018'), pack_grams: 550 };
  const request = planRequestFromDraft(draft, ['SF018'], [egg], ['SF018'], [], basket);
  assert.deepEqual(request.pantry_stock, [{ food_id: 'SF018', grams: 550 }]);
});

test('allows ordinary week-plan quantities to rebalance while protecting a new add', () => {
  const draft = {
    selectedRestrictions: [],
    customRestriction: '',
    weeklyBudget: 100,
    adults: 1,
    children: 2,
    planningLocation: null,
    selectedMealId: '10-14',
    customMealCount: null,
  };
  const basket = [
    { productId: 'SF006', name: 'white prawn', imageSource: null, suggestedQuantity: 0.25, unit: 'kg', source: 'usual', choice: 'need' },
    { productId: 'SF018', name: 'egg', imageSource: null, suggestedQuantity: 10, unit: 'biji', source: 'recommendation', choice: 'need' },
  ];
  const foods = [
    { food_id: 'SF006', pack_grams: 250, pack_label: '250 g' },
    { food_id: 'SF018', pack_grams: 580, pack_label: '10 biji' },
  ];

  const request = planRequestFromDraft(
    draft,
    ['SF006', 'SF018'],
    foods,
    ['SF006', 'SF018'],
    [],
    basket,
  );

  assert.deepEqual(request.minimum_purchase_quantities, [{ food_id: 'SF018', purchase_kg: 0.58 }]);
});

test('accepting a budget food idea keeps its own purchase floor and allows existing foods to rebalance', () => {
  const draft = {
    selectedRestrictions: [], customRestriction: '', weeklyBudget: 200,
    adults: 2, children: 2, planningLocation: null,
    selectedMealId: '6-9', customMealCount: null,
  };
  const foods = [
    { food_id: 'SF002', name: 'beef', category: 'protein', pack_grams: 250, pack_label: '250 g', week_floor_g_per_person: 500 },
    { food_id: 'SF022', name: 'prawn', category: 'protein', pack_grams: 1000, pack_label: '1 kg', week_floor_g_per_person: 300 },
  ];
  const basket = [
    { productId: 'SF002', name: 'beef', imageSource: null, suggestedQuantity: 2, unit: 'kg', minimumPurchaseKg: 2, source: 'usual', choice: 'need' },
    { productId: 'SF022', name: 'prawn', imageSource: null, suggestedQuantity: 1, unit: 'kg', minimumPurchaseKg: 1, source: 'recommendation', choice: 'need', budgetFallback: true },
  ];
  const request = planRequestFromDraft(draft, ['SF002'], foods, ['SF002', 'SF022'], [], basket);
  assert.deepEqual(request.minimum_purchase_quantities, [{ food_id: 'SF022', purchase_kg: 1 }]);
  assert.deepEqual(request.fixed_purchase_quantities, []);
});

test('an explicitly protected quantity remains a minimum during rebalance', () => {
  const draft = {
    selectedRestrictions: [], customRestriction: '', weeklyBudget: 100,
    adults: 2, children: 0, planningLocation: null,
    selectedMealId: '6-9', customMealCount: null,
  };
  const basket = [{
    productId: 'SF110', name: 'rice', imageSource: null,
    suggestedQuantity: 2, unit: 'kg', source: 'usual', choice: 'need',
    protectedQuantity: true,
  }];
  const request = planRequestFromDraft(draft, ['SF110'], catalog, ['SF110'], [], basket);
  assert.deepEqual(request.minimum_purchase_quantities, [{ food_id: 'SF110', purchase_kg: 2 }]);
});

test('week plan contains only the user picks; the rest lands in worth considering', () => {
  const picks = ['SF110', 'SF002', 'SF018', 'SF062', 'SF088'];
  const plan = {
    items: [food('SF110', 'carbohydrate'), food('SF002', 'protein'), food('SF018', 'protein'), food('SF062', 'vegetables'), food('SF088', 'fruit'), food('SFS1', 'protein'), food('SF074', 'vegetables')],
    suggestions: [],
  };
  const proposal = createPlanBasketProposal(plan, catalog, picks);
  assert.deepEqual(proposal.usuals.map((i) => i.productId), picks);
  const recIds = proposal.recommendations.map((i) => i.productId);
  assert.ok(recIds.includes('SFS1'), 'solver extra item must be worth considering');
  assert.ok(!recIds.includes('SF002'), 'week plan pick must not duplicate into worth considering');
  // fillers bring vegetables/protein/fruit to >=3 listed per category
  const listed = [...proposal.usuals, ...proposal.recommendations];
  for (const cat of ['protein', 'vegetables', 'fruit']) {
    assert.ok(listed.filter((i) => catalog.find((f) => f.food_id === i.productId)?.category === cat).length >= 3, `${cat} filled to 3`);
  }
});

test('catalog fallback (INFEASIBLE, empty items) still caps the week plan at 3 per category', () => {
  // User rule 2026-09-14: a failed solve must NOT dump all picks into the
  // week plan - the SAME caps apply: >4-per-category keeps 3, overflow goes
  // to worth considering.
  const wideCatalog = [
    ...catalog,
    { food_id: 'SF111', name: 'chicken', name_ms: 'ayam', category: 'protein', price_rm_per_100g: 1.5, price_is_estimated: false, price_available: true, pack_label: '1kg' },
    { food_id: 'SF112', name: 'fish', name_ms: 'ikan', category: 'protein', price_rm_per_100g: 2.0, price_is_estimated: false, price_available: true, pack_label: '1kg' },
  ];
  const ids = ['SF002', 'SF018', 'SFS1', 'SF111', 'SF112'];
  const plan = { status: 'INFEASIBLE', items: [], suggestions: [], worth_considering: [worth('SF133', 'other', 'recipe_pairing')] };
  const proposal = createPlanBasketProposal(plan, wideCatalog, ids);
  assert.equal(proposal.usuals.length, 3, '5 protein picks -> 3 in the week plan');
  const recIds = proposal.recommendations.map((i) => i.productId);
  assert.equal(recIds.filter((id) => ids.includes(id)).length, 2, 'both overflow picks stay visible');
  assert.ok(recIds.includes('SF133'), 'worth recommendation still shown');
});

test('catalog fallback caps the week plan at 15 foods in total', () => {
  const categories = ['carbohydrate', 'protein', 'vegetables', 'fruit', 'other'];
  const ids = Array.from({ length: 17 }, (_, i) => `SF${String(i + 1).padStart(3, '0')}`);
  const catalogWide = [
    ...catalog,
    ...ids.filter((id) => !catalog.some((f) => f.food_id === id)).map((id, i) => ({
      food_id: id, name: id, name_ms: id, category: categories[i % categories.length],
      price_rm_per_100g: 1, price_is_estimated: false, price_available: true, pack_label: '1kg',
    })),
  ];
  const plan = { status: 'INFEASIBLE', items: [], suggestions: [] };
  const proposal = createPlanBasketProposal(plan, catalogWide, ids);
  assert.equal(proposal.usuals.length, 15);
  const recIds = proposal.recommendations.map((i) => i.productId);
  assert.equal(recIds.filter((id) => ids.includes(id)).length, 2, 'both total-cap overflows stay visible');
});

test('catalog fallback honours the universal 1000 g/ml purchase floor', () => {
  // User rule 2026-09-14 (restated): EVERY week-plan line totals >= 1000 g
  // or 1000 ml - solids, per-piece and liquids alike. The fallback builds
  // catalogue picks at ceil(1000 / pack_grams) packs, mirroring the backend
  // pack_min_packs floor. 2026-09-16 user rule: gram-denominated totals
  // display as kg.
  const floorCatalog = [
    { food_id: 'SF300', name: 'tofu', name_ms: 'tahu', category: 'protein', price_rm_per_100g: 0.40, price_is_estimated: false, price_available: true, pack_label: '300 g', pack_grams: 300 },
    { food_id: 'SF301', name: 'egg', name_ms: 'telur', category: 'protein', price_rm_per_100g: 0.96, price_is_estimated: false, price_available: true, pack_label: '10 biji', pack_grams: 580 },
    { food_id: 'SF302', name: 'apple', name_ms: 'epal', category: 'fruit', price_rm_per_100g: 1.11, price_is_estimated: false, price_available: true, pack_label: '1 biji', pack_grams: 180 },
    { food_id: 'SF303', name: 'oil', name_ms: 'minyak', category: 'other', price_rm_per_100g: 1.20, price_is_estimated: false, price_available: true, pack_label: '500 ml', pack_grams: 500 },
  ];
  const plan = { status: 'INFEASIBLE', items: [], suggestions: [] };
  const proposal = createPlanBasketProposal(plan, floorCatalog, ['SF300', 'SF301', 'SF302', 'SF303']);
  const byId = Object.fromEntries(proposal.usuals.map((i) => [i.productId, i]));
  assert.equal(byId.SF300.suggestedQuantity, 1.2, 'tofu 300 g -> 4 packs = 1.2 kg');
  assert.equal(byId.SF300.unit, 'kg');
  assert.equal(byId.SF301.suggestedQuantity, 20, 'egg tray 580 g -> 2 packs = 20 biji');
  assert.equal(byId.SF301.unit, 'biji');
  assert.equal(byId.SF302.suggestedQuantity, 6, 'apple 180 g -> 6 pieces = 1080 g');
  assert.equal(byId.SF303.suggestedQuantity, 1000, 'oil 500 ml -> 2 packs = 1000 ml');
  assert.equal(byId.SF303.unit, 'ml');
});

test('approximate "+-" pack labels multiply out as kg (2026-09-16 unit rule)', () => {
  // Wet-market approximate-weight packs ("+-450g"): the number is real, so
  // they multiply out like any gram label and display as kg; a "+-" label
  // without a leading number reads "约 <label>"; ml/biji are untouched.
  const approxCatalog = [
    { food_id: 'SF400', name: 'kuey teow', name_ms: 'kuey teow', category: 'carbohydrate', price_rm_per_100g: 0.40, price_is_estimated: false, price_available: true, pack_label: '+-450g', pack_grams: 450 },
    { food_id: 'SF401', name: 'bundle thing', name_ms: 'bundle', category: 'other', price_rm_per_100g: 1.0, price_is_estimated: false, price_available: true, pack_label: '+- bundle', pack_grams: 500 },
    { food_id: 'SF402', name: 'santan', name_ms: 'santan', category: 'other', price_rm_per_100g: 0.35, price_is_estimated: false, price_available: true, pack_label: '200 ml', pack_grams: 200 },
  ];
  const plan = { status: 'INFEASIBLE', items: [], suggestions: [] };
  const proposal = createPlanBasketProposal(plan, approxCatalog, ['SF400', 'SF401', 'SF402']);
  const byId = Object.fromEntries(proposal.usuals.map((i) => [i.productId, i]));
  // floor 1000 g / 450 g pack = 3 packs = 1350 g -> 1.35 kg
  assert.deepEqual({ q: byId.SF400.suggestedQuantity, u: byId.SF400.unit }, { q: 1.35, u: 'kg' });
  // non-numeric "+-" label cannot be multiplied -> 约
  assert.equal(byId.SF401.unit, '约 bundle');
  assert.equal(byId.SF401.suggestedQuantity, 2, 'floor 1000 g / 500 g = 2 packs');
  // liquid stays ml
  assert.deepEqual({ q: byId.SF402.suggestedQuantity, u: byId.SF402.unit }, { q: 1000, u: 'ml' });
});

test('App keeps budget feedback at confirm time only; the fallback lives in the proposal', () => {
  const appSource = fs.readFileSync(new URL('../../App.tsx', import.meta.url), 'utf8');
  assert.doesNotMatch(appSource, /catalogFallbackUsuals/, 'fallback moved into createPlanBasketProposal');
  assert.match(appSource, /if \(fresh\) \{/);
  // The over-budget message must quote the BASKET's own minimum cost
  // (total_cost_rm), never min_budget_for_energy_rm - that field is the
  // budget needed to cover the week's energy, a different number whose
  // misquote told users their foods cost more than they do.
  assert.match(appSource, /const basketCost = fresh\.total_cost_rm \?\? 0;/);
  assert.doesNotMatch(appSource, /min_budget_for_energy_rm \?\? fresh\.total_cost_rm/);
  // 2026-09-14 user rule (restated): nutrition is NOT gated at confirm.
  // The only hard gate is genuine unaffordability - basket minimum cost
  // over budget. An energy-short but within-budget INFEASIBLE result
  // (days_coverable < days) must pass straight to price check.
  assert.match(appSource, /if \(basketCost > budget\) \{/);
  assert.doesNotMatch(appSource, /energyBudget/, 'nutrition gap must not block the price-check gate');
});

test('more than 4 picks in one category: 3 in week plan, overflow in worth considering', () => {
  const ids = ['SF002', 'SF018', 'SFS1', 'SF110', 'SF200'];
  const capped = createPlanBasketProposal(
    { items: ids.map((id) => food(id, 'protein')), suggestions: [] },
    catalog,
    ids,
  );
  assert.equal(capped.usuals.length, 3);
  assert.equal(capped.recommendations.filter((i) => ids.includes(i.productId)).length, 2);
});

test('overloaded selections keep at most 3 picks per main category even when marked curated', () => {
  const categories = ['carbohydrate', 'protein', 'vegetables'];
  const ids = Array.from({ length: 33 }, (_, i) => `heavy-${i}`);
  const plan = {
    curated_selection: true,
    items: ids.map((id, i) => food(id, categories[i % categories.length])),
    suggestions: [],
  };
  const proposal = createPlanBasketProposal(plan, catalog, ids);
  const counts = proposal.usuals.reduce((result, item) => {
    const category = categories[Number(item.productId.split('-')[1]) % categories.length];
    result[category] = (result[category] ?? 0) + 1;
    return result;
  }, {});

  assert.deepEqual(counts, { carbohydrate: 3, protein: 3, vegetables: 3 });
  assert.equal(proposal.usuals.length, 9);
});

test('solo household (1 adult): only 2 picks per category stay in the week plan', () => {
  // 2026-09-15 user decision: a one-person household cooks 1-2 dishes per
  // category, so >4 picks in one category keeps 2 (not 3); the total cap
  // already scales by the household table (12 solo since W5 2026-09-16).
  const ids = ['SF002', 'SF018', 'SFS1', 'SF110', 'SF200'];
  const capped = createPlanBasketProposal(
    { items: ids.map((id) => food(id, 'protein')), suggestions: [], adults: 1, children: 0 },
    catalog,
    ids,
  );
  assert.equal(capped.usuals.length, 2, '5 protein picks at 1A -> 2 in the week plan');
  assert.equal(capped.recommendations.filter((i) => ids.includes(i.productId)).length, 3);
});

const worth = (foodId, category, angle = 'nutrient_gap') => ({
  food_id: foodId,
  name: foodId,
  name_ms: foodId,
  category,
  angle,
  reason_en: 'high protein',
  reason_ms: 'kaya protein',
  est_cost_rm: 3.6,
});

test('backend worth_considering takes over the recommendation section', () => {
  const picks = ['SF110', 'SF002', 'SF062'];
  const plan = {
    items: [food('SF110', 'carbohydrate'), food('SF002', 'protein'), food('SF062', 'vegetables')],
    suggestions: [],
    worth_considering: [
      worth('SF018', 'protein'),
      { ...worth('SF133', 'other', 'recipe_pairing'), reason_en: 'curry base', reason_ms: 'asas kari', est_cost_rm: 6.35 },
    ],
  };
  const proposal = createPlanBasketProposal(plan, catalog, picks);
  assert.deepEqual(proposal.usuals.map((i) => i.productId), picks);
  const recIds = proposal.recommendations.map((i) => i.productId);
  assert.ok(recIds.includes('SF018'), 'worth item leads the recommendations');
  assert.ok(recIds.includes('SF133'));
  assert.ok(!recIds.includes('SFS1'), 'local filler heuristic must not run alongside worth items');
  const egg = proposal.recommendations.find((i) => i.productId === 'SF018');
  assert.match(egg.reason, /high protein/);
  assert.match(egg.reason, /kaya protein/);
  assert.match(egg.reason, /RM3\.60/);
});

test('worth items never duplicate a week-plan pick', () => {
  const picks = ['SF110', 'SF002'];
  const plan = {
    items: [food('SF110', 'carbohydrate'), food('SF002', 'protein')],
    suggestions: [],
    worth_considering: [worth('SF002', 'protein'), worth('SF018', 'protein')],
  };
  const proposal = createPlanBasketProposal(plan, catalog, picks);
  const recIds = proposal.recommendations.map((i) => i.productId);
  assert.ok(!recIds.includes('SF002'), 'picked food must not be re-recommended');
  assert.ok(recIds.includes('SF018'));
});

test('missing worth_considering field keeps the legacy local ranking', () => {
  const picks = ['SF110', 'SF002', 'SF062', 'SF088'];
  const plan = {
    items: [food('SF110', 'carbohydrate'), food('SF002', 'protein'), food('SF062', 'vegetables'), food('SF088', 'fruit'), food('SFS1', 'protein')],
    suggestions: [],
  };
  const proposal = createPlanBasketProposal(plan, catalog, picks);
  assert.ok(proposal.recommendations.some((i) => i.productId === 'SFS1'));
});

test('worth mode: the week plan still caps at 3 per category - overflow stays visible', () => {
  // 2026-09-14 user rule (final): even with worth_considering present, a
  // category where the user ticked more than 4 picks keeps only 3 in the week
  // plan; the overflow picks move to "Worth considering" (never vanish).
  const ids = ['SF002', 'SF018', 'SFS1', 'SF110', 'SF200'];
  const plan = {
    items: ids.map((id) => food(id, 'protein')),
    suggestions: [],
    worth_considering: [worth('SF133', 'other', 'recipe_pairing')],
  };
  const proposal = createPlanBasketProposal(plan, catalog, ids);
  assert.equal(proposal.usuals.length, 3, '5 protein picks -> 3 in the week plan');
  const recIds = proposal.recommendations.map((i) => i.productId);
  assert.ok(recIds.includes('SF133'), 'worth recommendation still shown');
  const overflow = proposal.recommendations.filter((i) => ids.includes(i.productId));
  assert.equal(overflow.length, 2, 'both overflow picks stay visible');
});

test('week plan is capped at 15 foods in total - extras overflow into worth considering', () => {
  // 2026-09-14 user rule (final): the whole week plan holds at most 15 foods.
  // 17 picks spread across categories (<=4 per category, so no per-category
  // cap fires) -> 15 in the week plan, 2 overflow.
  const categories = ['carbohydrate', 'protein', 'vegetables', 'fruit', 'other'];
  const ids = Array.from({ length: 17 }, (_, i) => `SF${String(i + 1).padStart(3, '0')}`);
  const plan = {
    items: ids.map((id, i) => food(id, categories[i % categories.length])),
    suggestions: [],
  };
  const proposal = createPlanBasketProposal(plan, catalog, ids);
  assert.equal(proposal.usuals.length, 15);
  const recIds = proposal.recommendations.map((i) => i.productId);
  assert.equal(recIds.filter((id) => ids.includes(id)).length, 2, 'both total-cap overflows stay visible');
});

test('accepted picks do not vanish when the proposal rebuilds from the posted set', () => {
  // Regression (2026-09-14): the proposal was rebuilt with the Q3 tick list,
  // so an accepted recommendation (in the posted set, not the tick list) fell
  // into the skipped "solver extras" branch and disappeared. The pick set
  // passed in is the POSTED selection (ticks + accepted), so it must land in
  // the week plan.
  const picks = ['SF110', 'SF002', 'SF018'];   // ticks + accepted egg
  const plan = {
    items: [food('SF110', 'carbohydrate'), food('SF002', 'protein'), food('SF018', 'protein')],
    suggestions: [],
    worth_considering: [worth('SF133', 'other', 'recipe_pairing')],
  };
  const proposal = createPlanBasketProposal(plan, catalog, picks);
  assert.deepEqual(proposal.usuals.map((i) => i.productId), picks);
});

test('worth recommendations carry real purchase units, never "item"', () => {
  const picks = ['SF110', 'SF002', 'SF062'];
  const plan = {
    items: [food('SF110', 'carbohydrate'), food('SF002', 'protein'), food('SF062', 'vegetables')],
    suggestions: [],
    worth_considering: [
      { ...worth('SF018', 'protein'), pack_label: '10 biji' },
      { ...worth('SF002B', 'protein'), by_weight: true, pack_label: '25 g' },
      worth('SF133', 'other'),   // not in catalogue and no pack info -> 'pack'
    ],
  };
  const proposal = createPlanBasketProposal(plan, catalog, picks);
  const byId = Object.fromEntries(proposal.recommendations.map((i) => [i.productId, i]));
  // 2026-09-17 v5-6a: pack units display as TOTALS - "10 biji" reads as
  // quantity 10 + unit biji (never "1 10 biji").
  assert.equal(byId.SF018.unit, 'biji');
  assert.equal(byId.SF018.suggestedQuantity, 10);
  // 2026-09-16 user rule: by-weight recs quote the 250 g counter unit as kg.
  assert.equal(byId.SF002B.unit, 'kg');
  assert.equal(byId.SF002B.suggestedQuantity, 0.25);
  assert.equal(byId.SF133.unit, 'pack');
});


test('optimistic add displays the universal 1000 g/ml floor until the re-solve', () => {
  // 2026-09-15 user rule: accepting a worth-considering item must enter the
  // week plan IMMEDIATELY at the purchase floor (no debounce + re-solve wait);
  // the display mirrors the fallback floor: ceil(1000/pack_grams) packs
  // multiplied out, by-weight counter items at 1000 g, unknown packs kept.
  const floorCatalog = [
    { food_id: 'SF300', name: 'tofu', name_ms: 'tahu', category: 'protein', price_rm_per_100g: 0.40, price_is_estimated: false, price_available: true, pack_label: '300 g', pack_grams: 300 },
    { food_id: 'SF301', name: 'egg', name_ms: 'telur', category: 'protein', price_rm_per_100g: 0.96, price_is_estimated: false, price_available: true, pack_label: '10 biji', pack_grams: 580 },
    { food_id: 'SF303', name: 'oil', name_ms: 'minyak', category: 'other', price_rm_per_100g: 1.20, price_is_estimated: false, price_available: true, pack_label: '500 ml', pack_grams: 500 },
    { food_id: 'SF304', name: 'rice', name_ms: 'beras', category: 'carbohydrate', price_rm_per_100g: 0.34, price_is_estimated: false, price_available: true, pack_label: '2 kg', pack_grams: 2000 },
  ];
  const draftItem = (productId, suggestedQuantity, unit) => ({
    productId,
    name: productId,
    imageSource: null,
    suggestedQuantity,
    unit,
    source: 'recommendation',
    choice: 'need',
  });

  const tofu = applyOptimisticAddQuantity(draftItem('SF300', 1, '300 g'), floorCatalog);
  assert.deepEqual({ q: tofu.suggestedQuantity, u: tofu.unit }, { q: 1.2, u: 'kg' }, 'tofu 300 g -> 4 packs = 1.2 kg');

  const egg = applyOptimisticAddQuantity(draftItem('SF301', 1, '10 biji'), floorCatalog);
  assert.deepEqual({ q: egg.suggestedQuantity, u: egg.unit }, { q: 20, u: 'biji' }, 'egg tray 580 g -> 2 packs = 20 biji');

  const oil = applyOptimisticAddQuantity(draftItem('SF303', 1, '500 ml'), floorCatalog);
  assert.deepEqual({ q: oil.suggestedQuantity, u: oil.unit }, { q: 1000, u: 'ml' }, 'oil 500 ml -> 2 packs = 1000 ml');

  const rice = applyOptimisticAddQuantity(draftItem('SF304', 1, '2 kg'), floorCatalog);
  assert.deepEqual({ q: rice.suggestedQuantity, u: rice.unit }, { q: 2, u: 'kg' }, 'rice 2 kg pack already covers the floor -> 1 pack = 2 kg');

  const byWeight = applyOptimisticAddQuantity(draftItem('SF002B', 250, 'g'), floorCatalog);
  assert.deepEqual({ q: byWeight.suggestedQuantity, u: byWeight.unit }, { q: 1, u: 'kg' }, 'by-weight counter item -> 1 kg');

  const unknown = applyOptimisticAddQuantity(draftItem('SF133', 1, 'pack'), floorCatalog);
  assert.deepEqual({ q: unknown.suggestedQuantity, u: unknown.unit }, { q: 1, u: 'pack' }, 'no pack data -> catalogue placeholder kept');
});


test('worth section order: nutrient gap, your picks, pairings, upgrades (2026-09-16)', () => {
  // User decision: the worth section leads with nutrient-gap recommendations,
  // then the user's OWN picks (demoted budget_fit + overflow picks), then
  // recipe pairings, then health upgrades - demoted picks must NOT lead.
  const picks = ['SF110', 'SF002', 'SF062', 'SF900'];
  const plan = {
    items: [food('SF110', 'carbohydrate'), food('SF002', 'protein'), food('SF062', 'vegetables')],
    suggestions: [],
    worth_considering: [
      { ...worth('SF900', 'protein', 'budget_fit'), pack_label: '1 kg' },
      worth('SF133', 'other', 'recipe_pairing'),
      worth('SF018', 'protein', 'nutrient_gap'),
      worth('SF195', 'carbohydrate', 'health_upgrade'),
    ],
  };
  const proposal = createPlanBasketProposal(plan, catalog, picks);
  const recIds = proposal.recommendations.map((i) => i.productId);
  assert.deepEqual(recIds, ['SF018', 'SF900', 'SF133', 'SF195'],
    'nutrient_gap -> your picks (budget_fit/overflow) -> recipe_pairing -> health_upgrade');
});

test('staple carbs always win the carbohydrate week-plan slots (2026-09-16)', () => {
  // User decision: within the carbohydrate class the rice/noodle/bread
  // family takes the week-plan slots FIRST - a solver response order that
  // lists flour ahead of rice must not push the rice into Worth considering.
  // Solver order deliberately puts BOTH flours ahead of the rice: the old
  // keep-in-order cap kept [noodles, vermicelli, wheat flour] and overflowed
  // the RICE.
  const ids = ['SF109', 'SF114', 'SF111', 'SF117', 'SF110'];
  const named = (id, name) => ({ ...food(id, 'carbohydrate'), name });
  const plan = {
    items: [
      named('SF109', 'yellow noodles'),
      named('SF114', 'rice vermicelli'),
      named('SF111', 'wheat flour'),
      named('SF117', 'self-raising flour'),
      named('SF110', 'white rice (raw)'),
    ],
    suggestions: [],
  };
  const proposal = createPlanBasketProposal(plan, catalog, ids);
  assert.equal(proposal.usuals.length, 3, '5 carb picks -> 3 in the week plan');
  const usualIds = proposal.usuals.map((i) => i.productId);
  assert.ok(usualIds.includes('SF110'), 'the RICE staple must keep its week-plan slot');
  assert.ok(!usualIds.includes('SF111'), 'wheat flour overflows');
  assert.ok(!usualIds.includes('SF117'), 'self-raising flour overflows');
  const recIds = proposal.recommendations.map((i) => i.productId);
  assert.ok(recIds.includes('SF111') && recIds.includes('SF117'),
    'both flour overflows stay visible in worth considering');
});

test('habit_picks mirror the endorsed picks: skipped ticks out, added-back worth items in (2026-09-16)', () => {
  // User decision (worth-Add loop fix): habit_picks = the original ticks
  // MINUS the ones the user skipped PLUS the worth/manual items they flipped
  // back to Need - the solver's demote domain must match what the user
  // actually stands behind on a re-post.
  const draft = {
    selectedRestrictions: [],
    customRestriction: '',
    weeklyBudget: 200,
    adults: 2,
    children: 0,
    planningLocation: null,
    selectedMealId: '6-9',
    customMealCount: null,
  };
  const ticks = ['SF110', 'SF002', 'SF018'];
  const item = (productId, source, choice) => ({
    productId, name: productId, imageSource: null,
    suggestedQuantity: 1, unit: 'kg', source, choice,
  });

  // No basket draft (the initial Q3 build): every tick is endorsed.
  const initial = planRequestFromDraft(draft, ticks, catalog, ticks, []);
  assert.deepEqual(initial.habit_picks, ticks);

  // The user skipped the beef; the egg is untouched.
  const skipped = planRequestFromDraft(draft, ticks, catalog, ticks, [], [
    item('SF110', 'usual', 'need'),
    item('SF002', 'usual', 'skip'),
    item('SF018', 'usual', 'need'),
  ]);
  assert.deepEqual(skipped.habit_picks, ['SF110', 'SF018'],
    'a skipped tick leaves the demote domain');

  // The user added back a demoted protein (worth -> need) that is NOT an
  // original tick, and skipped nothing: it joins the endorsed picks.
  const addedBack = planRequestFromDraft(
    draft, ticks, catalog, [...ticks, 'SF003'], [], [
      item('SF110', 'usual', 'need'),
      item('SF002', 'usual', 'need'),
      item('SF018', 'usual', 'need'),
      item('SF003', 'recommendation', 'need'),
    ]);
  assert.deepEqual(addedBack.habit_picks, [...ticks, 'SF003'],
    'an added-back worth item joins the endorsed picks');

  // Both at once: skip out + add back in.
  const both = planRequestFromDraft(
    draft, ticks, catalog, ['SF110', 'SF018', 'SF003'], [], [
      item('SF110', 'usual', 'need'),
      item('SF002', 'usual', 'skip'),
      item('SF018', 'usual', 'need'),
      item('SF003', 'recommendation', 'need'),
    ]);
  assert.deepEqual(both.habit_picks, ['SF110', 'SF018', 'SF003']);
});


test('curated response is not re-capped: every solver-selected pick stays in the week plan (2026-09-17)', () => {
  // Step 2 (A3): when the backend curated the ticks (curated_selection), the
  // solver's item set IS the final curation - the 15-kind cap must NOT push a
  // solver-selected pick back into worth considering.
  const categories = ['carbohydrate', 'protein', 'vegetables', 'fruit', 'other'];
  const ids = Array.from({ length: 16 }, (_, i) => `SF${String(i + 1).padStart(3, '0')}`);
  const plan = {
    items: ids.map((id, i) => food(id, categories[i % categories.length])),
    suggestions: [],
    curated_selection: true,
    unselected_picks: [],
    worth_considering: [worth('SF133', 'other', 'nutrient_gap')],
  };
  const proposal = createPlanBasketProposal(plan, catalog, ids);
  assert.deepEqual(proposal.usuals.map((i) => i.productId), ids,
    'all 16 curated solver picks stay in the week plan (no client-side cap)');
  assert.ok(proposal.recommendations.some((i) => i.productId === 'SF133'));
});

test('curated drops (unselected_picks) render via the backend worth items, never duplicated (2026-09-17)', () => {
  // The backend appends each unselected tick as a budget_fit worth item with
  // the "add back ~RM X · <tag>" reason; the client must NOT add a second
  // row from its overflow/dropped-pick pass.
  const ticks = ['SF110', 'SF002', 'SF018', 'SF062'];
  const plan = {
    items: [food('SF110', 'carbohydrate'), food('SF018', 'protein')],
    suggestions: [],
    curated_selection: true,
    unselected_picks: ['SF002', 'SF062'],
    worth_considering: [
      { ...worth('SF002', 'protein', 'budget_fit'), reason_en: 'Over budget at minimum purchase — add back ~RM 8.75 · Protein-rich' },
      { ...worth('SF062', 'vegetables', 'budget_fit'), reason_en: 'Over budget at minimum purchase — add back ~RM 5.70 · Leafy greens' },
    ],
    pick_reasons: {
      SF110: { en: 'Staple energy', ms: 'Tenaga utama' },
      SF018: { en: 'Cheap protein', ms: 'Protein murah' },
    },
  };
  const proposal = createPlanBasketProposal(plan, catalog, ticks);
  assert.deepEqual(proposal.usuals.map((i) => i.productId), ['SF110', 'SF018']);
  const sf002Rows = proposal.recommendations.filter((i) => i.productId === 'SF002');
  assert.equal(sf002Rows.length, 1, 'curated drop appears exactly once (backend worth item)');
  assert.match(sf002Rows[0].reason, /Over budget at minimum purchase/,
    'the backend add-back copy wins over the generic dropped-pick copy');
});

test('pick_reasons retire the hardcoded overflow copy for capped picks (2026-09-17)', () => {
  // Overflow picks (beyond-cap, non-curated) show the backend's curated
  // advantage tag when pick_reasons is present; older payloads without the
  // field keep the local fallback copy.
  const ids = ['SF002', 'SF018', 'SFS1', 'SF110', 'SF200'];
  const plan = {
    items: ids.map((id) => food(id, 'protein')),
    suggestions: [],
    worth_considering: [],
    pick_reasons: {
      SF002: { en: 'Iron-rich', ms: 'Kaya zat besi' },
      SF018: { en: 'Cheap protein', ms: 'Protein murah' },
      SFS1: { en: 'Omega-3 source', ms: 'Sumber omega-3' },
      SF110: { en: 'Staple energy', ms: 'Tenaga utama' },
      SF200: { en: 'Pantry basic', ms: 'Asas dapur' },
    },
  };
  const proposal = createPlanBasketProposal(plan, catalog, ids);
  assert.equal(proposal.usuals.length, 3, 'non-curated caps still apply');
  const overflow = proposal.recommendations.filter((i) => ids.includes(i.productId));
  assert.equal(overflow.length, 2, 'both overflow picks stay visible');
  for (const row of overflow) {
    assert.match(row.reason, / · /, `overflow reason uses the backend tag pair: ${row.reason}`);
    assert.doesNotMatch(row.reason, /usual picks/i, 'hardcoded copy retired when pick_reasons present');
  }
  // Older payload without pick_reasons -> generic copy survives (solver-extra
  // or dropped-pick copy, whichever path produced the row).
  const legacy = createPlanBasketProposal(
    { items: ids.map((id) => food(id, 'protein')), suggestions: [], worth_considering: [] },
    catalog, ids);
  const legacyOverflow = legacy.recommendations.filter((i) => ids.includes(i.productId));
  assert.ok(legacyOverflow.every((i) => !/ · /.test(i.reason)),
    'no pick_reasons -> no tag pair, fallback copy stands');
});
