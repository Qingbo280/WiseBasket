import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import ts from 'typescript';

const source = fs.readFileSync(new URL('./recipeExclusions.ts', import.meta.url), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext } }).outputText;
const { buildRecipeExclusions, buildRecipeNameRestrictions } = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`);

test('only supported exclusion codes leave the app, stably deduplicated', () => {
  assert.deepEqual(buildRecipeExclusions({ selectedRestrictions: ['pork', 'eggs', 'pork', 'gluten', 'other'] }), ['EGGS', 'NO_PORK']);
});

test('gluten and Other are carried to recipes only while selected', () => {
  assert.deepEqual(buildRecipeNameRestrictions({
    selectedRestrictions: ['gluten', 'other'], customRestriction: ' squid ',
  }), { glutenFree: true, customRestriction: 'squid' });
  assert.deepEqual(buildRecipeNameRestrictions({
    selectedRestrictions: ['none'], customRestriction: 'squid',
  }), { glutenFree: false, customRestriction: '' });
});

test('list and detail requests use repeated exclusion query parameters', () => {
  const api = fs.readFileSync(new URL('./recipeApi.ts', import.meta.url), 'utf8');
  const app = fs.readFileSync(new URL('../../App.tsx', import.meta.url), 'utf8');
  assert.match(api, /query\.append\('exclusions', code\)/);
  assert.match(api, /query\.set\('gluten_free', 'true'\)/);
  assert.match(api, /query\.set\('custom_restriction'/);
  assert.match(api, /query\.append\('planned_food_ids', id\)/);
  assert.match(app, /mealIdeasSnapshotRef\.current = \{ householdId, filters, hardRestrictionKey \}/);
  assert.match(app, /fetchRecipeDetail\(snapshot\.householdId, recipe\.recipeId, snapshot\.filters\)/);
});
