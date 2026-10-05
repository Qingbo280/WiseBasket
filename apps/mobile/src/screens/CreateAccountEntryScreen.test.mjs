import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';

const source = fs.readFileSync(new URL('./CreateAccountEntryScreen.tsx', import.meta.url), 'utf8');
const appSource = fs.readFileSync(new URL('../../App.tsx', import.meta.url), 'utf8');
const heroAsset = new URL('../../assets/images/auth/create-account-hero-basket.png', import.meta.url);

function readPngDimensions(fileUrl) {
  const bytes = fs.readFileSync(fileUrl);
  assert.equal(bytes.toString('ascii', 1, 4), 'PNG');
  return {
    height: bytes.readUInt32BE(20),
    width: bytes.readUInt32BE(16),
  };
}

test('create account keeps functional copy and form controls as real React Native UI', () => {
  for (const copy of [
    'Create account',
    'Save your plan and continue anytime.',
    'User name',
    'Email address',
    'Password',
    'Use at least 8 characters.',
    'Confirm password',
    'Already have an account?',
    'Log in',
    'Your information stays private and secure.',
  ]) {
    assert.match(source, new RegExp(copy.replace(/[.*+?^${}()|[\\]\\]/g, '\\$&')));
  }

  assert.match(source, /<TextInput/);
  assert.match(source, /secureTextEntry={!showPassword}/);
  assert.match(source, /secureTextEntry={!showConfirmPassword}/);
  assert.match(source, /onPress=\{\(\) => setShowPassword/);
  assert.match(source, /onPress=\{\(\) => setShowConfirmPassword/);
  assert.match(source, /accessibilityRole="button"/);
  assert.match(source, /minHeight: 48/);
  assert.doesNotMatch(source, /plannerApi|AuthProvider|fetch\(|axios/);
});

test('create account uses the cleaned transparent hero and existing foliage layers', () => {
  for (const asset of [
    'create-account-hero-basket.png',
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
  assert.deepEqual(readPngDimensions(heroAsset), { height: 970, width: 1398 });
});

test('create account keeps functional content responsive and decorative imagery out of layout flow', () => {
  assert.match(source, /const horizontalPadding = width <= 360 \? 24 : width <= 384 \? 28 : 34;/);
  assert.match(source, /const heroWidth = Math\.min\(width \* 0\.62, 260\);/);
  assert.match(source, /height: heroHeight/);
  assert.match(source, /contentContainerStyle=/);
  assert.match(source, /wrapper:[\s\S]*?overflow: 'hidden'/);
  assert.doesNotMatch(source, /transform:/);
});

test('keeps both Price Check next-step actions behind the shared auth flow', () => {
  assert.match(appSource, /onFinishForNow=\{handlePriceCheckFinish\}/);
  assert.match(appSource, /onPlanNextWeek=\{handlePriceCheckPlanNextWeek\}/);
  assert.match(appSource, /onLogin=\{\(\) => setScreen\('login-entry'\)\}/);
  assert.match(appSource, /onRegister=\{\(\) => setScreen\('create-account'\)\}/);
  assert.match(appSource, /onCreateAccount=\{\(\) => setScreen\('create-account'\)\}/);
  assert.match(appSource, /<CreateAccountEntryScreen/);
});
