import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

const appSource = fs.readFileSync(path.resolve(process.cwd(), 'App.tsx'), 'utf8');
const proposalSource = fs.readFileSync(
  path.resolve(process.cwd(), 'src/screens/planProposal.ts'),
  'utf8',
);
const screenSource = fs.readFileSync(
  path.resolve(process.cwd(), 'src/screens/CheckPricesScreen.tsx'),
  'utf8',
);

test('nearby-store budget overages do not trigger silent quantity reduction', () => {
  assert.doesNotMatch(appSource, /trimmedBudget|quantityTrimNotice|overRatio <= 1\.10/);
  assert.doesNotMatch(proposalSource, /budgetOverride/);
  assert.match(appSource, /if \(budget > 0 && cheapestStore !== null && cheapestStore > budget\)/);
  assert.match(appSource, /Your planned quantities have not been changed/);
  assert.match(appSource, /Edit the basket or change your weekly budget/);
  assert.doesNotMatch(screenSource, /silent quantity trim/);
});

test('exact planner purchase weight is carried as a minimum through replans', () => {
  assert.match(proposalSource, /item\.minimumPurchaseKg/);
  assert.match(proposalSource, /item\.purchase_g[\s\S]*\/ 1000/);
  assert.match(proposalSource, /minimumPurchaseKg !== undefined/);
});
