import type { RecipeFood, RecipeSuggestion } from './recipeApi';

type PreviewSource = Pick<RecipeSuggestion,
  'available_ingredients' | 'missing_required_ingredients'
> & Partial<Pick<RecipeSuggestion, 'available_main_ingredients' | 'missing_main_ingredients'>>;

function dedupeFoods(foods: readonly RecipeFood[]): RecipeFood[] {
  const seen = new Set<string>();
  const result: RecipeFood[] = [];
  for (const food of foods) {
    if (seen.has(food.canonical_food_id)) continue;
    seen.add(food.canonical_food_id);
    result.push(food);
  }
  return result;
}

/**
 * The two ingredient thumbnails under each meal-idea card. Main-role
 * ingredients lead so a card never previews "chicken egg + white sugar"
 * when sugar is only an optional seasoning. Backends predating the
 * main-ingredient fields keep the legacy available+missing order, and a
 * short main pool is topped up from those legacy lists without repeats.
 */
export function recipePreviewFoods(recipe: PreviewSource, count = 2): readonly RecipeFood[] {
  const legacy = [...recipe.available_ingredients, ...recipe.missing_required_ingredients];
  if (recipe.available_main_ingredients === undefined || recipe.missing_main_ingredients === undefined) {
    return legacy.slice(0, count);
  }
  const mains = dedupeFoods([...recipe.available_main_ingredients, ...recipe.missing_main_ingredients]);
  if (mains.length >= count) return mains.slice(0, count);
  return dedupeFoods([...mains, ...legacy]).slice(0, count);
}
