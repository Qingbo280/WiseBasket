import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

const appSource = fs.readFileSync(new URL('../../App.tsx', import.meta.url), 'utf8');

test('wires Q2 Continue to Q3 and Q3 Back to Q2 in the existing TestFlow', () => {
  assert.match(appSource, /PlanQuestionThreeScreen/);
  assert.match(appSource, /\| 'plan-question-3'/);
  assert.match(appSource, /planAdjustmentActive/);
  assert.match(appSource, /setScreen\('plan-question-3'\)/);
  assert.match(appSource, /if \(screen === 'plan-question-3'\)/);
  assert.match(appSource, /onBack=\{\(\) => setScreen\('plan-question-2'\)\}/);
});

test('lets Question 3 retry a failed live catalogue request', () => {
  const screenSource = fs.readFileSync(
    new URL('./PlanQuestionThreeScreen.tsx', import.meta.url),
    'utf8',
  );

  assert.match(appSource, /onCatalogRetry=\{\(\) => void loadPlanCatalog\(\)\}/);
  assert.match(screenSource, /accessibilityLabel="Retry food catalogue"/);
  assert.match(screenSource, /onPress=\{onCatalogRetry\}/);
});

test('keeps every questionnaire Skip action moving through the live Plan flow', () => {
  assert.match(appSource, /onSkip=\{\(\) => setScreen\('plan-question-2'\)\}/);
  assert.match(appSource, /onSkip=/);
  assert.match(appSource, /setScreen\('plan-question-3'\)/);
  assert.match(appSource, /onSkip=\{\(\) => void handlePlanPersonalizationComplete\(\)\}/);
});
