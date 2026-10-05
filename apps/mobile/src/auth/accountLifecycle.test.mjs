import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import test from 'node:test';
import ts from 'typescript';
import { normalizeAppProfileData } from '../services/appProfile.ts';
import { PLAN_DRAFT_DEFAULTS, UNSET_PLAN_SUMMARY, applyPlanPersonalization, getMealsAtHomeLabel } from '../screens/planFlowContent.ts';

// Run the provider's real handlers with deterministic hooks and mocked I/O.
function harness() {
  const slots = [];
  let cursor = 0;
  let savedProfile = null;
  let failed = false;
  let token = null;
  let householdLoader = async () => [];
  const calls = [];
  const react = {
    createContext: () => ({ Provider: 'provider' }),
    useState(initial) {
      const index = cursor++;
      if (!(index in slots)) slots[index] = initial;
      return [slots[index], value => { slots[index] = typeof value === 'function' ? value(slots[index]) : value; }];
    },
    useRef(initial) {
      const index = cursor++;
      if (!(index in slots)) slots[index] = { current: initial };
      return slots[index];
    },
    useCallback: callback => callback,
    useMemo: callback => callback(),
    useEffect: () => {},
  };
  class ApiError extends Error {}
  const mocks = {
    react,
    'react/jsx-runtime': { jsx: (type, props) => props },
    '../services/api': {
      ApiError,
      setSessionExpiredHandler: () => {},
      async apiRequest(path, options) {
        calls.push({ path, options });
        if (path.endsWith('/login') || path.endsWith('/register')) {
          return { access_token: 'access', refresh_token: 'refresh', user: { user_id: options.body.email, email: options.body.email } };
        }
        if (path.endsWith('/profile') && options.method === 'GET') {
          if (failed) throw new Error('offline');
          return { profile: savedProfile };
        }
        if (path.endsWith('/profile')) savedProfile = options.body.profile;
        return {};
      },
    },
    '../services/householdApi': {
      listHouseholds: () => householdLoader(),
      selectActiveHouseholdId: rows => rows[0]?.id ?? null,
      createHousehold: async input => ({ id: 1, ...input }),
    },
    '../services/appProfile': { normalizeAppProfileData },
    '../services/tokenStorage': {
      saveTokens: async value => { token = value; },
      getStoredTokens: async () => token,
      clearTokens: async () => { token = null; },
    },
  };
  const source = fs.readFileSync(new URL('./AuthProvider.tsx', import.meta.url), 'utf8');
  const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX } }).outputText;
  const exports = {};
  vm.runInNewContext(code, { exports, require: name => {
    assert.ok(name in mocks, `Unexpected dependency ${name}`);
    return mocks[name];
  }, setTimeout, clearTimeout });
  return {
    render() { cursor = 0; return exports.AuthProvider({ children: null }).value; },
    set profile(value) { savedProfile = value; },
    set failed(value) { failed = value; },
    set householdLoader(value) { householdLoader = value; },
    calls,
  };
}

test('new accounts have no saved preferences and show a zero summary; setup retains suggestions', async () => {
  const h = harness();
  await h.render().register('New user', 'new@example.com', 'password');
  const auth = h.render();
  assert.equal(auth.isAuthenticated, true);
  assert.equal(auth.profileLoadError, null);
  assert.equal(auth.appProfileData.personalization, undefined);
  assert.equal(UNSET_PLAN_SUMMARY.weeklyBudget, 0);
  assert.equal(UNSET_PLAN_SUMMARY.adults + UNSET_PLAN_SUMMARY.children, 0);
  assert.equal(getMealsAtHomeLabel(UNSET_PLAN_SUMMARY), '0');
  assert.equal(PLAN_DRAFT_DEFAULTS.weeklyBudget, 200);
});

test('returning users load saved preferences; logout and another account clear account data', async () => {
  const h = harness();
  h.profile = { display_name: 'Returning', personalization: { ...PLAN_DRAFT_DEFAULTS, weeklyBudget: 350 } };
  h.householdLoader = async () => [{ id: 9, adults: 3, children: 1 }];
  await h.render().login('a@example.com', 'password');
  let auth = h.render();
  assert.equal(applyPlanPersonalization(UNSET_PLAN_SUMMARY, auth.appProfileData.personalization).weeklyBudget, 350);
  assert.equal(auth.activeHouseholdId, 9);
  await auth.logout();
  auth = h.render();
  assert.equal(auth.isAuthenticated, false);
  assert.equal(Object.keys(auth.appProfileData).length, 0);
  assert.equal(auth.activeHouseholdId, null);
  h.profile = null;
  h.householdLoader = async () => [];
  await auth.login('b@example.com', 'password');
  assert.equal(h.render().appProfileData.personalization, undefined);
});

test('failed profile loading stays distinct from missing preferences and blocks overwrites until retry succeeds', async () => {
  const h = harness();
  h.failed = true;
  await h.render().login('a@example.com', 'password');
  let auth = h.render();
  assert.ok(auth.profileLoadError);
  await assert.rejects(auth.saveAppProfile({ display_name: 'Changed' }), /could not be loaded/);
  assert.equal(h.calls.filter(call => call.options?.method === 'PUT').length, 0);
  h.failed = false;
  h.profile = { display_name: 'Original', personalization: { ...PLAN_DRAFT_DEFAULTS, weeklyBudget: 400 } };
  await auth.retryProfile();
  auth = h.render();
  assert.equal(auth.profileLoadError, null);
  await auth.saveAppProfile({ display_name: 'Changed' });
  assert.equal(h.render().appProfileData.personalization.weeklyBudget, 400);
});

test('a late household response cannot repopulate state after logout', async () => {
  const h = harness();
  await h.render().login('a@example.com', 'password');
  let resolve;
  h.householdLoader = () => new Promise(done => { resolve = done; });
  const pending = h.render().refreshHouseholds();
  await h.render().logout();
  resolve([{ id: 9 }]);
  await pending;
  assert.equal(h.render().activeHouseholdId, null);
  assert.equal(h.render().households.length, 0);
});

test('switching accounts directly replaces saved preferences and household state', async () => {
  const h = harness();
  h.profile = { personalization: { ...PLAN_DRAFT_DEFAULTS, weeklyBudget: 500 } };
  h.householdLoader = async () => [{ id: 5 }];
  await h.render().login('first@example.com', 'password');
  assert.equal(h.render().activeHouseholdId, 5);
  h.profile = null;
  h.householdLoader = async () => [];
  await h.render().login('second@example.com', 'password');
  const auth = h.render();
  assert.equal(auth.user.user_id, 'second@example.com');
  assert.equal(auth.appProfileData.personalization, undefined);
  assert.equal(auth.activeHouseholdId, null);
});
