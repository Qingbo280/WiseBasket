import type { PriceCheckPriceResult } from '../priceCheckResultsContent';
import type { PriceCheckStoreDetailsData } from '../priceCheckStoreDetailsContent';
import { PRICE_CHECK_EGGS_RESULTS_FIXTURE } from './priceCheckResultsFixtures';

/**
 * VISUAL QA ONLY.
 *
 * This fixture is intentionally isolated from the production premise and
 * PriceCatcher contracts. It exists to render the approved Store Details
 * composition before those contracts expose the required detail fields.
 */
const HAPPY_MART_STOREFRONT = require('../../../assets/images/price-check/store-details/fixture-happy-mart-storefront.png');

export function createPriceCheckStoreDetailsFixture(
  selectedPriceResult: PriceCheckPriceResult = PRICE_CHECK_EGGS_RESULTS_FIXTURE.results[0],
): PriceCheckStoreDetailsData {
  const isHappyMart = selectedPriceResult.premiseId === 'fixture-happy-mart';

  return {
    selectedItem: PRICE_CHECK_EGGS_RESULTS_FIXTURE.selectedItem,
    selectedVariant: PRICE_CHECK_EGGS_RESULTS_FIXTURE.selectedVariant,
    selectedLocation: PRICE_CHECK_EGGS_RESULTS_FIXTURE.selectedLocation,
    selectedPriceResult: isHappyMart
      ? {
          ...selectedPriceResult,
          address: 'Jalan Sri Petaling, 57000 Kuala Lumpur',
        }
      : selectedPriceResult,
    metadata: {
      dataSource: 'PriceCatcher',
      updatedDate: '2 Sep 2026',
      note: 'Prices may vary by brand, pack size and availability.',
    },
    storeImage: isHappyMart ? HAPPY_MART_STOREFRONT : undefined,
  };
}

export const PRICE_CHECK_HAPPY_MART_STORE_DETAILS_FIXTURE =
  createPriceCheckStoreDetailsFixture();
