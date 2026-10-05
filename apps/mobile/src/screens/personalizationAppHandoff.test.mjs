import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';

const appSource = fs.readFileSync(new URL('../../App.tsx', import.meta.url), 'utf8');
const providerSource = fs.readFileSync(new URL('../auth/AuthProvider.tsx', import.meta.url), 'utf8');
const profileSource = fs.readFileSync(new URL('./ProfileScreen.tsx', import.meta.url), 'utf8');
const questionThreeSource = fs.readFileSync(new URL('./PlanQuestionThreeScreen.tsx', import.meta.url), 'utf8');

test('skips saved personalization when Plan opens again', () => {
  assert.match(appSource, /getSavedPlanPersonalization\(appProfileData\)/);
  assert.match(appSource, /if \(savedPersonalization\)/);
  assert.match(appSource, /applyPlanPersonalization\(/);
  assert.match(appSource, /setScreen\('plan-confirmation'\)/);
});

test('saves first-time Plan personalization through the existing account profile', () => {
  assert.match(appSource, /planPersonalizationFromDraft\(planDraft\)/);
  assert.match(appSource, /saveAppProfile\(\{ personalization \}\)/);
  assert.match(providerSource, /appProfileData/);
  assert.match(providerSource, /saveAppProfile/);
  assert.match(providerSource, /'\/api\/v1\/profile'/);
});

test('opens the same three questionnaire screens from Profile for later edits', () => {
  assert.match(appSource, /'profile-personalization'/);
  assert.match(appSource, /openPersonalizationEditor/);
  assert.match(appSource, /onPersonalizationPress=\{openPersonalizationEditor\}/);
  assert.match(profileSource, /onPersonalizationPress/);
  assert.match(profileSource, /Personalization/);
  assert.match(questionThreeSource, /isEditingPersonalization/);
  assert.match(questionThreeSource, /Save personalization/);
});

test('returns to Profile only when the questionnaire was entered from Profile', () => {
  const completionHandler = appSource.slice(
    appSource.indexOf('const handlePlanPersonalizationComplete'),
    appSource.indexOf('const committedNeedIdsRef'),
  );

  assert.match(completionHandler, /planQuestionOneEntrySource === 'profile-personalization'/);
  assert.match(completionHandler, /setScreen\('profile'\)/);
});

test('allows saving personalization edits without selecting usual products', () => {
  assert.match(questionThreeSource, /!isEditingPersonalization && isBuildBasketDisabled\(selectedProductIds\)/);
});
