import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import ts from 'typescript';

const file = new URL('./recipePantry.ts', import.meta.url);
const source = fs.existsSync(file) ? fs.readFileSync(file, 'utf8') : 'export {}';
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext } }).outputText;
const { saveRecipeHaveItems } = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`);

test('Have it saves canonical IDs without requiring quantity and avoids duplicate pantry rows', async () => {
  const calls = [];
  const existing = { pantry_item_id: 1, status: 'AVAILABLE', food: { canonical_food_id: 'egg' } };
  const items = await saveRecipeHaveItems(7, ['egg', 'rice', 'rice'], {
    list: async (id) => { assert.equal(id, 7); return [existing]; },
    create: async (id, input) => {
      calls.push([id, input]);
      return { pantry_item_id: 2, food: { canonical_food_id: input.canonical_food_id } };
    },
  });
  assert.deepEqual(calls, [[7, { canonical_food_id: 'rice' }]]);
  assert.equal(items.length, 2);
});

test('failed pantry saves reject so the screen can retain selections for retry', async () => {
  await assert.rejects(() => saveRecipeHaveItems(7, ['egg'], {
    list: async () => [], create: async () => { throw new Error('offline'); },
  }), /offline/);
});

test('recipe cards open details and pantry changes refresh recipe suggestions', () => {
  const basket = fs.readFileSync(new URL('../screens/MyBasketMainScreen.tsx', import.meta.url), 'utf8');
  const app = fs.readFileSync(new URL('../../App.tsx', import.meta.url), 'utf8');
  assert.match(basket, /onPress=\{\(\) => onRecipePress\?\.\(recipe\)\}/);
  assert.match(app, /onRecipePress=\{\(recipe\) => void handleMealIdeaPress\(recipe\)\}/);
  assert.match(app, /\[activeHouseholdId, isAuthenticated, pantryItems, plannedRecipeFoodKey, planDraft\.selectedRestrictions, planDraft\.customRestriction\]/);
  assert.match(app, /await saveRecipeHaveItems/);
});
