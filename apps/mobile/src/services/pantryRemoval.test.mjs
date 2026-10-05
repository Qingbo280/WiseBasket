import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import ts from 'typescript';

const source = fs.readFileSync(new URL('./pantryRemoval.ts', import.meta.url), 'utf8');
const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext } }).outputText;
const { removePantryFood, clearRemovedHaveChoice } = await import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}`);
const row = (id, food = 'A', status = 'AVAILABLE') => ({ pantry_item_id: id, status, food: { canonical_food_id: food } });

test('remove resolves all AVAILABLE duplicate IDs and leaves other stock untouched', async () => {
  const rows = [row(1), row(2), row(3, 'B'), row(4, 'A', 'REMOVED')];
  const calls = [];
  const result = await removePantryFood(7, 'A', { list: async () => rows, remove: async (...args) => calls.push(args) });
  assert.deepEqual(calls, [[7, 1], [7, 2]]);
  assert.deepEqual(result, [rows[2], rows[3]]);
});

test('no AVAILABLE matching row fails visibly without inventing a successful deletion', async () => {
  await assert.rejects(() => removePantryFood(7, 'A', {
    list: async () => [row(3, 'B'), row(4, 'A', 'REMOVED')], remove: async () => assert.fail('unexpected write'),
  }), /not saved in your pantry/);
});

test('failed DELETE rejects and a retry can remove the remaining duplicate', async () => {
  let rows = [row(1), row(2), row(3, 'B')];
  let fail = true;
  const api = { list: async () => rows, remove: async (_household, id) => {
    if (id === 2 && fail) throw new Error('offline');
    rows = rows.filter((item) => item.pantry_item_id !== id);
  } };
  await assert.rejects(() => removePantryFood(7, 'A', api), /offline/);
  fail = false;
  assert.deepEqual(await removePantryFood(7, 'A', api), [row(3, 'B')]);
});

test('removal clears the persisted Have choice without changing Need or Skip intentions', () => {
  const items = [{ productId: 'A', choice: 'have' }, { productId: 'B', choice: 'have' }, { productId: 'A', choice: 'need' }, { productId: 'A', choice: 'skip' }];
  assert.deepEqual(clearRemovedHaveChoice(items, 'A'), [
    { productId: 'A', choice: 'skip' }, items[1], items[2], items[3],
  ]);
  assert.equal(items[0].choice, 'have');
});

test('lost DELETE acknowledgement succeeds only when GET confirms the row is gone', async () => {
  let rows = [row(1), row(3, 'B')];
  const result = await removePantryFood(7, 'A', {
    list: async () => rows,
    remove: async () => { rows = [row(3, 'B')]; throw new Error('timeout'); },
  });
  assert.deepEqual(result, [row(3, 'B')]);
});

test('failed DELETE with unavailable reconciliation remains an error', async () => {
  let reads = 0;
  await assert.rejects(() => removePantryFood(7, 'A', {
    list: async () => { if (++reads > 1) throw new Error('read offline'); return [row(1)]; },
    remove: async () => { throw new Error('delete offline'); },
  }), /delete offline/);
});

test('a rejected DELETE is not retried or reported successful while GET still shows the row', async () => {
  let writes = 0;
  await assert.rejects(() => removePantryFood(7, 'A', {
    list: async () => [row(1)],
    remove: async () => { writes++; throw new Error('503'); },
  }), /503/);
  assert.equal(writes, 1);
});

test('Have synchronization captures rollback choices before yielding to a removal', () => {
  const app = fs.readFileSync(new URL('../../App.tsx', import.meta.url), 'utf8');
  const start = app.indexOf('const syncHaveChoicesToPantry =');
  const capture = app.indexOf('const previousDraft = basketDraftRef.current;', start);
  const barrier = app.indexOf('await pantryRemovalQueueRef.current;', start);
  const generation = app.indexOf('const intentId = ++haveIntentIdRef.current;', start);
  assert.ok(start >= 0 && generation > start && capture > generation && barrier > capture);
});
