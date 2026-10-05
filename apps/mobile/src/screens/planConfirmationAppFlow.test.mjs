import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';

const appSource = fs.readFileSync(new URL('../../App.tsx', import.meta.url), 'utf8');
const readIfPresent = (relativePath) => {
  const url = new URL(relativePath, import.meta.url);
  return fs.existsSync(url) ? fs.readFileSync(url, 'utf8') : '';
};
const confirmationSource = readIfPresent('./PlanConfirmationScreen.tsx');
const buildingSource = readIfPresent('./PlanBuildingScreen.tsx');
const summarySource = fs.readFileSync(new URL('./PlanSummary.tsx', import.meta.url), 'utf8');
const questionOneSource = fs.readFileSync(new URL('./PlanQuestionOneScreen.tsx', import.meta.url), 'utf8');
const questionTwoSource = fs.readFileSync(new URL('./PlanQuestionTwoScreen.tsx', import.meta.url), 'utf8');

test('shows the saved Plan settings before creating a new plan', () => {
  assert.match(appSource, /'plan-confirmation'/);
  assert.match(appSource, /PlanConfirmationScreen/);
  assert.match(appSource, /setScreen\('plan-confirmation'\)/);
  assert.match(appSource, /onConfirm=\{handlePlanConfirmationConfirm\}/);
  assert.match(confirmationSource, /PlanSummary/);
  assert.match(summarySource, /Budget/);
  assert.match(summarySource, /Household/);
  assert.match(summarySource, /Meals at home/);
});

test('requires confirmation before the saved Plan calls the planner', () => {
  assert.match(appSource, /handlePlanConfirmationConfirm/);
  assert.match(appSource, /setScreen\('plan-building'\)/);
  assert.match(appSource, /handleBuildBasket\(planDraft\)/);
  assert.match(confirmationSource, /Confirm & build plan/);
});

test('adjusts an existing Plan through only the first two questionnaire steps', () => {
  assert.match(appSource, /planAdjustmentActive/);
  assert.match(appSource, /onAdjust=\{handlePlanConfirmationAdjust\}/);
  assert.match(appSource, /stepCount=\{planAdjustmentActive \? 2 : 3\}/);
  assert.match(appSource, /handlePlanAdjustmentComplete/);
  assert.match(questionOneSource, /stepCount\?: number/);
  assert.match(questionTwoSource, /stepCount\?: number/);
  assert.match(questionOneSource, /Step 1 of \{stepCount\}/);
  assert.match(questionTwoSource, /Step 2 of \{stepCount\}/);
});

test('uses a dedicated loading state while the confirmed Plan is generated', () => {
  assert.match(appSource, /'plan-building'/);
  assert.match(appSource, /PlanBuildingScreen/);
  assert.match(appSource, /onRetry=\{\(\) => void handleBuildBasket\(planDraft\)\}/);
  assert.match(buildingSource, /Building your basket/);
  assert.match(buildingSource, /ActivityIndicator/);
});

test('keeps the building state free of the decorative basket icon tile', () => {
  assert.doesNotMatch(buildingSource, /loadingIcon/);
  assert.doesNotMatch(buildingSource, /basket-outline/);
  assert.match(buildingSource, /wisebasket-logo-horizontal\.png/);
});
