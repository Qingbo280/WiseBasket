export const PLAN_QUESTION_ONE_STEP_COUNT = 3 as const;

export const PLAN_QUESTION_ONE_DEFAULTS = {
  adults: 0,
  children: 0,
  selectedMealId: null,
} as const;

export const PLAN_QUESTION_ONE_MEAL_OPTIONS = [
  {
    id: '3-5',
    label: '1–4',
    supportingText: 'meals',
    assetKey: 'meals-3-5',
    accessibilityLabel: '1 to 4 meals',
  },
  {
    id: '6-9',
    label: '5–7',
    supportingText: 'meals',
    assetKey: 'meals-6-9',
    accessibilityLabel: '5 to 7 meals',
  },
  {
    id: '10-14',
    label: '8–10',
    supportingText: 'meals',
    assetKey: 'meals-10-14',
    accessibilityLabel: '8 to 10 meals',
  },
  {
    id: 'other',
    label: '11+',
    supportingText: 'meals',
    accessibilityLabel: '11 or more meals',
  },
] as const;

export type PlanQuestionOneMealId = (typeof PLAN_QUESTION_ONE_MEAL_OPTIONS)[number]['id'];

export function clampHouseholdCount(value: number, delta: number): number {
  return Math.min(9, Math.max(0, value + delta));
}

export function parseWholeNumberInput(value: string): number | null {
  const trimmed = value.trim();

  if (!/^\d+$/.test(trimmed)) {
    return null;
  }

  const parsed = Number(trimmed);
  return Number.isSafeInteger(parsed) && parsed >= 0 ? parsed : null;
}

export function isValidCustomMealCount(value: number | null): boolean {
  return value !== null && Number.isSafeInteger(value) && value >= 0;
}

export function isValidHousehold(adults: number, children: number): boolean {
  return adults + children > 0;
}

export function getContinueDisabled(
  selectedMealId: PlanQuestionOneMealId | null,
  customMealCount: number | null,
  adults = 1,
  children = 0,
): boolean {
  return (
    !isValidHousehold(adults, children)
    || selectedMealId === null
    || (selectedMealId === 'other' && !isValidCustomMealCount(customMealCount))
  );
}

export function clampCustomMealCount(value: number | null, delta: number): number | null {
  if (value === null) {
    return delta > 0 ? 1 : null;
  }

  return Math.max(0, value + delta);
}
