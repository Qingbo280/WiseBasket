import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';

const source = fs.readFileSync(new URL('./WelcomeScreen.tsx', import.meta.url), 'utf8');
const heroAsset = new URL('../../assets/images/auth/auth-basket-hero.png', import.meta.url);

function readPngDimensions(fileUrl) {
  const bytes = fs.readFileSync(fileUrl);
  assert.equal(bytes.toString('ascii', 1, 4), 'PNG');
  return {
    height: bytes.readUInt32BE(20),
    width: bytes.readUInt32BE(16),
  };
}

test('auth entry keeps functional copy and decorative artwork as real UI layers', () => {
  for (const copy of [
    'Save and continue',
    'Log in or create an account to keep going.',
    'Create account',
    'Log in',
    'Your information stays private and secure.',
  ]) {
    assert.match(source, new RegExp(copy.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
  }

  for (const asset of [
    'auth-basket-hero.png',
    'auth-plant-left-top.png',
    'auth-plant-right-middle.png',
    'auth-plant-bottom-left.png',
    'auth-plant-bottom-right.png',
  ]) {
    assert.match(source, new RegExp(asset));
  }

  assert.match(source, /pointerEvents=["']none["']/);
  assert.match(source, /minHeight:\s*48/);
});

test('keeps the default composition compact and independent from decorative layout', () => {
  assert.doesNotMatch(source, /ScrollView/);
  assert.match(source, /const heroWidth = Math\.min\(width \* 0\.77, 316\);/);
  assert.match(source, /const heroHeight = heroWidth \* \(520 \/ 647\);/);
  assert.match(source, /maxWidth: 316/);
  assert.match(source, /height: heroHeight/);
  assert.match(source, /const logoHeight = logoWidth \* \(389 \/ 1528\);/);
  assert.match(source, /height: logoHeight/);
  assert.match(source, /paddingTop: compactHeight \? 10 : 16/);
  assert.doesNotMatch(source, /contentLayer:[\s\S]*?flexGrow/);
});

test('hero asset canvas includes the complete right-side approved artwork', () => {
  assert.deepEqual(readPngDimensions(heroAsset), { height: 520, width: 647 });
});

test('keeps foliage as an edge-cropped framing system around the fixed content', () => {
  assert.match(source, /top: height \* 0\.15/);
  assert.match(source, /plantLeftTop:[\s\S]*?left: '-14%'/);
  assert.match(source, /plantRightMiddle:[\s\S]*?right: '-9%'/);
  assert.match(source, /bottom: -height \* 0\.01/);
  assert.match(source, /plantBottomRight:[\s\S]*?right: '-4%'/);
});

test('preserves the supplied foliage artwork proportions', () => {
  assert.match(source, /const plantBottomLeftWidth = Math\.min\(width \* 0\.23, 94\);/);
  assert.match(source, /const plantBottomRightWidth = Math\.min\(width \* 0\.44, 180\);/);
  assert.match(source, /height: plantLeftTopWidth \* \(1024 \/ 1536\)/);
  assert.match(source, /height: plantRightMiddleWidth \* \(1585 \/ 992\)/);
  assert.match(source, /height: plantBottomLeftWidth \* \(1535 \/ 1024\)/);
  assert.match(source, /height: plantBottomRightWidth \* \(1024 \/ 1536\)/);
});

test('uses the screen edge as the only foliage clipping boundary', () => {
  assert.match(source, /StyleSheet\.absoluteFill/);
  const decorativeLayer = source.match(/decorativeLayer:\s*{([\s\S]*?)\n  },/);
  assert.ok(decorativeLayer);
  assert.doesNotMatch(decorativeLayer[1], /overflow: 'hidden'/);
  const decorativeSource = source.slice(source.indexOf('function DecorativeLayer'), source.indexOf('function AuthActionButton'));
  assert.equal((decorativeSource.match(/resizeMode="contain"/g) ?? []).length, 4);
  assert.match(source, /wrapper:\s*{[\s\S]*?overflow: 'hidden'/);
});
