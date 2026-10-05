import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import ts from 'typescript';

const source = fs.readFileSync(new URL('./receiptReviewDraft.ts', import.meta.url), 'utf8');
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, esModuleInterop: true },
}).outputText;
const stored = new Map();
const mockStorage = {
  getItem: async (key) => stored.get(key) ?? null,
  setItem: async (key, value) => { stored.set(key, value); },
  removeItem: async (key) => { stored.delete(key); },
};
const module = { exports: {} };
new Function('require', 'module', 'exports', compiled)(
  () => ({ __esModule: true, default: mockStorage }), module, module.exports,
);
const { loadReceiptReviewDraft, saveReceiptReviewDraft, clearReceiptReviewDraft } = module.exports;

test('manual line client ID survives a saved draft and clears after confirmation', async () => {
  const id = '12345678-1234-4123-8123-123456789abc';
  const row = {
    id, lineId: null, clientLineId: id, foodId: 'SF018', name: 'Egg',
    price: 2.5, quantityKg: 2, quantityUnit: 'pcs', rawName: 'Added manually',
  };
  await saveReceiptReviewDraft('receipt-a', [row], [id]);
  const loaded = await loadReceiptReviewDraft('receipt-a');
  assert.equal(loaded.manualLines[0].clientLineId, id);
  assert.deepEqual(loaded.selectedManualIds, [id]);
  await clearReceiptReviewDraft('receipt-a');
  assert.equal(await loadReceiptReviewDraft('receipt-a'), null);
});

test('corrupt or foreign client IDs cannot be restored as manual rows', async () => {
  await mockStorage.setItem('wisebasket:receipt-review-draft:v1:receipt-b', JSON.stringify({
    manualLines: [{ id: 'not-a-uuid', lineId: null, clientLineId: 'not-a-uuid', foodId: 'SF018', name: 'Egg' }],
    selectedManualIds: ['not-a-uuid'],
  }));
  const loaded = await loadReceiptReviewDraft('receipt-b');
  assert.deepEqual(loaded.manualLines, []);
  assert.deepEqual(loaded.selectedManualIds, []);
});
