import type { ImageSourcePropType } from 'react-native';
import type {
  PriceCheckPriceResult,
  PriceCheckResultsCommonData,
} from './priceCheckResultsContent';

export const priceCheckStoreDetailsLayout = {
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
} as const;

export interface PriceCheckStoreDetailsMetadata {
  dataSource: string;
  updatedDate: string | null;
  note?: string;
}

export interface PriceCheckStoreDetailsData extends PriceCheckResultsCommonData {
  selectedPriceResult: PriceCheckPriceResult;
  metadata: PriceCheckStoreDetailsMetadata;
  storeImage?: ImageSourcePropType;
}

type StoreDetailsPriceInput = Pick<
  PriceCheckStoreDetailsData,
  'selectedVariant' | 'selectedPriceResult'
>;

export function formatStoreDetailsDistance(distanceKm: number | null): string {
  return distanceKm === null ? 'Area match' : `${distanceKm.toFixed(1)} km away`;
}

export function getStoreDetailsPriceBasis({
  selectedPriceResult,
  selectedVariant,
}: StoreDetailsPriceInput): string {
  if (selectedVariant?.retailQuantity && selectedVariant.retailUnit) {
    return `for ${selectedVariant.retailQuantity} ${selectedVariant.retailUnit}`;
  }

  if (selectedPriceResult.packLabel) {
    return `for ${selectedPriceResult.packLabel}`;
  }

  if (selectedPriceResult.normalizedUnit) {
    return `per ${selectedPriceResult.normalizedUnit}`;
  }

  if (selectedPriceResult.retailUnit) {
    return `per ${selectedPriceResult.retailUnit}`;
  }

  return 'Price basis unavailable';
}

export function getStoreDetailsPriceLabel({
  selectedPriceResult,
}: Pick<PriceCheckStoreDetailsData, 'selectedPriceResult'>): string {
  if (selectedPriceResult.packLabel) {
    return `${selectedPriceResult.currency} ${selectedPriceResult.price.toFixed(2)}`;
  }

  const normalizedPrice = selectedPriceResult.normalizedPrice;
  const normalizedUnit = selectedPriceResult.normalizedUnit;

  if (typeof normalizedPrice === 'number' && normalizedUnit) {
    return `${selectedPriceResult.currency} ${normalizedPrice.toFixed(2)} / ${normalizedUnit}`;
  }

  return `${selectedPriceResult.currency} ${selectedPriceResult.price.toFixed(2)}`;
}

export function getPremiseInitial(premiseName: string): string {
  const initial = premiseName.trim().charAt(0);
  return initial ? initial.toUpperCase() : '?';
}
