import type { StoreComparison } from '../api/plannerTypes';
import type { BasketDraftItem } from './basketContent';
import type {
  CheckPriceAdditionalMatchedItem,
  CheckPriceComparedItem,
  CheckPricePrototype,
  CheckPricePrototypeItem,
  CheckPriceStoreFixture,
} from './fixtures/demoPriceCalculator';

// Mirrors MAX_VISIBLE_COMPARED_ROWS in demoPriceCalculator (kept as a local
// constant so this module has no runtime dependency on the demo fixture).
const MAX_VISIBLE_COMPARED_ROWS = 3 as const;
const MAX_DISPLAYED_STORES = 3 as const;

/**
 * Builds the Check Prices display model from the REAL planner store quotes
 * (PlanResponse.store_comparison). Falls back to an honest "no prices" model
 * when the plan carried no store quotes (e.g. no location set).
 */

function roundCurrency(value: number): number {
  return Math.round((value + Number.EPSILON) * 100) / 100;
}

function getUniqueBasketItems(basketItems: readonly BasketDraftItem[]): BasketDraftItem[] {
  const seen = new Set<string>();
  return basketItems.filter((item) => {
    if (seen.has(item.productId)) return false;
    seen.add(item.productId);
    return true;
  });
}

function storePriceFor(
  store: StoreComparison,
  productId: string,
): number | null {
  const quote = store.items.find((item) => item.food_id === productId);
  return quote && quote.available && quote.cost_rm !== null ? quote.cost_rm : null;
}

export function buildPriceGuideFromStoreComparison(
  basketItems: readonly BasketDraftItem[],
  storeComparison: readonly StoreComparison[] | null | undefined,
  _estimatedCosts?: ReadonlyMap<string, number>,
): CheckPricePrototype {
  const storesInput = storeComparison ?? [];
  const uniqueItems = getUniqueBasketItems(basketItems);
  // A2.5 (2026-09-17): rank stores by the comparable full-basket figure
  // (live quote + estimate backfill) once the backend supplies it; the raw
  // quote total prices a different item set per store and is not comparable.
  const hasDisclosedEstimateBackfill = (store: StoreComparison): boolean =>
    store.estimated_total_rm !== undefined
    && store.estimated_items_count !== undefined;
  const storeBasketTotal = (store: StoreComparison): number =>
    hasDisclosedEstimateBackfill(store)
      ? store.estimated_total_rm!
      : store.total_cost_rm;
  const storeEstimateCount = (store: StoreComparison): number =>
    hasDisclosedEstimateBackfill(store) ? store.estimated_items_count! : 0;

  // Select the cards first. Every price signal on this screen must come from
  // these same stores, even when the API returns more candidates.
  const displayedStores = [...storesInput].sort((left, right) => {
    const coverageDifference = right.items_available - left.items_available;
    if (coverageDifference !== 0) return coverageDifference;

    const leftDistance = left.distance_km ?? Number.POSITIVE_INFINITY;
    const rightDistance = right.distance_km ?? Number.POSITIVE_INFINITY;
    if (leftDistance !== rightDistance) return leftDistance - rightDistance;

    const costDifference = storeBasketTotal(left) - storeBasketTotal(right);
    if (costDifference !== 0) return costDifference;
    return left.store_id.localeCompare(right.store_id);
  }).slice(0, MAX_DISPLAYED_STORES);

  const items: CheckPricePrototypeItem[] = uniqueItems.map((basketItem) => {
    const prices = displayedStores
      .map((store) => storePriceFor(store, basketItem.productId))
      .filter((price): price is number => price !== null)
      .sort((a, b) => a - b);
    return {
      productId: basketItem.productId,
      name: basketItem.name,
      imageSource: basketItem.imageSource,
      suggestedQuantity: basketItem.suggestedQuantity,
      unit: basketItem.unit,
      priceMin: prices[0] ?? null,
      priceMax: prices[prices.length - 1] ?? null,
      hasRecentPrice: prices.length > 0,
      // A2.5 (2026-09-17): disclose the single-store fallback ('priced at 1
      // store only') instead of reading like an area-wide price.
      quotingStoreCount: prices.length,
    };
  });
  const itemsById = new Map(items.map((item) => [item.productId, item]));
  const matchedItems = items.filter((item) => item.hasRecentPrice);
  const estimatedItems: CheckPricePrototypeItem[] = [];

  // E1 (2026-09-17 user decision): the guide shows what ONE store would
  // actually charge for the WHOLE basket - the same per-store full-basket
  // figure the nearby-store cards display (live quotes + estimate backfill,
  // A2.5), so the guide and the store list can never disagree. The old
  // cross-store per-item mix (each item at its cheapest store) was
  // physically unrealizable and read inconsistently next to the single-
  // store totals (bug10/12: guide 168.98 vs cheapest store 173.44).
  const completeStoreTotals = displayedStores
    .filter((store) => uniqueItems.every(
      (item) => storePriceFor(store, item.productId) !== null,
    ))
    .map((store) => storeBasketTotal(store))
    .filter((total): total is number =>
      total !== null && total !== undefined && Number.isFinite(total));
  const priceGuideMin = completeStoreTotals.length > 0
    ? roundCurrency(Math.min(...completeStoreTotals))
    : null;
  const priceGuideMax = completeStoreTotals.length > 0
    ? roundCurrency(Math.max(...completeStoreTotals))
    : null;

  // Items quoted by EVERY compared store drive the apples-to-apples compared total.
  const commonComparedItemIds = displayedStores.length === 0
    ? []
    : items
      .filter((item) => displayedStores.every((store) => storePriceFor(store, item.productId) !== null))
      .map((item) => item.productId);
  const visibleComparedItemIds = commonComparedItemIds.slice(0, MAX_VISIBLE_COMPARED_ROWS);
  const commonComparedSet = new Set(commonComparedItemIds);

  const displayedFixtures: CheckPriceStoreFixture[] = displayedStores.map((store) => {
    const comparedItems = commonComparedItemIds
      .map((productId): CheckPriceComparedItem | null => {
        const item = itemsById.get(productId);
        const price = storePriceFor(store, productId);
        if (!item || price === null) return null;
        return {
          productId: item.productId,
          name: item.name,
          imageSource: item.imageSource,
          suggestedQuantity: item.suggestedQuantity,
          unit: item.unit,
          price,
        };
      })
      .filter((item): item is CheckPriceComparedItem => item !== null);

    const pricedIds = new Set(
      items
        .filter((item) => storePriceFor(store, item.productId) !== null)
        .map((item) => item.productId),
    );
    const additionalMatchedItems: CheckPriceAdditionalMatchedItem[] = items
      .filter((item) => pricedIds.has(item.productId) && !commonComparedSet.has(item.productId))
      .map((item) => ({
        productId: item.productId,
        name: item.name,
        imageSource: item.imageSource,
        price: storePriceFor(store, item.productId)!,
      }));
    const unmatchedItems = items.filter((item) => !pricedIds.has(item.productId));

    return {
      id: store.store_id,
      name: store.store_name,
      distance: store.distance_km !== null ? `${store.distance_km.toFixed(1)} km` : 'Distance unknown',
      address: store.observed_date ? `Prices observed ${store.observed_date}` : '',
      basketMatchedItemCount: pricedIds.size,
      totalBasketItemCount: items.length,
      comparedItems,
      comparedTotal: commonComparedItemIds.length > 0
        ? roundCurrency(comparedItems.reduce((total, item) => total + item.price, 0))
        : null,
      isLowestComparedTotal: false,
      additionalMatchedItems,
      unmatchedItems,
      // A2.5 (2026-09-17): the comparable full-basket figure (live quote +
      // plan-estimate backfill), with the estimate count for the card meta.
      basketTotalRm: storeBasketTotal(store),
      basketEstimateCount: storeEstimateCount(store),
    };
  });

  // Surface the stores that can price the most basket items. Proximity and
  // checkout cost only break coverage ties; a cheap/near store must not
  // displace a store where the user can actually buy more of the basket.
  const minBy = <T,>(rows: readonly T[], score: (row: T) => number): T | null => {
    let bestRow: T | null = null;
    let bestScore = Number.POSITIVE_INFINITY;
    rows.forEach((row) => {
      const value = score(row);
      if (value < bestScore) {
        bestScore = value;
        bestRow = row;
      }
    });
    return bestRow;
  };

  const completeStores = displayedStores.filter((store) => uniqueItems.every(
    (item) => storePriceFor(store, item.productId) !== null,
  ));
  const cheapest = minBy(completeStores, (store) => storeBasketTotal(store));
  const hasAnyDistance = displayedStores.some((store) => store.distance_km !== null);
  const nearest = hasAnyDistance
    ? minBy(displayedStores, (store) => store.distance_km ?? Number.POSITIVE_INFINITY)
    : null;
  const bestMatch = displayedStores[0] ?? null;

  const tagsByStoreId = new Map<string, Set<string>>();
  const addPick = (store: StoreComparison | null, tag: string) => {
    if (!store) return;
    const tags = tagsByStoreId.get(store.store_id) ?? new Set<string>();
    tags.add(tag);
    tagsByStoreId.set(store.store_id, tags);
  };
  addPick(cheapest, 'Lowest price');
  addPick(nearest, 'Nearest');
  // 2026-09-17 user copy decision: 'Best value' read like a price claim the
  // basket totals often contradict - 'Best match' says what the score
  // actually measures (coverage-for-money fit), not 'cheapest'.
  addPick(bestMatch, 'Best match');

  const displayed: CheckPriceStoreFixture[] = displayedFixtures.map((store) => {
    const tags = tagsByStoreId.get(store.id);
    return {
      ...store,
      highlight: tags ? [...tags].join(' · ') : undefined,
    };
  });

  const comparableStores = displayed
    .filter((store) => store.comparedTotal !== null)
    .sort((a, b) => a.comparedTotal! - b.comparedTotal!);
  const lowestStore = comparableStores[0];
  const secondLowestStore = comparableStores.find((store) => store.id !== lowestStore?.id);
  const lowestDifference = lowestStore && secondLowestStore
    ? roundCurrency(secondLowestStore.comparedTotal! - lowestStore.comparedTotal!)
    : null;

  const stores = displayed.map((store) => {
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
      matchedItemCount: matchedItems.length,
      estimatedItemCount: estimatedItems.length,
      totalItemCount: items.length,
    },
    items,
    commonComparedItemIds,
    visibleComparedItemIds,
    stores,
  };
}
