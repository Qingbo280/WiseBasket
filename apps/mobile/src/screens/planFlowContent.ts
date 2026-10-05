import { PLAN_QUESTION_ONE_MEAL_OPTIONS, type PlanQuestionOneMealId } from './planQuestionOneContent.ts';
import type { PlanQuestionTwoRestrictionId } from './planQuestionTwoContent';
import type { PlanQuestionThreeProductId } from './planQuestionThreeContent';

export interface PlanningLocation {
  source: 'gps' | 'manual';
  label: string;
  address?: string;
  latitude?: number;
  longitude?: number;
  state?: string;
  district?: string;
}

export interface PlanDraft {
  adults: number;
  children: number;
  planningLocation: PlanningLocation | null;
  selectedMealId: PlanQuestionOneMealId | null;
  customMealCount: number | null;
  weeklyBudget: number | null;
  selectedRestrictions: PlanQuestionTwoRestrictionId[];
  customRestriction: string;
  usualProductIds: PlanQuestionThreeProductId[];
}

export interface PlanPersonalization {
  adults: number;
  children: number;
  selectedMealId: PlanQuestionOneMealId | null;
  customMealCount: number | null;
  weeklyBudget: number | null;
  selectedRestrictions: PlanQuestionTwoRestrictionId[];
  customRestriction: string;
  usualProductIds: PlanQuestionThreeProductId[];
}

export const PLAN_DRAFT_DEFAULTS: PlanDraft = {
  adults: 0,
  children: 0,
  planningLocation: null,
  selectedMealId: null,
  customMealCount: null,
  weeklyBudget: null,
  selectedRestrictions: [],
  customRestriction: '',
  usualProductIds: [],
};

// Display values before the account has saved its preferences.
export const UNSET_PLAN_SUMMARY: PlanDraft = {
  ...PLAN_DRAFT_DEFAULTS,
  adults: 0,
  children: 0,
  selectedMealId: 'other',
  customMealCount: 0,
  weeklyBudget: 0,
};

export function planPersonalizationFromDraft(
  draft: Pick<PlanDraft, keyof PlanPersonalization>,
): PlanPersonalization {
  return {
    adults: draft.adults,
    children: draft.children,
    selectedMealId: draft.selectedMealId,
    customMealCount: draft.customMealCount,
    weeklyBudget: draft.weeklyBudget,
    selectedRestrictions: [...draft.selectedRestrictions],
    customRestriction: draft.customRestriction,
    usualProductIds: [...draft.usualProductIds],
  };
}

export function applyPlanPersonalization(
  draft: PlanDraft,
  personalization: PlanPersonalization,
): PlanDraft {
  return {
    ...draft,
    ...planPersonalizationFromDraft(personalization),
  };
}

export function getMealsAtHomeLabel(planDraft: Pick<PlanDraft, 'selectedMealId' | 'customMealCount'>): string {
  if (planDraft.selectedMealId === null) return '—';
  if (planDraft.selectedMealId === 'other') {
    return planDraft.customMealCount === null ? '—' : String(planDraft.customMealCount);
  }

  return PLAN_QUESTION_ONE_MEAL_OPTIONS.find(
    (option) => option.id === planDraft.selectedMealId,
  )?.label ?? planDraft.selectedMealId.replace('-', '–');
}
