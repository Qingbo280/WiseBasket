import type { ImageSourcePropType } from 'react-native';
import type { FoodPriceUnit } from '../api/plannerTypes';

export interface PriceCheckSelectedItem {
  foodId: string;
  name: string;
  subtitle?: string;
  /** Default comparable purchase quantity supplied by the catalogue mapping. */
  quantityG?: number;
  imageSource: ImageSourcePropType;
  /**
   * Set from the conversion-unit response. It is never inferred from the
   * product name in the confirmation UI.
   */
  requiresVariantConfirmation: boolean;
}

export interface PriceCheckVariantOption {
  variantId: string;
  primaryLabel: string;
  secondaryLabel?: string;
  /** Required for live API-generated options; optional for presentation-only fixtures. */
  quantityG?: number;
  retailQuantity?: number;
  retailUnit?: string;
}

export interface PriceCheckVariantConfirmationConfig {
  question: string;
  options: readonly PriceCheckVariantOption[];
  defaultSelectedOptionId?: string;
  disclaimer?: string;
  infoMessage: string;
}

export function shouldRenderPriceCheckVariantConfirmation(
  selectedItem: Pick<PriceCheckSelectedItem, 'requiresVariantConfirmation'>,
): boolean {
  return selectedItem.requiresVariantConfirmation;
}

/** A choice screen is useful only when the user can choose between sizes. */
export function hasMultiplePriceCheckVariants(
  config: Pick<PriceCheckVariantConfirmationConfig, 'options'>,
): boolean {
  return config.options.length > 1;
}

export function getDefaultVariantId(
  config: Pick<PriceCheckVariantConfirmationConfig, 'options' | 'defaultSelectedOptionId'>,
): string | null {
  if (config.options.length === 0) {
    return null;
  }

  const requestedId = config.defaultSelectedOptionId;
  if (requestedId && config.options.some((option) => option.variantId === requestedId)) {
    return requestedId;
  }

  return config.options[0].variantId;
}

function positiveNumber(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) && value > 0 ? value : null;
}

function retailQuantityFromUnit(unit: string): Pick<
  PriceCheckVariantOption,
  'retailQuantity' | 'retailUnit'
> {
  const match = unit.trim().match(/^(\d+(?:\.\d+)?)\s*(.+)$/);
  if (!match) return {};

  return {
    retailQuantity: Number(match[1]),
    retailUnit: match[2],
  };
}

/**
 * Builds user-facing choices directly from production purchase conversions.
 * Builds a config whenever at least one valid conversion exists. The caller
 * shows the confirmation screen only for multiple choices and automatically
 * applies a single choice. No food-specific sizes or labels are inferred here.
 */
export function buildPriceCheckVariantConfirmation(
  selectedItem: Pick<PriceCheckSelectedItem, 'foodId' | 'quantityG'>,
  units: readonly FoodPriceUnit[],
): PriceCheckVariantConfirmationConfig | null {
  const validUnits = units.filter((unit) => {
    const factor = positiveNumber(unit.factor) ?? positiveNumber(selectedItem.quantityG);
    return Boolean(unit.unit.trim() && factor);
  });
  const options = validUnits.flatMap((unit, index) => {
    const quantityG = positiveNumber(unit.factor) ?? positiveNumber(selectedItem.quantityG);
    if (!quantityG) return [];
    return [{
      variantId: `${selectedItem.foodId}:unit-${index}`,
      primaryLabel: unit.unit_label,
      quantityG,
      ...retailQuantityFromUnit(unit.unit),
    }];
  }).sort((left, right) => right.quantityG - left.quantityG);
  if (options.length === 0) return null;

  return {
    question: 'Which size do you want to compare?',
    options,
    defaultSelectedOptionId: options[0].variantId,
    disclaimer: 'The actual weight and price may vary by store.',
    infoMessage: 'We’ll show nearby prices for your selected size.',
  };
}
