import assert from 'node:assert/strict';
import test from 'node:test';

import {
  applyPlanPersonalization,
  getMealsAtHomeLabel,
  planPersonalizationFromDraft,
} from './planFlowContent.ts';
import { getSavedPlanPersonalization } from '../services/appProfile.ts';

test('meal summary matches the selected button while preserving the stored meal ID', () => {
  assert.equal(getMealsAtHomeLabel({ selectedMealId: '3-5', customMealCount: null }), '1–4');
  assert.equal(getMealsAtHomeLabel({ selectedMealId: '6-9', customMealCount: null }), '5–7');
  assert.equal(getMealsAtHomeLabel({ selectedMealId: '10-14', customMealCount: null }), '8–10');
  assert.equal(getMealsAtHomeLabel({ selectedMealId: 'other', customMealCount: 12 }), '12');
});

test('round-trips personalization without replacing the current planning location', () => {
  const preferences = planPersonalizationFromDraft({
    adults: 3,
    children: 1,
    planningLocation: null,
    selectedMealId: '10-14',
    customMealCount: null,
    weeklyBudget: 250,
    selectedRestrictions: ['dairy'],
    customRestriction: '',
    usualProductIds: ['SF001', 'SF002'],
  });

  assert.deepEqual(
    applyPlanPersonalization(
      {
        adults: 2,
        children: 2,
        planningLocation: {
          source: 'manual',
          label: 'South View',
          address: 'South View Serviced Apartments',
        },
        selectedMealId: '6-9',
        customMealCount: null,
        weeklyBudget: 200,
        selectedRestrictions: ['none'],
        customRestriction: '',
        usualProductIds: [],
      },
      preferences,
    ),
    {
      adults: 3,
      children: 1,
      planningLocation: {
        source: 'manual',
        label: 'South View',
        address: 'South View Serviced Apartments',
      },
      selectedMealId: '10-14',
      customMealCount: null,
      weeklyBudget: 250,
      selectedRestrictions: ['dairy'],
      customRestriction: '',
      usualProductIds: ['SF001', 'SF002'],
    },
  );
});

test('hydrates only a valid saved personalization profile', () => {
  const saved = getSavedPlanPersonalization({
    personalization: {
      adults: 2,
      children: 1,
      selectedMealId: '6-9',
      customMealCount: null,
      weeklyBudget: 200,
      selectedRestrictions: ['none'],
      customRestriction: '',
      usualProductIds: ['SF001', 'SF001'],
    },
  });

  assert.deepEqual(saved?.usualProductIds, ['SF001']);
  assert.equal(
    getSavedPlanPersonalization({ personalization: { adults: -1 } }),
    null,
  );
});
