import type { ImageSourcePropType } from 'react-native';

export type BasketItemChoice = 'need' | 'have' | 'skip';
export type BasketItemSource = 'usual' | 'recommendation' | 'manual';

export interface BasketProposalItem {
  productId: string;
  name: string;
  /** Remote R2 image ({ uri }) when available; null renders a name fallback. */
  imageSource: ImageSourcePropType | null;
  suggestedQuantity: number;
  unit: string;
  /** Exact planner purchase weight; used as a replan floor for newly added or protected items. */
  minimumPurchaseKg?: number;
  /** Preserve this item's purchase amount as a minimum on replan. */
  protectedQuantity?: boolean;
  /** Marks an accepted rotating budget food idea. */
  budgetFallback?: boolean;
  /** A reviewed recipe add-on already supplied this purchasable amount. */
  recipeBundle?: boolean;
  needsSpace?: boolean;
  defaultChoice?: BasketItemChoice;
}

export interface BasketProposalRecommendation extends BasketProposalItem {
  reason: string;
  /** A food row whose Add action accepts the whole approved recipe bundle. */
  recipeId?: string;
  /** Backend worth angle (recipe_pairing / nutrient_gap / health_upgrade /
   *  budget_fit); absent for locally-built overflow/filler entries. Drives
   *  the 2026-09-16 worth-section group ordering. */
  angle?: string;
}

export interface BasketRecipeOpportunity {
  recipeId: string;
  name: string;
  estimatedCostRm: number;
  items: readonly BasketProposalItem[];
}

export interface BasketProposal {
  usuals: readonly BasketProposalItem[];
  recommendations: readonly BasketProposalRecommendation[];
  recipeOpportunities?: readonly BasketRecipeOpportunity[];
  /** Explicit weekly picks the reviewed recipe plan could not include. */
  deferredSelections?: readonly { productId: string; name: string }[];
}

export interface BasketDraftItem extends BasketProposalItem {
  source: BasketItemSource;
  choice: BasketItemChoice;
  reason?: string;
}

export function buildBasketDraft(proposal: BasketProposal): BasketDraftItem[] {
  return proposal.usuals.map((item) => ({
    ...item,
    source: 'usual',
    choice: item.defaultChoice ?? 'need',
  }));
}

export function setBasketItemChoice(
  draft: readonly BasketDraftItem[],
  productId: string,
  choice: BasketItemChoice,
): BasketDraftItem[] {
  return draft.map((item) => item.productId === productId ? { ...item, choice } : item);
}

export function addBasketRecommendation(
  draft: readonly BasketDraftItem[],
  recommendation: BasketProposalRecommendation,
): BasketDraftItem[] {
  const existing = draft.find((item) => item.productId === recommendation.productId);

  if (existing) {
    // 2026-09-16 user rule: a have/skip item stays in the week plan list, so
    // it can resurface here as a recommendation - "Add" flips it back to
    // Need (same semantics as addManualBasketItem), never a dead button.
    return existing.choice === 'need'
      ? [...draft]
      : setBasketItemChoice(draft, recommendation.productId, 'need');
  }

  return [
    ...draft,
    {
      ...recommendation,
      source: 'recommendation',
      choice: 'need',
    },
  ];
}

export function addBasketRecipeOpportunity(
  draft: readonly BasketDraftItem[],
  opportunity: BasketRecipeOpportunity,
): BasketDraftItem[] {
  return opportunity.items.reduce<BasketDraftItem[]>(
    (current, item) => {
      const existing = current.find((candidate) => candidate.productId === item.productId);
      if (existing) {
        const requiredKg = item.minimumPurchaseKg ?? 0;
        const existingKg = existing.minimumPurchaseKg ?? 0;
        if (existing.choice === 'need' && existingKg >= requiredKg) return current;
        return current.map((candidate) => candidate.productId === item.productId ? {
          ...candidate,
          suggestedQuantity: item.suggestedQuantity,
          unit: item.unit,
          minimumPurchaseKg: item.minimumPurchaseKg,
          protectedQuantity: true,
          recipeBundle: true,
          choice: 'need' as const,
        } : candidate);
      }
      return addBasketRecommendation(current, {
        ...item,
        recipeBundle: true,
        reason: `Needed for ${opportunity.name}.`,
      });
    },
    [...draft],
  );
}

export function addBasketSuggestedRecommendation(
  draft: readonly BasketDraftItem[],
  recommendation: BasketProposalRecommendation,
  proposal: BasketProposal,
): BasketDraftItem[] {
  const opportunity = recommendation.recipeId
    ? proposal.recipeOpportunities?.find((candidate) => candidate.recipeId === recommendation.recipeId)
    : undefined;
  return opportunity
    ? addBasketRecipeOpportunity(draft, opportunity)
    : addBasketRecommendation(draft, recommendation);
}

export function addManualBasketItem(
  draft: readonly BasketDraftItem[],
  item: BasketProposalItem,
): BasketDraftItem[] {
  const existing = draft.find((draftItem) => draftItem.productId === item.productId);

  if (existing) {
    return existing.choice === 'need'
      ? [...draft]
      : setBasketItemChoice(draft, item.productId, 'need');
  }

  return [
    ...draft,
    {
      ...item,
      source: 'manual',
      choice: 'need',
    },
  ];
}

export function removeBasketItem(
  draft: readonly BasketDraftItem[],
  productId: string,
): BasketDraftItem[] {
  return draft
    .filter((item) => item.productId !== productId || item.source === 'usual')
    .map((item) => item.productId === productId ? { ...item, choice: 'skip' } : item);
}

export function getNeedItems(draft: readonly BasketDraftItem[]): BasketDraftItem[] {
  return draft.filter((item) => item.choice === 'need');
}

export function getBasketSummary(draft: readonly BasketDraftItem[]) {
  const needItems = getNeedItems(draft);
  const visibleItems = needItems.slice(0, 4);
  const haveCount = draft.filter((item) => item.choice === 'have').length;
  const skippedCount = draft.filter((item) => item.choice === 'skip').length;

  return {
    count: needItems.length,
    visibleItems,
    overflowCount: Math.max(0, needItems.length - visibleItems.length),
    needCount: needItems.length,
    haveCount,
    skippedCount,
  };
}
