import type { PriceCheckSelectedItem } from './priceCheckItemVariantConfirmationContent';

export type PriceCheckSelectionDestination = 'variant-confirmation' | 'price-comparison';

/**
 * The single decision point for every future Price Check product source.
 * Production data must provide the boolean; this helper does not infer it
 * from a product name.
 */
export function getPriceCheckSelectionDestination(
  selectedItem: Pick<PriceCheckSelectedItem, 'requiresVariantConfirmation'>,
): PriceCheckSelectionDestination {
  return selectedItem.requiresVariantConfirmation
    ? 'variant-confirmation'
    : 'price-comparison';
}
