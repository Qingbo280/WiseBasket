import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

const screenPath = path.resolve(process.cwd(), 'src/screens/MealIdeasScreen.tsx');
const screenSource = fs.existsSync(screenPath) ? fs.readFileSync(screenPath, 'utf8') : '';
const basketSource = fs.readFileSync(
  path.resolve(process.cwd(), 'src/screens/MyBasketMainScreen.tsx'),
  'utf8',
);
const appSource = fs.readFileSync(path.resolve(process.cwd(), 'App.tsx'), 'utf8');

test('renders the approved Meal Ideas screen structure with supplied database recipes', () => {
  assert.match(screenSource, /Meal ideas/);
  assert.match(screenSource, /Browse recipes, with the best matches for your pantry first\./);
  assert.match(screenSource, /All.*Quick.*Stir-fry.*Soup.*Rice dish/s);
  assert.match(screenSource, /recipes\?: readonly MealIdea\[\]/);
  assert.match(screenSource, /recipes = \[\]/);
  assert.doesNotMatch(screenSource, /MEAL_IDEAS_RECIPES/);
  assert.match(screenSource, /flexWrap: ['"]wrap['"]/);
  assert.match(screenSource, /ScrollView/);
});

test('filters recipe cards locally and exposes favorite and card press interactions', () => {
  assert.match(screenSource, /setSelectedCategory/);
  assert.match(screenSource, /filteredRecipes/);
  assert.match(screenSource, /setFavoriteRecipeIds/);
  assert.match(screenSource, /Pressable/);
  assert.match(screenSource, /heart-outline/);
  assert.match(screenSource, /heart/);
});

test('native and web cards keep the compact one-line recipe badge', () => {
  const webSource = fs.readFileSync(path.resolve(process.cwd(), 'src/screens/MealIdeasScreen.web.tsx'), 'utf8');
  for (const source of [screenSource, webSource]) {
    assert.doesNotMatch(source, /\{recipe\.ingredientSummary\}/);
    assert.match(source, /<Text numberOfLines=\{1\} style=\{styles\.recipeTagText\}>\{recipe\.tag\}<\/Text>/);
    const footer = source.match(/recipeFooter: \{([\s\S]*?)\n  \},/)?.[1] ?? '';
    assert.doesNotMatch(footer, /flexWrap: 'wrap'/);
    assert.match(source, /maxWidth: '62%'/);
  }
});

test('keeps an odd filtered result in the left half-column', () => {
  const recipeCardStyle = screenSource.match(/recipeCard: \{([\s\S]*?)\n  \},/u)?.[1] ?? '';

  assert.match(recipeCardStyle, /flexBasis: ['"]48%['"]/);
  assert.match(recipeCardStyle, /flexGrow: 0/);
  assert.doesNotMatch(recipeCardStyle, /flexGrow: 1/);
});

test('connects My Basket See all to Meal Ideas and returns with the existing screen state', () => {
  assert.match(basketSource, /onSeeAllMealIdeas/);
  assert.match(basketSource, /accessibilityLabel=["']See all meal ideas["']/);
  assert.match(appSource, /'meal-ideas'/);
  assert.match(appSource, /fetchRecipeSuggestions/);
  assert.doesNotMatch(appSource, /confirmPantryItems\(householdId\)/);
  assert.match(appSource, /recipeImageSourceForId\(recipe\.recipe_id\)/);
  assert.match(appSource, /<MealIdeasScreen/);
  assert.match(appSource, /onBack=\{\(\) => setScreen\('my-basket-main'\)\}/);
  assert.match(appSource, /onSeeAllMealIdeas=\{\(\) => void openMealIdeas\(\)\}/);
});
