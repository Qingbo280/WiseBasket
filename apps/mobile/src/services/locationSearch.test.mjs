import assert from 'node:assert/strict';
import test from 'node:test';
import {
  buildLocationSearchPath,
  normalizeLocationSuggestion,
} from './locationSearch.ts';

test('builds an encoded location search path', () => {
  assert.equal(
    buildLocationSearchPath('  Jalan Ampang  '),
    '/api/v1/locations/search?q=Jalan%20Ampang',
  );
});

test('normalizes a valid backend suggestion and rejects incomplete data', () => {
  assert.deepEqual(
    normalizeLocationSuggestion({
      id: 'geoapify:ampang-point',
      label: 'Ampang Point, Kuala Lumpur',
      address: 'Jalan Mamanda 9, Ampang',
      latitude: 3.1579,
      longitude: 101.7614,
      state: 'W.P. Kuala Lumpur',
      district: 'Titiwangsa',
    }),
    {
      id: 'geoapify:ampang-point',
      label: 'Ampang Point, Kuala Lumpur',
      address: 'Jalan Mamanda 9, Ampang',
      latitude: 3.1579,
      longitude: 101.7614,
      state: 'W.P. Kuala Lumpur',
      district: 'Titiwangsa',
    },
  );

  assert.equal(
    normalizeLocationSuggestion({ label: 'Missing coordinates' }),
    null,
  );
});
