import test from 'node:test';
import assert from 'node:assert/strict';

const {
  calculateDemoPricePrototype,
  getDemoProductPriceRange,
} = await import('./fixtures/demoPriceCalculator.ts');
const { DEMO_STORE_PRICE_DATA } = await import('./fixtures/demoStorePrices.ts');

// Synthetic demo-catalog categories for the demo price records only (the
// real questionnaire catalogue is live backend data and intentionally not
// importable here).
const DEMO_PRODUCT_CATEGORY_BY_ID = {
  SF001: 'carbs',
  SF002: 'protein',
  SF003: 'protein',
  SF006: 'protein',
  SF007: 'protein',
  SF010: 'vege',
  SF011: 'vege',
  SF012: 'vege',
  SF013: 'vege',
  SF016: 'fruit',
  SF018: 'protein',
  SF019: 'carbs',
  SF020: 'protein',
  SF021: 'other',
  SF031: 'other',
  SF036: 'carbs',
  SF037: 'carbs',
  SF046: 'fruit',
  SF047: 'fruit',
  SF069: 'fruit',
};

const demoStores = [
  { id: 'store-a', name: 'Store A', distanceKm: 1.2 },
  { id: 'store-b', name: 'Store B', distanceKm: 2.4 },
  { id: 'store-c', name: 'Store C', distanceKm: 3.1 },
];

const demoPrices = [
  { storeId: 'store-a', productId: 'SF001', price: 10 },
  { storeId: 'store-b', productId: 'SF001', price: 11 },
  { storeId: 'store-c', productId: 'SF001', price: 9 },
  { storeId: 'store-a', productId: 'SF002', price: 2 },
  { storeId: 'store-b', productId: 'SF002', price: 1 },
  { storeId: 'store-c', productId: 'SF002', price: 2.5 },
  { storeId: 'store-a', productId: 'SF003', price: 3 },
  { storeId: 'store-b', productId: 'SF003', price: 2.5 },
  { storeId: 'store-c', productId: 'SF003', price: 4 },
  { storeId: 'store-a', productId: 'SF020', price: 5 },
  { storeId: 'store-b', productId: 'SF020', price: 4 },
];

const demoData = { stores: demoStores, prices: demoPrices };

function basketItem(productId, name = productId) {
  return {
    productId,
    name,
    imageSource: 1,
    suggestedQuantity: 1,
    unit: 'item',
    source: 'usual',
    choice: 'need',
  };
}

test('derives an item range from all available demo store prices', () => {
  assert.deepEqual(getDemoProductPriceRange('SF001', demoData), {
    min: 9,
    max: 11,
    prices: [9, 10, 11],
  });
});

test('derives matched count and supports missing prices', () => {
  const result = calculateDemoPricePrototype(
    [
      basketItem('SF001'),
      basketItem('SF002'),
      basketItem('SF003'),
      basketItem('SF020'),
      basketItem('SF999'),
    ],
    demoData,
  );

  assert.equal(result.priceGuide.matchedItemCount, 4);
  assert.equal(result.priceGuide.totalItemCount, 5);
  assert.equal(result.items.find((item) => item.productId === 'SF999').hasRecentPrice, false);
});

test('derives the common comparison intersection and keeps row order', () => {
  const result = calculateDemoPricePrototype(
    [basketItem('SF001'), basketItem('SF020'), basketItem('SF003'), basketItem('SF999')],
    demoData,
  );

  assert.deepEqual(result.commonComparedItemIds, ['SF001', 'SF003']);
  assert.deepEqual(result.visibleComparedItemIds, ['SF001', 'SF003']);
  assert.deepEqual(result.stores[0].comparedItems.map((item) => item.productId), ['SF001', 'SF003']);
  assert.deepEqual(result.stores[1].comparedItems.map((item) => item.productId), ['SF001', 'SF003']);
  assert.deepEqual(result.stores[2].comparedItems.map((item) => item.productId), ['SF001', 'SF003']);
});

test('derives compared totals, lowest store, and the second-lowest difference', () => {
  const result = calculateDemoPricePrototype(
    [basketItem('SF001'), basketItem('SF002'), basketItem('SF003')],
    demoData,
  );

  assert.deepEqual(result.stores.map((store) => store.comparedTotal), [15, 14.5, 15.5]);
  assert.equal(result.stores[1].isLowestComparedTotal, true);
  assert.equal(result.stores[1].comparisonDifferenceLabel, 'RM 0.50 lower');
  assert.equal(result.stores[0].comparisonDifferenceLabel, undefined);
});

test('derives each store coverage from the current basket', () => {
  const result = calculateDemoPricePrototype(
    [basketItem('SF001'), basketItem('SF002'), basketItem('SF003'), basketItem('SF020')],
    demoData,
  );

  assert.deepEqual(
    result.stores.map((store) => store.basketMatchedItemCount),
    [4, 4, 3],
  );
  assert.deepEqual(
    result.stores.map((store) => store.unmatchedItems.map((item) => item.productId)),
    [[], [], ['SF020']],
  );
});

test('changing basket product ids changes all derived presentation data', () => {
  const first = calculateDemoPricePrototype(
    [basketItem('SF001'), basketItem('SF002'), basketItem('SF003')],
    demoData,
  );
  const changed = calculateDemoPricePrototype(
    [basketItem('SF001'), basketItem('SF020'), basketItem('SF999')],
    demoData,
  );

  assert.notDeepEqual(changed.items.map((item) => item.productId), first.items.map((item) => item.productId));
  assert.equal(changed.priceGuide.totalItemCount, 3);
  assert.equal(changed.priceGuide.matchedItemCount, 2);
  assert.notEqual(changed.priceGuide.priceGuideMin, first.priceGuide.priceGuideMin);
  assert.notDeepEqual(
    changed.stores.map((store) => store.basketMatchedItemCount),
    first.stores.map((store) => store.basketMatchedItemCount),
  );
});

test('derives the happy-path guide and store totals from one demo dataset', () => {
  const result = calculateDemoPricePrototype(
    [
      basketItem('SF002', 'Eggs'),
      basketItem('SF003', 'Chicken'),
      basketItem('SF001', 'White rice'),
      basketItem('SF020', 'Milk'),
      basketItem('SF010', 'Water spinach'),
    ],
    DEMO_STORE_PRICE_DATA,
  );

  assert.equal(result.priceGuide.matchedItemCount, 5);
  assert.equal(result.commonComparedItemIds.length, 5);
  assert.deepEqual(result.stores.map((store) => store.comparedTotal), [52.4, 49.8, 51.2]);
  assert.equal(result.stores[1].comparisonDifferenceLabel, 'RM 1.40 lower');
  assert.deepEqual(
    result.items.map((item) => [item.priceMin, item.priceMax]),
    [
      [11.5, 12.3],
      [16.8, 18],
      [11.8, 12],
      [6.9, 7.2],
      [2.5, 3.3],
    ],
  );
  assert.equal(result.priceGuide.priceGuideMin, 49.5);
  assert.equal(result.priceGuide.priceGuideMax, 52.8);
});

test('covers canonical demo product ids across all approved food categories', () => {
  const pricedProductIds = new Set(DEMO_STORE_PRICE_DATA.prices.map((record) => record.productId));
  const coveredCategories = new Set(
    [...pricedProductIds]
      .map((productId) => DEMO_PRODUCT_CATEGORY_BY_ID[productId])
      .filter(Boolean),
  );

  assert.ok(pricedProductIds.size >= 15 && pricedProductIds.size <= 25);
  assert.equal([...pricedProductIds].every((productId) => productId in DEMO_PRODUCT_CATEGORY_BY_ID), true);
  assert.deepEqual([...coveredCategories].sort(), ['carbs', 'fruit', 'other', 'protein', 'vege']);
});

test('caps compact rows at three while preserving the full common comparison set', () => {
  const sixProductData = {
    stores: demoStores,
    prices: ['SF001', 'SF002', 'SF003', 'SF020', 'SF010', 'SF006']
      .flatMap((productId, index) => demoStores.map((store, storeIndex) => ({
        storeId: store.id,
        productId,
        price: index + storeIndex + 1,
      }))),
  };
  const result = calculateDemoPricePrototype(
    ['SF001', 'SF002', 'SF003', 'SF020', 'SF010', 'SF006'].map((productId) => basketItem(productId)),
    sixProductData,
  );

  assert.equal(result.commonComparedItemIds.length, 6);
  assert.deepEqual(result.visibleComparedItemIds, ['SF001', 'SF002', 'SF003']);
});
