import type { ImageSourcePropType } from 'react-native'

export interface FoodImageAsset {
  imageKey: string
  uri: string | null
}

// Public project bucket: Expo Go must still show catalogue images when a
// developer starts Metro without exporting the optional asset override.
const DEFAULT_ASSET_BASE_URL = 'https://pub-dcfc9899ab7c4365bd3f9442a34680bb.r2.dev'
const ASSET_BASE_URL = process.env.EXPO_PUBLIC_ASSET_BASE_URL?.trim().replace(/\/+$/, '') || DEFAULT_ASSET_BASE_URL

/**
 * Named food images in R2, keyed by a semantic image ID.
 *
 * The bucket uses the current backend food ID and WebP convention
 * (`foods/SFxxx.webp`). This semantic map remains available for callers that
 * use friendly image names; backend catalogue images resolve directly by ID.
 */
export const FOOD_IMAGE_KEYS: Readonly<Record<string, string>> = {
  'beef': 'foods/SF002.webp',
  'chicken': 'foods/SF006.webp',
  'pork': 'foods/SF009.webp',
  'eggs': 'foods/SF018.webp',
  'mackerel': 'foods/SF025.webp',
  'shallot': 'foods/SF054.webp',
  'cabbage': 'foods/SF055.webp',
  'onion': 'foods/SF056.webp',
  'potatoes': 'foods/SF057.webp',
  'bird-eye-chilli': 'foods/SF061.webp',
  'spinach': 'foods/SF062.webp',
  'eggplant': 'foods/SF063.webp',
  'green-chilli': 'foods/SF064.webp',
  'galangal': 'foods/SF066.webp',
  'garlic': 'foods/SF069.webp',
  'tomato': 'foods/SF072.webp',
  'okra': 'foods/SF073.webp',
  'kangkung': 'foods/SF074.webp',
  'carrots': 'foods/SF077.webp',
  'mustard-greens': 'foods/SF081.webp',
  'broccoli': 'foods/SF082.webp',
  'calamansi-lime': 'foods/SF083.webp',
  'long-beans': 'foods/SF084.webp',
  'green-capsicum': 'foods/SF085.webp',
  'cucumber': 'foods/SF087.webp',
  'guava': 'foods/SF088.webp',
  'watermelon': 'foods/SF089.webp',
  'bananas': 'foods/SF090.webp',
  'lai': 'foods/SF091.webp',
  'papaya': 'foods/SF092.webp',
  'red-dragon-fruit': 'foods/SF094.webp',
  'red-apple': 'foods/SF095.webp',
  'red-grapes': 'foods/SF096.webp',
  'pineapple': 'foods/SF097.webp',
  'lime': 'foods/SF098.webp',
  'honeydew': 'foods/SF101.webp',
  'coconut-milk': 'foods/SF103.webp',
  'grated-coconut': 'foods/SF104.webp',
  'yellow-noodles': 'foods/SF109.webp',
  'rice': 'foods/SF110.webp',
  'wheat-flour': 'foods/SF111.webp',
  'glutinous-rice': 'foods/SF112.webp',
  'white-sugar': 'foods/SF118.webp',
  'palm-sugar': 'foods/SF119.webp',
  'cooking-oil': 'foods/SF120.webp',
  'dhal': 'foods/SF124.webp',
  'peanuts': 'foods/SF127.webp',
  'soy-sauce': 'foods/SF129.webp',
  'chilli-sauce': 'foods/SF130.webp',
  'oyster-sauce': 'foods/SF131.webp',
  'tomato-sauce': 'foods/SF132.webp',
  'curry-powder': 'foods/SF133.webp',
  'salt': 'foods/SF151.webp',
  'sardines': 'foods/SF156.webp',
  'rice-noodles': 'foods/SF159.webp',
  'instant-noodles': 'foods/SF161.webp',
  'condensed-milk': 'foods/SF166.webp',
  'margarine': 'foods/SF171.webp',
  'milk': 'foods/SF176.webp',
  'oats': 'foods/SF195.webp',
}

/** Current backend food IDs mapped to their semantic image IDs. */
export const BACKEND_FOOD_IMAGE_IDS: Readonly<Record<string, string>> = {
  SF002: 'beef',
  SF006: 'chicken',
  SF009: 'pork',
  SF018: 'eggs',
  SF025: 'mackerel',
  SF054: 'shallot',
  SF055: 'cabbage',
  SF056: 'onion',
  SF057: 'potatoes',
  SF061: 'bird-eye-chilli',
  SF062: 'spinach',
  SF063: 'eggplant',
  SF064: 'green-chilli',
  SF066: 'galangal',
  SF069: 'garlic',
  SF072: 'tomato',
  SF073: 'okra',
  SF074: 'kangkung',
  SF077: 'carrots',
  SF081: 'mustard-greens',
  SF082: 'broccoli',
  SF083: 'calamansi-lime',
  SF084: 'long-beans',
  SF085: 'green-capsicum',
  SF087: 'cucumber',
  SF088: 'guava',
  SF089: 'watermelon',
  SF090: 'bananas',
  SF091: 'lai',
  SF092: 'papaya',
  SF094: 'red-dragon-fruit',
  SF095: 'red-apple',
  SF096: 'red-grapes',
  SF097: 'pineapple',
  SF098: 'lime',
  SF101: 'honeydew',
  SF103: 'coconut-milk',
  SF104: 'grated-coconut',
  SF109: 'yellow-noodles',
  SF110: 'rice',
  SF111: 'wheat-flour',
  SF112: 'glutinous-rice',
  SF118: 'white-sugar',
  SF119: 'palm-sugar',
  SF120: 'cooking-oil',
  SF124: 'dhal',
  SF127: 'peanuts',
  SF129: 'soy-sauce',
  SF130: 'chilli-sauce',
  SF131: 'oyster-sauce',
  SF132: 'tomato-sauce',
  SF133: 'curry-powder',
  SF151: 'salt',
  SF156: 'sardines',
  SF159: 'rice-noodles',
  SF161: 'instant-noodles',
  SF166: 'condensed-milk',
  SF171: 'margarine',
  SF176: 'milk',
  SF195: 'oats',
}

export function foodImageUriForKey(imageKey: string): string | null {
  return ASSET_BASE_URL ? `${ASSET_BASE_URL}/${imageKey}` : null
}

function imageKeyForBackendId(backendFoodId: string): string | null {
  const normalizedId = backendFoodId.trim().toUpperCase()
  return /^SF\d{3}$/.test(normalizedId) ? `foods/${normalizedId}.webp` : null
}

/** Resolve a canonical backend ID directly to its matching R2 WebP object. */
export function foodImageUriForBackendId(backendFoodId: string): string | null {
  const imageKey = imageKeyForBackendId(backendFoodId)
  return imageKey ? foodImageUriForKey(imageKey) : null
}

/** Cached R2 source for recipe ingredient thumbnails. */
export function cachedFoodImageSourceForBackendId(backendFoodId: string): ImageSourcePropType | null {
  const uri = foodImageUriForBackendId(backendFoodId)
  return uri ? { cache: 'force-cache', uri } : null
}

export function foodImageForBackendId(backendFoodId: string): FoodImageAsset | null {
  const imageKey = imageKeyForBackendId(backendFoodId)
  return imageKey ? { imageKey, uri: foodImageUriForKey(imageKey) } : null
}

export function foodImageForId(foodId: string): FoodImageAsset | null {
  const imageKey = FOOD_IMAGE_KEYS[foodId]
  return imageKey ? { imageKey, uri: foodImageUriForKey(imageKey) } : null
}
