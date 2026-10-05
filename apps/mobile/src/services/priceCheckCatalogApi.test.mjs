import assert from 'node:assert/strict';
import test from 'node:test';
import { filterPriceCheckCatalog } from '../screens/priceCheckProductSearchContent.ts';

const catalog = [
  { categoryKey: 'protein', foodId: 'SF002', name: 'Chicken Eggs', nameMs: 'Telur Ayam', subtitle: '30 eggs' },
  { categoryKey: 'vegetables', foodId: 'SF025', name: 'Tomato', nameMs: 'Tomato', subtitle: '1 kg' },
];

test('searches English and Malay food names', () => {
  assert.equal(filterPriceCheckCatalog(catalog, 'egg')[0]?.foodId, 'SF002');
  assert.equal(filterPriceCheckCatalog(catalog, 'telur')[0]?.foodId, 'SF002');
});

test('filters the live catalogue by selected category', () => {
  assert.deepEqual(filterPriceCheckCatalog(catalog, '', 'vegetables').map((item) => item.foodId), ['SF025']);
});
