import assert from 'node:assert/strict';
import test from 'node:test';

import {
  formatStoreDetailsDistance,
  getStoreDetailsPriceBasis,
  getStoreDetailsPriceLabel,
  getPremiseInitial,
} from './priceCheckStoreDetailsContent.ts';
import * as storeDetailsContent from './priceCheckStoreDetailsContent.ts';

const eggsDetails = {
  selectedVariant: {
    variantId: 'fixture-eggs-10-pcs',
    label: '10 pcs (Grade A)',
    retailQuantity: 10,
    retailUnit: 'pcs',
  },
  selectedPriceResult: {
    premiseId: 'fixture-happy-mart',
    premiseName: 'Happy Mart',
    premiseType: 'supermarket',
    distanceKm: 1.2,
    price: 11.9,
    currency: 'RM',
    packLabel: '10 pcs (Grade A)',
    retailUnit: 'pcs',
  },
};

test('formats a premise distance for the store summary', () => {
  assert.equal(formatStoreDetailsDistance(1.2), '1.2 km away');
  assert.equal(formatStoreDetailsDistance(null), 'Area match');
});

test('uses the selected retail quantity for a pack price basis', () => {
  assert.equal(getStoreDetailsPriceBasis(eggsDetails), 'for 10 pcs');
});

test('uses the normalized unit for a weight-based price basis', () => {
  assert.equal(
    getStoreDetailsPriceLabel({
      selectedPriceResult: {
        ...eggsDetails.selectedPriceResult,
        packLabel: undefined,
        price: 21.9,
        normalizedPrice: 21.9,
        normalizedUnit: 'kg',
      },
    }),
    'RM 21.90 / kg',
  );
  assert.equal(
    getStoreDetailsPriceBasis({
      selectedVariant: undefined,
      selectedPriceResult: {
        ...eggsDetails.selectedPriceResult,
        packLabel: undefined,
        normalizedPrice: 21.9,
        normalizedUnit: 'kg',
      },
    }),
    'per kg',
  );
});

test('shows the total price when a requested pack quantity is present', () => {
  assert.equal(
    getStoreDetailsPriceLabel({
      selectedPriceResult: {
        ...eggsDetails.selectedPriceResult,
        price: 26,
        packLabel: '10 kg',
        normalizedPrice: 0.26,
        normalizedUnit: '100 g',
      },
    }),
    'RM 26.00',
  );
});

test('derives a neutral premise avatar initial without inventing branding', () => {
  assert.equal(getPremiseInitial('Happy Mart'), 'H');
  assert.equal(getPremiseInitial(''), '?');
});

test('keeps the Store Details fixture within the compact 412dp density budget', () => {
  assert.deepEqual(storeDetailsContent.priceCheckStoreDetailsLayout, {
    headerHeight: 60,
    pageTitleFontSize: 30,
    heroHeightAt412: 112,
    summaryAvatarSize: 56,
    productArtworkSizeAt412: 80,
    productCardHorizontalPadding: 18,
    productCardGap: 12,
    priceBlockHorizontalPadding: 12,
    priceBlockVerticalPadding: 10,
    informationRowMinHeight: 44,
    informationNotePaddingVertical: 10,
    nextButtonHeight: 52,
    bottomPadding: 24,
  });
});
