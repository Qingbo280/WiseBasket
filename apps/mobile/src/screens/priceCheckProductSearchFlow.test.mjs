import assert from 'node:assert/strict';
import test from 'node:test';

import { getPriceCheckSelectionDestination } from './priceCheckProductSearchFlow.ts';

test('selects variant confirmation when the item requires it', () => {
  assert.equal(
    getPriceCheckSelectionDestination({
      name: 'Eggs',
      requiresVariantConfirmation: true,
    }),
    'variant-confirmation',
  );
});

test('skips confirmation from data rather than product name', () => {
  assert.equal(
    getPriceCheckSelectionDestination({
      name: 'Eggs',
      requiresVariantConfirmation: false,
    }),
    'price-comparison',
  );
  assert.equal(
    getPriceCheckSelectionDestination({
      name: 'Chicken',
      requiresVariantConfirmation: true,
    }),
    'variant-confirmation',
  );
});
