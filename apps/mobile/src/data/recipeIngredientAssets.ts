import type { ImageSourcePropType } from 'react-native';
import { foodImageUriForBackendId } from './foodAssetManifest';

/** Existing catalogue images used by the Recipe Demo ingredient rows. */
export const RECIPE_INGREDIENT_BACKEND_IDS: Readonly<Record<string, string>> = {
  Chicken: 'SF006',
  Kangkung: 'SF074',
  Chili: 'SF061',
  Onion: 'SF056',
  Rice: 'SF110',
  Egg: 'SF018',
  Garlic: 'SF069',
  'Soy sauce': 'SF129',
  Oil: 'SF120',
  Salt: 'SF151',
  'Oyster sauce': 'SF131',
};

export function recipeIngredientImageSource(name: string): ImageSourcePropType | null {
  const imageUri = foodImageUriForBackendId(RECIPE_INGREDIENT_BACKEND_IDS[name] ?? '');
  return imageUri ? { uri: imageUri } : null;
}
