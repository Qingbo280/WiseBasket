import type { PantryItem, PantryItemCreateInput } from './pantryApi';

/** Save ingredient presence, without inventing an amount the user hasn't entered. */
export async function saveRecipeHaveItems(
  householdId: number,
  foodIds: readonly string[],
  api: {
    list: (householdId: number) => Promise<readonly PantryItem[]>;
    create: (householdId: number, input: PantryItemCreateInput) => Promise<PantryItem>;
  },
): Promise<readonly PantryItem[]> {
  const current = [...await api.list(householdId)];
  const available = new Set(current.filter((item) => item.status === 'AVAILABLE')
    .map((item) => item.food.canonical_food_id));
  for (const foodId of new Set(foodIds)) {
    if (available.has(foodId)) continue;
    current.push(await api.create(householdId, { canonical_food_id: foodId }));
    available.add(foodId);
  }
  return current;
}
