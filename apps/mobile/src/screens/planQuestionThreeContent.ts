import type { ImageSourcePropType } from 'react-native';
import type { FoodInfo } from '../api/plannerTypes';

export const PLAN_QUESTION_THREE_CATEGORIES = [
  { id: 'carbs', label: 'Carbs' },
  { id: 'protein', label: 'Protein' },
  { id: 'vege', label: 'Vegetables' },
  { id: 'fruit', label: 'Fruit' },
  { id: 'other', label: 'Other' },
] as const;

export type PlanQuestionThreeCategoryId =
  (typeof PLAN_QUESTION_THREE_CATEGORIES)[number]['id'];

export type PlanQuestionThreeProductId = string;

export interface PlanQuestionThreeProduct {
  id: PlanQuestionThreeProductId;
  name: string;
  category: PlanQuestionThreeCategoryId;
  /** Remote R2 image ({ uri }) when the verified manifest has one for this
   *  backend food id; null renders the name fallback instead. */
  imageSource: ImageSourcePropType | null;
  /** Authoritative hard-exclusion codes for this food (from the backend
   *  catalogue). Products matching the user's selected restrictions are
   *  filtered out of the questionnaire. */
  exclusionCodes: readonly string[];
}

/**
 * LIVE BACKEND CATALOG - there is intentionally no hardcoded product list
 * in this module. The catalogue is populated from GET /api/v1/foods (which
 * only serves catalogue-eligible foods), so hidden foods never appear and
 * every id/names matches the real database.
 */
let catalogProducts: PlanQuestionThreeProduct[] = [];

const CATEGORY_BY_BACKEND_CATEGORY: Record<string, PlanQuestionThreeCategoryId> = {
  carbohydrate: 'carbs',
  protein: 'protein',
  vegetables: 'vege',
  fruit: 'fruit',
  other: 'other',
};

function displayName(name: string): string {
  const trimmed = name.trim();
  return trimmed ? trimmed.charAt(0).toUpperCase() + trimmed.slice(1) : trimmed;
}

export function mapCatalogFoodToQuestionThreeProduct(
  food: FoodInfo,
  imageUriForBackendId: (foodId: string) => string | null = () => null,
): PlanQuestionThreeProduct {
  const category = CATEGORY_BY_BACKEND_CATEGORY[food.category] ?? 'other';
  const uri = imageUriForBackendId(food.food_id);

  return {
    id: food.food_id,
    name: displayName(food.name || food.food_id),
    category,
    imageSource: uri ? { uri } : null,
    exclusionCodes: food.exclusion_codes ?? [],
  };
}

/**
 * Restriction (Q2) -> authoritative exclusion codes, mirroring the backend
 * contract in planProposal.ts (allergies/patterns map onto the same codes).
 * 'gluten' has no exclusion code in the database, so it filters nothing
 * here - it filters by grain NAME keywords below (GLUTEN_NAME_KEYWORDS) and
 * becomes a hard solver `excludes` list in planProposal.ts.
 */
export const EXCLUSION_CODES_BY_RESTRICTION: Readonly<
  Record<string, readonly string[]>
> = {
  pork: ['NO_PORK'],
  peanuts: ['PEANUTS'],
  dairy: ['MILK'],
  eggs: ['EGGS'],
};

/**
 * 2026-09-11 (Q2 'Gluten' toggle is now active): the database has no gluten
 * exclusion code, so gluten is filtered by canonical-name keywords. Deliberately
 * conservative - only unambiguous gluten grains, no rice-based staples:
 *   wheat flour / self-raising flour / bread / noodles / pasta / oats /
 *   spaghetti / barley / rye / semolina / gluten
 * Rice foods (white rice, glutinous rice, bihun, kuey teow) do NOT match -
 * "glutinous" does not contain "gluten".
 */
export const GLUTEN_NAME_KEYWORDS: readonly string[] = [
  'wheat',
  'flour',
  'bread',
  'noodle',
  'pasta',
  'oats',
  'spaghetti',
  'barley',
  'rye',
  'semolina',
  'gluten',
];

export function foodMatchesGlutenKeywords(name: string): boolean {
  const normalized = name.trim().toLowerCase();
  if (!normalized) {
    return false;
  }
  return GLUTEN_NAME_KEYWORDS.some((keyword) => normalized.includes(keyword));
}

/**
 * Q2 'Other' free-text best-effort matcher: every alphabetic token of at
 * least 3 letters in the user's text is substring-matched against the food
 * name ("seafood, squid" -> anything named ...seafood... or ...squid...).
 * Honest best-effort by design - the user sees exactly what disappeared
 * from Q3, and the same matches become hard solver excludes.
 */
export function foodMatchesRestrictionText(name: string, restrictionText: string): boolean {
  const normalized = name.trim().toLowerCase();
  if (!normalized) {
    return false;
  }
  const tokens = restrictionText
    .toLowerCase()
    .split(/[^a-z]+/)
    .filter((token) => token.length >= 3);
  return tokens.some((token) => (
    normalized.includes(token) ||
    (token.length >= 4 && token.endsWith('s') && !token.endsWith('ss') &&
      normalized.includes(token.slice(0, -1)))
  ));
}

export function filterProductsByRestrictions<
  T extends { name: string; exclusionCodes: readonly string[] },
>(
  products: readonly T[],
  selectedRestrictions: readonly string[],
  customRestriction = '',
): T[] {
  const blocked = new Set<string>();
  selectedRestrictions.forEach((restriction) => {
    (EXCLUSION_CODES_BY_RESTRICTION[restriction] ?? []).forEach((code) => blocked.add(code));
  });

  const filterGluten = selectedRestrictions.includes('gluten');
  const filterCustom =
    selectedRestrictions.includes('other') && customRestriction.trim().length > 0;

  if (blocked.size === 0 && !filterGluten && !filterCustom) {
    return [...products];
  }

  return products.filter((product) => {
    if (product.exclusionCodes.some((code) => blocked.has(code))) {
      return false;
    }
    if (filterGluten && foodMatchesGlutenKeywords(product.name)) {
      return false;
    }
    if (filterCustom && foodMatchesRestrictionText(product.name, customRestriction)) {
      return false;
    }
    return true;
  });
}

export function setPlanQuestionThreeProducts(products: readonly PlanQuestionThreeProduct[]) {
  catalogProducts = [...products];
}

export function getPlanQuestionThreeProducts(): readonly PlanQuestionThreeProduct[] {
  return catalogProducts;
}

export const PLAN_QUESTION_THREE_DEFAULTS = {
  selectedCategory: 'carbs',
  selectedProductIds: [] as const,
} as const satisfies {
  selectedCategory: PlanQuestionThreeCategoryId;
  selectedProductIds: readonly PlanQuestionThreeProductId[];
};

export const PLAN_QUESTION_THREE_SUMMARY_LIMIT = 4 as const;

export function getProductsForCategory(
  category: PlanQuestionThreeCategoryId,
): readonly PlanQuestionThreeProduct[] {
  return catalogProducts.filter((product) => product.category === category);
}

export function getVisibleProducts(
  category: PlanQuestionThreeCategoryId,
  searchQuery: string,
): readonly PlanQuestionThreeProduct[] {
  const normalizedQuery = searchQuery.trim().toLowerCase();

  if (!normalizedQuery) {
    return getProductsForCategory(category);
  }

  return catalogProducts.filter((product) =>
    product.name.toLowerCase().includes(normalizedQuery),
  );
}

export function toggleProductSelection(
  selectedProductIds: readonly PlanQuestionThreeProductId[],
  productId: PlanQuestionThreeProductId,
): PlanQuestionThreeProductId[] {
  if (selectedProductIds.includes(productId)) {
    return selectedProductIds.filter((id) => id !== productId);
  }

  return [...selectedProductIds, productId];
}

export function getSelectedProducts(
  selectedProductIds: readonly PlanQuestionThreeProductId[],
): readonly PlanQuestionThreeProduct[] {
  const selected = new Set(selectedProductIds);

  return catalogProducts.filter((product) => selected.has(product.id));
}

export function getSelectedSummary(
  selectedProductIds: readonly PlanQuestionThreeProductId[],
) {
  const selectedProducts = getSelectedProducts(selectedProductIds);

  return {
    count: selectedProducts.length,
    overflowCount: Math.max(0, selectedProducts.length - PLAN_QUESTION_THREE_SUMMARY_LIMIT),
    visibleProducts: selectedProducts.slice(0, PLAN_QUESTION_THREE_SUMMARY_LIMIT),
  };
}

export function isBuildBasketDisabled(
  selectedProductIds: readonly PlanQuestionThreeProductId[],
): boolean {
  return selectedProductIds.length === 0;
}
