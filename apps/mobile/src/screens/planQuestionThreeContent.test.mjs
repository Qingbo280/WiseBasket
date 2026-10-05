import test from 'node:test';
import assert from 'node:assert/strict';
import {
  getProductsForCategory,
  getVisibleProducts,
  getSelectedSummary,
  getPlanQuestionThreeProducts,
  isBuildBasketDisabled,
  mapCatalogFoodToQuestionThreeProduct,
  PLAN_QUESTION_THREE_CATEGORIES,
  PLAN_QUESTION_THREE_DEFAULTS,
  setPlanQuestionThreeProducts,
  toggleProductSelection,
  foodMatchesRestrictionText,
} from './planQuestionThreeContent.ts';

test('Other restriction matches common plural ingredient names in plan and recipes', () => {
  assert.equal(foodMatchesRestrictionText('Peanut Butter', 'no peanuts'), true);
  assert.equal(foodMatchesRestrictionText('Chicken egg', 'avoid eggs'), true);
  assert.equal(foodMatchesRestrictionText('White rice', 'no peanuts'), false);
});

test('keeps Question 3 on the approved categories with Carbs active and nothing selected', () => {
  assert.deepEqual(PLAN_QUESTION_THREE_CATEGORIES.map(({ label }) => ({ label })), [
    { label: 'Carbs' },
    { label: 'Protein' },
    { label: 'Vege' },
    { label: 'Fruit' },
    { label: 'Other' },
  ]);
  assert.deepEqual(PLAN_QUESTION_THREE_DEFAULTS, {
    selectedCategory: 'carbs',
    selectedProductIds: [],
  });
});

test('starts with an empty live catalog until the backend catalogue arrives', () => {
  setPlanQuestionThreeProducts([]);
  assert.equal(getPlanQuestionThreeProducts().length, 0);
  assert.equal(getProductsForCategory('protein').length, 0);
});

test('groups the live backend catalogue by questionnaire category', () => {
  setPlanQuestionThreeProducts([
    { id: 'SF110', name: 'White rice', category: 'carbs', imageSource: null },
    { id: 'SF018', name: 'Eggs', category: 'protein', imageSource: null },
    { id: 'SF055', name: 'Cabbage', category: 'vege', imageSource: null },
    { id: 'SF089', name: 'Watermelon', category: 'fruit', imageSource: null },
    { id: 'SF118', name: 'Sugar', category: 'other', imageSource: null },
  ]);

  assert.deepEqual(
    Object.fromEntries(
      PLAN_QUESTION_THREE_CATEGORIES.map((category) => [
        category.id,
        getProductsForCategory(category.id).map((product) => product.id),
      ]),
    ),
    {
      carbs: ['SF110'],
      protein: ['SF018'],
      vege: ['SF055'],
      fruit: ['SF089'],
      other: ['SF118'],
    },
  );
});

test('maps backend catalogue foods onto questionnaire products', () => {
  const mapped = mapCatalogFoodToQuestionThreeProduct({
    food_id: 'SF002',
    name: 'beef',
    name_ms: 'daging lembu',
    category: 'protein',
    allergen_tags: [],
    exclusion_codes: [],
    price_rm_per_100g: 1.23,
    price_unit: 'RM/100g',
    price_available: true,
    price_is_estimated: false,
    price_source: 'PRICECATCHER',
    price_updated: '2026-09-10',
    nutrients: {},
    nutrients_unit: 'per_100g',
    nutrition_available: true,
    nutrition_source: 'USDA',
    nutrition_updated: '2026-09-10',
    pack_grams: null,
    pack_label: '',
  });

  assert.equal(mapped.id, 'SF002');
  assert.equal(mapped.name, 'Beef');
  assert.equal(mapped.category, 'protein');
  assert.equal(mapped.imageSource, null); // no ASSET_BASE_URL under test
});

test('falls back to Other for unknown backend categories', () => {
  const mapped = mapCatalogFoodToQuestionThreeProduct({
    food_id: 'SF999',
    name: 'mystery',
    name_ms: 'mystery',
    category: 'beverage',
    allergen_tags: [],
    exclusion_codes: [],
    price_rm_per_100g: null,
    price_unit: 'RM/100g',
    price_available: false,
    price_is_estimated: false,
    price_source: '',
    price_updated: '',
    nutrients: {},
    nutrients_unit: 'per_100g',
    nutrition_available: false,
    nutrition_source: '',
    nutrition_updated: '',
    pack_grams: null,
    pack_label: '',
  });

  assert.equal(mapped.category, 'other');
});

test('searches across the whole live catalogue regardless of category', () => {
  setPlanQuestionThreeProducts([
    { id: 'SF110', name: 'White rice', category: 'carbs', imageSource: null },
    { id: 'SF018', name: 'Eggs', category: 'protein', imageSource: null },
    { id: 'SF055', name: 'Cabbage', category: 'vege', imageSource: null },
  ]);

  assert.deepEqual(getVisibleProducts('fruit', 'rice').map((product) => product.id), ['SF110']);
  assert.equal(getVisibleProducts('carbs', '').length, 1);
  assert.equal(getVisibleProducts('carbs', 'xyz').length, 0);
});

test('toggles selections and summarizes the first four picks', () => {
  setPlanQuestionThreeProducts([
    { id: 'SF001', name: 'A', category: 'carbs', imageSource: null },
    { id: 'SF002', name: 'B', category: 'protein', imageSource: null },
    { id: 'SF003', name: 'C', category: 'vege', imageSource: null },
    { id: 'SF004', name: 'D', category: 'fruit', imageSource: null },
    { id: 'SF005', name: 'E', category: 'other', imageSource: null },
  ]);

  let selected = toggleProductSelection([], 'SF001');
  selected = toggleProductSelection(selected, 'SF002');
  selected = toggleProductSelection(selected, 'SF003');
  selected = toggleProductSelection(selected, 'SF004');
  selected = toggleProductSelection(selected, 'SF005');

  const summary = getSelectedSummary(selected);
  assert.equal(summary.count, 5);
  assert.equal(summary.overflowCount, 1);
  assert.deepEqual(summary.visibleProducts.map((product) => product.id), [
    'SF001',
    'SF002',
    'SF003',
    'SF004',
  ]);

  assert.deepEqual(toggleProductSelection(selected, 'SF003'), ['SF001', 'SF002', 'SF004', 'SF005']);
  assert.equal(isBuildBasketDisabled([]), true);
  assert.equal(isBuildBasketDisabled(['SF001']), false);
});

test('carries exclusion codes from the backend catalogue onto products', () => {
  const mapped = mapCatalogFoodToQuestionThreeProduct({
    food_id: 'SF008',
    name: 'pork belly',
    name_ms: 'perut babi',
    category: 'protein',
    allergen_tags: [],
    exclusion_codes: ['NO_PORK'],
    price_rm_per_100g: 1.8,
    price_unit: 'RM/100g',
    price_available: true,
    price_is_estimated: false,
    price_source: 'PRICECATCHER',
    price_updated: '2026-09-10',
    nutrients: {},
    nutrients_unit: 'per_100g',
    nutrition_available: true,
    nutrition_source: 'USDA',
    nutrition_updated: '2026-09-10',
    pack_grams: null,
    pack_label: '',
  });

  assert.deepEqual(mapped.exclusionCodes, ['NO_PORK']);
});

test('filters restricted foods out of the questionnaire catalogue', async () => {
  const { filterProductsByRestrictions, EXCLUSION_CODES_BY_RESTRICTION } = await import(
    './planQuestionThreeContent.ts'
  );
  const products = [
    { id: 'SF008', name: 'Pork belly', exclusionCodes: ['NO_PORK'] },
    { id: 'SF009', name: 'Pork shoulder', exclusionCodes: ['NO_PORK'] },
    { id: 'SF036', name: 'Tiger prawn', exclusionCodes: ['SHELLFISH'] },
    { id: 'SF127', name: 'Peanut sauce', exclusionCodes: ['PEANUTS'] },
    { id: 'SF172', name: 'Peanut butter', exclusionCodes: ['PEANUTS'] },
    { id: 'SF170', name: 'Condensed milk', exclusionCodes: ['MILK'] },
    { id: 'SF018', name: 'Egg grade C', exclusionCodes: ['EGGS'] },
    { id: 'SF110', name: 'White rice', exclusionCodes: [] },
    { id: 'SF055', name: 'Bird eye chilli', exclusionCodes: [] },
    { id: 'SF161', name: 'Wheat flour', exclusionCodes: [] },
    { id: 'SF159', name: 'Rice vermicelli', exclusionCodes: [] },
  ];

  assert.deepEqual(
    filterProductsByRestrictions(products, ['none']).map((product) => product.id),
    products.map((product) => product.id),
  );
  assert.deepEqual(
    filterProductsByRestrictions(products, ['pork']).map((product) => product.id),
    ['SF036', 'SF127', 'SF172', 'SF170', 'SF018', 'SF110', 'SF055', 'SF161', 'SF159'],
  );
  assert.deepEqual(
    filterProductsByRestrictions(products, ['pork', 'peanuts', 'dairy']).map((product) => product.id),
    ['SF036', 'SF018', 'SF110', 'SF055', 'SF161', 'SF159'],
  );
  assert.deepEqual(
    filterProductsByRestrictions(products, ['eggs']).map((product) => product.id),
    ['SF008', 'SF009', 'SF036', 'SF127', 'SF172', 'SF170', 'SF110', 'SF055', 'SF161', 'SF159'],
  );
  // 'gluten' has no database exclusion code -> filtered by grain NAME keywords
  // (deliberately conservative: wheat/oats/bread/noodle..., NOT rice products).
  assert.equal(EXCLUSION_CODES_BY_RESTRICTION.gluten, undefined);
  assert.deepEqual(
    filterProductsByRestrictions(products, ['gluten']).map((product) => product.id),
    ['SF008', 'SF009', 'SF036', 'SF127', 'SF172', 'SF170', 'SF018', 'SF110', 'SF055', 'SF159'],
  );
  // 'other' free-text best-effort name-matches (display filter; the same
  // matches become hard solver excludes at plan time).
  assert.deepEqual(
    filterProductsByRestrictions(products, ['other'], 'pork, prawn').map((product) => product.id),
    ['SF127', 'SF172', 'SF170', 'SF018', 'SF110', 'SF055', 'SF161', 'SF159'],
  );
  // Empty custom text filters nothing.
  assert.equal(filterProductsByRestrictions(products, ['other']).length, products.length);
});
