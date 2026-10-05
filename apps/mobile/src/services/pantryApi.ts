import AsyncStorage from '@react-native-async-storage/async-storage';
import { apiRequest } from './api';
import { oilRawGrams } from './oilEquivalence';

const PANTRY_CACHE_KEY_PREFIX = 'wisebasket.mobile.pantry.v1.';

export interface PantryFood {
  canonical_food_id: string;
  name: string;
  name_ms: string | null;
  category: string;
}

export interface PantryItem {
  pantry_item_id: number;
  household_id: number;
  food: PantryFood;
  source: 'MANUAL' | 'RECEIPT';
  status: 'AVAILABLE' | 'REMOVED';
  basket_have_managed?: boolean;
  quantity: number | null;
  unit: string | null;
  created_at: string;
}

export interface PantryItemCreateInput {
  canonical_food_id: string;
  quantity?: number | null;
  unit?: string | null;
}

export interface PantryConfirmation {
  available_item_count: number;
  confirmed_at: string;
  household_id: number;
}

function pantryCacheKey(householdId: number) {
  return `${PANTRY_CACHE_KEY_PREFIX}${householdId}`;
}

/** Last-known pantry data is display-only; the API remains authoritative. */
export async function getCachedPantryItems(householdId: number): Promise<PantryItem[] | null> {
  try {
    const stored = await AsyncStorage.getItem(pantryCacheKey(householdId));
    if (!stored) return null;
    const parsed: unknown = JSON.parse(stored);
    return Array.isArray(parsed) ? parsed as PantryItem[] : null;
  } catch {
    // A corrupt or unavailable local cache must never block the Pantry screen.
    return null;
  }
}

export async function cachePantryItems(householdId: number, items: readonly PantryItem[]) {
  try {
    await AsyncStorage.setItem(pantryCacheKey(householdId), JSON.stringify(items));
  } catch {
    // Caching is an offline convenience, not a requirement for Pantry writes.
  }
}

/** The Pantry is the persistent source for the My Basket "What you have" view. */
export async function listPantryItems(householdId: number): Promise<PantryItem[]> {
  const items = await apiRequest<PantryItem[]>(`/api/v1/households/${householdId}/pantry-items`, {
    method: 'GET',
  });
  await cachePantryItems(householdId, items);
  return items;
}

export async function createPantryItem(
  householdId: number,
  input: PantryItemCreateInput,
): Promise<PantryItem> {
  return apiRequest<PantryItem>(`/api/v1/households/${householdId}/pantry-items`, {
    body: input,
    method: 'POST',
  });
}

/** Replace only basket-owned Have rows; response is the authoritative Pantry. */
export async function replaceBasketHaveItems(
  householdId: number,
  foodIds: readonly string[],
): Promise<PantryItem[]> {
  const items = await apiRequest<PantryItem[]>(`/api/v1/households/${householdId}/basket-have-items`, {
    body: { food_ids: [...new Set(foodIds)].sort() },
    method: 'PUT',
  });
  await cachePantryItems(householdId, items);
  return items;
}

export async function removePantryItem(householdId: number, pantryItemId: number): Promise<void> {
  await apiRequest<void>(`/api/v1/households/${householdId}/pantry-items/${pantryItemId}`, {
    method: 'DELETE',
  });
}

export async function updatePantryItem(
  householdId: number,
  pantryItemId: number,
  input: PantryItemCreateInput,
): Promise<PantryItem> {
  return apiRequest<PantryItem>(`/api/v1/households/${householdId}/pantry-items/${pantryItemId}`, {
    body: input,
    method: 'PATCH',
  });
}

export interface PantryConfirmation {
  household_id: number;
  available_item_count: number;
  confirmed_at: string;
}

/** Confirm the current pantry snapshot before requesting personalised recipes
 *  (Epic 5/6 confirmation gate). Planning treats only post-confirmation
 *  AVAILABLE items as trusted stock, so the plan-request assembly confirms
 *  right before reading. */
export async function confirmPantryItems(householdId: number): Promise<PantryConfirmation> {
  return apiRequest<PantryConfirmation>(`/api/v1/households/${householdId}/pantry-confirmations`, {
    method: 'POST',
  });
}

export interface PlannerPantryStockItem {
  food_id: string;
  grams: number;
}

function gramsForPantryItem(item: PantryItem): number | null {
  // Mirrors backend raw-edible conversion: kg/g for foods; only the reviewed
  // cooking-oil group also accepts ml/L at 0.92 g/ml. Everything else is
  // UNKNOWN and cannot reduce the plan's purchase demand.
  if (item.quantity == null || item.unit == null) return null;
  const unit = item.unit.trim().toLowerCase();
  if (unit === 'kg') return item.quantity * 1000;
  if (unit === 'g') return item.quantity;
  return oilRawGrams(item.food.canonical_food_id, item.quantity, unit);
}

/** W10 (I2 Phase 2 A2) plan-request assembly: confirm the current snapshot,
 *  then return the AVAILABLE items normalised to grams. Any failure surfaces
 *  as null so planning NEVER blocks on pantry bookkeeping - it simply plans
 *  from scratch (the safe default). */
export async function fetchConfirmedPantryStock(
  householdId: number,
): Promise<PlannerPantryStockItem[] | null> {
  try {
    await confirmPantryItems(householdId);
    const items = await listPantryItems(householdId);
    const stock: PlannerPantryStockItem[] = [];
    for (const item of items) {
      const grams = gramsForPantryItem(item);
      if (grams != null && grams > 0) {
        stock.push({ food_id: item.food.canonical_food_id, grams });
      }
    }
    return stock;
  } catch {
    return null;
  }
}
