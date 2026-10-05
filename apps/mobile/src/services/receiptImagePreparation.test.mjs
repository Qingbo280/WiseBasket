import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

const sourcePath = path.resolve(process.cwd(), 'src/services/receiptImagePreparation.ts');

test('normalizes receipt images to a compact JPEG before upload', () => {
  assert.ok(fs.existsSync(sourcePath), 'receipt image preparation service must exist');
  const source = fs.readFileSync(sourcePath, 'utf8');
  assert.match(source, /manipulateAsync/);
  assert.match(source, /SaveFormat\.JPEG/);
  assert.match(source, /MAX_RECEIPT_IMAGE_EDGE = 2000/);
  assert.match(source, /compress: 0\.8/);
});

test('keeps small receipts at their original size while bounding large uploads', () => {
  const source = fs.readFileSync(sourcePath, 'utf8');
  assert.match(source, /asset\.width > MAX_RECEIPT_IMAGE_EDGE \|\| asset\.height > MAX_RECEIPT_IMAGE_EDGE/);
  assert.match(source, /resize: \{ height: MAX_RECEIPT_IMAGE_EDGE \}/);
  assert.match(source, /resize: \{ width: MAX_RECEIPT_IMAGE_EDGE \}/);
});
