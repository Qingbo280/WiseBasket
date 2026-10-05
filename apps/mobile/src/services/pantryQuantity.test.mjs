import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import ts from 'typescript';

async function load(source) {
  const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext } }).outputText;
  return import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`);
}
const { parsePantryQuantity, PANTRY_QUANTITY_UNITS } = await load(fs.readFileSync(new URL('./pantryQuantity.ts', import.meta.url), 'utf8'));

test('accepts all six stock units and decimal amounts without converting them twice', () => {
  assert.deepEqual(PANTRY_QUANTITY_UNITS, ['kg', 'g', 'L', 'ml', 'pcs', 'pack']);
  for (const unit of PANTRY_QUANTITY_UNITS) {
    assert.deepEqual(parsePantryQuantity('12.5', unit), { quantity: 12.5, unit });
  }
  assert.deepEqual(parsePantryQuantity(' 0,25 ', 'kg'), { quantity: 0.25, unit: 'kg' });
  assert.deepEqual(parsePantryQuantity('.5', 'L'), { quantity: 0.5, unit: 'L' });
});

test('an empty amount explicitly clears both quantity and unit to unknown', () => {
  assert.deepEqual(parsePantryQuantity('   ', 'kg'), { quantity: null, unit: null });
  assert.deepEqual(parsePantryQuantity('', ''), { quantity: null, unit: null });
});

test('rejects zero, invalid numbers, excessive quantities and missing units before writes', () => {
  assert.throws(() => parsePantryQuantity('0', 'kg'), /Mark as eaten or Remove/);
  for (const input of ['-1', '.', '1e3', 'Infinity', 'NaN', '1.2.3', '100001']) {
    assert.throws(() => parsePantryQuantity(input, 'kg'));
  }
  assert.throws(() => parsePantryQuantity('1', ''), /Choose a unit/);
  assert.throws(() => parsePantryQuantity('1', 'bottle'), /Choose a unit/);
  assert.deepEqual(parsePantryQuantity('100000', 'g'), { quantity: 100000, unit: 'g' });
});

// Exercise the production API adapter with transport/storage substitutes.
const requests = [];
let failRequest = false;
const transportUrl = `data:text/javascript;base64,${Buffer.from(`
  export async function apiRequest(path, options) {
    return globalThis.__pantryQuantityTestRequest(path, options);
  }
`).toString('base64')}`;
globalThis.__pantryQuantityTestRequest = async (path, options) => {
  requests.push({ path, options });
  if (failRequest) throw new Error('Session expired');
  return { pantry_item_id: 42, quantity: 0.25, unit: 'kg' };
};
const apiSource = fs.readFileSync(new URL('./pantryApi.ts', import.meta.url), 'utf8')
  .replace("import AsyncStorage from '@react-native-async-storage/async-storage';", 'const AsyncStorage = { getItem: async () => null, setItem: async () => {} };')
  .replace("'./api'", JSON.stringify(transportUrl))
  .replace("import { oilRawGrams } from './oilEquivalence';", 'const oilRawGrams = () => null;');
const { updatePantryItem } = await load(apiSource);

test('PATCH includes the household, actual pantry row ID and unchanged food identity; response stays authoritative', async () => {
  const input = { canonical_food_id: 'SF001', ...parsePantryQuantity('250', 'g') };
  const updated = await updatePantryItem(7, 42, input);
  assert.deepEqual(requests.at(-1), {
    path: '/api/v1/households/7/pantry-items/42', options: { method: 'PATCH', body: input },
  });
  assert.equal(updated.quantity, 0.25);
  assert.equal(updated.unit, 'kg');
  await updatePantryItem(7, 42, { canonical_food_id: 'SF001', ...parsePantryQuantity('', 'g') });
  assert.deepEqual(requests.at(-1).options.body, { canonical_food_id: 'SF001', quantity: null, unit: null });
});

test('PATCH authentication/write failures reject so the editor retains the draft for retry', async () => {
  failRequest = true;
  await assert.rejects(updatePantryItem(7, 42, { canonical_food_id: 'SF001', quantity: 1, unit: 'kg' }), /Session expired/);
});
