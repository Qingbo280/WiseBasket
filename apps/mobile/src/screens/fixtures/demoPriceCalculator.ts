import type { BasketDraftItem } from '../basketContent';
import type { DemoPriceRecord, DemoStorePriceData } from './demoStorePrices';

/**
 * DEMO / SYNTHETIC FRONTEND LOGIC
 *
 * This calculator turns the current Need-item basket and the synthetic demo
 * records into the display model consumed by Check Prices. It is intentionally
 * isolated from the screen and is not a production price-matching, ranking,
 * planner, or total-estimation algorithm.
 */

export const MAX_VISIBLE_COMPARED_ROWS = 3 as const;

export interface CheckPricePrototypeItem {
  productId: string;
  name: string;
  imageSource: BasketDraftItem['imageSource'];
  suggestedQuantity: number;
  unit: string;
  priceMin: number | null;
  priceMax: number | null;
  hasRecentPrice: boolean;
  /** A2.5 (2026-09-17): how many compared stores quote this item; 1 = the
   *  single-store fallback (the lone quote is shown, labelled, never a dead
   *  'No recent price'). Undefined in the synthetic demo path. */
  quotingStoreCount?: number;
}

export interface CheckPriceComparedItem {
  productId: string;
  name: string;
  imageSource: BasketDraftItem['imageSource'];
  suggestedQuantity: number;
  unit: string;
  price: number;
}

export interface CheckPriceAdditionalMatchedItem {
  productId: string;
  name: string;
  imageSource: BasketDraftItem['imageSource'];
  price: number;
}

export interface CheckPriceStoreFixture {
  id: string;
  name: string;
  distance: string;
  address: string;
  /** Why this store is shown, e.g. 'Lowest price · Nearest' (real-data path). */
  highlight?: string;
  basketMatchedItemCount: number;
  totalBasketItemCount: number;
  comparedItems: readonly CheckPriceComparedItem[];
  comparedTotal: number | null;
  isLowestComparedTotal: boolean;
  comparisonDifferenceLabel?: string;
  additionalMatchedItems: readonly CheckPriceAdditionalMatchedItem[];
  unmatchedItems: readonly CheckPricePrototypeItem[];
  /** A2.5 (2026-09-17): full-basket total at this store = live quote + the
   *  plan's own estimate backfill for unpriced lines. Falls back to the
   *  compared-items total on old backends. */
  basketTotalRm?: number | null;
  /** How many of the basketTotalRm lines are plan estimates (not live
   *  quotes) - disclosed in the card meta. */
  basketEstimateCount?: number;
}

export interface CheckPricePrototype {
  priceGuide: {
    priceGuideMin: number | null;
    priceGuideMax: number | null;
    matchedItemCount: number;
    /** Items with no live store quote whose guide share is the plan's own
     *  area-price estimate (2026-09-14). */
    estimatedItemCount: number;
    totalItemCount: number;
  };
  items: readonly CheckPricePrototypeItem[];
  commonComparedItemIds: readonly string[];
  visibleComparedItemIds: readonly string[];
  stores: readonly CheckPriceStoreFixture[];
}

interface DemoPriceRange {
  min: number | null;
  max: number | null;
  prices: readonly number[];
}

interface PriceLookup {
  byStore: Map<string, Map<string, number>>;
  byProduct: Map<string, number[]>;
}

function roundCurrency(value: number): number {
  return Math.round((value + Number.EPSILON) * 100) / 100;
}

function buildPriceLookup(prices: readonly DemoPriceRecord[]): PriceLookup {
  const byStore = new Map<string, Map<string, number>>();
  const byProduct = new Map<string, number[]>();

  prices.forEach((record) => {
    const storePrices = byStore.get(record.storeId) ?? new Map<string, number>();
    storePrices.set(record.productId, record.price);
    byStore.set(record.storeId, storePrices);

    const productPrices = byProduct.get(record.productId) ?? [];
    productPrices.push(record.price);
    byProduct.set(record.productId, productPrices);
  });

  return { byStore, byProduct };
}

function getStoreProductPrice(
  lookup: PriceLookup,
  storeId: string,
  productId: string,
): number | null {
  return lookup.byStore.get(storeId)?.get(productId) ?? null;
}

export function getDemoProductPriceRange(
  productId: string,
  data: DemoStorePriceData,
): DemoPriceRange {
  const prices = [...(buildPriceLookup(data.prices).byProduct.get(productId) ?? [])]
    .sort((a, b) => a - b);

  return {
    min: prices[0] ?? null,
    max: prices[prices.length - 1] ?? null,
    prices,
  };
}

function toPrototypeItem(
  basketItem: BasketDraftItem,
  lookup: PriceLookup,
): CheckPricePrototypeItem {
  const range = getDemoProductPriceRangeFromLookup(basketItem.productId, lookup);

  return {
    productId: basketItem.productId,
    name: basketItem.name,
    imageSource: basketItem.imageSource,
    suggestedQuantity: basketItem.suggestedQuantity,
    unit: basketItem.unit,
    priceMin: range.min,
    priceMax: range.max,
    hasRecentPrice: range.min !== null,
  };
}

function getDemoProductPriceRangeFromLookup(
  productId: string,
  lookup: PriceLookup,
): DemoPriceRange {
  const prices = [...(lookup.byProduct.get(productId) ?? [])].sort((a, b) => a - b);

  return {
    min: prices[0] ?? null,
    max: prices[prices.length - 1] ?? null,
    prices,
  };
}

function getUniqueBasketItems(basketItems: readonly BasketDraftItem[]): BasketDraftItem[] {
  const seen = new Set<string>();

  return basketItems.filter((item) => {
    if (seen.has(item.productId)) {
      return false;
    }

    seen.add(item.productId);
    return true;
  });
}

function getComparisonItem(
  item: CheckPricePrototypeItem | undefined,
  price: number | null,
): CheckPriceComparedItem | null {
  if (!item || price === null) {
    return null;
  }

  return {
    productId: item.productId,
    name: item.name,
    imageSource: item.imageSource,
    suggestedQuantity: item.suggestedQuantity,
    unit: item.unit,
    price,
  };
}

export function calculateDemoPricePrototype(
  basketItems: readonly BasketDraftItem[],
  data: DemoStorePriceData,
): CheckPricePrototype {
  const uniqueBasketItems = getUniqueBasketItems(basketItems);
  const lookup = buildPriceLookup(data.prices);
  const items = uniqueBasketItems.map((item) => toPrototypeItem(item, lookup));
  const itemsById = new Map(items.map((item) => [item.productId, item]));
  const matchedItems = items.filter((item) => item.hasRecentPrice);
  const matchedItemCount = matchedItems.length;
  const storeIds = data.stores.map((store) => store.id);

  const priceGuideMin = matchedItems.length > 0
    ? roundCurrency(matchedItems.reduce((total, item) => total + item.priceMin!, 0))
    : null;
  const priceGuideMax = matchedItems.length > 0
    ? roundCurrency(matchedItems.reduce((total, item) => total + item.priceMax!, 0))
    : null;

  const commonComparedItemIds = data.stores.length === 0
    ? []
    : items
      .filter((item) => storeIds.every((storeId) => getStoreProductPrice(lookup, storeId, item.productId) !== null))
      .map((item) => item.productId);
  const visibleComparedItemIds = commonComparedItemIds.slice(0, MAX_VISIBLE_COMPARED_ROWS);
  const commonComparedSet = new Set(commonComparedItemIds);

  const storesWithoutComparison = data.stores.map((store) => {
    const comparedItems = commonComparedItemIds
      .map((productId) => getComparisonItem(
        itemsById.get(productId),
        getStoreProductPrice(lookup, store.id, productId),
      ))
      .filter((item): item is CheckPriceComparedItem => item !== null);
    const matchedBasketItems = items.filter((item) => getStoreProductPrice(lookup, store.id, item.productId) !== null);
    const additionalMatchedItems = matchedBasketItems
      .filter((item) => !commonComparedSet.has(item.productId))
      .map((item) => ({
        productId: item.productId,
        name: item.name,
        imageSource: item.imageSource,
        price: getStoreProductPrice(lookup, store.id, item.productId)!,
      }));
    const unmatchedItems = items.filter((item) => getStoreProductPrice(lookup, store.id, item.productId) === null);

    return {
      id: store.id,
      name: store.name,
      distance: `${store.distanceKm.toFixed(1)} km`,
      address: store.address,
      basketMatchedItemCount: matchedBasketItems.length,
      totalBasketItemCount: items.length,
      comparedItems,
      comparedTotal: commonComparedItemIds.length > 0
        ? roundCurrency(comparedItems.reduce((total, item) => total + item.price, 0))
        : null,
      isLowestComparedTotal: false,
      additionalMatchedItems,
      unmatchedItems,
    } satisfies CheckPriceStoreFixture;
  });

  const comparableStores = storesWithoutComparison
    .filter((store) => store.comparedTotal !== null)
    .sort((a, b) => a.comparedTotal! - b.comparedTotal!);
  const lowestStore = comparableStores[0];
  const secondLowestStore = comparableStores.find((store) => store.id !== lowestStore?.id);
  const lowestDifference = lowestStore && secondLowestStore
    ? roundCurrency(secondLowestStore.comparedTotal! - lowestStore.comparedTotal!)
    : null;

  const stores = storesWithoutComparison.map((store) => {
    const isLowestComparedTotal = store.id === lowestStore?.id;

    return {
      ...store,
      isLowestComparedTotal,
      comparisonDifferenceLabel: isLowestComparedTotal && lowestDifference !== null && lowestDifference > 0
        ? `RM ${lowestDifference.toFixed(2)} lower`
        : undefined,
    };
  });

  return {
    priceGuide: {
      priceGuideMin,
      priceGuideMax,
      matchedItemCount,
      estimatedItemCount: 0,   // demo fixture path: no plan estimates available
      totalItemCount: items.length,
    },
    items,
    commonComparedItemIds,
    visibleComparedItemIds,
    stores,
  };
}
