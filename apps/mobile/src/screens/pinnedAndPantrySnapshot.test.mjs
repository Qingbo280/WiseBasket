import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

const appSource = fs.readFileSync(path.resolve(process.cwd(), 'App.tsx'), 'utf8');
const proposalSource = fs.readFileSync(
  path.resolve(process.cwd(), 'src/screens/planProposal.ts'),
  'utf8',
);
const typesSource = fs.readFileSync(
  path.resolve(process.cwd(), 'src/api/plannerTypes.ts'),
  'utf8',
);

test('A1: previously-shown week-plan need set rides as pinned_food_ids', () => {
  // contract field exists on the request type
  assert.match(typesSource, /pinned_food_ids\?: string\[\] \| null/);
  // planRequestFromDraft accepts and forwards the pinned set
  assert.match(proposalSource, /pinnedFoodIds: readonly string\[\] = \[\]/);
  assert.match(proposalSource, /pinned_food_ids: \[\.\.\.pinnedFoodIds\]/);
  // App captures the committed need set BEFORE the post (fresh adds stay
  // curatable) and passes it as the last planRequestFromDraft argument
  assert.match(appSource, /const pinnedIds = committedNeedIdsRef\.current;/);
  assert.match(appSource, /basketDraftRef\.current,\s*\n?\s*pinnedIds,/);
});

test('A6: a re-solve never reshuffles the week plan (Have stays in place)', () => {
  // the rebuilt draft is stable-sorted by the PREVIOUS draft's positions -
  // without this a Have/Skip edit carried the item to the bottom via
  // carriedNonNeed once the re-solve response landed.
  assert.match(appSource, /const prevIndexById = new Map\(/);
  assert.match(appSource, /finalDraft\.sort\(/);
  assert.match(appSource, /prevIndexById\.get\(a\.productId\) \?\? Number\.MAX_SAFE_INTEGER/);
  // carriedNonNeed still exists (visibility rule) but no longer defines order
  assert.match(appSource, /const finalDraft = \[\.\.\.rebuiltDraft, \.\.\.carriedNonNeed\]/);
});

test('A2: pantry stock is a journey-level snapshot, not a per-post fetch', () => {
  assert.match(appSource, /pantryStockSnapshotRef/);
  assert.match(appSource, /pantryStockSnapshotDirtyRef/);
  assert.match(appSource, /const pantryStock = await pantryStockForPlan\(\);/);
  // the old per-post fetch must be gone from the plan path
  assert.doesNotMatch(
    appSource,
    /\(await fetchConfirmedPantryStock\(activeHouseholdId\)\) \?\? \[\]/,
  );
  // a failed refresh keeps the last good snapshot (never clears to zero)
  assert.match(appSource, /\?\? cached\s*\?\? \[\]/);
  // Mutations/reconciliation invalidate: have-choice success + final failure
  // read + recipe Have + receipt confirm + remaining-quantity save + removal.
  assert.equal(
    (appSource.match(/invalidatePantryStockSnapshot\(\);/g) ?? []).length,
    6,
    'all six pantry mutation/reconciliation paths invalidate the planning snapshot',
  );
  assert.match(appSource, /\/\/ A2: the have-sync just mutated pantry/);
  assert.match(appSource, /\/\/ A2: receipt confirm rewrote pantry/);
  const quantitySaveSource = appSource.slice(
    appSource.indexOf('const handlePantryQuantitySave ='),
    appSource.indexOf('const handlePantryItemRemove ='),
  );
  // Failed PATCHes must leave the existing stock snapshot intact.
  assert.match(quantitySaveSource, /const updated = await updatePantryItem\(/);
  assert.equal((quantitySaveSource.match(/invalidatePantryStockSnapshot\(\);/g) ?? []).length, 1);
  assert.ok(quantitySaveSource.indexOf('invalidatePantryStockSnapshot();')
    > quantitySaveSource.indexOf('const updated = await updatePantryItem('));
  assert.match(quantitySaveSource, /if \(activeHouseholdIdRef\.current !== householdId\) return;/);
  const removalSource = appSource.slice(
    appSource.indexOf('const handlePantryItemRemove ='),
    appSource.indexOf('const handleReceiptImageSelected ='),
  );
  // A confirmed DELETE removes stale fallback stock before marking it dirty;
  // a rejected deletion never reaches either mutation.
  assert.match(removalSource, /const updated = await removePantryFood\(/);
  assert.equal((removalSource.match(/invalidatePantryStockSnapshot\(\);/g) ?? []).length, 1);
  const completedRemoval = removalSource.indexOf('const updated = await removePantryFood(');
  const snapshotRemoval = removalSource.indexOf('pantryStockSnapshotRef.current =');
  const dirtySnapshot = removalSource.indexOf('invalidatePantryStockSnapshot();');
  assert.ok(completedRemoval >= 0 && snapshotRemoval > completedRemoval && dirtySnapshot > snapshotRemoval);
  assert.match(removalSource, /pantryStockSnapshotRef\.current\?\.filter\(\(stock\) => stock\.food_id !== item\.productId\) \?\? null/);
  assert.match(removalSource, /if \(activeHouseholdIdRef\.current !== householdId\) return;/);
});
