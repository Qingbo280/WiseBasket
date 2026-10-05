import type { ProductPreviewItem } from '../screens/MyBasketMainScreen';
import type { PriceCheckCatalogEntry } from './priceCheckCatalogApi';
import type { PantryItem, PantryItemCreateInput } from './pantryApi';

/** Persist purchased presence; track only records this shopping session creates. */
export async function syncPurchasedPantry(
  householdId: number,
  items: readonly ProductPreviewItem[],
  catalog: readonly PriceCheckCatalogEntry[],
  owned: Map<string, number>,
  api: {
    list: (id: number) => Promise<readonly PantryItem[]>;
    create: (id: number, input: PantryItemCreateInput) => Promise<PantryItem>;
    remove: (id: number, itemId: number) => Promise<void>;
  },
): Promise<readonly PantryItem[]> {
  const foodIds = new Set(items.map((item) => {
    if (!item.productId.startsWith('recipe-')) return item.productId;
    const matches = catalog.filter((food) => food.name.trim().toLowerCase() === item.name.trim().toLowerCase());
    if (matches.length !== 1) throw new Error(`${item.name} could not be matched to a pantry food. Please try again after the food list loads.`);
    return matches[0].foodId;
  }));
  const current = new Map((await api.list(householdId)).filter((item) => item.status === 'AVAILABLE')
    .map((item) => [item.food.canonical_food_id, item]));
  for (const foodId of foodIds) {
    if (current.has(foodId)) continue;
    const created = await api.create(householdId, { canonical_food_id: foodId });
    owned.set(foodId, created.pantry_item_id);
    current.set(foodId, created);
  }
  for (const [foodId, itemId] of owned) {
    if (foodIds.has(foodId)) continue;
    await api.remove(householdId, itemId);
    owned.delete(foodId);
    if (current.get(foodId)?.pantry_item_id === itemId) current.delete(foodId);
  }
  return [...current.values()];
}
