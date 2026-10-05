/**
 * Compatibility export for the earlier TestFlow import name.
 *
 * The actual demo data and derivation now live in demoStorePrices.ts and
 * demoPriceCalculator.ts. No static display totals are kept here.
 */
export {
  calculateDemoPricePrototype as createCheckPricePrototype,
  MAX_VISIBLE_COMPARED_ROWS,
} from './demoPriceCalculator';
export type {
  CheckPriceAdditionalMatchedItem,
  CheckPriceComparedItem,
  CheckPricePrototype,
  CheckPricePrototypeItem,
  CheckPriceStoreFixture,
} from './demoPriceCalculator';
