import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import ts from 'typescript';

const file = new URL('./recipeIngredientBadge.ts', import.meta.url);
const source = fs.existsSync(file) ? fs.readFileSync(file, 'utf8') : 'export {}';
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext } }).outputText;
const { recipeIngredientBadge } = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`);

test('the compact badge counts every ingredient, without a required/optional split', () => {
  assert.deepEqual(recipeIngredientBadge({
    available_ingredients: [{}, {}], ingredient_count: 5,
    required_match_count: 2, required_ingredient_count: 2, optional_ingredient_count: 3,
  }), { tag: '2/5 ingredients', tagTone: 'blue' });
  assert.deepEqual(recipeIngredientBadge({
    available_ingredients: [{}], ingredient_count: 7,
    required_match_count: 1, required_ingredient_count: 3, optional_ingredient_count: 4,
  }), { tag: '1/7 ingredients', tagTone: 'blue' });
  assert.deepEqual(recipeIngredientBadge({ available_ingredients: [], ingredient_count: 2 }), {
    tag: '0/2 ingredients', tagTone: 'blue',
  });
  assert.deepEqual(recipeIngredientBadge({ available_ingredients: [{}, {}], ingredient_count: 2 }), {
    tag: '2/2 ingredients', tagTone: 'green',
  });
});

test('unknown or inconsistent totals do not invent a required/optional split', () => {
  assert.deepEqual(recipeIngredientBadge({ available_ingredients: [{}, {}, {}] }), {
    tag: '3 ingredients available', tagTone: 'blue',
  });
  assert.deepEqual(recipeIngredientBadge({
    available_ingredients: [{}, {}], ingredient_count: 5,
    required_match_count: 2, required_ingredient_count: 2, optional_ingredient_count: 2,
  }), { tag: '2/5 ingredients', tagTone: 'blue' });
  for (const total of [null, NaN, -1, 1.5, 0]) {
    const badge = recipeIngredientBadge({ available_ingredients: [{}], ingredient_count: total });
    assert.equal(badge.tag, '1 ingredient available');
    assert.equal(badge.tagTone, 'blue');
  }
});

test('the My Basket recipe card uses its original metadata and tag layout', () => {
  const app = fs.readFileSync(new URL('../../App.tsx', import.meta.url), 'utf8');
  assert.match(app, /\.\.\.recipeIngredientBadge\(recipe\)/);
  assert.match(app, /ingredientCount: Number\.isInteger\(recipe\.ingredient_count\)/);
  const myBasket = fs.readFileSync(new URL('../screens/MyBasketMainScreen.tsx', import.meta.url), 'utf8');
  assert.match(myBasket, /recipe\.ingredientCount === undefined \? 'Ingredients' : `\$\{recipe\.ingredientCount\} items`/);
  assert.doesNotMatch(myBasket, /ingredientSummary=\{recipe\.ingredientSummary\}/);
  assert.doesNotMatch(myBasket, /tagTone=\{recipe\.tagTone\}/);
});
