import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

const receiptApiSource = fs.readFileSync(path.resolve(process.cwd(), 'src/services/receiptApi.ts'), 'utf8');
const apiSource = fs.readFileSync(path.resolve(process.cwd(), 'src/services/api.ts'), 'utf8');

test('uploads receipt images as authenticated multipart data', () => {
  assert.match(receiptApiSource, /new FormData\(\)/);
  assert.match(receiptApiSource, /Platform\.OS === 'web'/);
  assert.match(receiptApiSource, /await imageResponse\.blob\(\)/);
  assert.match(receiptApiSource, /new File\(imageUri\)/);
  assert.doesNotMatch(receiptApiSource, /as unknown as Blob/);
  assert.match(receiptApiSource, /body\.append\('file'/);
  assert.match(receiptApiSource, /households\/\$\{householdId\}\/receipts/);
  assert.match(apiSource, /body instanceof FormData/);
  assert.match(apiSource, /!isMultipart/);
});

test('polls PaddleOCR-backed receipt processing and confirms reviewed lines', () => {
  assert.match(receiptApiSource, /receipt\.status === 'DONE'/);
  assert.match(receiptApiSource, /receipt\.status === 'FAILED'/);
  assert.match(receiptApiSource, /setTimeout\(resolve, 1_000\)/);
  assert.match(receiptApiSource, /receipts\/\$\{receiptId\}\/confirm/);
  assert.match(receiptApiSource, /added_lines/);
});

test('polling timeout tracks the backend 240-second deadline with network slack', () => {
  assert.match(receiptApiSource, /RECEIPT_QUEUE_WAIT_TIMEOUT_MS = 260_000/);
});
