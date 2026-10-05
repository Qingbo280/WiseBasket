import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import ts from 'typescript';

function readIfPresent(filePath) {
  return fs.existsSync(filePath) ? fs.readFileSync(filePath, 'utf8') : '';
}

const detailSource = readIfPresent(path.resolve(process.cwd(), 'src/screens/RecipeDetailScreen.tsx'));
const mealSource = fs.readFileSync(
  path.resolve(process.cwd(), 'src/screens/MealIdeasScreen.tsx'),
  'utf8',
);
const basketSource = fs.readFileSync(
  path.resolve(process.cwd(), 'src/screens/MyBasketMainScreen.tsx'),
  'utf8',
);
const appSource = fs.readFileSync(path.resolve(process.cwd(), 'App.tsx'), 'utf8');

test('renders database-backed recipe detail content with ingredients and cooking steps', () => {
  assert.match(detailSource, /recipe: RecipeDetail/);
  assert.match(detailSource, /ingredientsFromRecipe\(recipe\)/);
  assert.match(detailSource, /\{recipe\.name\}/);
  assert.match(detailSource, /recipe\.cooking_steps\.map/);
  assert.match(detailSource, /Ingredients/);
  assert.match(detailSource, /title="From what you have"/);
  assert.match(detailSource, /title="Other ingredients"/);
  assert.match(detailSource, /How to cook/);
  assert.match(detailSource, /BasketItemImage/);
  assert.match(detailSource, /cachedFoodImageSourceForBackendId\(ingredient\.foodId\)/);
});

test('keeps each backend requirement flag with its ingredient, independent of pantry grouping', async () => {
  const mapping = detailSource.match(/export function ingredientsFromRecipe[\s\S]*?\n\}/)?.[0];
  assert.ok(mapping, 'ingredient mapping exists');
  const compiled = ts.transpileModule(mapping, { compilerOptions: { module: ts.ModuleKind.ESNext } }).outputText;
  const { ingredientsFromRecipe } = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`);
  const ingredients = ingredientsFromRecipe({
    ingredients: [
      { food: { canonical_food_id: 'egg', name: 'Egg' }, required: true },
      { food: { canonical_food_id: 'oil', name: 'Oil' }, required: false },
    ],
  });
  assert.deepEqual(ingredients, [
    { foodId: 'egg', id: 'egg', name: 'Egg', required: true },
    { foodId: 'oil', id: 'oil', name: 'Oil', required: false },
  ]);
  assert.doesNotMatch(detailSource, /ingredient\.required \? 'Required' : 'Optional'/,
    'the recipe screen uses its original ingredient presentation');
});

test('opens a local ingredient check sheet and applies Have it or Need it choices', () => {
  assert.match(detailSource, /Modal/);
  assert.match(detailSource, /Check your ingredients/);
  assert.match(detailSource, /Let us know what you already have/);
  assert.match(detailSource, /Have it/);
  assert.match(detailSource, /Need it/);
  assert.match(detailSource, /selectionById/);
  assert.match(detailSource, /setSelectionById/);
  assert.match(detailSource, /handleApplySelections/);
  assert.match(detailSource, /selectedHave/);
  assert.match(detailSource, /selectedNeed/);
  assert.match(detailSource, /setHaveIngredients/);
  assert.match(detailSource, /onNeedItemsAdded/);
  assert.match(detailSource, /setOtherIngredients/);
  assert.match(detailSource, /const selectedHaveIds = new Set\(selectedHave\.map\(\(ingredient\) => ingredient\.id\)\)/);
  assert.match(detailSource, /!selectedHaveIds\.has\(ingredient\.id\)/);
  assert.match(detailSource, /initialIngredientState/);
  assert.match(detailSource, /onIngredientStateChange/);
  assert.match(detailSource, /onHaveItemsAdded/);
  assert.match(detailSource, /nextHaveIngredients/);
  assert.match(detailSource, /nextOtherIngredients/);
  assert.match(detailSource, /Add needed items to shopping list/);
  assert.match(detailSource, /onRequestClose/);
});

test('detail retains backend quantity fields while using the original recipe presentation', async () => {
  const mapping = detailSource.match(/export function ingredientsFromRecipe[\s\S]*?\n\}/)[0];
  const compiled = ts.transpileModule(mapping, { compilerOptions: { module: ts.ModuleKind.ESNext } }).outputText;
  const { ingredientsFromRecipe } = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`);
  const quantity = { quantity_status: 'INSUFFICIENT', is_quantity_sufficient: false,
    required_quantity_kg: 0.2, available_quantity_kg: 0.001, shortfall_quantity_kg: 0.199 };
  const [item] = ingredientsFromRecipe({ ingredients: [{ food: { canonical_food_id: 'SF018', name: 'Chicken egg' }, required: true, ...quantity }] });
  for (const [key, value] of Object.entries(quantity)) assert.equal(item[key], value);
  assert.doesNotMatch(detailSource, /ingredientQuantityLabel\(ingredient\)/);
  assert.doesNotMatch(detailSource, /recipeQuantityLabel\(recipe\)/);
  assert.match(detailSource, /Alert\.alert\('Ingredients could not be saved'/);
  assert.match(appSource, /onFailed: showFailure/);
  assert.match(appSource, /window\.confirm/);
  assert.match(appSource, /haveIntentIdRef\.current !== intentId/);
  assert.match(appSource, /await haveSyncQueueRef\.current\.whenIdle\(\)/);
});

for (const platform of ['web', 'ios', 'android']) {
  test(`${platform} shows a save failure, keeps choices and enables retry`, async () => {
    const handler = detailSource.match(/const handleApplySelections = async \(\) => \{[\s\S]*?\n  \};/)?.[0];
    assert.ok(handler);
    const compiled = ts.transpileModule(handler, { compilerOptions: { module: ts.ModuleKind.ESNext } }).outputText;
    const busy = [];
    const browserAlerts = [];
    const nativeAlerts = [];
    const choices = { egg: 'have' };
    const createHandler = new Function('env', `
      const { isSaving, setIsSaving, otherIngredients, selectionById, onHaveItemsAdded,
        setSelectionById, setIsCheckSheetOpen, Platform, window, Alert } = env;
      ${compiled}
      return handleApplySelections;
    `);
    const apply = createHandler({
      isSaving: false, setIsSaving: (value) => busy.push(value),
      otherIngredients: [{ id: 'egg', foodId: 'SF018', name: 'Egg' }],
      selectionById: choices,
      onHaveItemsAdded: async () => { throw new Error('Network unavailable'); },
      setSelectionById: () => assert.fail('failed saves must retain choices'),
      setIsCheckSheetOpen: () => assert.fail('failed saves must keep the sheet open'),
      Platform: { OS: platform },
      window: { alert: (message) => browserAlerts.push(message) },
      Alert: { alert: (...args) => nativeAlerts.push(args) },
    });
    await apply();
    assert.deepEqual(busy, [true, false]);
    assert.deepEqual(choices, { egg: 'have' });
    if (platform === 'web') {
      assert.equal(browserAlerts.length, 1);
      assert.match(browserAlerts[0], /Ingredients could not be saved/);
      assert.match(browserAlerts[0], /Network unavailable/);
      assert.match(browserAlerts[0], /Your choices are kept/);
      assert.deepEqual(nativeAlerts, []);
    } else {
      assert.deepEqual(browserAlerts, []);
      assert.deepEqual(nativeAlerts, [['Ingredients could not be saved', 'Network unavailable']]);
    }
  });
}

test('wires Meal Ideas to Recipe Detail and keeps recipe shopping items in the frontend basket view', () => {
  assert.match(mealSource, /onRecipePress/);
  assert.match(appSource, /'recipe-detail'/);
  assert.match(appSource, /selectedMealIdea/);
  assert.match(appSource, /<RecipeDetailScreen/);
  assert.match(appSource, /onBack=\{\(\) => setScreen\('meal-ideas'\)\}/);
  assert.match(appSource, /onNeedItemsAdded/);
  assert.match(appSource, /recipeIngredientState/);
  assert.match(appSource, /recipeHaveItems/);
  assert.match(appSource, /initialIngredientState=\{recipeIngredientState \?\? undefined\}/);
  assert.match(appSource, /onIngredientStateChange=\{setRecipeIngredientState\}/);
  assert.match(appSource, /onHaveItemsAdded/);
  assert.match(basketSource, /recipeShoppingListItems/);
  assert.match(basketSource, /recipeHaveItems/);
  assert.match(basketSource, /Shopping list/);
});
