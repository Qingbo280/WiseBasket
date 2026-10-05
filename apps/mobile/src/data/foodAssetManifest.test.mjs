import assert from 'node:assert/strict';
import test from 'node:test';

process.env.EXPO_PUBLIC_ASSET_BASE_URL = 'https://assets.example.test/';
const { foodImageForBackendId, foodImageUriForBackendId } = await import('./foodAssetManifest.ts');

test('builds the canonical R2 food object URL from a backend food ID', () => {
  assert.equal(
    foodImageUriForBackendId('sf001'),
    'https://assets.example.test/foods/SF001.webp',
  );
  assert.deepEqual(foodImageForBackendId('SF002'), {
    imageKey: 'foods/SF002.webp',
    uri: 'https://assets.example.test/foods/SF002.webp',
  });
  assert.equal(
    foodImageUriForBackendId('SF195'),
    'https://assets.example.test/foods/SF195.webp',
  );
});

test('rejects non-canonical food IDs', () => {
  assert.equal(foodImageUriForBackendId('rice'), null);
});
