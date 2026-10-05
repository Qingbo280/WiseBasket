import type { FoodInfo, PlanItem, StoreComparison } from '../api/plannerTypes';
import type { BasketDraftItem } from '../screens/basketContent';
import type { ConfirmedLocation } from './confirmedLocationContent';

interface BasketPriceResponse {
  items: Array<{
    food_id: string;
    estimated_cost_rm: number | null;
    latest_observed_date: string | null;
  }>;
  stores: Array<{
    store_id: string;
    store_name: string;
    matched_item_count: number;
    basket_cost_rm: number;
    distance_km: number | null;
    latest_observed_date: string | null;
    items: Array<{ food_id: string; cost_rm: number }>;
  }>;
}

type BasketPriceRequestItem = { food_id: string; quantity_kg: number };

function fallbackQuantityKg(item: BasketDraftItem, food?: FoodInfo): number | null {
  const unit = item.unit.trim().toLowerCase();
  if (unit === 'kg') return item.suggestedQuantity;
  if (unit === 'g' || unit === 'gram' || unit === 'grams' || unit === 'ml') {
    return item.suggestedQuantity / 1000;
  }
  if (unit === 'l' || unit === 'litre' || unit === 'liter') return item.suggestedQuantity;

  const packLabel = food?.pack_label?.trim() ?? '';
  const packMatch = /^(\d+(?:[.,]\d+)?)\s*(kg|g|ml|l|biji)$/i.exec(packLabel);
  if (!packMatch || !food?.pack_grams) return null;
  const amountPerPack = Number.parseFloat(packMatch[1].replace(',', '.'));
  const requestedPacks = packMatch[2].toLowerCase() === unit && amountPerPack > 0
    ? item.suggestedQuantity / amountPerPack
    : item.suggestedQuantity;
  return requestedPacks * food.pack_grams / 1000;
}

export function basketPriceRequestItems(
  basketItems: readonly BasketDraftItem[],
  planItems: readonly PlanItem[],
  catalogFoods: readonly FoodInfo[],
): BasketPriceRequestItem[] {
  const planById = new Map(planItems.map((item) => [item.food_id, item]));
  const foodById = new Map(catalogFoods.map((food) => [food.food_id, food]));
  return basketItems.flatMap((item) => {
    const planItem = planById.get(item.productId);
    const quantityKg = planItem && planItem.grams > 0
      ? planItem.grams / 1000
      : fallbackQuantityKg(item, foodById.get(item.productId));
    return quantityKg && quantityKg > 0
      ? [{ food_id: item.productId, quantity_kg: quantityKg }]
      : [];
  });
}

export function basketPriceStoreComparisons(
  response: BasketPriceResponse,
  items: readonly BasketPriceRequestItem[],
): StoreComparison[] {
  const totalItems = items.length;
  const cheapestTotal = response.stores.length > 0
    ? Math.min(...response.stores.map((store) => store.basket_cost_rm))
    : null;
  return response.stores.map((store) => {
    const costs = new Map(store.items.map((item) => [item.food_id, item.cost_rm]));
    return {
      store_id: store.store_id,
      store_name: store.store_name,
      total_cost_rm: store.basket_cost_rm,
      is_cheapest: cheapestTotal !== null && store.basket_cost_rm === cheapestTotal,
      items_available: store.matched_item_count,
      items_missing: totalItems - store.matched_item_count,
      price_coverage_ratio: store.matched_item_count / totalItems,
      observed_date: store.latest_observed_date,
      distance_km: store.distance_km,
      missing_item_options: [],
      items: items.map((item) => ({
        food_id: item.food_id,
        available: costs.has(item.food_id),
        cost_rm: costs.get(item.food_id) ?? null,
        price_rm_per_100g: null,
      })),
      // The V2 basket-prices endpoint never backfills unavailable lines.
      // Explicit zero prevents legacy consumers from treating items_missing
      // as if those lines carried undisclosed catalogue estimates.
      estimated_items_count: 0,
    };
  });
}

/** Block only on real quoted prices, comparing stores with the best coverage. */
export function overBudgetStoreQuote(
  stores: readonly Pick<StoreComparison, 'items_available' | 'total_cost_rm'>[],
  budgetRm: number,
): { quotedSubtotalRm: number; pricedItemCount: number } | null {
  if (!Number.isFinite(budgetRm) || budgetRm <= 0) return null;
  const quotedStores = stores.filter((store) =>
    store.items_available > 0 && Number.isFinite(store.total_cost_rm) && store.total_cost_rm >= 0);
  if (quotedStores.length === 0) return null;
  const pricedItemCount = Math.max(...quotedStores.map((store) => store.items_available));
  const quotedSubtotalRm = Math.min(...quotedStores
    .filter((store) => store.items_available === pricedItemCount)
    .map((store) => store.total_cost_rm));
  return quotedSubtotalRm > budgetRm ? { quotedSubtotalRm, pricedItemCount } : null;
}

export async function fetchBasketPrices(
  basketItems: readonly BasketDraftItem[],
  planItems: readonly PlanItem[],
  catalogFoods: readonly FoodInfo[],
  location: ConfirmedLocation,
): Promise<StoreComparison[]> {
  const items = basketPriceRequestItems(basketItems, planItems, catalogFoods);
  if (items.length === 0) return [];

  const locationPayload = location.latitude !== undefined && location.longitude !== undefined
    ? { latitude: location.latitude, longitude: location.longitude }
    : { state: location.state, district: location.district };
  if (!('latitude' in locationPayload) && !locationPayload.state) return [];

  const { apiRequest } = await import('./api');
  const response = await apiRequest<BasketPriceResponse>('/api/v2/basket-prices', {
    auth: false,
    method: 'POST',
    body: { location: locationPayload, items },
  });
  return basketPriceStoreComparisons(response, items);
}
