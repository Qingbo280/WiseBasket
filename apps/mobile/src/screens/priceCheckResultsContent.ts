import type { ImageSourcePropType } from 'react-native';
import type { PriceCheckSelectedItem } from './priceCheckItemVariantConfirmationContent';

export type PriceCheckResultsStatus = 'loading' | 'empty' | 'error' | 'success';

export type PriceCheckPremiseType =
  | 'supermarket'
  | 'minimarket'
  | 'wet-market'
  | 'hypermarket'
  | 'other';

export interface PriceCheckSelectedVariant {
  variantId: string;
  label: string;
  quantityG?: number;
  retailQuantity?: number;
  retailUnit?: string;
}

export interface PriceCheckSelectedLocation {
  label: string;
  latitude: number | null;
  longitude: number | null;
  state?: string;
  district?: string;
}

export interface PriceCheckPriceResult {
  premiseId: string;
  premiseName: string;
  premiseType: PriceCheckPremiseType;
  address?: string;
  latitude?: number | null;
  longitude?: number | null;
  distanceKm: number | null;
  price: number;
  currency: string;
  retailUnit?: string;
  packLabel?: string;
  normalizedPrice?: number | null;
  normalizedUnit?: string;
  priceDate?: string | null;
}

export interface PriceCheckResultSummaryBanner {
  claim: 'lower-price' | 'neutral';
  message: string;
  tone: 'success' | 'neutral';
  supportingCopy?: string;
}

export interface PriceCheckResultsMetadata {
  dataSource: string;
  updatedDate: string | null;
  resultCount: number;
  pricesComparable: boolean;
  comparisonBaseline?: number | null;
  bestResultId?: string;
  summaryBanner?: PriceCheckResultSummaryBanner;
}

export interface PriceCheckResultsCommonData {
  selectedItem: PriceCheckSelectedItem;
  selectedVariant?: PriceCheckSelectedVariant;
  selectedLocation: PriceCheckSelectedLocation;
}

export interface PriceCheckResultsSuccessData extends PriceCheckResultsCommonData {
  status: 'success';
  results: readonly PriceCheckPriceResult[];
  metadata: PriceCheckResultsMetadata;
}

export interface PriceCheckResultsLoadingData extends PriceCheckResultsCommonData {
  status: 'loading';
}

export interface PriceCheckResultsEmptyData extends PriceCheckResultsCommonData {
  status: 'empty';
  message?: string;
}

export interface PriceCheckResultsErrorData extends PriceCheckResultsCommonData {
  status: 'error';
  message?: string;
}

export type PriceCheckResultsData =
  | PriceCheckResultsSuccessData
  | PriceCheckResultsLoadingData
  | PriceCheckResultsEmptyData
  | PriceCheckResultsErrorData;

type ComparableResult = Pick<PriceCheckPriceResult, 'premiseId' | 'price'>;

type ResultHighlightConfig = Pick<
  PriceCheckResultsMetadata,
  'pricesComparable' | 'bestResultId'
>;

export function getBestPriceResultId(
  results: readonly ComparableResult[],
  config: ResultHighlightConfig,
): string | null {
  if (!config.pricesComparable || results.length === 0) {
    return null;
  }

  if (config.bestResultId && results.some((result) => result.premiseId === config.bestResultId)) {
    return config.bestResultId;
  }

  const comparableResults = results.filter((result) => Number.isFinite(result.price));
  if (comparableResults.length === 0) {
    return null;
  }

  return comparableResults.reduce((best, result) =>
    result.price < best.price ? result : best,
  ).premiseId;
}

export function canShowLowerPriceClaim(
  results: readonly ComparableResult[],
  metadata: Pick<PriceCheckResultsMetadata, 'pricesComparable' | 'comparisonBaseline' | 'bestResultId'>,
): boolean {
  const baseline = metadata.comparisonBaseline;
  if (
    !metadata.pricesComparable ||
    typeof baseline !== 'number' ||
    !Number.isFinite(baseline)
  ) {
    return false;
  }

  const bestResultId = getBestPriceResultId(results, metadata);
  const bestResult = results.find((result) => result.premiseId === bestResultId);

  return Boolean(bestResult && Number.isFinite(bestResult.price) && bestResult.price < baseline);
}

export function getEffectiveSummaryBanner(
  results: readonly ComparableResult[],
  metadata: Pick<
    PriceCheckResultsMetadata,
    'pricesComparable' | 'comparisonBaseline' | 'bestResultId' | 'summaryBanner'
  >,
): PriceCheckResultSummaryBanner | null {
  const banner = metadata.summaryBanner;
  if (!banner) {
    return null;
  }

  if (banner.claim === 'lower-price' && !canShowLowerPriceClaim(results, metadata)) {
    return null;
  }

  return banner;
}

export function formatPriceCheckPrice({
  currency,
  price,
}: Pick<PriceCheckPriceResult, 'currency' | 'price'>): string {
  return `${currency} ${price.toFixed(2)}`;
}

export function getProductArtworkAccessibilityLabel(
  selectedItem: Pick<PriceCheckSelectedItem, 'name'>,
): string {
  return `${selectedItem.name} product illustration`;
}

export type PriceCheckProductArtwork = ImageSourcePropType;
