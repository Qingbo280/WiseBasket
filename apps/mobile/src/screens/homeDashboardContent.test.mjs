import test from 'node:test';
import assert from 'node:assert/strict';

import {
  DASHBOARD_PLAN_PLATES,
  DASHBOARD_PLAN_EMPTY_ZONES,
  DASHBOARD_PLAN_SCALE,
  DASHBOARD_LAYOUT,
  DASHBOARD_TYPE_SCALE,
  getDashboardGreeting,
  getDashboardHeroDimensions,
  getDashboardHorizontalPadding,
  getDashboardPlanPlateDimensions,
  getDashboardPlanProgress,
  getDashboardPlanState,
  getRecentCheckPreview,
  mapRecentPriceCheck,
} from './homeDashboardContent.ts';

const selectedItem = {
  foodId: 'food-spinach',
  name: 'Spinach',
  subtitle: 'Fresh spinach',
  imageSource: 42,
  requiresVariantConfirmation: false,
};

test('maps only the real product and price fields into a recent check card', () => {
  const recentCheck = mapRecentPriceCheck({
    selectedItem,
    selectedPriceResult: {
      premiseId: 'store-a',
      premiseName: 'Neighbourhood Market',
      premiseType: 'wet-market',
      distanceKm: 1.4,
      price: 4.2,
      currency: 'RM',
    },
  });

  assert.deepEqual(recentCheck, {
    id: 'food-spinach:store-a',
    imageSource: 42,
    productName: 'Spinach',
    priceLabel: 'RM 4.20',
    storeName: 'Neighbourhood Market',
    distanceLabel: '1.4 km',
  });
});

test('does not fabricate price, store, or distance when the result is unavailable', () => {
  const recentCheck = mapRecentPriceCheck({
    selectedItem,
    selectedPriceResult: null,
  });

  assert.deepEqual(recentCheck, {
    id: 'food-spinach',
    imageSource: 42,
    productName: 'Spinach',
    priceLabel: null,
    storeName: null,
    distanceLabel: null,
  });
});

test('keeps recent checks in source order and caps the home preview at four items', () => {
  const checks = Array.from({ length: 5 }, (_, index) => ({ id: `item-${index}` }));

  assert.deepEqual(getRecentCheckPreview(checks), checks.slice(0, 4));
});

test('uses the empty plan state until a real plan boundary is supplied', () => {
  assert.equal(getDashboardPlanState(null), 'empty');
  assert.equal(getDashboardPlanState({ budget_rm: 120, total_cost_rm: 95, items: [] }), 'populated');
});

test('uses a neutral greeting when no display name exists', () => {
  assert.equal(getDashboardGreeting(9, null), 'Welcome back!');
  assert.equal(getDashboardGreeting(9, 'Amina'), 'Good morning, Amina!');
  assert.equal(getDashboardGreeting(15, 'Amina'), 'Good afternoon, Amina!');
  assert.equal(getDashboardGreeting(20, 'Amina'), 'Good evening, Amina!');
});

test('keeps the approved Android horizontal padding across supported widths', () => {
  assert.deepEqual(
    [360, 384, 412, 432].map(getDashboardHorizontalPadding),
    [20, 22, 24, 24],
  );
});

test('uses a modest Android-readable dashboard type scale', () => {
  assert.deepEqual(DASHBOARD_TYPE_SCALE, {
    greeting: 23,
    supportingGreeting: 14,
    heroMessage: 17,
    actionTitle: 16,
    actionBody: 14,
    sectionTitle: 19,
    planTitle: 18,
    planBody: 13,
    planButton: 15,
    body: 14,
    metadata: 12,
    navLabel: 12,
    navPrimaryLabel: 12,
  });
});

test('compresses vertical layout without shrinking Android touch targets', () => {
  assert.deepEqual(DASHBOARD_LAYOUT, {
    contentTop: 8,
    greetingTop: 10,
    heroTop: 12,
    heroAspectRatio: 2048 / 768,
    actionTop: 12,
    actionMinHeight: 142,
    sectionGap: 18,
    sectionHeadingGap: 8,
    planPadding: 14,
    recentImageHeight: 76,
    recentMinHeight: 158,
    tipPadding: 14,
    minimumTouchTarget: 48,
  });
});

test('caps the approved Hero banner to the Dashboard content width', () => {
  assert.deepEqual(getDashboardHeroDimensions(360), { width: 320, height: 120 });
  assert.deepEqual(getDashboardHeroDimensions(412), { width: 364, height: 136.5 });
  assert.deepEqual(getDashboardHeroDimensions(432), { width: 384, height: 144 });
});

test('preserves both approved plan plate aspect ratios across supported widths', () => {
  assert.deepEqual(DASHBOARD_PLAN_PLATES, {
    empty: { width: 1848, height: 552 },
    summary: { width: 1847, height: 540 },
  });

  for (const kind of ['empty', 'summary']) {
    const dimensions = getDashboardPlanPlateDimensions(412, kind);
    const expectedWidth = Math.min(
      (412 - getDashboardHorizontalPadding(412) * 2) * DASHBOARD_PLAN_SCALE,
      412 - 16,
    );
    assert.equal(dimensions.width, expectedWidth);
    const source = DASHBOARD_PLAN_PLATES[kind];
    assert.ok(Math.abs(dimensions.height - (expectedWidth * source.height) / source.width) < 0.001);
  }
});

test('keeps the empty plan overlay zones proportional and complete', () => {
  assert.deepEqual(DASHBOARD_PLAN_EMPTY_ZONES, {
    left: 18,
    content: 56,
    right: 26,
  });
  assert.equal(
    Object.values(DASHBOARD_PLAN_EMPTY_ZONES).reduce((total, zone) => total + zone, 0),
    100,
  );
});

test('derives a bounded plan progress value only from real item counts', () => {
  assert.equal(getDashboardPlanProgress(3, 6), 0.5);
  assert.equal(getDashboardPlanProgress(8, 6), 1);
  assert.equal(getDashboardPlanProgress(-1, 6), 0);
  assert.equal(getDashboardPlanProgress(undefined, 6), null);
  assert.equal(getDashboardPlanProgress(2, 0), null);
});
