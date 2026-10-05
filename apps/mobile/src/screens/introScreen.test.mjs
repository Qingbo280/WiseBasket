import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

const screenPath = new URL('./IntroScreen.tsx', import.meta.url);
const appPath = new URL('../../App.tsx', import.meta.url);
const screenSource = fs.existsSync(screenPath) ? fs.readFileSync(screenPath, 'utf8') : '';
const appSource = fs.readFileSync(appPath, 'utf8');

test('renders exactly two approved intro images in a horizontal pager', () => {
  assert.ok(screenSource, 'IntroScreen.tsx should exist');
  assert.match(screenSource, /06_intro_01\.png/);
  assert.match(screenSource, /06_intro_02\.png/);
  assert.match(screenSource, /const INTRO_PAGES = \[/);
  assert.match(screenSource, /horizontal/);
  assert.match(screenSource, /pagingEnabled/);
  assert.match(screenSource, /INTRO_PAGES\.length/);
  assert.doesNotMatch(screenSource, /06_intro_03\.png|Page 3/);
});

test('uses transparent accessible hit areas without duplicating baked intro controls', () => {
  assert.match(screenSource, /Skip introduction/);
  assert.match(screenSource, /Next introduction page/);
  assert.match(screenSource, /Start WiseBasket/);
  assert.match(screenSource, /<Pressable/);
  assert.doesNotMatch(screenSource, /<Text[^>]*>\s*(Skip|Next|Start WiseBasket)/);
  assert.doesNotMatch(screenSource, /pagination|progressDot|PageIndicator/);
});

test('keeps the logo inside each swipeable page and uses a compact logo size', () => {
  const pageRenderer = screenSource.slice(screenSource.indexOf('function IntroPageImage'));

  assert.match(pageRenderer, /LOGO_IMAGE/);
  assert.match(pageRenderer, /styles\.pageLogo/);
  assert.doesNotMatch(screenSource.slice(0, screenSource.indexOf('function IntroPageImage')), /styles\.logoLayer/);
  assert.match(screenSource, /width: 116/);
});

test('starts TestFlow at Intro and sends completion to Auth Entry before Home', () => {
  assert.match(appSource, /import \{ IntroScreen \} from ['"]\.\/src\/screens\/IntroScreen['"]/);
  // Restored sessions skip the intro straight to Home (ported #237 semantics);
  // a guest session still starts at the two-page Intro.
  assert.match(appSource, /useState<TestScreen>\(isAuthenticated \? 'home-dashboard' : 'intro'\)/);
  assert.match(appSource, /const handleIntroComplete = \(pageIndex: number\) =>/);
  assert.match(appSource, /handleIntroComplete[\s\S]*setIntroReturnPage\(pageIndex\)/);
  assert.match(appSource, /handleIntroComplete[\s\S]*setAuthCompletionIntent\('home-dashboard'\)/);
  assert.match(appSource, /handleIntroComplete[\s\S]*setScreen\('auth-entry'\)/);
  const introHandler = appSource.slice(
    appSource.indexOf('const handleIntroComplete'),
    appSource.indexOf('const handlePlanLocationBack'),
  );
  assert.doesNotMatch(introHandler, /setLocationPurpose\('plan'\)/);
  assert.doesNotMatch(introHandler, /setScreen\('location-get-location'\)/);
  assert.match(appSource, /if \(screen === 'intro'\)/);
  assert.match(appSource, /<IntroScreen initialPage=\{introReturnPage\} onComplete=\{handleIntroComplete\} \/>/);
  assert.doesNotMatch(appSource, /IntroLocationScreen|FirstLaunchLocationScreen/);
});

test('routes successful Intro authentication to Home without requiring a product', () => {
  // Ported #237 semantics: login/register remount the flow onto Home; a
  // pending plan-next-week intent rides the authHandoff ref across that
  // remount instead of a post-login navigation call.
  assert.match(appSource, /authHandoff\.current = authCompletionIntent === 'plan-next-week' \? selectedProduct : null/);
  assert.match(appSource, /if \(isAuthenticated && authHandoff\.current\)/);
  assert.match(appSource, /authHandoff\.current = null;\s*void openPlanQuestionOne\('price-check-next-step'\)/);
  assert.doesNotMatch(appSource, /handleEnterDashboardAfterAuth/);
});
