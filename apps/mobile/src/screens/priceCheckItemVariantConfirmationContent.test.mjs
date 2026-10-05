import assert from 'node:assert/strict';
import test from 'node:test';

import {
  getDefaultVariantId,
  shouldRenderPriceCheckVariantConfirmation,
} from './priceCheckItemVariantConfirmationContent.ts';

test('uses the explicit default variant when it is available', () => {
  const config = {
    options: [
      { variantId: 'small', primaryLabel: '10 pcs' },
      { variantId: 'large', primaryLabel: '1 tray' },
    ],
    defaultSelectedOptionId: 'large',
  };

  assert.equal(getDefaultVariantId(config), 'large');
});

test('falls back to the first available variant', () => {
  const config = {
    options: [
      { variantId: 'small', primaryLabel: '10 pcs' },
      { variantId: 'large', primaryLabel: '1 tray' },
    ],
    defaultSelectedOptionId: 'missing',
  };

  assert.equal(getDefaultVariantId(config), 'small');
});

test('renders confirmation from data instead of product name', () => {
  assert.equal(
    shouldRenderPriceCheckVariantConfirmation({ requiresVariantConfirmation: true }),
    true,
  );
  assert.equal(
    shouldRenderPriceCheckVariantConfirmation({
      name: 'Eggs',
      requiresVariantConfirmation: false,
    }),
    false,
  );
  assert.equal(
    shouldRenderPriceCheckVariantConfirmation({
      name: 'Chicken Breast',
      requiresVariantConfirmation: true,
    }),
    true,
  );
});
