import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

const screenSource = fs.readFileSync(
  path.resolve(process.cwd(), 'src/screens/PlanBasketScreen.tsx'),
  'utf8',
);
const basketContentSource = fs.readFileSync(
  path.resolve(process.cwd(), 'src/screens/basketContent.ts'),
  'utf8',
);
const summarySource = fs.readFileSync(
  path.resolve(process.cwd(), 'src/screens/PlanSummary.tsx'),
  'utf8',
);

test('provides a local catalog search overlay for adding manual basket items', () => {
  assert.match(screenSource, /Add item/);
  assert.match(screenSource, /Search foods/);
  assert.match(screenSource, /getPlanQuestionThreeProducts/);
  assert.match(screenSource, /addManualBasketItem/);
  assert.match(basketContentSource, /source: 'manual'/);
  assert.match(screenSource, /isAddItemOpen/);
});

test('keeps basket rows compact while preserving the two-line product name layout', () => {
  assert.match(screenSource, /numberOfLines=\{2\}/);
  assert.match(screenSource, /height: 48,/);
  assert.match(screenSource, /minWidth: 54,/);
  assert.match(screenSource, /Added/);
});

test('reuses transparent approved artwork and removes icon box treatment', () => {
  assert.match(summarySource, /adult\.png/);
  assert.match(summarySource, /child\.png/);
  assert.match(summarySource, /meals-6-9\.png/);
  assert.match(screenSource, /BASKET_CONFIRMATION_ART/);
  assert.doesNotMatch(screenSource, /backgroundColor: '#FFF3F0'/);
  assert.doesNotMatch(screenSource, /backgroundColor: '#EEF9F0'/);
});

test('keeps the add-item title at natural height inside its sheet header', () => {
  assert.match(screenSource, /addItemSheetHeader/);
  assert.match(screenSource, /addItemSheetTitle/);
  assert.match(screenSource, /minHeight: 68,/);
});

test('does not close the add-item sheet when a catalog item is added', () => {
  const addManualItemBlock = screenSource.match(
    /const addManualItem = \(item: BasketProposalItem\) => \{[\s\S]*?\n  \};/,
  )?.[0];

  assert.ok(addManualItemBlock);
  assert.doesNotMatch(addManualItemBlock, /setIsAddItemOpen\(false\)/);
});

test('collapses usual, manually added and optimistically added items as one bounded list', () => {
  assert.match(screenSource, /const USUALS_COLLAPSED_LIMIT = 3;/);
  // 2026-09-17 (A6 completion): one draft-order filter replaces the old
  // source-grouped concat ([...usuals, ...manuals, ...added]) - the render
  // must not reshuffle the week plan when a re-solve promotes sources.
  assert.match(screenSource, /const allUsualItems = basketDraft\.filter\(/);
  assert.match(screenSource, /item\.source === 'recommendation'/);
  assert.match(screenSource, /allUsualItems\.slice\(0, USUALS_COLLAPSED_LIMIT\)/);
  assert.match(screenSource, /allUsualItems\.length - visibleUsualItems\.length/);
  assert.doesNotMatch(screenSource, /manualItems\.map\(/);
});
