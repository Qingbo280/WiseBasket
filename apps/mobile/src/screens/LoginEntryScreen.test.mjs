import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';

const source = fs.readFileSync(new URL('./LoginEntryScreen.tsx', import.meta.url), 'utf8');
const appSource = fs.readFileSync(new URL('../../App.tsx', import.meta.url), 'utf8');
const heroAsset = new URL('../../assets/images/auth/login-hero-basket.png', import.meta.url);

function readPngDimensions(fileUrl) {
  const bytes = fs.readFileSync(fileUrl);
  assert.equal(bytes.toString('ascii', 1, 4), 'PNG');
  return {
    height: bytes.readUInt32BE(20),
    width: bytes.readUInt32BE(16),
  };
}

test('login keeps functional copy and inputs as real React Native UI', () => {
  for (const copy of [
    'Log in',
    'Welcome back. Continue your plan anytime.',
    'Email address',
    'Password',
    'Forgot password?',
    'Don’t have an account?',
    'Create account',
    'Your information stays private and secure.',
  ]) {
    assert.match(source, new RegExp(copy.replace(/[.*+?^${}()|[\\]\\]/g, '\\$&')));
  }

  assert.match(source, /<TextInput/);
  assert.match(source, /secureTextEntry={!showPassword}/);
  assert.match(source, /onPress=\{\(\) => setShowPassword/);
  assert.match(source, /accessibilityRole="button"/);
  assert.match(source, /minHeight: 48/);
  assert.doesNotMatch(source, /plannerApi|AuthProvider|fetch\(|axios/);
});

test('login uses the complete transparent hero and existing foliage layers', () => {
  for (const asset of [
    'login-hero-basket.png',
    'auth-plant-left-top.png',
    'auth-plant-right-middle.png',
    'auth-plant-bottom-left.png',
    'auth-plant-bottom-right.png',
    'wisebasket-logo-horizontal.png',
  ]) {
    assert.match(source, new RegExp(asset));
  }

  assert.match(source, /pointerEvents=["']none["']/);
  assert.match(source, /StyleSheet\.absoluteFill/);
  assert.match(source, /resizeMode="contain"/);
  assert.deepEqual(readPngDimensions(heroAsset), { height: 897, width: 1304 });
});

test('login keeps normal content responsive and keeps the decorative layer out of layout flow', () => {
  assert.match(source, /const horizontalPadding = width <= 360 \? 24 : width <= 384 \? 28 : 34;/);
  assert.match(source, /const heroWidth = Math\.min\(width \* 0\.75, 310\);/);
  assert.match(source, /height: heroHeight/);
  assert.match(source, /contentContainerStyle=/);
  assert.match(source, /wrapper:[\s\S]*?overflow: 'hidden'/);
  assert.doesNotMatch(source, /transform:/);
});

test('keeps both Price Check next-step actions behind the shared auth flow', () => {
  assert.match(appSource, /onFinishForNow=\{handlePriceCheckFinish\}/);
  assert.match(appSource, /onPlanNextWeek=\{handlePriceCheckPlanNextWeek\}/);
  assert.match(appSource, /onLogin=\{\(\) => setScreen\('login-entry'\)\}/);
  assert.match(appSource, /<LoginEntryScreen/);
});
