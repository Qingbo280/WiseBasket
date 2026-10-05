import type { RecipeSuggestion } from './recipeApi';

export function recipeIngredientBadge(
  recipe: Pick<RecipeSuggestion, 'available_ingredients' | 'ingredient_count'>
): { tag: string; tagTone: 'green' | 'blue' } {
  const available = recipe.available_ingredients.length;
  const total = recipe.ingredient_count;
  if (typeof total !== 'number' || !Number.isInteger(total) || total < available || total < 0) {
    // The older suggestion response omits missing optional ingredients, so
    // its lists cannot establish an accurate total. Show only what is known.
    return {
      tag: `${available} ${available === 1 ? 'ingredient' : 'ingredients'} available`,
      tagTone: 'blue',
    };
  }
  return {
    tag: `${available}/${total} ingredients`,
    tagTone: total > 0 && available === total ? 'green' : 'blue',
  };
}
