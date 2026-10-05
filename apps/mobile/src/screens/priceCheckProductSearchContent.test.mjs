import assert from 'node:assert/strict';
import test from 'node:test';
import {
  PRICE_CHECK_CATEGORIES,
  PRICE_CHECK_POPULAR_ITEMS,
  getPriceCheckGridTileWidth,
} from './priceCheckProductSearchContent.ts';

test('keeps the approved static product-search content order', () => {
  assert.deepEqual(
    PRICE_CHECK_POPULAR_ITEMS.map((item) => item.label),
    ['Rice', 'Eggs', 'Chicken', 'Cooking Oil', 'Milk', 'Tomato'],
  );
  assert.deepEqual(
    PRICE_CHECK_CATEGORIES.map((category) => category.label),
    ['Carbs', 'Protein', 'Vegetables', 'Fruit', 'Dairy', 'Other'],
  );
});

test('uses unique asset keys for every tile', () => {
  const assetKeys = [
    ...PRICE_CHECK_POPULAR_ITEMS.map((item) => item.assetKey),
    ...PRICE_CHECK_CATEGORIES.map((category) => category.assetKey),
  ];

  assert.equal(new Set(assetKeys).size, assetKeys.length);
});

test('keeps three columns inside the approved Android widths', () => {
  const widths = [360, 384, 412, 432];
  const padding = [20, 22, 24, 24];

  assert.deepEqual(
    widths.map((width, index) => Math.round(getPriceCheckGridTileWidth(width, padding[index]))),
    [100, 107, 115, 121],
  );
});
