import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import ts from 'typescript';

const file = new URL('./shoppingPantry.ts', import.meta.url);
const source = fs.existsSync(file) ? fs.readFileSync(file, 'utf8') : 'export {}';
const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext } }).outputText;
const { syncPurchasedPantry } = await import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}`);

test('purchased foods save presence without using planned quantities; undo preserves pre-existing pantry', async () => {
  const existing = { pantry_item_id: 1, status: 'AVAILABLE', food: { canonical_food_id: 'SF018' } };
  const calls = [], owned = new Map();
  const api = { list: async () => [existing], create: async (id, input) => {
    calls.push(input);
    return { pantry_item_id: 2, status: 'AVAILABLE', food: { canonical_food_id: input.canonical_food_id } };
  }, remove: async (id, itemId) => calls.push(['remove', itemId]) };
  const result = await syncPurchasedPantry(7, [{ productId: 'SF018', name: 'Egg' }, { productId: 'SF110', name: 'Rice', suggestedQuantity: 5000 }], [], owned, api);
  assert.deepEqual(calls, [{ canonical_food_id: 'SF110' }]);
  assert.equal(result.length, 2);
  await syncPurchasedPantry(7, [], [], owned, api);
  assert.deepEqual(calls[1], ['remove', 2]);
  assert.equal(owned.size, 0);
});

test('recipe shopping items resolve to canonical IDs rather than synthetic display IDs', async () => {
  const inputs = [];
  await syncPurchasedPantry(7, [{ productId: 'recipe-rice', name: 'Rice' }], [{ foodId: 'SF110', name: 'rice' }], new Map(), {
    list: async () => [], create: async (id, input) => { inputs.push(input); return { pantry_item_id: 1, food: { canonical_food_id: input.canonical_food_id } }; },
    remove: async () => {},
  });
  assert.deepEqual(inputs, [{ canonical_food_id: 'SF110' }]);
});

test('unknown recipe foods fail before any pantry writes', async () => {
  await assert.rejects(() => syncPurchasedPantry(7, [{ productId: 'recipe-unknown', name: 'Unknown' }], [], new Map(), {
    list: async () => [], create: async () => assert.fail('must not write'), remove: async () => {},
  }), /could not be matched/);
});
