import assert from 'node:assert/strict';
import test from 'node:test';
import {
  PRICE_CHECK_NEXT_STEP_OPTIONS,
  getPriceCheckNextStepDestination,
  getPriceCheckNextStepHeroHeight,
  resetPriceCheckItemState,
} from './priceCheckNextStepContent.ts';

test('keeps the approved Next Step option order and copy', () => {
  assert.deepEqual(
    PRICE_CHECK_NEXT_STEP_OPTIONS.map(({ id, title, supportingText }) => ({
      id,
      title,
      supportingText,
    })),
    [
      {
        id: 'check-another-item',
        title: 'Check another item',
        supportingText: 'Compare another product',
      },
      {
        id: 'plan-next-week',
        title: 'Plan next week’s groceries',
        supportingText: 'Build a smarter weekly grocery plan',
      },
      {
        id: 'finish-for-now',
        title: 'I’m good for now',
        supportingText: 'Finish here and come back later',
      },
    ],
  );
});

test('routes Check another item to Product Search and Plan next week to Question 1', () => {
  assert.equal(
    getPriceCheckNextStepDestination('check-another-item'),
    'price-check-product-search',
  );
  assert.equal(getPriceCheckNextStepDestination('plan-next-week'), 'plan-question-1');
  assert.equal(getPriceCheckNextStepDestination('finish-for-now'), 'auth-entry');
});

test('clears item-specific state without changing location state', () => {
  const location = { label: 'Bonsaa South', district: 'Kuala Lumpur' };
  const state = {
    selectedLocation: location,
    selectedProduct: { foodId: 'fixture-eggs' },
    selectedPriceResult: { premiseId: 'fixture-happy-mart' },
    qaNextDestinationStatus: 'confirmed-selection',
  };

  assert.deepEqual(resetPriceCheckItemState(state), {
    selectedLocation: location,
    selectedProduct: null,
    selectedPriceResult: null,
    qaNextDestinationStatus: 'skipped-confirmation',
  });
});

test('scales the approved Hero to the viewport instead of its source pixel height', () => {
  assert.deepEqual(
    [360, 384, 412, 432].map(getPriceCheckNextStepHeroHeight),
    [240, 256, 275, 288],
  );
});
