import assert from 'node:assert/strict';
import test from 'node:test';

import {
  basketPriceRequestItems,
  basketPriceStoreComparisons,
  overBudgetStoreQuote,
} from './basketPriceApi.ts';
import { buildPriceGuideFromStoreComparison } from '../screens/priceGuideFromPlan.ts';

const draft = (productId, suggestedQuantity, unit) => ({
  productId,
  name: productId,
  imageSource: null,
  suggestedQuantity,
  unit,
  source: 'usual',
  choice: 'need',
});

test('uses exact planner purchase mass for count-labelled fixed packs', () => {
  const items = basketPriceRequestItems(
    [draft('SF018', 10, 'biji')],
    [{ food_id: 'SF018', grams: 580 }],
    [{ food_id: 'SF018', pack_label: '10 biji', pack_grams: 580 }],
  );

  assert.deepEqual(items, [{ food_id: 'SF018', quantity_kg: 0.58 }]);
});

test('normalizes a catalogue 250 g pack to kilograms without duplicating the label', () => {
  const items = basketPriceRequestItems(
    [draft('FISH', 0.25, 'kg')],
    [],
    [{ food_id: 'FISH', pack_label: '250 g', pack_grams: 250 }],
  );

  assert.deepEqual(items, [{ food_id: 'FISH', quantity_kg: 0.25 }]);
});

test('V2 missing prices remain missing and are not presented as estimated totals', () => {
  const basket = [
    draft('SF001', 1, 'kg'), draft('SF002', 1, 'kg'), draft('SF106', 0.5, 'kg'),
  ];
  const requestItems = basketPriceRequestItems(basket, [], []);
  assert.deepEqual(requestItems, [
    { food_id: 'SF001', quantity_kg: 1 },
    { food_id: 'SF002', quantity_kg: 1 },
    { food_id: 'SF106', quantity_kg: 0.5 },
  ]);
  const stores = basketPriceStoreComparisons({
    items: [],
    stores: [{
      store_id: 'store-a',
      store_name: 'STORE A',
      matched_item_count: 2,
      basket_cost_rm: 60,
      distance_km: 1,
      latest_observed_date: '2026-09-24',
      items: [
        { food_id: 'SF001', cost_rm: 20 },
        { food_id: 'SF002', cost_rm: 40 },
      ],
    }],
  }, requestItems);

  assert.equal(stores[0].total_cost_rm, 60);
  assert.equal(stores[0].items_missing, 1);
  assert.equal(stores[0].estimated_items_count, 0);
  assert.equal(stores[0].estimated_total_rm, undefined);
  assert.equal(stores[0].items.find((item) => item.food_id === 'SF106').cost_rm, null);
  const guide = buildPriceGuideFromStoreComparison(basket, stores);
  assert.equal(guide.items.find((item) => item.productId === 'SF106').hasRecentPrice, false);
  assert.equal(
    stores[0].total_cost_rm,
    stores[0].items.reduce(
      (total, item) => total + (item.cost_rm ?? 0),
      0,
    ),
  );
});

test('blocks a quoted subtotal above budget even when some basket items have no recent price', () => {
  const stores = [
    { store_id: 'mydin', items_available: 17, total_cost_rm: 156.71 },
    { store_id: 'aeon', items_available: 17, total_cost_rm: 191.71 },
    { store_id: 'jaya', items_available: 17, total_cost_rm: 209.75 },
  ];

  assert.deepEqual(overBudgetStoreQuote(stores, 100), {
    quotedSubtotalRm: 156.71,
    pricedItemCount: 17,
  });
});

test('compares stores with the best price coverage and allows a quoted subtotal within budget', () => {
  const stores = [
    { store_id: 'partial', items_available: 2, total_cost_rm: 30 },
    { store_id: 'best-a', items_available: 17, total_cost_rm: 156.71 },
    { store_id: 'best-b', items_available: 17, total_cost_rm: 160 },
  ];

  assert.equal(overBudgetStoreQuote(stores, 100)?.quotedSubtotalRm, 156.71);
  assert.equal(overBudgetStoreQuote(stores, 156.71), null);
  assert.equal(overBudgetStoreQuote([], 100), null);
});
