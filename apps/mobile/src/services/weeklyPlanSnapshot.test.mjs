import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

import {
  createWeeklyPlanSnapshot,
  needsQuantityPolicyRefresh,
  normalizeWeeklyPlanSnapshot,
  weeklyPlanStorageOwner,
} from './weeklyPlanSnapshot.ts';

const appSource = readFileSync(new URL('../../App.tsx', import.meta.url), 'utf8');

const snapshot = {
  version: 1,
  savedAt: '2026-09-24T10:00:00.000Z',
  planDraft: {
    adults: 1,
    children: 2,
    planningLocation: { source: 'manual', label: 'Petaling', state: 'Selangor', district: 'Petaling' },
    selectedMealId: '3-5',
    customMealCount: null,
    weeklyBudget: 100,
    selectedRestrictions: ['none'],
    customRestriction: '',
    usualProductIds: ['SF018'],
  },
  basketDraft: [{
    productId: 'SF018',
    name: 'chicken egg',
    imageSource: null,
    suggestedQuantity: 10,
    unit: 'biji',
    source: 'usual',
    choice: 'have',
  }],
  planResult: { status: 'FEASIBLE', items: [], plan_generation_id: 'plan-1' },
  postedSelectionIds: ['SF018'],
};

test('restores the exact chosen weekly plan and item choices', () => {
  assert.deepEqual(normalizeWeeklyPlanSnapshot(snapshot), snapshot);
});

test('older saved quantities are refreshed while new plans keep their quantity policy version', () => {
  assert.equal(needsQuantityPolicyRefresh(snapshot), true);
  const current = createWeeklyPlanSnapshot(snapshot);
  assert.equal(needsQuantityPolicyRefresh(current), false);
  assert.equal(current.quantityPolicyVersion, 3);
  assert.equal(needsQuantityPolicyRefresh({ ...current, quantityPolicyVersion: 2 }), true);
});

test('rejects malformed or empty active-plan snapshots', () => {
  assert.equal(normalizeWeeklyPlanSnapshot({ ...snapshot, basketDraft: [] }), null);
  assert.equal(normalizeWeeklyPlanSnapshot({ ...snapshot, version: 2 }), null);
  assert.equal(normalizeWeeklyPlanSnapshot({ ...snapshot, planResult: null }), null);
});

test('separates guest plans from each signed-in user', () => {
  assert.equal(weeklyPlanStorageOwner(null), 'guest');
  assert.equal(weeklyPlanStorageOwner('user-123'), 'user:user-123');
  assert.notEqual(weeklyPlanStorageOwner('user-123'), weeklyPlanStorageOwner('user-456'));
});

test('App hydrates and saves a weekly-plan snapshot without rebuilding it', () => {
  assert.match(appSource, /loadWeeklyPlanSnapshot\(weeklyPlanOwner\)/);
  assert.match(appSource, /restoreWeeklyPlanSnapshot\(snapshot\)/);
  assert.match(appSource, /saveWeeklyPlanSnapshot\(/);

  const hydrationStart = appSource.indexOf('loadWeeklyPlanSnapshot(weeklyPlanOwner)');
  const hydrationEnd = appSource.indexOf('}, [authLoading, weeklyPlanOwner]);', hydrationStart);
  const hydrationBlock = appSource.slice(hydrationStart, hydrationEnd);
  assert.doesNotMatch(hydrationBlock, /createPlan\(/);
  assert.doesNotMatch(hydrationBlock, /postPlanForSelection\(/);
});
