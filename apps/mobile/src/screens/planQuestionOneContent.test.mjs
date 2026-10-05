import assert from 'node:assert/strict';
import test from 'node:test';
import {
  clampCustomMealCount,
  clampHouseholdCount,
  getContinueDisabled,
  isValidCustomMealCount,
  PLAN_QUESTION_ONE_DEFAULTS,
  PLAN_QUESTION_ONE_MEAL_OPTIONS,
  PLAN_QUESTION_ONE_STEP_COUNT,
  parseWholeNumberInput,
} from './planQuestionOneContent.ts';

test('keeps Question 1 on exactly three steps with the approved default state', () => {
  assert.equal(PLAN_QUESTION_ONE_STEP_COUNT, 3);
  assert.deepEqual(PLAN_QUESTION_ONE_DEFAULTS, {
    adults: 2,
    children: 2,
    selectedMealId: '6-9',
  });
});

test('keeps the approved meal option order and copy', () => {
  assert.deepEqual(
    PLAN_QUESTION_ONE_MEAL_OPTIONS.map(({ id, label, supportingText }) => ({
      id,
      label,
      supportingText,
    })),
    [
      { id: '3-5', label: '3–5', supportingText: 'meals' },
      { id: '6-9', label: '6–9', supportingText: 'meals' },
      { id: '10-14', label: '10–14', supportingText: 'meals' },
      { id: 'other', label: 'Other', supportingText: '' },
    ],
  );
});

test('keeps household counters within the visual control range', () => {
  assert.equal(clampHouseholdCount(0, -1), 0);
  assert.equal(clampHouseholdCount(2, 1), 3);
  assert.equal(clampHouseholdCount(9, 1), 9);
});

test('keeps custom meal input unset until a whole number is entered', () => {
  assert.equal(parseWholeNumberInput(''), null);
  assert.equal(parseWholeNumberInput('  '), null);
  assert.equal(parseWholeNumberInput('8'), 8);
  assert.equal(parseWholeNumberInput('8.5'), null);
  assert.equal(parseWholeNumberInput('-1'), null);
  assert.equal(parseWholeNumberInput('1e2'), null);
});

test('keeps Other Continue disabled until a valid custom meal count exists', () => {
  assert.equal(isValidCustomMealCount(null), false);
  assert.equal(isValidCustomMealCount(8), true);
  assert.equal(isValidCustomMealCount(-1), false);
  assert.equal(isValidCustomMealCount(1.2), false);
  assert.equal(getContinueDisabled('other', null), true);
  assert.equal(getContinueDisabled('other', 8), false);
  assert.equal(getContinueDisabled('6-9', null), false);
});

test('requires at least one household member before continuing', () => {
  assert.equal(getContinueDisabled('6-9', null, 0, 0), true);
  assert.equal(getContinueDisabled('6-9', null, 1, 0), false);
  assert.equal(getContinueDisabled('6-9', null, 0, 1), false);
});

test('only decrements custom meals to zero and plus can start explicit input', () => {
  assert.equal(clampCustomMealCount(null, -1), null);
  assert.equal(clampCustomMealCount(null, 1), 1);
  assert.equal(clampCustomMealCount(0, -1), 0);
  assert.equal(clampCustomMealCount(8, 1), 9);
});
