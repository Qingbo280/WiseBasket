import test from 'node:test';
import assert from 'node:assert/strict';
import {
  addManualBasketItem,
  addBasketRecommendation,
  addBasketRecipeOpportunity,
  addBasketSuggestedRecommendation,
  buildBasketDraft,
  getBasketSummary,
  getNeedItems,
  removeBasketItem,
  setBasketItemChoice,
} from './basketContent.ts';

const IMAGE = { uri: 'fixture-image' };

const proposal = {
  usuals: [
    {
      productId: 'SF001',
      name: 'White rice',
      imageSource: IMAGE,
      suggestedQuantity: 5,
      unit: 'kg',
      defaultChoice: 'need',
    },
    {
      productId: 'SF003',
      name: 'Chicken',
      imageSource: IMAGE,
      suggestedQuantity: 2,
      unit: 'kg',
      defaultChoice: 'have',
    },
  ],
  recommendations: [
    {
      productId: 'SF010',
      name: 'Water spinach',
      imageSource: IMAGE,
      suggestedQuantity: 500,
      unit: 'g',
      reason: 'Adds vegetable variety',
    },
  ],
};

test('builds one basket draft from usual proposal defaults', () => {
  const draft = buildBasketDraft(proposal);

  assert.deepEqual(draft.map(({ productId, source, choice }) => ({ productId, source, choice })), [
    { productId: 'SF001', source: 'usual', choice: 'need' },
    { productId: 'SF003', source: 'usual', choice: 'have' },
  ]);
  assert.deepEqual(getNeedItems(draft).map(({ productId }) => productId), ['SF001']);
});

test('updates usual choices without creating a second list', () => {
  const draft = buildBasketDraft(proposal);
  const updated = setBasketItemChoice(draft, 'SF001', 'skip');

  assert.equal(updated.find(({ productId }) => productId === 'SF001')?.choice, 'skip');
  assert.equal(getNeedItems(updated).length, 0);
});

test('adds a recommendation as a Need item and keeps its source', () => {
  const draft = addBasketRecommendation(buildBasketDraft(proposal), proposal.recommendations[0]);
  const added = draft.find(({ productId }) => productId === 'SF010');

  assert.deepEqual(
    added && { source: added.source, choice: added.choice },
    { source: 'recommendation', choice: 'need' },
  );
  assert.deepEqual(getNeedItems(draft).map(({ productId }) => productId), ['SF001', 'SF010']);
});

test('adds a manual catalog item as Need and does not duplicate an existing product', () => {
  const original = buildBasketDraft(proposal);
  const manualItem = {
    productId: 'SF010',
    name: 'Water spinach',
    imageSource: IMAGE,
    suggestedQuantity: 1,
    unit: 'item',
  };
  const withManual = addManualBasketItem(original, manualItem);
  const added = withManual.find(({ productId }) => productId === 'SF010');

  assert.deepEqual(
    added && { source: added.source, choice: added.choice },
    { source: 'manual', choice: 'need' },
  );
  assert.equal(addManualBasketItem(withManual, manualItem).length, withManual.length);
  assert.equal(getNeedItems(withManual).length, 2);
  assert.equal(removeBasketItem(withManual, 'SF010').some(({ productId }) => productId === 'SF010'), false);
});

test('removes recommendations but changes usual removals to Skip', () => {
  const draft = addBasketRecommendation(buildBasketDraft(proposal), proposal.recommendations[0]);
  const afterUsualRemoval = removeBasketItem(draft, 'SF001');
  const afterRecommendationRemoval = removeBasketItem(afterUsualRemoval, 'SF010');

  assert.equal(afterUsualRemoval.find(({ productId }) => productId === 'SF001')?.choice, 'skip');
  assert.equal(afterRecommendationRemoval.some(({ productId }) => productId === 'SF010'), false);
});

test('summary counts Need, Have and Skip while retaining the legacy thumbnail fields', () => {
  const draft = Array.from({ length: 6 }, (_, index) => ({
    productId: `SF${index + 1}`,
    name: `Product ${index + 1}`,
    imageSource: IMAGE,
    suggestedQuantity: 1,
    unit: 'item',
    source: 'usual',
    choice: index === 5 ? 'have' : index === 4 ? 'skip' : 'need',
  }));
  const summary = getBasketSummary(draft);

  assert.equal(summary.count, 4);
  assert.equal(summary.visibleItems.length, 4);
  assert.equal(summary.overflowCount, 0);
  assert.equal(summary.needCount, 4);
  assert.equal(summary.haveCount, 1);
  assert.equal(summary.skippedCount, 1);
});

test('accepting a recipe opportunity adds every missing food once', () => {
  const draft = buildBasketDraft(proposal);
  const opportunity = {
    recipeId: 'rice-spinach-egg', name: 'Rice, Spinach and Egg', estimatedCostRm: 8,
    items: [
      { productId: 'SF010', name: 'Water spinach', imageSource: IMAGE, suggestedQuantity: 0.5, unit: 'kg' },
      { productId: 'SF018', name: 'Egg', imageSource: IMAGE, suggestedQuantity: 10, unit: 'biji', minimumPurchaseKg: 0.55 },
    ],
  };
  const accepted = addBasketRecipeOpportunity(draft, opportunity);
  assert.deepEqual(getNeedItems(accepted).map((item) => item.productId), ['SF001', 'SF010', 'SF018']);
  assert.equal(addBasketRecipeOpportunity(accepted, opportunity).length, accepted.length);
  assert.equal(accepted.find((item) => item.productId === 'SF018')?.unit, 'biji');
  assert.equal(accepted.find((item) => item.productId === 'SF018')?.recipeBundle, true);
});

test('a recipe bundle restores a skipped ingredient at the required pack amount', () => {
  const skipped = [{
    productId: 'SF018', name: 'Egg', imageSource: IMAGE,
    suggestedQuantity: 2, unit: 'biji', minimumPurchaseKg: 0.11,
    source: 'usual', choice: 'skip',
  }];
  const opportunity = {
    recipeId: 'egg-rice', name: 'Egg rice', estimatedCostRm: 5,
    items: [{
      productId: 'SF018', name: 'Egg', imageSource: IMAGE,
      suggestedQuantity: 10, unit: 'biji', minimumPurchaseKg: 0.55,
    }],
  };
  const accepted = addBasketRecipeOpportunity(skipped, opportunity);
  assert.deepEqual(accepted.map((item) => ({
    choice: item.choice, suggestedQuantity: item.suggestedQuantity,
    minimumPurchaseKg: item.minimumPurchaseKg, recipeBundle: item.recipeBundle,
  })), [{ choice: 'need', suggestedQuantity: 10, minimumPurchaseKg: 0.55, recipeBundle: true }]);
});

test('the original food-row Add action accepts all missing ingredients for its recipe', () => {
  const opportunity = {
    recipeId: 'egg-rice', name: 'Egg rice', estimatedCostRm: 7,
    items: [
      { productId: 'SF018', name: 'Egg', imageSource: IMAGE, suggestedQuantity: 10, unit: 'biji', minimumPurchaseKg: 0.55 },
      { productId: 'SF010', name: 'Spinach', imageSource: IMAGE, suggestedQuantity: 0.25, unit: 'kg', minimumPurchaseKg: 0.25 },
    ],
  };
  const recommendation = { ...opportunity.items[0], reason: 'Egg rice', recipeId: opportunity.recipeId };
  const accepted = addBasketSuggestedRecommendation([], recommendation, {
    usuals: [], recommendations: [recommendation], recipeOpportunities: [opportunity],
  });
  assert.deepEqual(accepted.map((item) => item.productId), ['SF018', 'SF010']);
});
