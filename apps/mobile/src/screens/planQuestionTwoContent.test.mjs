import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {
  getContinueDisabled,
  isCustomRestrictionSelected,
  isSupportedRestriction,
  isValidCustomRestriction,
  isValidWeeklyBudget,
  PLAN_QUESTION_TWO_BUDGET_OPTIONS,
  PLAN_QUESTION_TWO_DEFAULTS,
  PLAN_QUESTION_TWO_RESTRICTION_OPTIONS,
  PLAN_QUESTION_TWO_STEP_COUNT,
  parsePositiveBudgetInput,
  toggleRestriction,
} from './planQuestionTwoContent.ts';

test('keeps Question 2 at three steps with the approved defaults', () => {
  assert.equal(PLAN_QUESTION_TWO_STEP_COUNT, 3);
  assert.deepEqual(PLAN_QUESTION_TWO_DEFAULTS, {
    customRestriction: '',
    selectedBudget: 200,
    selectedRestrictions: ['none'],
    weeklyBudget: 200,
  });
});

test('exposes the four approved quick budget values', () => {
  assert.deepEqual(PLAN_QUESTION_TWO_BUDGET_OPTIONS, [100, 150, 200, 250]);
});

test('parses only positive whole-number budget input', () => {
  assert.equal(parsePositiveBudgetInput('200'), 200);
  assert.equal(parsePositiveBudgetInput(' 250 '), 250);
  assert.equal(parsePositiveBudgetInput(''), null);
  assert.equal(parsePositiveBudgetInput('0'), null);
  assert.equal(parsePositiveBudgetInput('-10'), null);
  assert.equal(parsePositiveBudgetInput('12.5'), null);
  assert.equal(parsePositiveBudgetInput('1e2'), null);
});

test('blocks Continue until the weekly budget is a valid whole number', () => {
  assert.equal(isValidWeeklyBudget(null), false);
  assert.equal(isValidWeeklyBudget(0), false);
  assert.equal(isValidWeeklyBudget(12.5), false);
  assert.equal(isValidWeeklyBudget(200), true);
  assert.equal(getContinueDisabled(null), true);
  assert.equal(getContinueDisabled(200), false);
});

test('keeps the Other input hidden by default and visible only when Other is selected', () => {
  assert.equal(isCustomRestrictionSelected(PLAN_QUESTION_TWO_DEFAULTS.selectedRestrictions), false);
  assert.equal(isCustomRestrictionSelected(['other']), true);
});

test('requires a non-whitespace custom restriction before Continue is enabled', () => {
  assert.equal(isValidCustomRestriction(''), false);
  assert.equal(isValidCustomRestriction('   '), false);
  assert.equal(isValidCustomRestriction('Seafood'), true);
  assert.equal(getContinueDisabled(200, ['other'], ''), true);
  assert.equal(getContinueDisabled(200, ['other'], '   '), true);
  assert.equal(getContinueDisabled(200, ['other'], 'Seafood'), false);
});

test('keeps No restrictions exclusive while allowing specific restrictions to multi-select', () => {
  assert.deepEqual(toggleRestriction(['none'], 'other'), ['other']);
  assert.deepEqual(toggleRestriction(['other'], 'pork'), ['other', 'pork']);
  assert.deepEqual(toggleRestriction(['none'], 'pork'), ['pork']);
  assert.deepEqual(toggleRestriction(['pork'], 'peanuts'), ['pork', 'peanuts']);
  assert.deepEqual(toggleRestriction(['pork', 'peanuts'], 'pork'), ['peanuts']);
  assert.deepEqual(toggleRestriction(['pork', 'peanuts'], 'none'), ['none']);
  assert.deepEqual(toggleRestriction(['none'], 'none'), ['none']);
});

test('keeps the approved restriction option order and labels', () => {
  assert.deepEqual(
    PLAN_QUESTION_TWO_RESTRICTION_OPTIONS.map(({ id, label }) => ({ id, label })),
    [
      { id: 'none', label: 'No restrictions' },
      { id: 'pork', label: 'No pork' },
      { id: 'peanuts', label: 'Peanuts' },
      { id: 'dairy', label: 'Dairy' },
      { id: 'eggs', label: 'Eggs' },
      { id: 'gluten', label: 'Gluten' },
      { id: 'other', label: 'Other' },
    ],
  );
});

test('only enables restrictions supported by the planner contract', () => {
  assert.equal(isSupportedRestriction('none'), true);
  assert.equal(isSupportedRestriction('pork'), true);
  assert.equal(isSupportedRestriction('peanuts'), true);
  assert.equal(isSupportedRestriction('dairy'), true);
  assert.equal(isSupportedRestriction('eggs'), true);
  // 2026-09-11: 'gluten' and 'other' are now ACTIVE - gluten filters the
  // catalogue by grain name keywords, 'other' free-text name-matches, and
  // both become hard solver excludes at plan time (planProposal.ts).
  assert.equal(isSupportedRestriction('gluten'), true);
  assert.equal(isSupportedRestriction('other'), true);
});

test('disables unsupported restrictions without submitting them', () => {
  const screenSource = fs.readFileSync(
    new URL('./PlanQuestionTwoScreen.tsx', import.meta.url),
    'utf8',
  );

  assert.match(screenSource, /disabled=\{!isSupported\}/);
  assert.doesNotMatch(screenSource, /Not yet supported/);
  assert.match(screenSource, /if \(!isSupportedRestriction\(restrictionId\)\) return/);
});
