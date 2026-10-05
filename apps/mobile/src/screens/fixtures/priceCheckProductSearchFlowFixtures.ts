import {
  PRICE_CHECK_POPULAR_BACKEND_IDS,
  type PriceCheckPopularItem,
} from '../priceCheckProductSearchContent';
import type { PriceCheckSelectedItem } from '../priceCheckItemVariantConfirmationContent';
import { foodImageUriForBackendId } from '../../data/foodAssetManifest';
import type { ImageSourcePropType } from 'react-native';

const POPULAR_ITEM_IMAGES = {
  chicken: require('../../../assets/images/price-check-search/products/chicken.png'),
  cookingOil: require('../../../assets/images/price-check-search/products/cooking-oil.png'),
  milk: require('../../../assets/images/price-check-search/products/milk.png'),
  rice: require('../../../assets/images/price-check-search/products/rice.png'),
  tomato: require('../../../assets/images/price-check-search/products/tomato.png'),
} as const;

function r2FoodImage(foodId: string, fallback: ImageSourcePropType): ImageSourcePropType {
  const uri = foodImageUriForBackendId(foodId);
  return uri ? { uri } : fallback;
}

/**
 * Presentation mapping for the six curated Popular Item tiles. Food IDs and
 * default quantities correspond to the current canonical backend catalogue.
 * The backend exposes no production-eligible pack variants for these items,
 * so they proceed directly to nearby-price lookup.
 */
export const PRICE_CHECK_POPULAR_FLOW_QA_FIXTURES: Record<
  PriceCheckPopularItem['assetKey'],
  PriceCheckSelectedItem
> = {
  rice: {
    foodId: PRICE_CHECK_POPULAR_BACKEND_IDS.rice,
    name: 'Rice',
    subtitle: '10 kg',
    quantityG: 10000,
    imageSource: r2FoodImage(
      PRICE_CHECK_POPULAR_BACKEND_IDS.rice,
      POPULAR_ITEM_IMAGES.rice,
    ),
    requiresVariantConfirmation: false,
  },
  eggs: {
    foodId: PRICE_CHECK_POPULAR_BACKEND_IDS.eggs,
    name: 'Chicken Egg',
    subtitle: '30 eggs',
    quantityG: 1740,
    imageSource: r2FoodImage(
      PRICE_CHECK_POPULAR_BACKEND_IDS.eggs,
      require('../../../assets/images/price-check-search/products/eggs.png'),
    ),
    requiresVariantConfirmation: false,
  },
  chicken: {
    foodId: PRICE_CHECK_POPULAR_BACKEND_IDS.chicken,
    name: 'Whole Chicken',
    subtitle: '1 kg',
    quantityG: 1000,
    imageSource: r2FoodImage(
      PRICE_CHECK_POPULAR_BACKEND_IDS.chicken,
      POPULAR_ITEM_IMAGES.chicken,
    ),
    requiresVariantConfirmation: false,
  },
  cookingOil: {
    foodId: PRICE_CHECK_POPULAR_BACKEND_IDS.cookingOil,
    name: 'Cooking Oil (Bottle)',
    subtitle: '1 kg',
    quantityG: 1000,
    imageSource: r2FoodImage(
      PRICE_CHECK_POPULAR_BACKEND_IDS.cookingOil,
      POPULAR_ITEM_IMAGES.cookingOil,
    ),
    requiresVariantConfirmation: false,
  },
  milk: {
    foodId: PRICE_CHECK_POPULAR_BACKEND_IDS.milk,
    name: 'Fresh / UHT Milk',
    subtitle: '1 litre',
    quantityG: 1030,
    imageSource: r2FoodImage(
      PRICE_CHECK_POPULAR_BACKEND_IDS.milk,
      POPULAR_ITEM_IMAGES.milk,
    ),
    requiresVariantConfirmation: false,
  },
  tomato: {
    foodId: PRICE_CHECK_POPULAR_BACKEND_IDS.tomato,
    name: 'Tomato',
    subtitle: '1 kg',
    quantityG: 1000,
    imageSource: r2FoodImage(
      PRICE_CHECK_POPULAR_BACKEND_IDS.tomato,
      POPULAR_ITEM_IMAGES.tomato,
    ),
    requiresVariantConfirmation: false,
  },
};

export function selectedItemForPopularItem(
  item: PriceCheckPopularItem,
): PriceCheckSelectedItem {
  return PRICE_CHECK_POPULAR_FLOW_QA_FIXTURES[item.assetKey];
}
