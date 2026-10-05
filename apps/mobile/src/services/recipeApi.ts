import { apiRequest } from './api';

export interface RecipeFood {
  canonical_food_id: string;
  category: string;
  name: string;
  name_ms: string | null;
}

export interface RecipeSuggestion {
  available_ingredients: readonly RecipeFood[];
  description: string | null;
  missing_required_ingredients: readonly RecipeFood[];
  name: string;
  recipe_id: string;
  required_ingredient_count: number;
  required_match_count: number;
  // Older deployed APIs may omit the total until the backend is updated.
  ingredient_count?: number;
  optional_ingredient_count?: number;
  // Main-role (protein/staple/main vegetable) ingredient projections. Older
  // deployed APIs omit them; meal-idea previews fall back to the raw lists.
  available_main_ingredients?: readonly RecipeFood[];
  missing_main_ingredients?: readonly RecipeFood[];
  quantity_status?: string;
  is_quantity_sufficient?: boolean | null;
  required_quantity_sufficient_count?: number;
}

export interface RecipeIngredientQuantity {
  quantity_status?: string;
  is_quantity_sufficient?: boolean | null;
  required_quantity_kg?: number | null;
  available_quantity_kg?: number | null;
  shortfall_quantity_kg?: number | null;
}

export interface RecipeDetail extends RecipeSuggestion {
  cooking_steps: readonly string[];
  ingredients: readonly ({ food: RecipeFood; required: boolean } & RecipeIngredientQuantity)[];
}

export interface RecipeRequestFilters {
  exclusions?: readonly string[];
  glutenFree?: boolean;
  customRestriction?: string;
  /** An ordering hint only; never owned pantry stock. */
  plannedFoodIds?: readonly string[];
}

function recipeQuery(filters: RecipeRequestFilters): string {
  const query = new URLSearchParams();
  [...new Set(filters.exclusions ?? [])].sort().forEach((code) => query.append('exclusions', code));
  if (filters.glutenFree) query.set('gluten_free', 'true');
  if (filters.customRestriction?.trim()) query.set('custom_restriction', filters.customRestriction.trim());
  [...new Set(filters.plannedFoodIds ?? [])].sort().forEach((id) => query.append('planned_food_ids', id));
  return query.toString() ? `?${query.toString()}` : '';
}

/** Fetch the user's database-backed recipe suggestions for the Meal Ideas view. */
export async function fetchRecipeSuggestions(householdId: number, filters: RecipeRequestFilters = {}): Promise<readonly RecipeSuggestion[]> {
  const recipes = await apiRequest<RecipeSuggestion[]>(
    `/api/v1/households/${householdId}/recipe-suggestions${recipeQuery(filters)}`,
    { method: 'GET' },
  );
  if (!Array.isArray(recipes)) throw new Error('Recipe suggestions returned an invalid response.');
  return recipes;
}

export function fetchRecipeDetail(householdId: number, recipeId: string, filters: RecipeRequestFilters = {}): Promise<RecipeDetail> {
  // Planned foods cannot change pantry matches or the recipe detail. Carry
  // exactly the same hard filters as the list to avoid a safety gap.
  const { plannedFoodIds: _plannedFoodIds, ...hardFilters } = filters;
  return apiRequest<RecipeDetail>(`/api/v1/households/${householdId}/recipes/${recipeId}${recipeQuery(hardFilters)}`, {
    method: 'GET',
  });
}
