import type { ImageSourcePropType } from 'react-native';
import type { FoodInfo } from '../api/plannerTypes';
import type { PriceCheckSelectedItem } from '../screens/priceCheckItemVariantConfirmationContent';
import type {
  PriceCheckCatalogItem,
  PriceCheckCategoryKey,
} from '../screens/priceCheckProductSearchContent';
import { foodImageUriForBackendId } from '../data/foodAssetManifest';
import { apiRequest } from './api';

export interface PriceCheckCatalogEntry extends PriceCheckCatalogItem {
  imageSource: ImageSourcePropType;
  purchasePriceRmPer100g?: number | null;
  minPurchasePriceRmPer100g?: number | null;
  soldByWeight?: boolean;
}

const CATEGORY_IMAGES: Record<PriceCheckCategoryKey, ImageSourcePropType> = {
  carbs: require('../../assets/images/price-check-search/categories/carbs.png'),
  dairy: require('../../assets/images/price-check-search/categories/dairy.png'),
  fruit: require('../../assets/images/price-check-search/categories/fruit.png'),
  other: require('../../assets/images/price-check-search/categories/other.png'),
  protein: require('../../assets/images/price-check-search/categories/protein.png'),
  vegetables: require('../../assets/images/price-check-search/categories/vegetables.png'),
};

export function priceCheckCategoryFor(food: Pick<FoodInfo, 'category' | 'name'>): PriceCheckCategoryKey {
  const category = food.category.trim().toLocaleLowerCase();
  const name = food.name.toLocaleLowerCase();
  if (/milk|yogurt|cheese|dairy/.test(name)) return 'dairy';
  if (category === 'carbohydrate' || category === 'staples') return 'carbs';
  if (category === 'protein') return 'protein';
  if (category === 'vegetable' || category === 'vegetables') return 'vegetables';
  if (category === 'fruit') return 'fruit';
  return 'other';
}

export function mapFoodToPriceCheckCatalogEntry(food: FoodInfo): PriceCheckCatalogEntry {
  const categoryKey = priceCheckCategoryFor(food);
  const imageUri = foodImageUriForBackendId(food.food_id);
  return {
    categoryKey,
    foodId: food.food_id,
    imageSource: imageUri ? { uri: imageUri } : CATEGORY_IMAGES[categoryKey],
    name: food.name,
    nameMs: food.name_ms || undefined,
    purchasePriceRmPer100g: food.price_rm_per_100g_purchase ?? null,
    minPurchasePriceRmPer100g: food.min_price_rm_per_100g_purchase ?? null,
    soldByWeight: food.sold_by_weight === true,
    quantityG:
      typeof food.pack_grams === 'number' && Number.isFinite(food.pack_grams) && food.pack_grams > 0
        ? food.pack_grams
        : undefined,
    subtitle: food.pack_label || undefined,
  };
}

export function selectedItemFromCatalogEntry(entry: PriceCheckCatalogEntry): PriceCheckSelectedItem {
  return {
    foodId: entry.foodId,
    imageSource: entry.imageSource,
    name: entry.name,
    quantityG: entry.quantityG,
    requiresVariantConfirmation: false,
    subtitle: entry.subtitle,
  };
}

export async function fetchPriceCheckCatalog(): Promise<PriceCheckCatalogEntry[]> {
  const foods = await apiRequest<FoodInfo[]>('/api/v1/foods', {
    auth: false,
    method: 'GET',
    // UAT resolves representative prices at query time and can take more than
    // 10 seconds before accounting for mobile-network latency or a cold start.
    timeoutMs: 30_000,
  });
  if (!Array.isArray(foods)) throw new Error('Food catalogue returned an invalid response.');
  return foods.map(mapFoodToPriceCheckCatalogEntry);
}
