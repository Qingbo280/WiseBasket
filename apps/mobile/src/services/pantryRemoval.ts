import type { PantryItem } from './pantryApi';

/** A display row can represent several older AVAILABLE records. */
export async function removePantryFood(
  householdId: number,
  foodId: string,
  api: {
    list: (householdId: number) => Promise<PantryItem[]>;
    remove: (householdId: number, pantryItemId: number) => Promise<void>;
  },
): Promise<PantryItem[]> {
  let items = await api.list(householdId);
  const rows = items.filter((item) => item.status === 'AVAILABLE'
    && item.food.canonical_food_id === foodId);
  if (rows.length === 0) throw new Error('This food is not saved in your pantry. Refresh and try again.');
  for (const row of rows) {
    try {
      await api.remove(householdId, row.pantry_item_id);
    } catch (error) {
      // The server may have committed before its acknowledgement was lost.
      // Only an authoritative read proving this row absent permits success.
      let refreshed: PantryItem[];
      try { refreshed = await api.list(householdId); } catch { throw error; }
      if (refreshed.some((item) => item.pantry_item_id === row.pantry_item_id && item.status === 'AVAILABLE')) throw error;
      items = refreshed;
    }
  }
  const removedIds = new Set(rows.map((row) => row.pantry_item_id));
  return items.filter((item) => !removedIds.has(item.pantry_item_id));
}

/** Removing stock does not remove a separate intention to buy more. */
export function clearRemovedHaveChoice<T extends { productId: string; choice: 'have' | 'need' | 'skip' }>(
  items: readonly T[], foodId: string,
): T[] {
  return items.map((item) => item.productId === foodId && item.choice === 'have'
    ? { ...item, choice: 'skip' } : item);
}
