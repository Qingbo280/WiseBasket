import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import ts from 'typescript';

const source = fs.readFileSync(new URL('./oilEquivalence.ts', import.meta.url), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext } }).outputText;
const { oilGroup, oilRawGrams } = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`);

test('mobile oil conversion mirrors 0.92 g/ml backend rule', () => {
  assert.equal(oilRawGrams('SF120', 1000, 'ml'), 920);
  assert.equal(oilRawGrams('SF121', 1, 'l'), 920);
  assert.equal(oilRawGrams('SF123', 1, 'kg'), 1000);
  assert.equal(oilRawGrams('SF122', 1000, 'ml'), null);
  assert.equal(oilGroup('SF122'), 'SF122');
});
