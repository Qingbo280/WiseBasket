export const PLAN_QUESTION_TWO_STEP_COUNT = 3 as const;

export const PLAN_QUESTION_TWO_DEFAULTS = {
  customRestriction: '',
  selectedBudget: null,
  selectedRestrictions: [] as const,
  weeklyBudget: null,
} as const;

export const PLAN_QUESTION_TWO_BUDGET_OPTIONS = [100, 150, 200, 250] as const;

export const PLAN_QUESTION_TWO_RESTRICTION_OPTIONS = [
  { id: 'none', label: 'No restrictions', assetKey: 'restriction-none' },
  { id: 'pork', label: 'No pork', assetKey: 'restriction-pork' },
  { id: 'peanuts', label: 'Peanuts', assetKey: 'restriction-peanuts' },
  { id: 'dairy', label: 'Dairy', assetKey: 'restriction-dairy' },
  { id: 'eggs', label: 'Eggs', assetKey: 'restriction-eggs' },
  // 2026-09-11: both previously-disabled toggles are now ACTIVE.
  //  - 'gluten' has no hard-exclusion code in the database, so it filters
  //    client-side by grain name keywords (see GLUTEN_NAME_KEYWORDS in
  //    planQuestionThreeContent.ts) and maps to hard solver `excludes` in
  //    planProposal.ts - the plan can never quietly buy a filtered food.
  //  - 'other' reveals the free-text field; the text matches food names the
  //    same way (Q3 filter + solver excludes).
  { id: 'gluten', label: 'Gluten', assetKey: 'restriction-gluten' },
  { id: 'other', label: 'Other', assetKey: null },
] as const;

export type PlanQuestionTwoRestrictionId =
  (typeof PLAN_QUESTION_TWO_RESTRICTION_OPTIONS)[number]['id'];

export function isSupportedRestriction(restrictionId: PlanQuestionTwoRestrictionId): boolean {
  const option = PLAN_QUESTION_TWO_RESTRICTION_OPTIONS.find(({ id }) => id === restrictionId);
  return option !== undefined && !('supported' in option && option.supported === false);
}

export function parsePositiveBudgetInput(value: string): number | null {
  const trimmed = value.trim();

  if (!/^\d+$/.test(trimmed)) {
    return null;
  }

  const parsed = Number(trimmed);

  return Number.isSafeInteger(parsed) && parsed > 0 ? parsed : null;
}

export function isValidWeeklyBudget(value: number | null): value is number {
  return value !== null && Number.isSafeInteger(value) && value > 0;
}

export function isCustomRestrictionSelected(
  selected: readonly PlanQuestionTwoRestrictionId[],
): boolean {
  return selected.includes('other');
}

export function isValidCustomRestriction(value: string): boolean {
  return value.trim().length > 0;
}

export function getContinueDisabled(
  weeklyBudget: number | null,
  selectedRestrictions: readonly PlanQuestionTwoRestrictionId[] = [],
  customRestriction = '',
): boolean {
  if (!isValidWeeklyBudget(weeklyBudget)) {
    return true;
  }

  if (selectedRestrictions.length === 0) {
    return true;
  }

  return (
    isCustomRestrictionSelected(selectedRestrictions)
    && !isValidCustomRestriction(customRestriction)
  );
}

export function toggleRestriction(
  selected: readonly PlanQuestionTwoRestrictionId[],
  restrictionId: PlanQuestionTwoRestrictionId,
): PlanQuestionTwoRestrictionId[] {
  if (restrictionId === 'none') {
    return ['none'];
  }

  const withoutNone = selected.filter((id) => id !== 'none');

  if (withoutNone.includes(restrictionId)) {
    return withoutNone.filter((id) => id !== restrictionId);
  }

  return [...withoutNone, restrictionId];
}
