import type { ImageSourcePropType } from 'react-native';
import type { PriceCheckSelectedItem } from './priceCheckItemVariantConfirmationContent';
import type { PriceCheckPriceResult } from './priceCheckResultsContent';

export interface DashboardPlanSummary {
  budget?: number;
  completedItems?: number;
  estimatedTotal?: number;
  remainingBudget?: number;
  totalItems?: number;
}

export type DashboardPlanData = DashboardPlanSummary;

export const DASHBOARD_PLAN_PLATES = {
  empty: { width: 1848, height: 552 },
  summary: { width: 1847, height: 540 },
} as const;

export const DASHBOARD_PLAN_SCALE = 1.05;

export const DASHBOARD_PLAN_EMPTY_ZONES = {
  left: 18,
  content: 56,
  right: 26,
} as const;

export const DASHBOARD_TYPE_SCALE = {
  greeting: 23,
  supportingGreeting: 14,
  heroMessage: 17,
  actionTitle: 16,
  actionBody: 14,
  sectionTitle: 19,
  planTitle: 18,
  planBody: 13,
  planButton: 15,
  body: 14,
  metadata: 12,
  navLabel: 12,
  navPrimaryLabel: 12,
} as const;

export const DASHBOARD_LAYOUT = {
  contentTop: 8,
  greetingTop: 10,
  heroTop: 12,
  heroAspectRatio: 2048 / 768,
  actionTop: 12,
  actionMinHeight: 142,
  sectionGap: 18,
  sectionHeadingGap: 8,
  planPadding: 14,
  recentImageHeight: 76,
  recentMinHeight: 158,
  tipPadding: 14,
  minimumTouchTarget: 48,
} as const;

export interface DashboardRecentCheck {
  id: string;
  imageSource: ImageSourcePropType;
  productName: string;
  priceLabel: string | null;
  storeName: string | null;
  distanceLabel: string | null;
}

export function getDashboardHorizontalPadding(width: number): number {
  if (width <= 360) return 20;
  if (width <= 384) return 22;
  return 24;
}

export function getDashboardHeroDimensions(viewportWidth: number): { width: number; height: number } {
  const contentWidth = Math.max(0, viewportWidth - getDashboardHorizontalPadding(viewportWidth) * 2);

  return {
    width: contentWidth,
    height: contentWidth / DASHBOARD_LAYOUT.heroAspectRatio,
  };
}

export function getDashboardPlanPlateDimensions(
  viewportWidth: number,
  kind: keyof typeof DASHBOARD_PLAN_PLATES,
): { width: number; height: number } {
  const contentWidth = Math.max(0, viewportWidth - getDashboardHorizontalPadding(viewportWidth) * 2);
  const source = DASHBOARD_PLAN_PLATES[kind];

  const width = Math.min(contentWidth * DASHBOARD_PLAN_SCALE, viewportWidth - 16);

  return {
    width,
    height: width * (source.height / source.width),
  };
}

export function getDashboardPlanProgress(
  completedItems?: number,
  totalItems?: number,
): number | null {
  if (
    !Number.isFinite(completedItems)
    || !Number.isFinite(totalItems)
    || totalItems === undefined
    || totalItems <= 0
    || completedItems === undefined
  ) {
    return null;
  }

  return Math.min(1, Math.max(0, completedItems / totalItems));
}

export function getDashboardGreeting(hour: number, displayName?: string | null): string {
  const name = displayName?.trim();
  if (!name) return 'Welcome back!';

  if (hour < 12) return `Good morning, ${name}!`;
  if (hour < 18) return `Good afternoon, ${name}!`;
  return `Good evening, ${name}!`;
}

export function mapRecentPriceCheck({
  selectedItem,
  selectedPriceResult,
}: {
  selectedItem: PriceCheckSelectedItem;
  selectedPriceResult: PriceCheckPriceResult | null;
}): DashboardRecentCheck {
  const priceLabel = selectedPriceResult
    ? `${selectedPriceResult.currency} ${selectedPriceResult.price.toFixed(2)}`
    : null;
  const distanceLabel =
    selectedPriceResult && Number.isFinite(selectedPriceResult.distanceKm)
      ? `${selectedPriceResult.distanceKm!.toFixed(1)} km`
      : null;

  return {
    id: `${selectedItem.foodId}${selectedPriceResult ? `:${selectedPriceResult.premiseId}` : ''}`,
    imageSource: selectedItem.imageSource,
    productName: selectedItem.name,
    priceLabel,
    storeName: selectedPriceResult?.premiseName ?? null,
    distanceLabel,
  };
}

export function getRecentCheckPreview<T>(
  recentChecks: readonly T[],
  limit = 4,
): readonly T[] {
  return recentChecks.slice(0, limit);
}

export function getDashboardPlanState(
  plan: DashboardPlanData | null | undefined,
): 'empty' | 'populated' {
  return plan ? 'populated' : 'empty';
}
