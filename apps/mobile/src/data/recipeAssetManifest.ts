import type { ImageSourcePropType } from 'react-native';

const ASSET_BASE_URL = process.env.EXPO_PUBLIC_ASSET_BASE_URL?.replace(/\/+$/, '') ?? '';

/**
 * Recipe artwork is stored in R2 using the same slug as `recipe_catalog.recipe_id`:
 * `recipes/{recipe_id}.webp`.
 */
export function recipeImageUriForId(recipeId: string): string | null {
  const normalizedId = recipeId.trim().toLowerCase();
  if (!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(normalizedId) || !ASSET_BASE_URL) {
    return null;
  }
  return `${ASSET_BASE_URL}/recipes/${normalizedId}.webp`;
}

export function recipeImageSourceForId(recipeId: string): ImageSourcePropType | null {
  const uri = recipeImageUriForId(recipeId);
  // Keep downloaded WebP recipe artwork available for subsequent cards/detail
  // views instead of repeatedly fetching the same R2 object.
  return uri ? { cache: 'force-cache', uri } : null;
}
