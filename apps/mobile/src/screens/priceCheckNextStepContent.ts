export type PriceCheckNextStepOptionId =
  | 'check-another-item'
  | 'plan-next-week'
  | 'finish-for-now';

export type PriceCheckNextStepDestination =
  | 'price-check-product-search'
  | 'plan-question-1'
  | 'auth-entry';

const PRICE_CHECK_NEXT_STEP_HERO_ASPECT_RATIO = 1.5;

export const PRICE_CHECK_NEXT_STEP_OPTIONS = [
  {
    id: 'check-another-item',
    title: 'Check another item',
    supportingText: 'Compare another product',
    icon: 'search-outline',
    visualVariant: 'primary',
  },
  {
    id: 'plan-next-week',
    title: 'Plan next week’s groceries',
    supportingText: 'Build a smarter weekly grocery plan',
    icon: 'basket-outline',
    visualVariant: 'secondary',
  },
  {
    id: 'finish-for-now',
    title: 'I’m good for now',
    supportingText: 'Finish here and come back later',
    icon: 'time-outline',
    visualVariant: 'tertiary',
  },
] as const;

export function getPriceCheckNextStepDestination(
  optionId: PriceCheckNextStepOptionId,
): PriceCheckNextStepDestination {
  if (optionId === 'check-another-item') return 'price-check-product-search';
  if (optionId === 'plan-next-week') return 'plan-question-1';
  return 'auth-entry';
}

export function getPriceCheckNextStepHeroHeight(width: number): number {
  return Math.round(width / PRICE_CHECK_NEXT_STEP_HERO_ASPECT_RATIO);
}

export function resetPriceCheckItemState<
  T extends {
    selectedProduct: unknown;
    selectedPriceResult: unknown;
    qaNextDestinationStatus: unknown;
  },
>(state: T): T {
  return {
    ...state,
    selectedProduct: null,
    selectedPriceResult: null,
    qaNextDestinationStatus: 'skipped-confirmation',
  };
}
