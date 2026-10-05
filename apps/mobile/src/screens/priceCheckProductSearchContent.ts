export const PRICE_CHECK_POPULAR_ITEMS = [
  { assetKey: 'rice', label: 'Rice' },
  { assetKey: 'eggs', label: 'Eggs' },
  { assetKey: 'chicken', label: 'Chicken' },
  { assetKey: 'cookingOil', label: 'Cooking Oil' },
  { assetKey: 'milk', label: 'Milk' },
  { assetKey: 'tomato', label: 'Tomato' },
] as const;

export const PRICE_CHECK_CATEGORIES = [
  { assetKey: 'carbs', label: 'Carbs' },
  { assetKey: 'protein', label: 'Protein' },
  { assetKey: 'vegetables', label: 'Vegetables' },
  { assetKey: 'fruit', label: 'Fruit' },
  { assetKey: 'dairy', label: 'Dairy' },
  { assetKey: 'other', label: 'Other' },
] as const;

export const PRICE_CHECK_GRID_GAP = 10;

export function getPriceCheckGridTileWidth(width: number, horizontalPadding: number) {
  return (width - horizontalPadding * 2 - PRICE_CHECK_GRID_GAP * 2) / 3;
}

export type PriceCheckPopularItem = (typeof PRICE_CHECK_POPULAR_ITEMS)[number];
export type PriceCheckCategory = (typeof PRICE_CHECK_CATEGORIES)[number];

export type PriceCheckCategoryKey = PriceCheckCategory['assetKey'];

/** Current backend identities for the six curated popular-item shortcuts. */
export const PRICE_CHECK_POPULAR_BACKEND_IDS: Readonly<
  Record<PriceCheckPopularItem['assetKey'], string>
> = {
  chicken: 'SF006',
  cookingOil: 'SF120',
  eggs: 'SF018',
  milk: 'SF176',
  rice: 'SF110',
  tomato: 'SF072',
};

export interface PriceCheckCatalogItem {
  foodId: string;
  name: string;
  nameMs?: string;
  subtitle?: string;
  quantityG?: number;
  categoryKey: PriceCheckCategoryKey;
}

export function filterPriceCheckCatalog<T extends PriceCheckCatalogItem>(
  catalog: readonly T[],
  query: string,
  categoryKey?: PriceCheckCategoryKey,
): T[] {
  const needle = query.trim().toLocaleLowerCase();

  return catalog.filter((item) => {
    if (categoryKey && item.categoryKey !== categoryKey) return false;
    if (!needle) return true;

    return [item.name, item.nameMs, item.subtitle]
      .filter((value): value is string => Boolean(value))
      .some((value) => value.toLocaleLowerCase().includes(needle));
  });
}
