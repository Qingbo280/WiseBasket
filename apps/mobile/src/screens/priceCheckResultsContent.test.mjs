import assert from 'node:assert/strict';
import test from 'node:test';

import {
  canShowLowerPriceClaim,
  getBestPriceResultId,
  getEffectiveSummaryBanner,
  formatPriceCheckPrice,
} from './priceCheckResultsContent.ts';

const comparableResults = [
  { premiseId: 'near', price: 11.9 },
  { premiseId: 'far', price: 12.6 },
];

test('highlights the supplied best comparable result instead of its row position', () => {
  assert.equal(
    getBestPriceResultId(comparableResults, {
      pricesComparable: true,
      bestResultId: 'far',
    }),
    'far',
  );
});

test('derives the lowest price only when results are comparable', () => {
  assert.equal(
    getBestPriceResultId(comparableResults, { pricesComparable: true }),
    'near',
  );
  assert.equal(
    getBestPriceResultId(comparableResults, { pricesComparable: false }),
    null,
  );
});

test('shows a lower-price claim only with a valid comparison baseline', () => {
  assert.equal(
    canShowLowerPriceClaim(comparableResults, {
      pricesComparable: true,
      comparisonBaseline: 13,
    }),
    true,
  );
  assert.equal(
    canShowLowerPriceClaim(comparableResults, {
      pricesComparable: true,
      comparisonBaseline: null,
    }),
    false,
  );
  assert.equal(
    canShowLowerPriceClaim(comparableResults, {
      pricesComparable: false,
      comparisonBaseline: 13,
    }),
    false,
  );
});

test('removes an unsupported lower-price banner instead of making the claim', () => {
  assert.equal(
    getEffectiveSummaryBanner(
      comparableResults,
      {
        pricesComparable: true,
        comparisonBaseline: null,
        summaryBanner: {
          claim: 'lower-price',
          message: 'Lower price found nearby!',
          tone: 'success',
        },
      },
    ),
    null,
  );
});

test('formats prices with the configured currency and two decimals', () => {
  assert.equal(formatPriceCheckPrice({ currency: 'RM', price: 11.9 }), 'RM 11.90');
});
