import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import ts from 'typescript';

const source = fs.readFileSync(new URL('./basketHaveSync.ts', import.meta.url), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext } }).outputText;
const { BasketHaveSyncQueue, reconcileFailedHaveChoices } = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`);

test('rapid Have toggles serialize writes and keep the latest desired set', async () => {
  let release;
  const first = new Promise((resolve) => { release = resolve; });
  const writes = [];
  const applied = [];
  const queue = new BasketHaveSyncQueue(async (id, foods) => {
    writes.push([id, foods]);
    if (writes.length === 1) await first;
    return foods;
  }, async () => []);
  queue.enqueue({ householdId: 1, foodIds: ['B', 'A', 'A'], onApplied: (items) => applied.push(items), onFailed: () => assert.fail() });
  queue.enqueue({ householdId: 1, foodIds: ['A'], onApplied: (items) => applied.push(items), onFailed: () => assert.fail() });
  release();
  await queue.whenIdle();
  assert.deepEqual(writes, [[1, ['A', 'B']], [1, ['A']]]);
  assert.deepEqual(applied, [['A']]);
});

test('permanent failure reports the final authoritative GET, including a write committed despite timeout', async () => {
  let reads = 0;
  let failed;
  const queue = new BasketHaveSyncQueue(async () => { throw new Error('timeout'); }, async () => ++reads === 1 ? [] : ['A']);
  queue.enqueue({ householdId: 1, foodIds: ['A'], onApplied: () => assert.fail(), onFailed: (error, items) => { failed = [error.message, items]; } });
  await queue.whenIdle();
  assert.equal(reads, 2);
  assert.deepEqual(failed, ['timeout', ['A']]);
});

test('a newer intent during the final reconciliation GET suppresses the old failure', async () => {
  let release;
  let reads = 0;
  let writes = 0;
  const finalRead = new Promise((resolve) => { release = resolve; });
  const applied = [];
  const queue = new BasketHaveSyncQueue(async (_id, foods) => {
    if (++writes <= 2) throw new Error('timeout');
    return foods;
  }, async () => ++reads === 2 ? finalRead : []);
  queue.enqueue({ householdId: 1, foodIds: ['A'], onApplied: () => assert.fail(), onFailed: () => assert.fail('stale failure') });
  while (reads < 2) await new Promise((resolve) => setImmediate(resolve));
  queue.enqueue({ householdId: 1, foodIds: ['B'], onApplied: (items) => applied.push(items), onFailed: () => assert.fail() });
  release(['A']);
  await queue.whenIdle();
  assert.deepEqual(applied, [['B']]);
});

test('failed Have reconciles saved choices without reverting newer edits or treating manual pantry as managed Have', () => {
  const previous = [{ productId: 'A', choice: 'need' }, { productId: 'B', choice: 'have' }, { productId: 'C', choice: 'skip' }];
  const intended = [{ productId: 'A', choice: 'have' }, { productId: 'B', choice: 'need' }, { productId: 'C', choice: 'have' }];
  const current = [...intended.slice(0, 2), { productId: 'C', choice: 'skip' }];
  assert.deepEqual(reconcileFailedHaveChoices(current, intended, previous, new Set(['B']), new Set(['B'])), previous);
  assert.equal(reconcileFailedHaveChoices(current, intended, previous, new Set(['B']), new Set())[1].choice, 'need');
});

test('unknown write outcome reconciles with GET and retries the latest intent', async () => {
  const calls = [];
  const queue = new BasketHaveSyncQueue(async (_id, foods) => {
    calls.push(`PUT:${foods.join(',')}`);
    if (calls.length === 1) throw new Error('network after commit');
    return foods;
  }, async () => { calls.push('GET'); return []; });
  let applied;
  queue.enqueue({ householdId: 1, foodIds: ['A'], onApplied: (items) => { applied = items; }, onFailed: () => assert.fail() });
  await queue.whenIdle();
  assert.deepEqual(calls, ['PUT:A', 'GET', 'PUT:A']);
  assert.deepEqual(applied, ['A']);
});

test('household switch suppresses old response and sends only the new household intent', async () => {
  let release;
  const first = new Promise((resolve) => { release = resolve; });
  const applied = [];
  const queue = new BasketHaveSyncQueue(async (id, foods) => {
    if (id === 1) await first;
    return foods;
  }, async () => []);
  queue.enqueue({ householdId: 1, foodIds: ['A'], onApplied: () => applied.push(1), onFailed: () => assert.fail() });
  queue.cancelExcept(2);
  queue.enqueue({ householdId: 2, foodIds: ['B'], onApplied: () => applied.push(2), onFailed: () => assert.fail() });
  release();
  await queue.whenIdle();
  assert.deepEqual(applied, [2]);
});
