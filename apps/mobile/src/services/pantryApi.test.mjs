import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

const source = fs.readFileSync(
  path.resolve(process.cwd(), 'src/services/pantryApi.ts'),
  'utf8',
);

test('uses the authenticated household Pantry API as the persistent contract', () => {
  assert.match(source, /@react-native-async-storage\/async-storage/);
  assert.match(source, /PANTRY_CACHE_KEY_PREFIX/);
  assert.match(source, /getCachedPantryItems/);
  assert.match(source, /cachePantryItems/);
  assert.match(source, /households\/\$\{householdId\}\/pantry-items/);
  assert.match(source, /method: 'GET'/);
  assert.match(source, /method: 'POST'/);
  assert.match(source, /method: 'DELETE'/);
  assert.match(source, /canonical_food_id: string/);
});
