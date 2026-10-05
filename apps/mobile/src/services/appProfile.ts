import {
  PLAN_QUESTION_ONE_MEAL_OPTIONS,
  type PlanQuestionOneMealId,
} from '../screens/planQuestionOneContent.ts';
import type { PlanPersonalization } from '../screens/planFlowContent.ts';
import { PLAN_QUESTION_TWO_RESTRICTION_OPTIONS } from '../screens/planQuestionTwoContent.ts';

export interface AppProfileData {
  [key: string]: unknown;
  display_name?: string;
  personalization?: PlanPersonalization;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

function isSafeInteger(value: unknown): value is number {
  return typeof value === 'number' && Number.isSafeInteger(value);
}

function isMealId(value: unknown): value is PlanQuestionOneMealId {
  return PLAN_QUESTION_ONE_MEAL_OPTIONS.some((option) => option.id === value);
}

function isRestrictionId(value: unknown): value is PlanPersonalization['selectedRestrictions'][number] {
  return PLAN_QUESTION_TWO_RESTRICTION_OPTIONS.some((option) => option.id === value);
}

function isNullableNonNegativeInteger(value: unknown): value is number | null {
  return value === null || (isSafeInteger(value) && value >= 0);
}

function isNullablePositiveInteger(value: unknown): value is number | null {
  return value === null || (isSafeInteger(value) && value > 0);
}

function normalizePlanPersonalization(value: unknown): PlanPersonalization | null {
  if (!isRecord(value)) return null;

  const selectedRestrictions = value.selectedRestrictions;
  const usualProductIds = value.usualProductIds;
  const adults = value.adults;
  const children = value.children;
  const selectedMealId = value.selectedMealId;
  const customMealCount = value.customMealCount;
  const weeklyBudget = value.weeklyBudget;
  const customRestriction = value.customRestriction;

  if (
    !isSafeInteger(adults)
    || adults < 0
    || adults > 9
    || !isSafeInteger(children)
    || children < 0
    || children > 9
    || !isMealId(selectedMealId)
    || !isNullableNonNegativeInteger(customMealCount)
    || !isNullablePositiveInteger(weeklyBudget)
    || !Array.isArray(selectedRestrictions)
    || !selectedRestrictions.every(isRestrictionId)
    || typeof customRestriction !== 'string'
    || !Array.isArray(usualProductIds)
    || !usualProductIds.every((id) => typeof id === 'string' && id.trim().length > 0)
  ) {
    return null;
  }

  return {
    adults,
    children,
    selectedMealId,
    customMealCount,
    weeklyBudget,
    selectedRestrictions: [...new Set(selectedRestrictions)],
    customRestriction,
    usualProductIds: [...new Set(usualProductIds)],
  };
}

export function getSavedPlanPersonalization(
  profileData: AppProfileData | null | undefined,
): PlanPersonalization | null {
  return normalizePlanPersonalization(profileData?.personalization);
}

export function normalizeAppProfileData(value: unknown): AppProfileData {
  if (!isRecord(value)) return {};

  const personalization = normalizePlanPersonalization(value.personalization);
  return {
    ...value,
    ...(personalization ? { personalization } : {}),
  };
}
