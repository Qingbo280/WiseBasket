import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

const appSource = fs.readFileSync(path.resolve(process.cwd(), 'App.tsx'), 'utf8');
const basketScreenSource = fs.readFileSync(
  path.resolve(process.cwd(), 'src/screens/PlanBasketScreen.tsx'),
  'utf8',
);

test('keeps one shared PlanDraft through Q1, Q2, Q3 and My Basket', () => {
  assert.match(appSource, /PlanDraft/);
  assert.match(appSource, /PLAN_DRAFT_DEFAULTS/);
  assert.match(appSource, /onStateChange=/);
  assert.match(appSource, /initialAdults=\{planDraft\.adults\}/);
  assert.match(appSource, /initialWeeklyBudget=\{planDraft\.weeklyBudget\}/);
  assert.match(appSource, /initialSelectedProductIds=\{planDraft\.usualProductIds\}/);
  assert.match(appSource, /plan-question-3/);
  assert.match(appSource, /plan-basket/);
  // multi-line call with the catalogue argument (gluten/custom name-matching)
  assert.match(appSource, /planRequestFromDraft\(\s*draftOverride,\s*draftOverride\.usualProductIds,/);
  // the proposal is built from the POSTED selection set (need items incl.
  // accepted recommendations), never the stale Q3 tick list - else accepted
  // items vanish from the rebuilt basket (2026-09-14 regression fix).
  assert.match(appSource, /createPlanBasketProposal\(\s*result,\s*planCatalogFoods \?\? \[\],\s*request\.selected_food_ids,/);
  assert.match(appSource, /check-prices/);
  assert.match(appSource, /CheckPricesScreen/);
  assert.match(appSource, /buildPriceGuideFromStoreComparison\(checkPriceItems, basketStoreComparison\)/);
  assert.match(appSource, /fetchBasketPrices/);
});

test('routes Q3 Build my basket into the shared basket flow', () => {
  assert.match(appSource, /onBuildBasket=\{\(\) => \{[\s\S]*?void handlePlanPersonalizationComplete\(\);/);
  assert.match(appSource, /setScreen\('plan-basket'\)/);
  assert.match(appSource, /onBack=\{handlePlanBasketBack\}/);
  assert.match(appSource, /onCheckPrices=\{\(items\) => void handleConfirmCheckPrices\(items\)\}/);
  assert.match(appSource, /const finalItems = getNeedItems\(basketDraftRef\.current\)/);
  assert.match(appSource, /setCheckPriceItems\(finalItems\)/);
});

test('returns a generated plan to the feature that launched it', () => {
  const handlerBody = appSource.match(
    /const handlePlanBasketBack = \(\) => \{([\s\S]*?)\n  \};/,
  )?.[1];

  assert.ok(handlerBody, 'Plan Basket should define a source-aware back handler');
  assert.match(handlerBody, /home-create-plan/);
  assert.match(handlerBody, /home-plan-next-week/);
  assert.match(handlerBody, /setScreen\('home-dashboard'\)/);
  assert.match(handlerBody, /my-basket-plan-next-week/);
  assert.match(handlerBody, /setScreen\('my-basket-main'\)/);
  assert.match(handlerBody, /price-check-next-step/);
  assert.match(handlerBody, /setScreen\('price-check-next-step'\)/);
});

test('labels the generated basket back action without naming Question 3', () => {
  assert.match(basketScreenSource, /accessibilityLabel="Go back"/);
  assert.doesNotMatch(basketScreenSource, /Go back to Question 3/);
});

test('routes the confirmed basket to Check Prices while retaining TestFlow navigation', () => {
  assert.match(appSource, /if \(screen === 'check-prices'\)/);
  assert.match(appSource, /onBack=\{\(\) => \{\s*setScreen\('plan-basket'\);\s*\}\}/);
  assert.match(appSource, /basketItems=\{checkPriceItems\}/);
});

test('keeps BasketDraft and selected store in the existing TestFlow owner', () => {
  assert.match(appSource, /const \[basketDraft, setBasketDraft\]/);
  assert.match(appSource, /const \[selectedStoreId, setSelectedStoreId\]/);
  // 2026-09-14 opt-in journey: draft changes route through the re-plan wrapper
  // (selection changes debounce-re-post with selected_food_ids), not the raw
  // state setter.
  assert.match(appSource, /onBasketDraftChange=\{handleBasketDraftChange\}/);
  assert.match(appSource, /onSelectedStoreIdChange=\{setSelectedStoreId\}/);
  assert.match(appSource, /getNeedItems\(basketDraft\)/);
});

test('opt-in journey: build posts the tick set, accepts re-post selected_food_ids', () => {
  assert.match(appSource, /selectedFoodIdsRef/);
  assert.match(appSource, /postPlanForSelection\(draftOverride\.usualProductIds,\s*draftOverride\)/);
  assert.match(appSource, /postPlanForSelection\(needIds\)/);
  assert.match(appSource, /selected_food_ids/);
});

test('confirm and check prices re-solves the final need set before navigating', () => {
  // 2026-09-14 user rule: the price-check list must be exactly the review
  // basket, with quantities re-solved from it - cancel the pending debounce,
  // force the re-post and navigate only on success.
  assert.match(appSource, /const handleConfirmCheckPrices = async/);
  assert.match(appSource, /clearTimeout\(replanTimerRef\.current\)/);
  assert.match(appSource, /if \(!ok\) return; \/\/ stay on the basket screen/);
  // out-of-order re-plan guard: only the latest post may commit its result
  assert.match(appSource, /const seq = \+\+postSeqRef\.current/);
  assert.match(appSource, /if \(seq !== postSeqRef\.current\) return false/);
  assert.match(appSource, /setPostedSelectionIds\(selectedIds\)/);
});

test('fresh store quotes are checked against budget before opening Check Prices', () => {
  const handler = appSource.split('const handleConfirmCheckPrices = async')[1]?.split('\n  };')[0] ?? '';
  const fetchPosition = handler.indexOf('await fetchBasketPrices(');
  const budgetCheckPosition = handler.indexOf('overBudgetStoreQuote(freshStoreComparison, budget)');
  const navigationPosition = handler.indexOf("setScreen('check-prices')");

  assert.ok(fetchPosition >= 0 && fetchPosition < budgetCheckPosition);
  assert.ok(budgetCheckPosition < navigationPosition);
  assert.match(handler, /if \(overBudgetQuote\) \{[\s\S]*?setBudgetBlockMessage\([\s\S]*?return;/);
});

test('worth-considering adds are immediate and then re-solve recipe pairings', () => {
  // 2026-09-15 user rule: tapping Add on a worth-considering item must put it
  // into the week plan IMMEDIATELY at the universal 1000 g/ml purchase floor
  // before the debounced backend re-solve refreshes quantities and pairings.
  assert.match(appSource, /applyOptimisticAddQuantity/);
  // additions are diffed against the LAST COMMITTED re-solve need set
  assert.match(appSource, /committedNeedIdsRef/);
  // every Need/Have/Skip change that changes the Need set re-posts so Worth
  // considering always reflects the recipes enabled by the current choices.
  assert.match(appSource, /const needSetChanged = committedNeed\.length !== nextNeedIds\.length/);
  assert.match(appSource, /if \(!needSetChanged\) return;/);
  assert.match(appSource, /void postPlanForSelection\(nextNeedIds\)/);
  // The debounced post reads the current Have/Skip choices, not the previous
  // React render's basket snapshot.
  assert.match(appSource, /basketDraftRef\.current = committed;\s*\n?\s*setBasketDraft\(committed\)/);
  // the committed baseline is refreshed on every re-solve commit
  assert.match(appSource, /committedNeedIdsRef\.current = getNeedItems\(rebuiltDraft\)/);
  // fresh adds only: items already in the draft keep their solver quantity
  assert.match(appSource, /!prevDraftIds\.has\(id\)/);
});

test('a newer basket edit invalidates an in-flight re-plan before it can replace the draft', () => {
  const changeHandler = appSource.match(
    /const handleBasketDraftChange = \(next: readonly BasketDraftItem\[\]\) => \{([\s\S]*?)\n  \};/,
  )?.[1];
  assert.ok(changeHandler);
  assert.match(changeHandler, /if \(planPostInFlightRef\.current\) \{\s*\/\/[^]*?postSeqRef\.current \+= 1;/);
  assert.doesNotMatch(changeHandler, /if \(!planResult \|\| planBuild\.busy\)/);
  assert.match(appSource, /if \(seq !== postSeqRef\.current\) return false/);
  assert.match(changeHandler, /clearTimeout\(replanTimerRef\.current\);[\s\S]*?if \(!needSetChanged\) return;/);
});
