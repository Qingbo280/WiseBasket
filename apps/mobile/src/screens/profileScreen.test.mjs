import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

const screenSource = fs.readFileSync(
  path.resolve(process.cwd(), 'src/screens/ProfileScreen.tsx'),
  'utf8',
);
const appSource = fs.readFileSync(path.resolve(process.cwd(), 'App.tsx'), 'utf8');
const homeSource = fs.readFileSync(
  path.resolve(process.cwd(), 'src/screens/HomeDashboardScreen.tsx'),
  'utf8',
);
const basketSource = fs.readFileSync(
  path.resolve(process.cwd(), 'src/screens/MyBasketMainScreen.tsx'),
  'utf8',
);

test('renders a local profile page with only name, email, and logout', () => {
  assert.match(screenSource, /export function ProfileScreen/);
  assert.match(screenSource, /Name/);
  assert.match(screenSource, /Email/);
  assert.match(screenSource, /Log out/);
  assert.match(screenSource, /TextInput/);
  assert.doesNotMatch(screenSource, /Password|phone|date of birth/i);
});

test('uses the same account-circle profile icon from Home and My Basket', () => {
  assert.match(homeSource, /name="account-circle-outline"/);
  assert.match(basketSource, /name="account-circle-outline"/);
  assert.match(homeSource, /onProfilePress/);
  assert.match(basketSource, /onProfilePress/);
});

test('keeps profile return source local to the existing TestFlow', () => {
  assert.match(appSource, /ProfileScreen/);
  assert.match(appSource, /'profile'/);
  assert.match(appSource, /profileReturnScreen/);
  assert.match(appSource, /openProfile\('home-dashboard'\)/);
  assert.match(appSource, /openProfile\('my-basket-main'\)/);
  assert.match(appSource, /const handleProfileLogout = \(\) =>/);
  assert.match(appSource, /setScreen\('auth-entry'\)/);
});

test('exposes the saved Plan personalization settings from Profile', () => {
  assert.match(screenSource, /onPersonalizationPress/);
  assert.match(screenSource, /Personalization/);
  assert.match(appSource, /onPersonalizationPress=\{openPersonalizationEditor\}/);
});
