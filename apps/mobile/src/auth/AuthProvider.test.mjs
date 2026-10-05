import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';

const providerSource = fs.readFileSync(new URL('./AuthProvider.tsx', import.meta.url), 'utf8');
const appSource = fs.readFileSync(new URL('../../App.tsx', import.meta.url), 'utf8');

test('mounts AuthProvider as the single app-level authentication owner', () => {
  assert.match(appSource, /<AuthProvider>/);
  assert.match(appSource, /useAuth\(\)/);
  assert.doesNotMatch(appSource, /loginAccount|registerAccount|logoutAccount|saveAccountDisplayName/);
});

test('restores tokens and profile data when the app starts', () => {
  assert.match(providerSource, /getStoredTokens\(\)/);
  assert.match(providerSource, /apiRequest<BackendUser>\('\/api\/v1\/auth\/me'\)/);
  assert.match(providerSource, /fetchProfile\(currentUser\)/);
  assert.match(providerSource, /await refreshHouseholds\(\)/);
});

test('loads the signed-in user households without inventing one', () => {
  assert.match(providerSource, /listHouseholds/);
  assert.match(providerSource, /selectActiveHouseholdId\(nextHouseholds\)/);
  assert.match(providerSource, /activeHouseholdId: number \| null/);
});

test('persists profile names and revokes the backend session on logout', () => {
  assert.match(providerSource, /persistAppProfile\(appProfileDataRef\.current\)/);
  assert.match(providerSource, /'\/api\/v1\/profile'/);
  assert.match(providerSource, /'\/api\/v1\/auth\/logout'/);
  assert.match(providerSource, /clearSession\(\)/);
});
