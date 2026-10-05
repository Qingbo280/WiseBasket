import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

const screenSource = fs.readFileSync(
  path.resolve(process.cwd(), 'src/screens/PlanBasketScreen.tsx'),
  'utf8',
);

test('keeps the basket flow in one screen with three local view states', () => {
  assert.match(screenSource, /basketView/);
  assert.match(screenSource, /'edit'/);
  assert.match(screenSource, /'review'/);
  assert.match(screenSource, /'confirmed'/);
  assert.match(screenSource, /Review your basket/);
  assert.match(screenSource, /Basket confirmed!/);
});

test('derives footer and review content from BasketDraft Need items', () => {
  assert.match(screenSource, /getNeedItems/);
  assert.match(screenSource, /getBasketSummary/);
  assert.match(screenSource, /Review basket/);
  assert.match(screenSource, /Confirm &amp; check prices/);
  assert.match(screenSource, /Back to edit basket/);
});

test('keeps BasketDraft owned by TestFlow so Have choices survive into My Basket', () => {
  assert.match(screenSource, /basketDraft: readonly BasketDraftItem\[\]/);
  assert.match(screenSource, /onBasketDraftChange/);
  assert.doesNotMatch(screenSource, /useState<BasketDraftItem\[\]>/);
});

test('reuses the shared PlanSummary component for the approved summary visual', () => {
  assert.match(screenSource, /import \{ PlanSummary \}/);
  assert.match(screenSource, /<PlanSummary planDraft=\{planDraft\}/);
  assert.doesNotMatch(screenSource, /function ProfileSummary/);
});


test('confirm-time re-solve shows busy feedback on the check-prices button', () => {
  // 2026-09-14 real-device feedback: tapping "Let's check prices" silently
  // re-solves quantities for seconds with zero feedback. The screen must
  // surface the busy state (disabled button + "Checking prices…" label).
  assert.match(screenSource, /checkPriceBusy\?: boolean/);
  assert.match(screenSource, /busy=\{checkPriceBusy\}/);
  assert.match(screenSource, /disabled=\{busy\}/);
  assert.match(screenSource, /busy \? 'Checking prices…'/);
});

test('optimistically added worth-considering items render in the week plan immediately', () => {
  // 2026-09-15 user rule: an accepted recommendation lives in the draft as
  // source 'recommendation' until the next re-solve promotes it to a usual -
  // the week plan section must render those items (and count them) instead
  // of waiting for the backend round trip. 2026-09-16 user rule: a have/skip
  // item STAYS in the week plan list, so recommendation items render
  // regardless of their choice.
  assert.match(screenSource, /item\.source === 'recommendation',?\s*\)/);
  assert.doesNotMatch(screenSource, /item\.source === 'recommendation' && item\.choice === 'need'/);
  // 2026-09-17 (A6 completion): draft-order filter, not the source-grouped
  // concat - recommendation items still render (regex above), positions
  // just no longer jump between source groups on a re-solve.
  assert.match(screenSource, /const allUsualItems = basketDraft\.filter\(/);
  assert.match(screenSource, /count=\{allUsualItems\.length\}/);
});

test('worth considering never repeats an item already present in week plan', () => {
  assert.match(screenSource, /const weekPlanIds = new Set\(allUsualItems\.map/);
  assert.match(screenSource, /recommendation\) => !weekPlanIds\.has\(recommendation\.productId\)/);
  assert.match(screenSource, /count=\{availableRecommendations\.length\}/);
  assert.match(screenSource, /No new safe, priced food idea is available right now\./);
});

test('keeps the original basket layout while a food-row add can accept its recipe bundle', () => {
  assert.doesNotMatch(screenSource, /Some chosen foods are outside this recipe plan/);
  assert.doesNotMatch(screenSource, /RecipeOpportunityRow/);
  assert.doesNotMatch(screenSource, /Add ingredients/);
  assert.match(screenSource, /addBasketSuggestedRecommendation/);
  assert.match(screenSource, /count=\{availableRecommendations\.length\}/);
});

test('worth-considering rows do not show the temporary recipe-unlock subtitle', () => {
  assert.doesNotMatch(screenSource, /recommendation\.reason/);
  assert.doesNotMatch(screenSource, /recommendationReason/);
});
