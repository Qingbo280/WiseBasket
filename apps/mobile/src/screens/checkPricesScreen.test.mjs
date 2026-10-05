import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

const screenSource = fs.readFileSync(
  path.resolve(process.cwd(), 'src/screens/CheckPricesScreen.tsx'),
  'utf8',
);
const basketSource = fs.readFileSync(
  path.resolve(process.cwd(), 'src/screens/PlanBasketScreen.tsx'),
  'utf8',
);
const fixtureSource = fs.readFileSync(
  path.resolve(process.cwd(), 'src/screens/fixtures/demoPriceCalculator.ts'),
  'utf8',
);

test('renders a page-specific Check Prices flow without main bottom navigation', () => {
  assert.match(screenSource, /Check Prices/);
  assert.doesNotMatch(screenSource, /BottomNavigation|DashboardBottomNavigation/);
  assert.doesNotMatch(screenSource, /progress|Progress/);
  assert.doesNotMatch(screenSource, /information-circle-outline/);
  assert.match(screenSource, /Price Guide/);
  assert.match(screenSource, /Nearby stores/);
  assert.match(screenSource, /Your items/);
  assert.match(screenSource, /View prices/);
});

test('keeps the expanded item list stable while presenting priced items first', () => {
  assert.match(screenSource, /pricedItems/);
  assert.match(screenSource, /noRecentPriceItems/);
  assert.match(screenSource, /hasRecentPrice/);
  assert.match(screenSource, /displayItems\.map/);
});

test('uses the shared My Basket plan summary and fits all store cards in one row', () => {
  assert.match(screenSource, /import \{ PlanSummary \}/);
  assert.match(screenSource, /<PlanSummary planDraft=\{planDraft\}/);
  assert.match(basketSource, /import \{ PlanSummary \}/);
  assert.match(basketSource, /<PlanSummary planDraft=\{planDraft\}/);
  assert.match(screenSource, /storeCardsRow/);
  assert.doesNotMatch(screenSource, /snapToInterval|horizontal/);
});

test('uses singular and plural compared-item copy and explains the no-store path', () => {
  assert.match(screenSource, /formatComparedItemCount/);
  assert.match(screenSource, /item compared/);
  assert.match(screenSource, /items compared/);
  assert.match(screenSource, /Not seeing a store that works for you\?/);
  assert.match(screenSource, /choose where to shop yourself/);
});

test('keeps comparison data separate from compact visible rows', () => {
  assert.match(screenSource, /commonComparedItemIds/);
  assert.match(screenSource, /visibleComparedItemIds/);
  assert.match(screenSource, /MAX_VISIBLE_COMPARED_ROWS/);
  assert.match(screenSource, /slice\(0, MAX_VISIBLE_COMPARED_ROWS\)/);
  assert.match(screenSource, /more compared items/);
  assert.match(screenSource, /comparedTotal/);
  assert.match(screenSource, /formatComparedItemCount/);
});

test('shows at most three price rows in each compact store card', () => {
  assert.match(fixtureSource, /MAX_VISIBLE_COMPARED_ROWS = 3/);
  assert.match(screenSource, /slice\(0, MAX_VISIBLE_COMPARED_ROWS\)/);
  assert.match(screenSource, /hiddenComparedCount/);
  assert.match(screenSource, /more compared items/);
});

test('keeps nearby store cards clean and gives the lowest total a subtle cue', () => {
  assert.doesNotMatch(screenSource, /store\.tag|styles\.storeTag|lowestStoreLabel/);
  assert.doesNotMatch(screenSource, /minHeight: 85/);
  assert.match(screenSource, /storeTotalValueRow/);
  assert.match(screenSource, /name="arrow-down"/);
  assert.match(screenSource, /formatComparedTotalLabel/);
});

test('supports the shared Store Details sheet and store-independent continuation', () => {
  assert.match(screenSource, /StoreDetailsSheet/);
  assert.match(screenSource, /selectedStoreId/);
  assert.match(screenSource, /onSelectedStoreIdChange/);
  assert.match(screenSource, /Choose this store/);
  assert.match(screenSource, /Add all \{basketItems\.length\} items to my shopping list/);
  assert.match(screenSource, /Prices are estimates/);
});

test('renders the derived missing-price state in Store Details', () => {
  assert.match(screenSource, /unmatchedItems/);
  assert.match(screenSource, /No price from this store/);
  assert.match(screenSource, /formatPriceGuideRange/);
});

test('labels an incomplete store total using its actual matched-item count', () => {
  assert.match(
    screenSource,
    /formatComparedTotalLabel\(store\.basketMatchedItemCount\)/,
  );
  assert.doesNotMatch(
    screenSource,
    /formatComparedTotalLabel\(commonComparedItemIds\.length\)/,
  );
});

test('switches the bottom action between no-store and selected-store states', () => {
  assert.match(screenSource, /selectedStoreId !== null/);
  assert.match(screenSource, /selectedStore\.name/);
  assert.match(screenSource, /shoppingListActionSelected/);
  assert.match(screenSource, /Add all \{basketItems\.length\} items to my shopping list/);
});

test('keeps card comparison metadata and actions aligned', () => {
  assert.match(screenSource, /alignItems: 'stretch'/);
  assert.match(screenSource, /flexDirection: 'column'/);
  assert.match(screenSource, /comparisonMeta/);
  assert.match(screenSource, /marginTop: 'auto'/);
});

test('uses stronger price values and a readable address in Store Details', () => {
  assert.match(screenSource, /comparedRowSheet/);
  assert.match(screenSource, /sheetPrice/);
  assert.match(screenSource, /sheetAddress/);
  assert.match(screenSource, /\{store\.address\}/);
  assert.match(screenSource, /sheetScrollContent/);
});

test('keeps Your items price ranges on one constrained line', () => {
  assert.match(screenSource, /numberOfLines=\{1\}[^>]*style=\{styles\.itemPrice\}/s);
  assert.match(screenSource, /itemPrice:\s*\{[\s\S]*?flexShrink: 0/);
  assert.match(screenSource, /itemPrice:\s*\{[\s\S]*?maxWidth: 142/);
});
