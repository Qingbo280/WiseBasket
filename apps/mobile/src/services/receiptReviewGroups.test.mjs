import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import ts from 'typescript';

async function load(file) {
  const source = fs.readFileSync(new URL(file, import.meta.url), 'utf8');
  const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext } }).outputText;
  return import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`);
}
const { groupReceiptReviewRows, selectedReceiptGroupRowIds, updateReceiptReviewGroup } = await load('./receiptReviewGroups.ts');
const { prepareReceiptConfirmation, replaceReceiptRowFood, markReceiptRowReviewed,
  buildReceiptReviewRows, prefillReceiptCandidateRows, initialSelectedReceiptRowIds } = await load('./receiptReviewRows.ts');
const row = (id, extra = {}) => ({
  id, lineId: id, foodId: 'SF017', name: 'Chicken breast', price: 2.55,
  quantityKg: 1, quantityUnit: 'kg', suggestedOnly: false, reviewStatus: 'PROPOSED', ...extra,
});
const sum = (values) => Math.round(values.reduce((a, b) => a + b, 0) * 1e6) / 1e6;

test('one food shows one row with converted amounts and summed prices while source purchases survive', () => {
  const lines = [row('a'), row('b', { quantityKg: 500, quantityUnit: 'g' }), row('c', { foodId: 'SF014' })];
  const selected = new Set(['a', 'b', 'c']);
  const groups = groupReceiptReviewRows(lines);
  assert.equal(groups.length, 2);
  assert.deepEqual(groups[0].sourceRowIds, ['a', 'b']);
  assert.equal(groups[0].quantityKg, 1.5);
  assert.equal(groups[0].quantityUnit, 'kg');
  assert.equal(groups[0].price, 5.1);
  const { confirmation, invalidLineIds } = prepareReceiptConfirmation(lines, selected);
  assert.deepEqual(invalidLineIds, []);
  assert.deepEqual(confirmation.lines.map((item) => item.line_id), ['a', 'b', 'c']);
  assert.equal(confirmation.lines[1].qty, 500);
  assert.equal(confirmation.lines[1].unit, 'g');
});

test('editing a combined total preserves source IDs, positive quantities and every sen', () => {
  const lines = [row('a'), row('b', { quantityKg: 0.5 }), row('c', { quantityKg: null, quantityUnit: null })];
  const selected = new Set(['a', 'b', 'c']);
  const group = groupReceiptReviewRows(lines)[0];
  assert.equal(group.quantityKg, null);
  const edited = updateReceiptReviewGroup(lines, group, {
    quantityKg: 2, quantityUnit: 'kg', quantityInput: '2.0', quantityEdited: true,
    price: 10.01, priceInput: '10.01',
  });
  const displayed = groupReceiptReviewRows(edited)[0];
  assert.equal(displayed.quantityKg, 2);
  assert.equal(displayed.quantityInput, '2.0');
  assert.equal(displayed.price, 10.01);
  const payload = prepareReceiptConfirmation(edited, selected);
  assert.deepEqual(payload.invalidLineIds, []);
  assert.equal(sum(payload.confirmation.lines.map((item) => item.qty)), 2);
  assert.equal(sum(payload.confirmation.lines.map((item) => item.price_rm)), 10.01);
  assert.deepEqual(payload, prepareReceiptConfirmation(edited, selected));
  assert.equal(lines[2].quantityKg, null);
});

test('unknown or incompatible quantities are not guessed, and users can enter quantity then unit', () => {
  const selected = new Set(['a', 'b']);
  const original = [row('a'), row('b', { quantityUnit: 'pack', price: null })];
  let group = groupReceiptReviewRows(original)[0];
  assert.equal(group.quantityKg, null);
  assert.equal(group.price, null);
  let lines = updateReceiptReviewGroup(original, group, { quantityKg: 1.5, quantityInput: '1.5', quantityEdited: true });
  group = groupReceiptReviewRows(lines)[0];
  lines = updateReceiptReviewGroup(lines, group, { quantityUnit: 'kg', quantityEdited: true });
  group = groupReceiptReviewRows(lines)[0];
  assert.equal(group.quantityKg, 1.5);
  assert.equal(group.quantityUnit, 'kg');
  assert.deepEqual(prepareReceiptConfirmation(lines, selected).invalidLineIds, []);
});

test('mixed selection requires explicit group acceptance while already-confirmed rows stay locked', () => {
  const lines = [row('a'), row('b', { suggestedOnly: true }), row('c'),
    row('d', { reviewStatus: 'CONFIRMED' }), row('e', { foodId: null })];
  assert.equal(groupReceiptReviewRows(lines).length, 2);
  const selected = selectedReceiptGroupRowIds(lines, new Set(['a', 'd']));
  assert.deepEqual([...selected], ['d']);
  const payload = prepareReceiptConfirmation(lines, selected).confirmation;
  assert.deepEqual(payload.lines.map((line) => line.canonical_food_id), [null, null, null, 'SF017', null]);
  assert.ok(!('qty' in payload.lines[3]));
});

test('two proposed pineapple purchases display one row before any checkbox is selected', () => {
  const raw = ['pineapple-1', 'pineapple-2'].map((id) => ({
    line_id: id, name_raw: 'PINEAPPLE', price_rm: 1.59, qty: 1, unit: 'pc',
    status: 'PROPOSED', match_basis: 'MODEL_SUGGESTION',
    proposed_food: { canonical_food_id: 'SF097', name: 'pineapple' },
    candidates: [{ canonical_food_id: 'SF097', score: 0.9 }],
  }));
  let lines = buildReceiptReviewRows(raw);
  const initialSelection = new Set(initialSelectedReceiptRowIds(lines));
  lines = prefillReceiptCandidateRows(lines, [{ foodId: 'SF097', name: 'pineapple', soldByWeight: true }]);
  let groups = groupReceiptReviewRows(lines);
  assert.equal(groups.length, 1);
  assert.equal(groups[0].quantityKg, 2);
  assert.equal(groups[0].quantityUnit, 'pc');
  assert.equal(groups[0].price, 3.18);
  assert.equal(groups[0].suggestedOnly, true);
  assert.deepEqual(groups[0].sourceRowIds, ['pineapple-1', 'pineapple-2']);
  assert.equal(selectedReceiptGroupRowIds(lines, initialSelection).size, 0);
  assert.ok(prepareReceiptConfirmation(lines, initialSelection).confirmation.lines.every((r) => r.canonical_food_id === null));

  // The existing checkbox accepts all underlying purchases once.
  const ids = groups[0].sourceRowIds;
  lines = ids.reduce((rows, id) => markReceiptRowReviewed(rows, id), lines);
  const selected = selectedReceiptGroupRowIds(lines, new Set(ids));
  groups = groupReceiptReviewRows(lines);
  assert.equal(groups.length, 1);
  assert.equal(groups[0].suggestedOnly, false);
  const { confirmation, invalidLineIds } = prepareReceiptConfirmation(lines, selected);
  assert.deepEqual(invalidLineIds, []);
  assert.deepEqual(confirmation.lines.map((r) => r.line_id), ids);
  assert.equal(sum(confirmation.lines.map((r) => r.qty)), 2);
  assert.equal(sum(confirmation.lines.map((r) => r.price_rm)), 3.18);

  const deselected = selectedReceiptGroupRowIds(lines, new Set());
  assert.equal(groupReceiptReviewRows(lines).length, 1);
  assert.ok(prepareReceiptConfirmation(lines, deselected).confirmation.lines.every((r) => r.canonical_food_id === null));
});

test('selection is independent of member order and groups never mix different food identities', () => {
  const lines = [row('exact'), row('candidate', { suggestedOnly: true }), row('other', { foodId: 'SF014' })];
  for (const ordered of [lines, [...lines].reverse()]) {
    assert.equal(groupReceiptReviewRows(ordered).length, 2);
    const selected = selectedReceiptGroupRowIds(ordered, new Set(['exact', 'other']));
    assert.deepEqual([...selected], ['other']);
  }
  assert.equal(selectedReceiptGroupRowIds(lines, new Set(['exact', 'candidate', 'other'])).size, 3);
});

test('the screen uses whole-group selection for checkbox, totals and confirmation without changing layout', () => {
  const screen = fs.readFileSync(new URL('../screens/ReceiptReviewScreen.tsx', import.meta.url), 'utf8');
  assert.match(screen, /selectedReceiptGroupRowIds\(lines, new Set\(selectedIds\)\)/);
  assert.match(screen, /ids\.every\(\(memberId\) => current\.includes\(memberId\)\)/);
  assert.match(screen, /prepareReceiptConfirmation\(lines, selectedIdSet\)/);
  assert.match(screen, /lines\.filter\(\(line\) => selectedIdSet\.has\(line\.id\)\)/);
});

test('unmatched biscuits are hidden, excluded from totals and skipped without losing the receipt line', () => {
  const lines = [row('a'), row('b'), row('biscuits', {
    foodId: null, name: 'Cannot be matched', price: 8.5,
    quantityKg: null, quantityUnit: null, suggestedOnly: true,
  })];
  const selected = new Set(['a', 'b']);
  const displayed = groupReceiptReviewRows(lines);
  assert.equal(displayed.length, 1);
  assert.equal(displayed[0].price, 5.1);
  assert.deepEqual(displayed[0].sourceRowIds, ['a', 'b']);
  const { confirmation, invalidLineIds } = prepareReceiptConfirmation(lines, selected);
  assert.deepEqual(invalidLineIds, []);
  assert.equal(confirmation.lines.length, 3);
  assert.equal(confirmation.lines[2].line_id, 'biscuits');
  assert.equal(confirmation.lines[2].canonical_food_id, null);
  assert.deepEqual(groupReceiptReviewRows([lines[2]]), []);
});

test('a real catalogue candidate remains reviewable after matching but is not silently accepted', () => {
  const lines = [row('candidate', { suggestedOnly: true })];
  assert.equal(groupReceiptReviewRows(lines).length, 1);
  assert.equal(prepareReceiptConfirmation(lines, new Set()).confirmation.lines[0].canonical_food_id, null);
});

test('replacement merges newly identical rows and manual entries retain their retry identity', () => {
  const selected = new Set(['a', 'manual']);
  const original = [row('a'), row('manual', { lineId: null, clientLineId: 'stable-client', foodId: 'SF014' })];
  const lines = replaceReceiptRowFood(original, 'manual', { foodId: 'SF017', name: 'Chicken breast', suggestedOnly: false });
  const group = groupReceiptReviewRows(lines)[0];
  assert.equal(groupReceiptReviewRows(lines).length, 1);
  const edited = updateReceiptReviewGroup(lines, group, { quantityKg: 3, quantityEdited: true });
  const payload = prepareReceiptConfirmation(edited, selected).confirmation;
  assert.equal(payload.lines[0].line_id, 'a');
  assert.equal(payload.added_lines[0].client_line_id, 'stable-client');
  assert.equal(payload.lines[0].qty + payload.added_lines[0].qty, 3);
});

test('changing units applies to the combined displayed amount, not mixed raw magnitudes', () => {
  const lines = [row('a'), row('b', { quantityKg: 500, quantityUnit: 'g' })];
  const selected = new Set(['a', 'b']);
  const group = groupReceiptReviewRows(lines)[0];
  const updated = updateReceiptReviewGroup(lines, group, { quantityUnit: 'pcs', quantityEdited: true });
  assert.equal(groupReceiptReviewRows(updated)[0].quantityKg, 1.5);
  assert.ok(updated.every((line) => line.quantityUnit === 'pcs'));
});

test('grouped rough estimates retain the approximate marker and sum without losing purchases', () => {
  const lines = [row('a', { foodId: 'SF076', quantityKg: 0.2, quantityEstimated: true,
    quantityHeuristicEstimated: true, suggestedOnly: true }),
  row('b', { foodId: 'SF076', quantityKg: 0.3, suggestedOnly: true })];
  const [group] = groupReceiptReviewRows(lines);
  assert.equal(group.quantityKg, 0.5);
  assert.equal(group.quantityHeuristicEstimated, true);
  const screen = fs.readFileSync(new URL('../screens/ReceiptReviewScreen.tsx', import.meta.url), 'utf8');
  assert.match(screen, /line\.quantityPriceEstimated \|\| line\.quantityHeuristicEstimated \? '~'/);
});
