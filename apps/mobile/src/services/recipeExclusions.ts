import type { PlanDraft } from '../screens/planFlowContent';

/** Only database-backed legacy exclusion codes; never send SF food IDs. */
export function buildRecipeExclusions(draft: Pick<PlanDraft, 'selectedRestrictions'>): string[] {
  const codes: Record<string, string> = {
    pork: 'NO_PORK',
    peanuts: 'PEANUTS',
    dairy: 'MILK',
    eggs: 'EGGS',
  };
  return [...new Set(draft.selectedRestrictions.map((id) => codes[id]).filter((code): code is string => !!code))].sort();
}

/** Q2 restrictions without database codes, mirrored by the recipe API's
 * canonical-name matcher. Only send Other text while its toggle is active. */
export function buildRecipeNameRestrictions(
  draft: Pick<PlanDraft, 'selectedRestrictions' | 'customRestriction'>,
): { glutenFree: boolean; customRestriction: string } {
  return {
    glutenFree: draft.selectedRestrictions.includes('gluten'),
    customRestriction: draft.selectedRestrictions.includes('other') ? draft.customRestriction.trim() : '',
  };
}
