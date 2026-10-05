import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import ts from 'typescript';

// recipePreview.ts imports only types, so transpile + data-URL import works.
const source = fs.readFileSync(new URL('./recipePreview.ts', import.meta.url), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext } }).outputText;
const { recipePreviewFoods } = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`);

const appSource = fs.readFileSync(new URL('../../App.tsx', import.meta.url), 'utf8');

function food(id, name = id) {
  return { canonical_food_id: id, category: 'test', name, name_ms: null };
}

function suggestion(overrides) {
  return {
    available_ingredients: [food('egg', 'chicken egg')],
    missing_required_ingredients: [food('sugar', 'white sugar')],
    ...overrides,
  };
}

test('meal idea thumbnails lead with main ingredients, never optional sugar', () => {
  const preview = recipePreviewFoods(suggestion({
    available_main_ingredients: [food('egg', 'chicken egg')],
    missing_main_ingredients: [food('tomato', 'tomato')],
  }));
  assert.deepEqual(preview.map((item) => item.canonical_food_id), ['egg', 'tomato']);
});

test('a short main pool is topped up from the legacy lists without repeats', () => {
  const preview = recipePreviewFoods(suggestion({
    available_main_ingredients: [food('egg', 'chicken egg')],
    missing_main_ingredients: [],
  }));
  assert.deepEqual(preview.map((item) => item.canonical_food_id), ['egg', 'sugar']);
  const onlyMissing = recipePreviewFoods(suggestion({
    available_ingredients: [],
    missing_required_ingredients: [food('oil', 'cooking oil'), food('chicken', 'whole chicken')],
    available_main_ingredients: [],
    missing_main_ingredients: [food('chicken', 'whole chicken')],
  }));
  assert.deepEqual(onlyMissing.map((item) => item.canonical_food_id), ['chicken', 'oil']);
});

test('older backends without main fields keep the legacy available+missing order', () => {
  const preview = recipePreviewFoods(suggestion({}));
  assert.deepEqual(preview.map((item) => item.canonical_food_id), ['egg', 'sugar']);
});

test('App.tsx wires card thumbnails through the shared preview selector', () => {
  assert.match(appSource, /import \{ recipePreviewFoods \} from '\.\/src\/services\/recipePreview';/);
  assert.match(appSource, /const ingredients = recipePreviewFoods\(recipe\)/);
  assert.doesNotMatch(appSource, /missing_required_ingredients\]\s*\n?\s*\.slice\(0, 2\)/);
});
