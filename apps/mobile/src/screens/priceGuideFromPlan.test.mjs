import assert from 'node:assert/strict';
import test from 'node:test';

import { buildPriceGuideFromStoreComparison } from './priceGuideFromPlan.ts';

const basketItems = [
  {
    productId: 'SF001',
    name: 'rice',
    imageSource: null,
    suggestedQuantity: 1,
    unit: '5kg',
    source: 'usual',
    choice: 'need',
  },
  {
    productId: 'SF002',
    name: 'beef',
    imageSource: null,
    suggestedQuantity: 1,
    unit: '1kg',
    source: 'usual',
    choice: 'need',
  },
  {
    productId: 'SF999',
    name: 'mystery item',
    imageSource: null,
    suggestedQuantity: 2,
    unit: 'pack',
    source: 'added',
    choice: 'need',
  },
];

function storeQuote(overrides) {
  return {
    store_id: 'store',
    store_name: 'STORE',
    total_cost_rm: 0,
    is_cheapest: false,
    items_available: 0,
    items_missing: 3,
    price_coverage_ratio: 0,
    observed_date: '2026-09-07',
    distance_km: null,
    missing_item_options: [],
    items: [],
    ...overrides,
  };
}

const itemQuote = (foodId, cost) => ({
  food_id: foodId,
  available: cost !== null,
  cost_rm: cost,
  price_rm_per_100g: null,
});

// Four stores with distinct winners: cheapest = store-b (RM50), nearest =
// store-c (0.5 km), best coverage-for-money = store-d (full coverage, RM70).
const fourStores = [
  storeQuote({
    store_id: 'store-a', store_name: 'MID EVERYTHING', total_cost_rm: 60, distance_km: 3,
    items_available: 2, items_missing: 1, price_coverage_ratio: 0.67,
    items: [itemQuote('SF001', 20), itemQuote('SF002', 40), itemQuote('SF999', null)],
  }),
  storeQuote({
    store_id: 'store-b', store_name: 'CHEAP FAR', total_cost_rm: 50, distance_km: 8,
    items_available: 1, items_missing: 2, price_coverage_ratio: 0.33,
    items: [itemQuote('SF001', 18), itemQuote('SF002', 60), itemQuote('SF999', null)],
  }),
  storeQuote({
    store_id: 'store-c', store_name: 'NEAR PRICEY', total_cost_rm: 90, distance_km: 0.5,
    items_available: 1, items_missing: 2, price_coverage_ratio: 0.33,
    items: [itemQuote('SF001', 30), itemQuote('SF002', 55), itemQuote('SF999', null)],
  }),
  storeQuote({
    store_id: 'store-d', store_name: 'FULL COVERAGE', total_cost_rm: 70, distance_km: 5,
    items_available: 3, items_missing: 0, price_coverage_ratio: 1,
    items: [itemQuote('SF001', 25), itemQuote('SF002', 45), itemQuote('SF999', 5)],
  }),
];

test('maps real store quotes into the price guide model', () => {
  const prototype = buildPriceGuideFromStoreComparison(basketItems, fourStores);

  assert.equal(prototype.priceGuide.matchedItemCount, 3);
  assert.equal(prototype.priceGuide.totalItemCount, 3);
  // Only store-d prices the whole basket, so its actual total is the guide.
  assert.equal(prototype.priceGuide.priceGuideMin, 70);
  assert.equal(prototype.priceGuide.priceGuideMax, 70);

  const mystery = prototype.items.find((item) => item.productId === 'SF999');
  assert.equal(mystery?.hasRecentPrice, true);
});

test('shows the three stores with the most priced basket items', () => {
  const prototype = buildPriceGuideFromStoreComparison(basketItems, fourStores);

  assert.deepEqual(
    prototype.stores.map((store) => [store.id, store.highlight]),
    [
      ['store-d', 'Lowest price · Best match'],
      ['store-a', undefined],
      ['store-c', 'Nearest'],
    ],
  );
  // Lower coverage loses even when its quoted subset is cheaper.
  assert.equal(prototype.stores.some((store) => store.id === 'store-b'), false);
});

test('guide, item ranges, and compared count use only the three displayed stores', () => {
  const stores = [
    storeQuote({
      store_id: 'giant', total_cost_rm: 43.59, distance_km: 0.5,
      items_available: 3, items_missing: 0,
      items: [itemQuote('SF001', 13.59), itemQuote('SF002', 4), itemQuote('SF999', 26)],
    }),
    storeQuote({
      store_id: 'segi', total_cost_rm: 54.76, distance_km: 0.6,
      items_available: 3, items_missing: 0,
      items: [itemQuote('SF001', 15.30), itemQuote('SF002', 4.96), itemQuote('SF999', 34.50)],
    }),
    storeQuote({
      store_id: 'aeon', total_cost_rm: 53.26, distance_km: 1.6,
      items_available: 3, items_missing: 0,
      items: [itemQuote('SF001', 14.39), itemQuote('SF002', 3.42), itemQuote('SF999', 35.45)],
    }),
    storeQuote({
      store_id: 'hidden-full', total_cost_rm: 57.20, distance_km: 2,
      items_available: 3, items_missing: 0,
      items: [itemQuote('SF001', 16.20), itemQuote('SF002', 4.75), itemQuote('SF999', 36.25)],
    }),
    storeQuote({
      store_id: 'hidden-partial', total_cost_rm: 0.50, distance_km: 0.1,
      items_available: 1, items_missing: 2,
      items: [itemQuote('SF001', 0.50), itemQuote('SF002', null), itemQuote('SF999', null)],
    }),
  ];
  const prototype = buildPriceGuideFromStoreComparison(basketItems, stores);

  assert.deepEqual(prototype.stores.map((store) => store.id), ['giant', 'segi', 'aeon']);
  assert.deepEqual(
    [prototype.priceGuide.priceGuideMin, prototype.priceGuide.priceGuideMax],
    [43.59, 54.76],
  );
  assert.deepEqual(
    prototype.items.map((item) => [item.productId, item.priceMin, item.priceMax, item.quotingStoreCount]),
    [
      ['SF001', 13.59, 15.30, 3],
      ['SF002', 3.42, 4.96, 3],
      ['SF999', 26, 35.45, 3],
    ],
  );
  assert.deepEqual(prototype.commonComparedItemIds, ['SF001', 'SF002', 'SF999']);
  assert.equal(prototype.priceGuide.matchedItemCount, 3);
  assert.equal(prototype.stores[0].highlight, 'Lowest price · Nearest · Best match');
});

test('a price quoted only by a hidden store does not match a displayed basket item', () => {
  const stores = [1, 2, 3].map((distance) => storeQuote({
    store_id: `visible-${distance}`, total_cost_rm: 30 + distance, distance_km: distance,
    items_available: 2, items_missing: 1,
    items: [itemQuote('SF001', 10 + distance), itemQuote('SF002', 20), itemQuote('SF999', null)],
  }));
  stores.push(storeQuote({
    store_id: 'hidden', total_cost_rm: 5, distance_km: 0.1,
    items_available: 1, items_missing: 2,
    items: [itemQuote('SF001', null), itemQuote('SF002', null), itemQuote('SF999', 5)],
  }));

  const prototype = buildPriceGuideFromStoreComparison(basketItems, stores);
  const hiddenOnlyItem = prototype.items.find((item) => item.productId === 'SF999');

  assert.equal(prototype.stores.length, 3);
  assert.equal(prototype.priceGuide.matchedItemCount, 2);
  assert.equal(hiddenOnlyItem?.hasRecentPrice, false);
  assert.equal(hiddenOnlyItem?.priceMin, null);
  assert.deepEqual(prototype.commonComparedItemIds, ['SF001', 'SF002']);
  assert.equal(prototype.priceGuide.priceGuideMin, null);
});

test('merges tags when one store wins multiple criteria', () => {
  const oneStore = [
    storeQuote({
      store_id: 'only', store_name: 'ONLY STORE', total_cost_rm: 60, distance_km: 1.2,
      items_available: 2, items_missing: 1, price_coverage_ratio: 0.67,
      items: [itemQuote('SF001', 20), itemQuote('SF002', 40), itemQuote('SF999', null)],
    }),
  ];
  const prototype = buildPriceGuideFromStoreComparison(basketItems, oneStore);

  assert.equal(prototype.stores.length, 1);
  assert.equal(prototype.stores[0].highlight, 'Nearest · Best match');
});

test('omits the nearest tag when no store has a distance', () => {
  const noDistance = fourStores.map((store) => ({ ...store, distance_km: null }));
  const prototype = buildPriceGuideFromStoreComparison(basketItems, noDistance);

  assert.deepEqual(
    prototype.stores.map((store) => store.highlight),
    ['Lowest price · Best match', undefined, undefined],
  );
  assert.equal(prototype.stores.some((store) => store.highlight?.includes('Nearest')), false);
});

test('keeps matched/additional/unmatched detail on displayed stores', () => {
  const prototype = buildPriceGuideFromStoreComparison(basketItems, fourStores);
  const fullCoverage = prototype.stores.find((store) => store.id === 'store-d');

  // SF001+SF002 are quoted by stores a/b/c too, so they are the common set;
  // SF999 is the additional matched item at store-d.
  assert.deepEqual(prototype.commonComparedItemIds, ['SF001', 'SF002']);
  assert.deepEqual(fullCoverage?.additionalMatchedItems.map((item) => item.productId), ['SF999']);
  assert.equal(fullCoverage?.basketMatchedItemCount, 3);
  assert.equal(fullCoverage?.totalBasketItemCount, 3);
  assert.equal(fullCoverage?.distance, '5.0 km');
  assert.equal(fullCoverage?.address, 'Prices observed 2026-09-07');
  // Compared totals are ranked within the displayed stores (store-a: 20+40).
  assert.equal(prototype.stores.find((store) => store.id === 'store-a')?.isLowestComparedTotal, true);
  assert.equal(prototype.stores.find((store) => store.id === 'store-d')?.isLowestComparedTotal, false);
  assert.equal(prototype.stores.find((store) => store.id === 'store-d')?.comparedTotal, 70);
  assert.equal(prototype.stores.find((store) => store.id === 'store-c')?.comparedTotal, 85);
});

test('returns an honest empty model when no store quotes exist', () => {
  const prototype = buildPriceGuideFromStoreComparison(basketItems, null);

  assert.equal(prototype.priceGuide.priceGuideMin, null);
  assert.equal(prototype.priceGuide.matchedItemCount, 0);
  assert.equal(prototype.priceGuide.totalItemCount, 3);
  assert.deepEqual(prototype.stores, []);
  assert.ok(prototype.items.every((item) => !item.hasRecentPrice));
});

test('planner estimates never masquerade as recent nearby prices', () => {
  const storesMissingOne = [
    storeQuote({
      // E1: the guide rides the A2.5 full-basket figure (live quotes +
      // estimate backfill) - model the backend's estimated_total_rm.
      store_id: 'only', store_name: 'ONLY STORE', total_cost_rm: 60,
      estimated_total_rm: 20 + 40 + 5.5, estimated_items_count: 1,
      distance_km: 1.2,
      items_available: 2, items_missing: 1, price_coverage_ratio: 0.67,
      items: [itemQuote('SF001', 20), itemQuote('SF002', 40), itemQuote('SF999', null)],
    }),
  ];
  const estimates = new Map([['SF999', 5.5]]);
  const prototype = buildPriceGuideFromStoreComparison(
    basketItems, storesMissingOne, estimates);

  assert.equal(prototype.priceGuide.matchedItemCount, 2);
  assert.equal(prototype.priceGuide.estimatedItemCount, 0);
  assert.equal(prototype.priceGuide.priceGuideMin, null);
  assert.equal(prototype.priceGuide.priceGuideMax, null);
  const mystery = prototype.items.find((item) => item.productId === 'SF999');
  assert.equal(mystery?.hasRecentPrice, false);
  assert.equal(mystery?.priceMin, null);

  // No estimate available -> still honest emptiness for that item only.
  // E1: use the plain (pre-A2.5) store payload - no estimated_total_rm, so
  // the guide falls back to the quote-only total_cost_rm (60).
  const storesMissingOnePlain = [
    storeQuote({
      store_id: 'only', store_name: 'ONLY STORE', total_cost_rm: 60,
      distance_km: 1.2,
      items_available: 2, items_missing: 1, price_coverage_ratio: 0.67,
      items: [itemQuote('SF001', 20), itemQuote('SF002', 40), itemQuote('SF999', null)],
    }),
  ];
  const noEstimates = buildPriceGuideFromStoreComparison(
    basketItems, storesMissingOnePlain);
  assert.equal(noEstimates.priceGuide.priceGuideMin, null);
  assert.equal(noEstimates.priceGuide.estimatedItemCount, 0);
});


// A2.5 (2026-09-17): store cards carry the comparable full-basket total
// (live quote + plan-estimate backfill, same source as the price guide) with
// the estimate count disclosed, and ranking follows it.
test('store cards carry the estimate-backfilled basket total (A2.5)', () => {
  const stores = [
    storeQuote({
      store_id: 'partial', store_name: 'PARTIAL', total_cost_rm: 60, distance_km: 1,
      items_available: 2, items_missing: 1, price_coverage_ratio: 0.67,
      items: [itemQuote('SF001', 20), itemQuote('SF002', 40), itemQuote('SF999', null)],
      estimated_items_count: 1, estimated_total_rm: 65.5,
    }),
    storeQuote({
      store_id: 'full', store_name: 'FULL', total_cost_rm: 70, distance_km: 2,
      items_available: 3, items_missing: 0, price_coverage_ratio: 1,
      items: [itemQuote('SF001', 22), itemQuote('SF002', 38), itemQuote('SF999', 10)],
      estimated_items_count: 0, estimated_total_rm: 70,
    }),
  ];
  const prototype = buildPriceGuideFromStoreComparison(basketItems, stores);

  const partial = prototype.stores.find((s) => s.id === 'partial');
  assert.equal(partial?.basketTotalRm, 65.5);
  assert.equal(partial?.basketEstimateCount, 1);
  const full = prototype.stores.find((s) => s.id === 'full');
  assert.equal(full?.basketTotalRm, 70);
  assert.equal(full?.basketEstimateCount, 0);
  assert.equal(prototype.priceGuide.priceGuideMin, 70);
  assert.equal(prototype.priceGuide.priceGuideMax, 70);

  // Only a full-coverage store may make a lowest whole-basket claim.
  assert.doesNotMatch(partial?.highlight ?? '', /Lowest price/);
  assert.match(full?.highlight ?? '', /Lowest price/);
});

test('old-backend quotes without estimate fields fall back to the raw quote total', () => {
  const stores = [
    storeQuote({
      store_id: 'legacy', store_name: 'LEGACY', total_cost_rm: 60, distance_km: 1,
      items_available: 2, items_missing: 1, price_coverage_ratio: 0.67,
      items: [itemQuote('SF001', 20), itemQuote('SF002', 40), itemQuote('SF999', null)],
    }),
  ];
  const prototype = buildPriceGuideFromStoreComparison(basketItems, stores);
  const legacy = prototype.stores.find((s) => s.id === 'legacy');
  assert.equal(legacy?.basketTotalRm, 60);
  assert.equal(
    legacy?.basketEstimateCount,
    0,
    'missing prices must not be relabelled as undisclosed estimates',
  );
  assert.equal(
    legacy?.basketTotalRm,
    legacy?.additionalMatchedItems.reduce(
      (total, item) => total + item.price,
      legacy.comparedTotal ?? 0,
    ),
  );
});

test('items quoted by exactly one store carry quotingStoreCount=1 (A2.5 single-store fallback)', () => {
  const stores = [
    storeQuote({
      store_id: 's1', store_name: 'S1', total_cost_rm: 60, distance_km: 1,
      items_available: 1, items_missing: 2, price_coverage_ratio: 0.33,
      items: [itemQuote('SF001', 20), itemQuote('SF002', null), itemQuote('SF999', null)],
    }),
    storeQuote({
      store_id: 's2', store_name: 'S2', total_cost_rm: 40, distance_km: 2,
      items_available: 2, items_missing: 1, price_coverage_ratio: 0.67,
      items: [itemQuote('SF001', null), itemQuote('SF002', 40), itemQuote('SF999', null)],
    }),
  ];
  const prototype = buildPriceGuideFromStoreComparison(basketItems, stores);
  const beef = prototype.items.find((item) => item.productId === 'SF002');
  assert.equal(beef?.quotingStoreCount, 1);
  assert.equal(beef?.hasRecentPrice, true);
  const rice = prototype.items.find((item) => item.productId === 'SF001');
  assert.equal(rice?.quotingStoreCount, 1);
});
