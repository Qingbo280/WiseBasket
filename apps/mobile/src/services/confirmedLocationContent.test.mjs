import test from 'node:test';
import assert from 'node:assert/strict';

import {
  createConfirmedLocation,
  getLocationDisplayLabel,
  normalizeStoredConfirmedLocation,
} from './confirmedLocationContent.ts';

test('uses the short label for a readable confirmed-location display', () => {
  assert.equal(
    getLocationDisplayLabel({
      address: '58100 Kuala Lumpur',
      shortLabel: 'Jalan Klang Lama, Kuala Lumpur',
    }),
    'Jalan Klang Lama, Kuala Lumpur',
  );
});

test('creates a confirmed location without changing its source or coordinates', () => {
  const confirmed = createConfirmedLocation(
    {
      address: '58100 Kuala Lumpur',
      latitude: 3.0881,
      longitude: 101.6778,
      source: 'gps',
      state: 'Selangor',
    },
    '2026-09-15T10:00:00.000Z',
  );

  assert.deepEqual(confirmed, {
    address: '58100 Kuala Lumpur',
    latitude: 3.0881,
    longitude: 101.6778,
    source: 'gps',
    state: 'Selangor',
    confirmedAt: '2026-09-15T10:00:00.000Z',
  });
});

test('normalizes only valid persisted confirmed locations', () => {
  assert.deepEqual(
    normalizeStoredConfirmedLocation({
      address: ' Kuala Lumpur ',
      confirmedAt: '2026-09-15T10:00:00.000Z',
      latitude: 3.139,
      longitude: 101.6869,
      shortLabel: ' Kuala Lumpur ',
      source: 'manual',
    }),
    {
      address: 'Kuala Lumpur',
      confirmedAt: '2026-09-15T10:00:00.000Z',
      latitude: 3.139,
      longitude: 101.6869,
      shortLabel: 'Kuala Lumpur',
      source: 'manual',
    },
  );
  assert.equal(normalizeStoredConfirmedLocation({ address: 'Kuala Lumpur' }), null);
  assert.equal(normalizeStoredConfirmedLocation({ source: 'gps', address: 'Kuala Lumpur' }), null);
});
