import type { PlanResponse } from '../api/plannerTypes';
import type { BasketDraftItem } from '../screens/basketContent';
import type { PlanDraft } from '../screens/planFlowContent';

export const WEEKLY_PLAN_SNAPSHOT_VERSION = 1 as const;
export const WEEKLY_PLAN_QUANTITY_POLICY_VERSION = 3 as const;

export interface WeeklyPlanSnapshot {
  version: typeof WEEKLY_PLAN_SNAPSHOT_VERSION;
  quantityPolicyVersion?: number;
  savedAt: string;
  planDraft: PlanDraft;
  basketDraft: BasketDraftItem[];
  planResult: PlanResponse;
  postedSelectionIds: string[];
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === 'string' && value.trim().length > 0;
}

function isBasketDraftItem(value: unknown): value is BasketDraftItem {
  if (!isRecord(value)) return false;
  return (
    isNonEmptyString(value.productId)
    && isNonEmptyString(value.name)
    && typeof value.suggestedQuantity === 'number'
    && Number.isFinite(value.suggestedQuantity)
    && value.suggestedQuantity >= 0
    && isNonEmptyString(value.unit)
    && ['usual', 'recommendation', 'manual'].includes(String(value.source))
    && ['need', 'have', 'skip'].includes(String(value.choice))
  );
}

function isPlanDraft(value: unknown): value is PlanDraft {
  if (!isRecord(value)) return false;
  return (
    Number.isSafeInteger(value.adults)
    && Number.isSafeInteger(value.children)
    && (value.weeklyBudget === null || (
      typeof value.weeklyBudget === 'number' && Number.isFinite(value.weeklyBudget)
    ))
    && isNonEmptyString(value.selectedMealId)
    && Array.isArray(value.selectedRestrictions)
    && value.selectedRestrictions.every(isNonEmptyString)
    && typeof value.customRestriction === 'string'
    && Array.isArray(value.usualProductIds)
    && value.usualProductIds.every(isNonEmptyString)
  );
}

function isPlanResult(value: unknown): value is PlanResponse {
  return (
    isRecord(value)
    && isNonEmptyString(value.status)
    && Array.isArray(value.items)
    && isNonEmptyString(value.plan_generation_id)
  );
}

export function normalizeWeeklyPlanSnapshot(value: unknown): WeeklyPlanSnapshot | null {
  if (!isRecord(value) || value.version !== WEEKLY_PLAN_SNAPSHOT_VERSION) return null;
  if (!isNonEmptyString(value.savedAt) || Number.isNaN(Date.parse(value.savedAt))) return null;
  if (!isPlanDraft(value.planDraft) || !isPlanResult(value.planResult)) return null;
  if (!Array.isArray(value.basketDraft) || value.basketDraft.length === 0) return null;
  if (!value.basketDraft.every(isBasketDraftItem)) return null;
  if (!Array.isArray(value.postedSelectionIds) || !value.postedSelectionIds.every(isNonEmptyString)) {
    return null;
  }

  return value as unknown as WeeklyPlanSnapshot;
}

export function weeklyPlanStorageOwner(userId: string | null | undefined): string {
  return userId ? `user:${userId}` : 'guest';
}

export function needsQuantityPolicyRefresh(snapshot: WeeklyPlanSnapshot): boolean {
  return (snapshot.quantityPolicyVersion ?? 1) < WEEKLY_PLAN_QUANTITY_POLICY_VERSION;
}

export function createWeeklyPlanSnapshot(input: Omit<WeeklyPlanSnapshot, 'version' | 'savedAt'>): WeeklyPlanSnapshot {
  return {
    ...input,
    version: WEEKLY_PLAN_SNAPSHOT_VERSION,
    quantityPolicyVersion: input.quantityPolicyVersion ?? WEEKLY_PLAN_QUANTITY_POLICY_VERSION,
    savedAt: new Date().toISOString(),
    basketDraft: [...input.basketDraft],
    postedSelectionIds: [...input.postedSelectionIds],
  };
}
