import type { PriceCheckResultsSuccessData } from '../priceCheckResultsContent';
import { PRICE_CHECK_EGGS_VARIANT_SELECTED_ITEM } from './priceCheckItemVariantConfirmationFixtures';

/**
 * VISUAL QA ONLY.
 *
 * These rows mirror the approved reference composition. They are not
 * PriceCatcher records and must not be used as production fallback data.
 */
export const PRICE_CHECK_EGGS_RESULTS_FIXTURE: PriceCheckResultsSuccessData = {
  status: 'success',
  selectedItem: PRICE_CHECK_EGGS_VARIANT_SELECTED_ITEM,
  selectedVariant: {
    variantId: 'fixture-eggs-10-pcs',
    label: '10 pcs (Grade A)',
    retailQuantity: 10,
    retailUnit: 'pcs',
  },
  selectedLocation: {
    label: 'Bonsaa South, Kuala Lumpur',
    latitude: null,
    longitude: null,
    state: 'W.P. Kuala Lumpur',
    district: 'Bangsar South',
  },
  results: [
    {
      premiseId: 'fixture-happy-mart',
      premiseName: 'Happy Mart',
      premiseType: 'supermarket',
      distanceKm: 1.2,
      price: 11.9,
      currency: 'RM',
      packLabel: '10 pcs (Grade A)',
      retailUnit: 'pcs',
    },
    {
      premiseId: 'fixture-fresh-pick',
      premiseName: 'FreshPick',
      premiseType: 'minimarket',
      distanceKm: 2.1,
      price: 12.6,
      currency: 'RM',
      packLabel: '10 pcs (Grade A)',
      retailUnit: 'pcs',
    },
    {
      premiseId: 'fixture-jaya-grocer',
      premiseName: 'Jaya Grocer',
      premiseType: 'supermarket',
      distanceKm: 3.5,
      price: 13.2,
      currency: 'RM',
      packLabel: '10 pcs (Grade A)',
      retailUnit: 'pcs',
    },
    {
      premiseId: 'fixture-pasar-taman',
      premiseName: 'Pasar Taman',
      premiseType: 'wet-market',
      distanceKm: 4.2,
      price: 12,
      currency: 'RM',
      packLabel: '10 pcs (Grade A)',
      retailUnit: 'pcs',
    },
  ],
  metadata: {
    dataSource: 'PriceCatcher',
    updatedDate: '2 Sep 2026',
    resultCount: 4,
    pricesComparable: true,
    comparisonBaseline: 13,
    bestResultId: 'fixture-happy-mart',
    summaryBanner: {
      claim: 'lower-price',
      message: 'Lower price found nearby!',
      supportingCopy: 'Compare prices and choose what works for you.',
      tone: 'success',
    },
  },
};
