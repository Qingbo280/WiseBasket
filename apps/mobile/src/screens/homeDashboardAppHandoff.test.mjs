import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

const appSource = fs.readFileSync(new URL('../../App.tsx', import.meta.url), 'utf8');

test('keeps the checked item available when the auth entry resolves to Dashboard', () => {
  assert.match(appSource, /HomeDashboardScreen/);
  assert.match(appSource, /mapRecentPriceCheck/);
  assert.match(appSource, /home-dashboard/);
});

test('allows Home Dashboard to render without a selected Price Check product', () => {
  assert.match(appSource, /if \(screen === 'home-dashboard'\) \{/);
  assert.match(appSource, /recentChecks=\{recentChecks\}/);
});

test('uses the existing Price Check event for Dashboard entry points', () => {
  assert.match(appSource, /onPriceCheckPress/);
  assert.match(appSource, /setScreen\('location-price-check'\)/);
});

test('starts a fresh app session at the two-page Intro before Auth Entry', () => {
  // Restored sessions skip the intro straight to Home (ported #237 semantics);
  // a guest session still starts at the two-page Intro.
  assert.match(appSource, /useState<TestScreen>\(isAuthenticated \? 'home-dashboard' : 'intro'\)/);
  assert.match(appSource, /const handleIntroComplete = \(pageIndex: number\) =>/);
  assert.match(appSource, /handleIntroComplete[\s\S]*setAuthCompletionIntent\('home-dashboard'\)/);
  assert.match(appSource, /handleIntroComplete[\s\S]*setScreen\('auth-entry'\)/);
});

test('reuses a confirmed location for Home and My Basket Price Check entries', () => {
  assert.match(appSource, /onPriceCheckPress=\{\(\) => void openPriceCheckFromMainArea\('home-dashboard'\)\}/);
  assert.match(appSource, /onPriceCheckPress=\{\(\) => void openPriceCheckFromMainArea\('my-basket-main'\)\}/);
  assert.match(appSource, /const openPriceCheckFromMainArea = async[\s\S]*const location = await resolveConfirmedLocation\(\)[\s\S]*if \(location\)[\s\S]*setSelectedLocation\(priceCheckLocationFromConfirmed\(location\)\)[\s\S]*setScreen\('location-price-check'\)/);
  assert.match(appSource, /setLocationPurpose\('price-check'\);[\s\S]*setScreen\('location-get-location'\);/);
});

test('returns from Price Check location confirmation to Home', () => {
  assert.match(appSource, /const handlePriceCheckLocationBack = \(\) => \{[\s\S]*setScreen\('home-dashboard'\);/);
  assert.match(appSource, /onBack=\{\s*locationPurpose === 'price-check'\s*\?\s*handlePriceCheckLocationBack/);
});

test('does not require auth when Price Check starts from a main feature area', () => {
  assert.match(appSource, /type PriceCheckEntrySource =/);
  assert.match(appSource, /const openPriceCheckFromMainArea = async \(source: Exclude<PriceCheckEntrySource, 'first-use'>\) =>/);
  assert.match(appSource, /const handlePriceCheckFinish = \(\) =>/);
  assert.match(appSource, /const handlePriceCheckPlanNextWeek = \(\) =>/);
  assert.match(appSource, /if \(priceCheckEntrySource === 'home-dashboard'\)/);
  assert.match(appSource, /if \(priceCheckEntrySource === 'my-basket-main'\)/);
  assert.match(appSource, /onFinishForNow=\{handlePriceCheckFinish\}/);
  assert.match(appSource, /onPlanNextWeek=\{handlePriceCheckPlanNextWeek\}/);
});

test('gates first-use Price Check next-step actions behind auth and resumes the chosen action', () => {
  assert.match(appSource, /type AuthCompletionIntent = 'home-dashboard' \| 'plan-next-week';/);
  assert.match(appSource, /authCompletionIntent === 'plan-next-week'/);
  assert.match(appSource, /setAuthCompletionIntent\('plan-next-week'\)/);
  assert.match(appSource, /openPlanQuestionOne\('price-check-next-step'\)/);
  assert.match(appSource, /setScreen\('auth-entry'\)/);
});

test('returns I\u2019m good for now to Home from every main feature area', () => {
  const finishHandler = appSource.slice(
    appSource.indexOf('const handlePriceCheckFinish'),
    appSource.indexOf('const handleLocationUseForPurpose'),
  );

  assert.match(finishHandler, /priceCheckEntrySource === 'my-basket-main'[\s\S]*setScreen\('home-dashboard'\)/);
  assert.doesNotMatch(finishHandler, /setScreen\('my-basket-main'\)/);
});

test('persists completed Price Checks for the Home Recently checked section', () => {
  assert.match(appSource, /const \[recentChecks, setRecentChecks\] = useState<readonly DashboardRecentCheck\[\]>\(\[\]\);/);
  assert.match(appSource, /setRecentChecks\(\(currentChecks\) => \[/);
  assert.match(appSource, /currentChecks\.filter\(\(check\) => check\.id !== completedCheck\.id\)/);
  assert.match(appSource, /recentChecks=\{recentChecks\}/);
});

test('returns to Price Check search after Next and locks search back to Home', () => {
  assert.match(appSource, /onNext=\{handleCheckAnotherItem\}/);
  assert.match(appSource, /onBack=\{\(\) => setScreen\('home-dashboard'\)\}/);
});

test('wires both Dashboard plan entry points to the shared Question 1 screen', () => {
  assert.match(appSource, /openPlanQuestionOne\('home-create-plan'\)/);
  assert.match(appSource, /openPlanQuestionOne\('home-plan-next-week'\)/);
  assert.match(appSource, /PlanQuestionOneScreen/);
});

test('falls back to the shared Location screen when a plan has no saved location', () => {
  assert.match(appSource, /type LocationPurpose = 'price-check' \| 'plan' \| 'home'/);
  assert.match(appSource, /useState<TestScreen>\(isAuthenticated \? 'home-dashboard' : 'intro'\)/);
  assert.match(appSource, /setLocationPurpose\('plan'\)/);
  assert.match(appSource, /setScreen\('location-get-location'\)/);
  assert.match(appSource, /if \(screen === 'location-get-location'\)/);
  assert.match(appSource, /<LocationGetLocationScreen/);
  assert.match(appSource, /onUseCurrentLocation=\{\(\) => void handleLocationUseForPurpose\(\)\}/);
});

test('keeps the plan back chain source-aware across Location and Question 1', () => {
  assert.match(appSource, /const handlePlanLocationBack = \(\) =>/);
  assert.match(appSource, /planQuestionOneEntrySource === 'home-create-plan'[\s\S]*planQuestionOneEntrySource === 'home-plan-next-week'/);
  assert.match(appSource, /if \(planQuestionOneEntrySource === 'my-basket-plan-next-week'\)/);
  assert.match(appSource, /if \(planQuestionOneEntrySource === 'price-check-next-step'\)/);
  const questionOneBack = appSource.slice(
    appSource.indexOf('const handlePlanQuestionOneBack'),
    appSource.indexOf('const handleIntroComplete'),
  );
  assert.match(questionOneBack, /home-create-plan[\s\S]*home-plan-next-week[\s\S]*setScreen\('home-dashboard'\)/);
  assert.match(questionOneBack, /my-basket-plan-next-week[\s\S]*setScreen\('my-basket-main'\)/);
  assert.match(questionOneBack, /price-check-next-step[\s\S]*setScreen\('price-check-next-step'\)/);
  assert.match(appSource, /onBack=\{handlePlanQuestionOneBack\}/);
  assert.match(appSource, /setScreen\('location-get-location'\)/);
});

test('stores a frontend planning location without changing Price Check state', () => {
  assert.match(appSource, /setPendingLocation\(\{[\s\S]*?source: 'gps'/);
  assert.match(appSource, /setPendingLocation\(\{[\s\S]*?address: suggestion\.address[\s\S]*?shortLabel: suggestion\.label[\s\S]*?source: 'manual'/);
  assert.match(appSource, /planningLocationFromConfirmed/);
  assert.match(appSource, /setSelectedLocation\(priceCheckLocationFromConfirmed\(savedLocation\)\)/);
  assert.match(appSource, /setLocationPurpose\('price-check'\)/);
  assert.match(appSource, /setScreen\('location-price-check'\)/);
});

test('keeps Question 1 Back source-aware inside the existing TestFlow', () => {
  assert.match(appSource, /type PlanQuestionOneEntrySource/);
  assert.match(appSource, /'price-check-next-step'/);
  assert.match(appSource, /'my-basket-plan-next-week'/);
  assert.match(appSource, /handlePlanQuestionOneBack/);
  assert.match(appSource, /onBack=\{handlePlanQuestionOneBack\}/);
});

test('wires Question 1 Continue to Question 2 and returns Question 2 Back to Question 1', () => {
  assert.match(appSource, /PlanQuestionTwoScreen/);
  assert.match(appSource, /\| 'plan-question-2'/);
  assert.match(appSource, /onContinue=\{\(\) => setScreen\('plan-question-2'\)\}/);
  assert.match(appSource, /if \(screen === 'plan-question-2'\)/);
  assert.match(appSource, /onBack=\{\(\) => setScreen\('plan-question-1'\)\}/);
});

test('uses the approved dashboard Hero banner asset directly', () => {
  const dashboardSource = fs.readFileSync(
    new URL('./HomeDashboardScreen.tsx', import.meta.url),
    'utf8',
  );

  assert.match(dashboardSource, /DASHBOARD_HERO_IMAGE/);
  assert.match(dashboardSource, /03_home_hero_banner\.png/);
  assert.doesNotMatch(dashboardSource, /heroSkyShape|heroCloudBack|heroCloudFront/);
});

test('uses the approved seasonal tip banner instead of rebuilding its copy', () => {
  const dashboardSource = fs.readFileSync(
    new URL('./HomeDashboardScreen.tsx', import.meta.url),
    'utf8',
  );
  const tipSource = dashboardSource.slice(
    dashboardSource.indexOf('function ShoppingTipCard'),
    dashboardSource.indexOf('type DashboardTab'),
  );

  assert.match(dashboardSource, /DASHBOARD_TIP_IMAGE/);
  assert.match(dashboardSource, /03_tips\.jpg/);
  assert.match(tipSource, /source=\{DASHBOARD_TIP_IMAGE\}/);
  assert.match(tipSource, /resizeMode="cover"/);
  assert.doesNotMatch(tipSource, /tipIcon|lightbulb-on-outline/);
  assert.doesNotMatch(tipSource, /Small seasonal swaps can help|Seasonal vegetables can sometimes be a better-value option/);
});

test('constrains the seasonal tip banner to the dashboard content width', () => {
  const dashboardSource = fs.readFileSync(
    new URL('./HomeDashboardScreen.tsx', import.meta.url),
    'utf8',
  );
  const tipSource = dashboardSource.slice(
    dashboardSource.indexOf('function ShoppingTipCard'),
    dashboardSource.indexOf('type DashboardTab'),
  );

  assert.match(tipSource, /const bannerWidth =/);
  assert.match(tipSource, /const bannerHeight = bannerWidth \/ \(1370 \/ 346\)/);
  assert.match(tipSource, /height: bannerHeight/);
  assert.match(dashboardSource, /<ShoppingTipCard\s+devUI=\{devUI\}\s+horizontalPadding=\{horizontalPadding\}\s+viewportWidth=\{width\}\s+\/>/);
});

test('uses the approved static empty-plan image and keeps live plan boundaries', () => {
  const dashboardSource = fs.readFileSync(
    new URL('./HomeDashboardScreen.tsx', import.meta.url),
    'utf8',
  );

  assert.match(dashboardSource, /DASHBOARD_EMPTY_PLAN_IMAGE/);
  assert.match(dashboardSource, /home-dashboard\.png/);
  assert.match(dashboardSource, /PlanSummary/);
});

test('uses the shared PlanSummary for the active Dashboard plan state', () => {
  const dashboardSource = fs.readFileSync(
    new URL('./HomeDashboardScreen.tsx', import.meta.url),
    'utf8',
  );

  assert.match(dashboardSource, /import \{ PlanSummary \} from ['"]\.\/PlanSummary['"]/);
  assert.match(dashboardSource, /planDraft\?: PlanDraft \| null/);
  assert.match(dashboardSource, /<PlanSummary planDraft=\{planDraft\} \/>/);
  assert.match(dashboardSource, /onPress=\{onBasketPress\}/);
  assert.doesNotMatch(dashboardSource, /DASHBOARD_PLAN_SUMMARY_PLATE/);
});

test('passes only a confirmed basket-backed plan to Home Dashboard', () => {
  assert.match(appSource, /const activePlanDraft = basketDraft\.length > 0 \? planDraft : null/);
  assert.match(appSource, /planDraft=\{activePlanDraft\}/);
});

test('renders the empty-plan visual directly from the static image', () => {
  const dashboardSource = fs.readFileSync(
    new URL('./HomeDashboardScreen.tsx', import.meta.url),
    'utf8',
  );
  const emptyPlanSource = dashboardSource.slice(
    dashboardSource.indexOf('function EmptyPlanCard'),
    dashboardSource.indexOf('function PlanProgressRing'),
  );

  assert.match(emptyPlanSource, /source=\{DASHBOARD_EMPTY_PLAN_IMAGE\}/);
  assert.match(emptyPlanSource, /resizeMode="cover"/);
  assert.match(emptyPlanSource, /height: imageHeight/);
  assert.match(dashboardSource, /DASHBOARD_EMPTY_PLAN_IMAGE_VISIBLE_ASPECT_RATIO = 1933 \/ 568/);
  assert.match(dashboardSource, /planEmptyStaticImage:\s*\{[\s\S]*aspectRatio: DASHBOARD_EMPTY_PLAN_IMAGE_VISIBLE_ASPECT_RATIO,[\s\S]*width: '100%'/);
  assert.match(emptyPlanSource, /<Pressable/);
  assert.match(emptyPlanSource, /onPress=\{onCreatePlanPress\}/);
});

test('passes a dedicated Create a plan callback to the empty Dashboard plan card', () => {
  const dashboardSource = fs.readFileSync(
    new URL('./HomeDashboardScreen.tsx', import.meta.url),
    'utf8',
  );

  assert.match(dashboardSource, /onCreatePlanPress\?: \(\) => void/);
  assert.match(dashboardSource, /<EmptyPlanCard onCreatePlanPress=\{onCreatePlanPress\}/);
});

test('keeps Quick Action card text and CTA in separate responsive layout areas', () => {
  const dashboardSource = fs.readFileSync(
    new URL('./HomeDashboardScreen.tsx', import.meta.url),
    'utf8',
  );
  const quickActionSource = dashboardSource.slice(
    dashboardSource.indexOf('function QuickActionCard'),
    dashboardSource.indexOf('function SectionHeading'),
  );

  assert.match(dashboardSource, /actionCard:\s*\{[\s\S]*flexDirection: 'column'/);
  assert.match(dashboardSource, /actionTitle:\s*\{[\s\S]*flex: 1,[\s\S]*flexShrink: 1/);
  assert.match(quickActionSource, /styles\.actionHeading/);
  assert.match(quickActionSource, /styles\.actionBody/);
  assert.match(quickActionSource, /styles\.actionFooter/);
  assert.match(dashboardSource, /actionBody:\s*\{[\s\S]*marginTop: 20/);
  assert.match(dashboardSource, /actionFooter:\s*\{[\s\S]*marginTop: 'auto',[\s\S]*alignItems: 'flex-end'/);
  assert.doesNotMatch(dashboardSource, /actionArrow:\s*\{[^}]*position: 'absolute'/);
});

test('keeps Recently Checked close to the Weekly Plan card', () => {
  const dashboardSource = fs.readFileSync(
    new URL('./HomeDashboardScreen.tsx', import.meta.url),
    'utf8',
  );

  assert.match(dashboardSource, /'recentSectionMarginTop', 4\)/);
  assert.match(dashboardSource, /planPlate:\s*\{[\s\S]*marginBottom: 4,/);
});

test('keeps the empty-plan image within the existing plan section', () => {
  const dashboardSource = fs.readFileSync(
    new URL('./HomeDashboardScreen.tsx', import.meta.url),
    'utf8',
  );

  assert.match(dashboardSource, /<EmptyPlanCard onCreatePlanPress=\{onCreatePlanPress\} viewportWidth=\{viewportWidth\} \/>/);
  assert.match(dashboardSource, /styles\.planPlate, styles\.planEmptyStaticImage/);
});

test('keeps the Price Check navigation label inside its enlarged circle', () => {
  const dashboardSource = fs.readFileSync(
    new URL('./HomeDashboardScreen.tsx', import.meta.url),
    'utf8',
  );

  assert.match(dashboardSource, /navPriceCheck:\s*{[\s\S]*height: 96,[\s\S]*width: 96,/);
  assert.match(dashboardSource, /navPriceCheckLabel:\s*{[\s\S]*fontSize: 13,[\s\S]*lineHeight: 16,/);
  assert.match(dashboardSource, /<Text numberOfLines=\{1\} style=\{styles\.navPriceCheckLabel\}>Price Check<\/Text>/);
});
