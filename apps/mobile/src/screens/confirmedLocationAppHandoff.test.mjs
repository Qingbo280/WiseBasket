import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

const appSource = fs.readFileSync(new URL('../../App.tsx', import.meta.url), 'utf8');
const locationSource = fs.readFileSync(new URL('./LocationGetLocationScreen.tsx', import.meta.url), 'utf8');
const dashboardSource = fs.readFileSync(new URL('./HomeDashboardScreen.tsx', import.meta.url), 'utf8');

test('loads and saves the frontend confirmed shopping location', () => {
  assert.match(appSource, /loadConfirmedLocation/);
  assert.match(appSource, /saveConfirmedLocation/);
  assert.match(appSource, /pendingLocation/);
  assert.match(appSource, /onConfirmLocation/);
});

test('requires explicit confirmation before GPS or manual selection becomes confirmed', () => {
  assert.match(appSource, /setPendingLocation\(/);
  assert.match(appSource, /setScreen\('location-get-location'\)/);
  assert.match(appSource, /createConfirmedLocation\(/);
  assert.match(appSource, /setConfirmedLocation\(/);
  assert.match(locationSource, /Confirm this location/);
  assert.match(locationSource, /Change location/);
});

test('reuses a saved location before Price Check and Generate Plan', () => {
  assert.match(appSource, /if \(confirmedLocation\)/);
  assert.match(appSource, /setSelectedLocation\(/);
  assert.match(appSource, /setPlanDraft\(/);
  assert.match(appSource, /setScreen\('location-price-check'\)/);
  assert.match(appSource, /setScreen\('plan-question-1'\)/);
});

test('routes the two Home feature cards directly into their product flows', () => {
  const priceCheckEntry = appSource.slice(
    appSource.indexOf('const openPriceCheckFromMainArea'),
    appSource.indexOf('const openHomeLocationEditor'),
  );
  const planEntry = appSource.slice(
    appSource.indexOf('const openPlanQuestionOne'),
    appSource.indexOf('const openProfile'),
  );

  assert.match(priceCheckEntry, /const location = await resolveConfirmedLocation\(\)/);
  assert.match(priceCheckEntry, /if \(location\)[\s\S]*setScreen\('location-price-check'\)/);
  assert.match(planEntry, /const location = await resolveConfirmedLocation\(\)/);
  assert.match(planEntry, /if \(location\)[\s\S]*setScreen\('plan-question-1'\)/);
});

test('keeps Price Check search back locked to Home regardless of entry source', () => {
  const planBackHandler = appSource.slice(
    appSource.indexOf('const handlePlanQuestionOneBack'),
    appSource.indexOf('const handleIntroComplete'),
  );

  assert.match(planBackHandler, /home-create-plan[\s\S]*home-plan-next-week[\s\S]*setScreen\('home-dashboard'\)/);
  assert.match(appSource, /onBack=\{\(\) => setScreen\('home-dashboard'\)\}[\s\S]*onCatalogRetry/);
});

test('waits for saved-location hydration before routing Home feature cards', () => {
  assert.match(appSource, /confirmedLocationHydrationRef/);
  assert.match(appSource, /const resolveConfirmedLocation = async \(\): Promise<ConfirmedLocation \| null> =>/);
  assert.match(appSource, /const location = await resolveConfirmedLocation\(\)/);
});

test('shows an editable confirmed shopping location on Home', () => {
  assert.match(dashboardSource, /confirmedLocation\?:/);
  assert.match(dashboardSource, /onLocationPress\?:/);
  assert.match(dashboardSource, /Shopping near/);
  assert.match(dashboardSource, /Set your shopping location/);
  assert.match(dashboardSource, /map-marker/);
  assert.match(dashboardSource, /chevron-right/);
});

test('keeps the location card responsive and touchable at the required widths', () => {
  assert.match(dashboardSource, /locationCardMain:\s*\{[\s\S]*flex: 1,[\s\S]*minWidth: 0/);
  assert.match(dashboardSource, /locationCopy:\s*\{[\s\S]*flex: 1,[\s\S]*minWidth: 0/);
  assert.match(dashboardSource, /locationChevron:\s*\{[\s\S]*flexShrink: 0,[\s\S]*minHeight: DASHBOARD_LAYOUT\.minimumTouchTarget/);
  assert.match(locationSource, /confirmationCopy:\s*\{[\s\S]*flex: 1,[\s\S]*minWidth: 0/);
  assert.match(locationSource, /confirmButton:\s*\{[\s\S]*minHeight: 54/);
});
