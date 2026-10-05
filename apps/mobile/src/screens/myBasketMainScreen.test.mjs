import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

const screenSource = fs.readFileSync(
  path.resolve(process.cwd(), 'src/screens/MyBasketMainScreen.tsx'),
  'utf8',
);
const appSource = fs.readFileSync(path.resolve(process.cwd(), 'App.tsx'), 'utf8');
const dashboardSource = fs.readFileSync(
  path.resolve(process.cwd(), 'src/screens/HomeDashboardScreen.tsx'),
  'utf8',
);

test('builds the My Basket dashboard from shared plan data and real UI sections', () => {
  assert.match(screenSource, /<Text[^>]*>My Basket<\/Text>/);
  assert.match(screenSource, /Your week, your way\./);
  assert.match(screenSource, /PlanSummary/);
  assert.match(screenSource, /Shopping list/);
  assert.match(screenSource, /What you have/);
  assert.match(screenSource, /<RecipeSuggestionSection onSeeAllMealIdeas=\{onSeeAllMealIdeas\} onRecipePress=\{onRecipePress\} recipes=\{recipeSuggestions\} \/>/);
  assert.match(screenSource, /Plan next week/);
  assert.match(screenSource, /DashboardBottomNavigation/);
  assert.match(screenSource, /activeTab="basket"/);
});

test('places database recipe suggestions after What you have with recipe navigation', () => {
  const whatYouHaveIndex = screenSource.indexOf('title="What you have"');
  const recipeIndex = screenSource.indexOf('<RecipeSuggestionSection onSeeAllMealIdeas=');
  const planNextWeekIndex = screenSource.indexOf('<PlanNextWeekCard');

  assert.ok(whatYouHaveIndex >= 0);
  assert.ok(recipeIndex > whatYouHaveIndex);
  assert.ok(planNextWeekIndex > recipeIndex);
  assert.match(screenSource, /Not sure what to cook\?/);
  assert.match(screenSource, /Meal ideas using what you have\./);
  assert.match(screenSource, /See all/);
  assert.match(screenSource, /recipes\.slice\(0, 2\)/);
  assert.match(screenSource, /recipeSuggestions = \[\]/);
  assert.doesNotMatch(screenSource, /favorite|Favorite|saved recipe/i);
});

test('purchased ticks persist pantry presence and trigger the recipe refresh path', () => {
  assert.ok(appSource.includes('onPurchasedShoppingItemsChange={handlePurchasedShoppingItemsChange}'));
  const handler = appSource.split('const handlePurchasedShoppingItemsChange =')[1]?.split('const handleRecipeHaveItemsAdded')[0] ?? '';
  assert.ok(handler.includes('await syncPurchasedPantry'));
  assert.ok(handler.includes('setPantryItems(updated)'));
  assert.ok(appSource.includes('[activeHouseholdId, isAuthenticated, pantryItems, plannedRecipeFoodKey,'));
});

test('reduces only the space before Plan next week without changing shared content spacing', () => {
  assert.match(screenSource, /content: \{[\s\S]*?gap: 12/);
  assert.match(screenSource, /planCard: \{[\s\S]*?marginTop: -12/);
});

test('keeps dashboard counts and thumbnail overflow derived from supplied items', () => {
  assert.match(screenSource, /basketItems\.filter\([\s\S]*?item\.choice === 'need'/);
  assert.match(screenSource, /pantryItems: readonly BasketDraftItem\[\]/);
  assert.match(screenSource, /const whatYouHaveItems = \[/);
  assert.match(screenSource, /recipeHaveItems/);
  assert.match(screenSource, /receiptHaveItems/);
  assert.match(screenSource, /foodImageUriForBackendId\(food\.canonical_food_id\)/);
  assert.match(screenSource, /productId: food\.canonical_food_id/);
  assert.match(appSource, /new Map\(current\.map\(\(item\) => \[item\.canonical_food_id, item\]\)\)/);
  assert.match(screenSource, /MAX_VISIBLE_THUMBNAILS = 4/);
  assert.match(screenSource, /slice\(0, MAX_VISIBLE_THUMBNAILS\)/);
  assert.match(screenSource, /overflowCount/);
  assert.match(screenSource, /\+\{overflowCount\}/);
  assert.match(screenSource, /overflowLabel/);
  assert.doesNotMatch(screenSource, /MY_BASKET_WHAT_YOU_HAVE_FIXTURE/);
});

test('deduplicates pantry foods before rendering What you have', () => {
  assert.match(screenSource, /function uniqueItemsByProductId\(items: readonly BasketDraftItem\[\]\)/);
  assert.match(screenSource, /const uniquePantryItems = uniqueItemsByProductId\(pantryItems\)/);
  assert.match(screenSource, /\.\.\.uniquePantryItems,/);
});

test('keeps the three dashboard cards and tabs tappable', () => {
  assert.match(screenSource, /setDetailView\('shopping-list'\)/);
  assert.match(screenSource, /setDetailView\('what-you-have'\)/);
  assert.match(screenSource, /onPlanNextWeek/);
  assert.match(screenSource, /onHomePress=\{onHomePress\}/);
  assert.match(screenSource, /onPriceCheckPress=\{onPriceCheckPress\}/);
});

test('shows the selected store and its prices in Shopping List detail', () => {
  assert.match(screenSource, /selectedStoreId/);
  assert.match(screenSource, /pricePrototype\.stores\.find/);
  assert.match(screenSource, /Shopping at/);
  assert.match(screenSource, /Estimated prices from this store/);
  assert.match(screenSource, /selectedStore\.address/);
  assert.match(screenSource, /No recent price/);
  assert.match(screenSource, /detailPrice/);
});

test('keeps Shopping List usable without a selected store', () => {
  assert.match(screenSource, /Store not selected/);
  assert.match(screenSource, /Choose where to shop when you&apos;re ready\./);
  assert.match(screenSource, /formatGeneralItemPrice/);
});

test('toggles a Shopping List item between purchased and unpurchased states', () => {
  assert.match(screenSource, /purchasedShoppingItems/);
  assert.match(screenSource, /purchasedShoppingItemIds/);
  assert.match(screenSource, /persistedPurchasedShoppingItems/);
  assert.match(screenSource, /onPurchasedShoppingItemsChange/);
  assert.match(screenSource, /const shoppingListItems = basketItems\.filter\([\s\S]*?item\.choice === 'need'/);
  assert.match(screenSource, /const remainingShoppingListItems = shoppingListItems\.filter\([\s\S]*?purchasedShoppingItemIds\.has\(item\.productId\)/);
  assert.match(screenSource, /setPurchasedShoppingItems/);
  assert.match(screenSource, /onItemPurchased/);
  assert.match(screenSource, /accessibilityRole="checkbox"/);
  assert.match(screenSource, /isPurchased/);
  assert.match(screenSource, /checkbox-marked/);
  assert.match(screenSource, /detailCompletedText/);
  assert.match(screenSource, /textDecorationLine: 'line-through'/);
  assert.match(screenSource, /accessibilityState=\{\{ checked: isPurchased \}\}/);
  assert.match(screenSource, /const isCompletedShoppingListItem = isShoppingList && isPurchased/);
  assert.match(screenSource, /isCompletedShoppingListItem && styles\.detailCompletedText/);
  assert.match(screenSource, /current\.filter\(\(purchasedItem\) => purchasedItem\.productId !== item\.productId\)/);
  assert.doesNotMatch(screenSource, /if \(!isPurchased\) onItemPurchased\?\.\(item\)/);
  assert.match(screenSource, /items=\{detailView === 'shopping-list' \? shoppingListItems : whatYouHaveItems\}/);
  assert.match(screenSource, /items=\{remainingShoppingListItems\}[\s\S]*?title="Shopping list"/);
  assert.match(screenSource, /subtitle=\{`\$\{remainingShoppingListItems\.length\} items left to buy\.`\}/);
});

test('marks stock as eaten through the same awaited persistence callback as removal', () => {
  // Local hiding used to leave stock available after reopening the screen.
  assert.doesNotMatch(screenSource, /consumedWhatYouHaveItemIds/);
  assert.match(screenSource, /onItemConsumed=\{onPantryItemRemove\}/);
  assert.match(screenSource, /onItemRemoved=\{onPantryItemRemove\}/);
  assert.match(screenSource, /await action\(item\)/);
  assert.match(screenSource, /onItemConsumed/);
  assert.match(screenSource, /const confirmItemConsumed = \(item: ProductPreviewItem\) =>/);
  assert.match(screenSource, /confirmRemoval\(item, true\)/);
  assert.match(screenSource, /eaten \? 'Mark as eaten\?'/);
  assert.match(screenSource, /Once confirmed, \$\{item\.name\} will be marked as eaten\./);
  assert.match(screenSource, /\{ text: 'Cancel', style: 'cancel' \}/);
  assert.match(screenSource, /window\.confirm/);
  assert.match(screenSource, /pendingRemovalIds\.current\.has\(item\.productId\)/);
  assert.match(screenSource, /accessibilityRole="alert"/);
  assert.match(screenSource, /Mark \$\{item\.name\} as eaten/);
  assert.match(screenSource, /onPress=\{\(\) => confirmItemConsumed\(item\)\}/);
  assert.match(screenSource, /name="check-circle-outline"/);
  assert.match(screenSource, /items=\{detailView === 'shopping-list' \? shoppingListItems : whatYouHaveItems\}/);
  assert.doesNotMatch(screenSource, /onItemConsumed[\s\S]*?removePantryItem/);
});

test('adds an explicit Modify mode before removing a What You Have item', () => {
  assert.match(screenSource, /const \[isModifyMode, setIsModifyMode\] = useState\(false\)/);
  assert.match(screenSource, /accessibilityLabel="Modify What You Have"/);
  assert.match(screenSource, />Modify<\/Text>/);
  assert.match(screenSource, />Done<\/Text>/);
  assert.match(screenSource, /const confirmItemRemoval = \(item: ProductPreviewItem\) =>/);
  assert.match(screenSource, /accessibilityLabel=\{`Remove \$\{item\.name\}`\}/);
  assert.match(screenSource, /name="trash-can-outline"/);
  assert.match(screenSource, /Remove \$\{item\.name\} from What You Have\?/);
  assert.match(screenSource, /detailSectionHeader/);
  const foodsAtHomeIndex = screenSource.indexOf("'Foods at home'");
  const modifyButtonIndex = screenSource.indexOf('accessibilityLabel="Modify What You Have"');
  assert.ok(foodsAtHomeIndex >= 0 && modifyButtonIndex > foodsAtHomeIndex);
});

test('saves remaining amounts explicitly inside Modify while preserving direct removal', () => {
  assert.match(screenSource, /onPantryQuantitySave/);
  assert.match(screenSource, /keyboardType="decimal-pad"/);
  assert.match(screenSource, /Remaining quantity for \$\{item\.name\}/);
  assert.doesNotMatch(screenSource, /onEndEditing=/);
  assert.match(screenSource, /Save remaining amount for \$\{item\.name\}/);
  assert.match(screenSource, /Cancel remaining amount for \$\{item\.name\}/);
  assert.match(screenSource, /onItemRemoved/);
  assert.match(screenSource, /Remove \$\{item\.name\} from What You Have\?/);
  assert.match(screenSource, /isModifyMode && !isShoppingList && onPantryQuantitySave && editablePantryFoodIds\.has\(item\.productId\)/);
  assert.doesNotMatch(screenSource, /whatYouHaveQuantityOverrides/);
});

test('stock removal preserves a separate Shopping List intention to buy more', () => {
  // Persistent stock removal must not silently delete an existing Need row.
  assert.match(
    screenSource,
    /const shoppingListItems = basketItems\.filter\(\(item\) => item\.choice === 'need'\);/,
  );
  assert.match(screenSource, /items=\{detailView === 'shopping-list' \? shoppingListItems : whatYouHaveItems\}/);
});

test('keeps dashboard previews compact and leaves Plan next week artwork controlled', () => {
  assert.match(screenSource, /height: 44/);
  assert.match(screenSource, /height: 48/);
  assert.match(screenSource, /paddingTop: 10/);
  assert.match(screenSource, /resizeMode="contain"/);
  assert.match(screenSource, /marginTop: -56/);
  assert.match(screenSource, /width: '114%'/);
  assert.doesNotMatch(screenSource, /planVisualRegion/);
});

test('uses the supplied Plan next week card visual as the only card surface', () => {
  assert.match(screenSource, /plan-next-week\.png/);
  assert.match(screenSource, /planNextWeekVisual/);
  assert.match(screenSource, /<Image[\s\S]*source=\{visual\}/);
  assert.doesNotMatch(screenSource, /planVisualPlaceholder/);
  assert.doesNotMatch(screenSource, /planCardHeader|planCardTitle|planSectionIcon/);
});

test('wires Home Dashboard My Basket to the shared main tab screen', () => {
  assert.match(appSource, /MyBasketMainScreen/);
  assert.match(appSource, /'my-basket-main'/);
  assert.match(appSource, /onBasketPress=\{\(\) => void openMyBasket\(\)\}/);
  assert.match(appSource, /basketItems=\{basketDraft\}/);
  assert.match(appSource, /selectedStoreId=\{selectedStoreId\}/);
  assert.match(appSource, /purchasedShoppingItems/);
  assert.match(appSource, /persistedPurchasedShoppingItems/);
  assert.match(appSource, /onPurchasedShoppingItemsChange/);
  assert.match(appSource, /pricePrototype=\{buildPriceGuideFromStoreComparison\(getNeedItems\(basketDraft\), basketStoreComparison\)\}/);
  assert.match(dashboardSource, /type DashboardTab = 'home' \| 'basket'/);
  assert.match(dashboardSource, /selected: activeTab === 'home'/);
  assert.match(dashboardSource, /selected: activeTab === 'basket'/);
});

test('returns to My Basket when Plan next week starts Question 1 from the basket tab', () => {
  assert.match(appSource, /onPlanNextWeek=\{\(\) => void openPlanQuestionOne\('my-basket-plan-next-week'\)\}/);
  assert.match(appSource, /planQuestionOneEntrySource === 'my-basket-plan-next-week'/);
  assert.match(appSource, /setScreen\('my-basket-main'\)/);
});

test('places the supplied OCR banner above What You Have with proportional transparent hit areas', () => {
  const bannerIndex = screenSource.indexOf('<OcrReceiptBanner');
  const foodsAtHomeIndex = screenSource.indexOf("isShoppingList ? 'Items' : 'Foods at home'");

  assert.ok(bannerIndex >= 0);
  assert.ok(foodsAtHomeIndex > bannerIndex);
  assert.match(screenSource, /ocr-banner-cropped\.png/);
  assert.match(screenSource, /aspectRatio: 1761 \/ 732/);
  assert.match(screenSource, /accessibilityLabel="Take photo"/);
  assert.match(screenSource, /accessibilityLabel="Upload image"/);
  assert.match(screenSource, /style=\{styles\.ocrTakePhotoHitArea\}/);
  assert.match(screenSource, /style=\{styles\.ocrUploadImageHitArea\}/);
  assert.match(screenSource, /left: '33\.5%'/);
  assert.match(screenSource, /left: '66\.4%'/);
  assert.match(screenSource, /onTakePhoto/);
  assert.match(screenSource, /onUploadImage/);
  assert.doesNotMatch(screenSource, /Alert\.alert\('Take photo pressed'\)/);
  assert.doesNotMatch(screenSource, /Alert\.alert\('Upload image pressed'\)/);
  assert.doesNotMatch(screenSource, /<Button[\s>]/);
});

test('keeps the OCR banner compact while rendering the full PNG at its own aspect ratio', () => {
  assert.match(screenSource, /style=\{styles\.ocrBannerImage\}/);
  assert.match(screenSource, /ocrBanner: \{[\s\S]*?alignSelf: 'center'[\s\S]*?width: '94%'/);
  assert.match(screenSource, /ocrBanner: \{[\s\S]*?Platform\.select\(\{ web: \{ aspectRatio: 1761 \/ 732/);
  assert.match(screenSource, /ocrBannerImage: \{[\s\S]*?aspectRatio: 1761 \/ 732[\s\S]*?height: undefined[\s\S]*?width: '100%'/);
  assert.doesNotMatch(screenSource, /source=\{OCR_BANNER_VISUAL\}[\s\S]*?StyleSheet\.absoluteFill/);
});
