import test from 'node:test';
import assert from 'node:assert/strict';
import { PLAN_DRAFT_DEFAULTS } from './planFlowContent.ts';

test('starts the shared plan draft with the approved Q1-Q3 defaults', () => {
  assert.deepEqual(PLAN_DRAFT_DEFAULTS, {
    adults: 2,
    children: 2,
    selectedMealId: '6-9',
    customMealCount: null,
    weeklyBudget: 200,
    selectedRestrictions: ['none'],
    customRestriction: '',
    planningLocation: null,
    usualProductIds: [],
  });
});
