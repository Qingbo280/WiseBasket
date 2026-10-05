import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

const fixtureSource = fs.readFileSync(
  path.resolve(process.cwd(), 'src/screens/fixtures/demoStorePrices.ts'),
  'utf8',
);
const calculatorSource = fs.readFileSync(
  path.resolve(process.cwd(), 'src/screens/fixtures/demoPriceCalculator.ts'),
  'utf8',
);

test('keeps Check Prices data in isolated synthetic frontend files', () => {
  assert.match(fixtureSource, /DEMO \/ SYNTHETIC FRONTEND DATA/);
  assert.match(fixtureSource, /DemoPriceRecord/);
  assert.match(fixtureSource, /address/);
  assert.match(fixtureSource, /DEMO_STORE_PRICE_RECORDS/);
  assert.doesNotMatch(fixtureSource, /priceGuideMin|comparedTotal|comparisonDifferenceLabel/);
  assert.match(calculatorSource, /DEMO \/ SYNTHETIC FRONTEND LOGIC/);
  assert.match(calculatorSource, /calculateDemoPricePrototype/);
  assert.match(calculatorSource, /getDemoProductPriceRange/);
});

test('derives display totals and comparisons instead of storing final values', () => {
  assert.match(calculatorSource, /priceGuideMin/);
  assert.match(calculatorSource, /comparedTotal/);
  assert.match(calculatorSource, /isLowestComparedTotal/);
  assert.match(calculatorSource, /comparisonDifferenceLabel/);
  assert.match(calculatorSource, /No production price|no production price|production price/);
  assert.match(calculatorSource, /roundCurrency/);
});
