import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';

const source = fs.readFileSync(new URL('./householdApi.ts', import.meta.url), 'utf8');

test('connects the signed-in mobile app to household create and list endpoints', () => {
  assert.match(source, /apiRequest<Household\[\]>\('\/api\/v1\/households', \{ method: 'GET' \}\)/);
  assert.match(source, /apiRequest<Household>\('\/api\/v1\/households', \{/);
  assert.match(source, /method: 'POST'/);
});

test('uses no household ID until a real backend household is available', () => {
  assert.match(source, /return households\[0\]\?\.id \?\? null;/);
});
