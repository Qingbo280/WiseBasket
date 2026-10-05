import type {
  PriceCheckSelectedItem,
  PriceCheckVariantConfirmationConfig,
} from '../priceCheckItemVariantConfirmationContent';

/**
 * VISUAL QA ONLY.
 *
 * These values intentionally do not represent production SKU records. They
 * are isolated here so the reusable screen can be rendered before the API
 * exposes a confirmed retail-variant contract.
 */
const EGGS_ILLUSTRATION = require('../../../assets/images/price-check-search/products/eggs.png');

export const PRICE_CHECK_EGGS_VARIANT_SELECTED_ITEM: PriceCheckSelectedItem = {
  foodId: 'fixture-food-eggs',
  name: 'Eggs',
  subtitle: 'Chicken eggs (Grade A)',
  imageSource: EGGS_ILLUSTRATION,
  requiresVariantConfirmation: true,
};

export const PRICE_CHECK_EGGS_VARIANT_CONFIRMATION: PriceCheckVariantConfirmationConfig = {
  question: 'Which size do you want to compare?',
  options: [
    {
      variantId: 'fixture-eggs-10-pcs',
      primaryLabel: '10 pcs',
      secondaryLabel: 'about 600 g',
      quantityG: 600,
      retailQuantity: 10,
      retailUnit: 'pcs',
    },
    {
      variantId: 'fixture-eggs-1-tray',
      primaryLabel: '1 tray',
      secondaryLabel: '30 pcs',
      quantityG: 1740,
      retailQuantity: 30,
      retailUnit: 'pcs',
    },
  ],
  defaultSelectedOptionId: 'fixture-eggs-10-pcs',
  disclaimer: 'The actual weight and price may vary by store.',
  infoMessage: 'We’ll show nearby prices for your selected size.',
};
