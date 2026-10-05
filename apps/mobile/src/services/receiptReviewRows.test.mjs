import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import ts from 'typescript';

const file = new URL('./receiptReviewRows.ts', import.meta.url);
const source = fs.existsSync(file) ? fs.readFileSync(file, 'utf8') : 'export {}';
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext } }).outputText;
const {
  buildReceiptReviewRows, confirmedReceiptFoodId, defaultReceiptManualQuantity,
  initialSelectedReceiptRowIds, isLockedConfirmedReceiptRow, markReceiptRowReviewed,
  prefillReceiptCandidateRows,
  prepareReceiptConfirmation,
  rankedReceiptCandidateEntries,
  RECEIPT_UNIT_OPTIONS, replaceReceiptRowFood,
} = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`);
const food = { canonical_food_id: 'chicken', name: 'Chicken', name_ms: null, category: 'Protein' };
const line = (id, proposed_food = food) => ({
  line_id: id, display_order: Number(id), name_raw: 'AYAM RAW LABEL', expanded_name: 'expanded chicken',
  qty: 1, unit: 'kg', price_rm: 12.5, proposed_food, candidates: [], status: 'PROPOSED',
});

test('unit dropdown options are all valid receipt units accepted at confirmation', () => {
  for (const option of RECEIPT_UNIT_OPTIONS) {
    const rows = [{
      id: 'unit-1', lineId: null, foodId: 'chicken', name: 'Chicken', price: 1,
      quantityKg: 1, quantityUnit: option,
    }];
    const { invalidLineIds } = prepareReceiptConfirmation(rows, new Set(['unit-1']));
    assert.deepEqual(invalidLineIds, [], `unit ${option} must pass confirmation validation`);
  }
});

test('each receipt row has only a catalogue name or Cannot be matched, without raw OCR text', () => {
  const rows = buildReceiptReviewRows([line('1'), line('2', null)]);
  assert.deepEqual(rows.map((row) => row.name), ['Chicken', 'Cannot be matched']);
  assert.deepEqual(rows.map((row) => row.lineId), ['1', '2']);
  assert.equal(rows[1].foodId, null);
  assert.ok(rows.every((row) => row.rawName === undefined));
});

test('genuine repeated purchases and different items matched to the same food keep separate rows', () => {
  const rows = buildReceiptReviewRows([line('1'), { ...line('2'), price_rm: 15, name_raw: 'AYAM BREAST' }]);
  assert.equal(rows.length, 2);
  assert.deepEqual(rows.map((row) => row.price), [12.5, 15]);
});

test('only a trusted exact match or previously confirmed row is selected by default', () => {
  const rows = buildReceiptReviewRows([
    { ...line('1'), match_basis: 'CANDIDATE' },
    { ...line('2'), match_basis: 'CANONICAL_EXACT' },
    { ...line('3'), match_basis: null, status: 'CONFIRMED' },
  ]);
  assert.deepEqual(rows.map((row) => row.foodId), [null, 'chicken', 'chicken']);
});

test('skipped rows remain reviewable but do not silently re-enter the purchase', () => {
  const rows = buildReceiptReviewRows([
    { ...line('1'), match_basis: 'CANONICAL_EXACT', status: 'SKIPPED' },
    {
      ...line('2', null), status: 'SKIPPED', match_basis: 'CANDIDATE',
      candidates: [{ canonical_food_id: 'rice', score: 0.7 }, { canonical_food_id: 'chicken', score: 0.9 }],
    },
  ]);
  assert.deepEqual(rows.map((row) => row.lineId), ['1', '2']);
  assert.equal(rows[0].foodId, 'chicken');
  assert.ok(rows.every((row) => row.reviewStatus === 'SKIPPED' && row.suggestedOnly));
  assert.deepEqual(initialSelectedReceiptRowIds(rows), []);
  const withInitialValue = prefillReceiptCandidateRows(rows, [
    { foodId: 'rice', name: 'Rice' }, { foodId: 'chicken', name: 'Chicken' },
  ]);
  assert.equal(withInitialValue[1].foodId, 'chicken');
  assert.deepEqual(initialSelectedReceiptRowIds(withInitialValue), []);
  assert.deepEqual(withInitialValue.map((row) => confirmedReceiptFoodId(row, new Set())), [null, null]);
  assert.equal(confirmedReceiptFoodId(withInitialValue[1], new Set(['2'])), 'chicken');
});

test('confirmed rows are locked to their original food even if selection state is stale', () => {
  const [confirmed, skipped] = buildReceiptReviewRows([
    { ...line('1'), status: 'CONFIRMED', match_basis: null },
    { ...line('2'), status: 'SKIPPED', match_basis: 'CANONICAL_EXACT' },
  ]);
  assert.equal(isLockedConfirmedReceiptRow(confirmed), true);
  assert.equal(isLockedConfirmedReceiptRow(skipped), false);
  assert.deepEqual(initialSelectedReceiptRowIds([confirmed, skipped]), ['1']);
  assert.equal(confirmedReceiptFoodId(confirmed, new Set()), 'chicken');
  assert.equal(confirmedReceiptFoodId(skipped, new Set()), null);
});

test('replacing an unmatched food updates its existing row and preserves quantity, price and order', () => {
  const rows = buildReceiptReviewRows([line('1', null), line('2')]);
  const updated = replaceReceiptRowFood(rows, '1', { foodId: 'rice', name: 'Rice', imageSource: null });
  assert.equal(updated.length, 2);
  assert.deepEqual(updated.map((row) => row.lineId), ['1', '2']);
  assert.equal(updated[0].name, 'Rice');
  assert.equal(updated[0].quantityKg, 1);
  assert.equal(updated[0].price, 12.5);
  assert.equal(rows[0].foodId, null);
});

test('receipt suggestions retain descending match-score order even when catalog order differs', () => {
  const receiptLine = {
    ...line('1', null),
    candidates: [
      { canonical_food_id: 'rice', score: 0.72 },
      { canonical_food_id: 'chicken', score: 0.93 },
      { canonical_food_id: 'tofu', score: 0.84 },
    ],
  };
  const [row] = buildReceiptReviewRows([receiptLine]);
  assert.deepEqual(row.candidateFoodIds, ['chicken', 'tofu', 'rice']);

  const catalog = [
    { foodId: 'rice', name: 'Rice' },
    { foodId: 'tofu', name: 'Tofu' },
    { foodId: 'chicken', name: 'Chicken' },
  ];
  assert.deepEqual(
    rankedReceiptCandidateEntries(catalog, row.candidateFoodIds).map((entry) => entry.foodId),
    ['chicken', 'tofu', 'rice'],
  );
});

test('receipt suggestions skip unavailable and duplicate candidate IDs without disturbing rank', () => {
  const catalog = [{ foodId: 'tofu' }, { foodId: 'chicken' }];
  assert.deepEqual(
    rankedReceiptCandidateEntries(catalog, ['missing', 'chicken', 'chicken', 'tofu'])
      .map((entry) => entry.foodId),
    ['chicken', 'tofu'],
  );
});

test('highest-ranked candidate is an initial value but the review selection stays separate', () => {
  const receiptLine = {
    ...line('1', null),
    candidates: [
      { canonical_food_id: 'rice', score: 0.72 },
      { canonical_food_id: 'chicken', score: 0.93 },
    ],
  };
  const initial = buildReceiptReviewRows([receiptLine]);
  const suggested = prefillReceiptCandidateRows(initial, [
    { foodId: 'rice', name: 'Rice' }, { foodId: 'chicken', name: 'Chicken' },
  ]);
  assert.equal(suggested[0].foodId, 'chicken');
  assert.equal(suggested[0].name, 'Chicken');
  assert.equal(suggested[0].suggestedOnly, true);
  assert.deepEqual(initialSelectedReceiptRowIds(initial), []);
  assert.deepEqual(initialSelectedReceiptRowIds(suggested), []);
  assert.equal(confirmedReceiptFoodId(suggested[0], new Set()), null);
  assert.equal(confirmedReceiptFoodId(suggested[0], new Set([suggested[0].id])), 'chicken');
  assert.equal(initial[0].foodId, null);
  assert.equal(prefillReceiptCandidateRows(suggested, [
    { foodId: 'rice', name: 'Rice' }, { foodId: 'chicken', name: 'Chicken' },
  ]), suggested);
  const refreshed = prefillReceiptCandidateRows(suggested, [{ foodId: 'rice', name: 'Rice' }]);
  assert.equal(refreshed[0].foodId, 'rice');
  const accepted = markReceiptRowReviewed(suggested, suggested[0].id);
  assert.equal(accepted[0].suggestedOnly, false);
  assert.deepEqual(initialSelectedReceiptRowIds(accepted), [suggested[0].id]);
  assert.equal(prefillReceiptCandidateRows(accepted, [{ foodId: 'rice', name: 'Rice' }]), accepted);
  const explicitlyChosen = replaceReceiptRowFood(suggested, suggested[0].id, {
    foodId: 'rice', name: 'Rice', imageSource: null, suggestedOnly: false,
  });
  assert.deepEqual(initialSelectedReceiptRowIds(explicitlyChosen), [suggested[0].id]);
});

test('a receipt price alone never invents kg or egg counts', () => {
  const rows = buildReceiptReviewRows([
    { ...line('1', null), qty: 1, unit: null, price_rm: 4.5,
      candidates: [{ canonical_food_id: 'chili', score: 0.9 }] },
    { ...line('2', null), qty: 1, unit: null, price_rm: 8.7,
      candidates: [{ canonical_food_id: 'egg', score: 0.9 }] },
  ]);
  assert.deepEqual(rows.map((row) => [row.quantityKg, row.quantityUnit]), [[null, null], [null, null]]);
  const filled = prefillReceiptCandidateRows(rows, [
    { foodId: 'chili', name: 'Chili', soldByWeight: true, purchasePriceRmPer100g: 3 },
    { foodId: 'egg', name: 'Egg', soldByWeight: false, purchasePriceRmPer100g: 1.5,
      quantityG: 580, subtitle: '10 biji' },
  ]);
  assert.deepEqual(filled.map((row) => [row.quantityKg, row.quantityUnit]), [[null, null], [null, null]]);
  assert.deepEqual(initialSelectedReceiptRowIds(filled), []);
  const edited = { ...filled[0], quantityKg: 0.2, quantityEdited: true };
  assert.equal(prefillReceiptCandidateRows([edited], [
    { foodId: 'chili', name: 'Chili', soldByWeight: true, purchasePriceRmPer100g: 4 },
  ])[0].quantityKg, 0.2);
});

test('a vetted minimum price prefills an exact weighed match for direct confirmation', () => {
  const [raw] = buildReceiptReviewRows([{ ...line('1'), qty: 1, unit: null,
    match_basis: 'CANONICAL_EXACT', price_rm: 3 }]);
  const [filled] = prefillReceiptCandidateRows([raw], [
    { foodId: 'chicken', name: 'Chicken', soldByWeight: true,
      purchasePriceRmPer100g: 1.5, minPurchasePriceRmPer100g: 0.24 },
  ]);
  assert.equal(filled.foodId, 'chicken');
  assert.deepEqual(initialSelectedReceiptRowIds([filled]), ['1']);
  assert.deepEqual([filled.quantityKg, filled.quantityUnit], [1.3, 'kg']);
  assert.equal(filled.quantityPriceEstimated, true);
  const { confirmation, invalidLineIds } = prepareReceiptConfirmation([filled], new Set(['1']));
  assert.deepEqual(invalidLineIds, []);
  assert.deepEqual(confirmation.lines[0], {
    line_id: '1', canonical_food_id: 'chicken', qty: 1.3, unit: 'kg', price_rm: 3,
  });
});

test('RM 2.47 pineapple at RM 0.20 per 100g rounds 1.235 kg upward to 1.3 kg', () => {
  const [raw] = buildReceiptReviewRows([{ ...line('1', null), name_raw: 'PINEAPPLE',
    qty: 1, unit: null, price_rm: 2.47,
    candidates: [{ canonical_food_id: 'pineapple', score: 0.9 }] }]);
  const catalog = [{ foodId: 'pineapple', name: 'Pineapple', soldByWeight: true,
    purchasePriceRmPer100g: 0.5, minPurchasePriceRmPer100g: 0.2 }];
  const [filled] = prefillReceiptCandidateRows([raw], catalog);
  assert.deepEqual([filled.quantityKg, filled.quantityUnit], [1.3, 'kg']);
  assert.equal(filled.quantityPriceEstimated, true);
  assert.deepEqual(initialSelectedReceiptRowIds([filled]), []);
  assert.equal(prepareReceiptConfirmation([filled], new Set()).confirmation.lines[0].canonical_food_id, null);
  assert.deepEqual(prepareReceiptConfirmation([filled], new Set(['1'])).invalidLineIds, []);
  const [repriced] = prefillReceiptCandidateRows([{ ...filled, price: 2.4 }], catalog);
  assert.equal(repriced.quantityKg, 1.2);
  const [edited] = prefillReceiptCandidateRows([{ ...filled, quantityKg: 0.8,
    quantityEdited: true }], catalog);
  assert.equal(edited.quantityKg, 0.8);
  const [changedFood] = replaceReceiptRowFood([filled], '1', {
    foodId: 'other-fruit', name: 'Other fruit', soldByWeight: true,
    minPurchasePriceRmPer100g: 0.5,
  });
  assert.deepEqual([changedFood.quantityKg, changedFood.quantityUnit], [0.5, 'kg']);
});

test('price estimation fails closed for absent, zero or invalid minimum rates', () => {
  const [raw] = buildReceiptReviewRows([{ ...line('1', null), qty: 1, unit: null,
    price_rm: 2, candidates: [{ canonical_food_id: 'fruit', score: 0.9 }] }]);
  for (const rate of [undefined, null, 0, -1, Number.NaN, Number.POSITIVE_INFINITY]) {
    const [filled] = prefillReceiptCandidateRows([raw], [{ foodId: 'fruit', name: 'Fruit',
      soldByWeight: true, minPurchasePriceRmPer100g: rate }]);
    assert.deepEqual([filled.quantityKg, filled.quantityUnit], [null, null]);
  }
  const [free] = prefillReceiptCandidateRows([{ ...raw, price: 0 }], [{ foodId: 'fruit', name: 'Fruit',
    soldByWeight: true, minPurchasePriceRmPer100g: 0.2 }]);
  assert.equal(free.quantityKg, null);
});

test('rece3 sprouts and bread get editable rough amounts without invented prices or auto-selection', () => {
  const raw = buildReceiptReviewRows([
    { ...line('1', null), name_raw: 'BEAN SPROUT CLEANED', qty: 1, unit: null,
      price_rm: 0.77, candidates: [{ canonical_food_id: 'SF076', score: 0.9 }] },
    { ...line('2', null), name_raw: 'SOMERSET COTTAGE', qty: 1, unit: null,
      price_rm: 4.45, candidates: [{ canonical_food_id: 'SF160', score: 0.9 }] },
  ]);
  const catalog = [
    { foodId: 'SF076', name: 'bean sprouts', soldByWeight: true,
      quantityG: 500, minPurchasePriceRmPer100g: null },
    { foodId: 'SF160', name: 'sliced bread', soldByWeight: false,
      quantityG: 400, minPurchasePriceRmPer100g: null },
  ];
  const filled = prefillReceiptCandidateRows(raw, catalog);
  assert.deepEqual(filled.map((r) => r.quantityKg), [0.2, 0.4]);
  assert.ok(filled.every((r) => r.quantityUnit === 'kg' && r.quantityEstimated && r.quantityHeuristicEstimated));
  assert.ok(filled.every((r) => !r.quantityPriceEstimated));
  assert.deepEqual(initialSelectedReceiptRowIds(filled), []);
  assert.deepEqual(filled.map((r) => r.price), [0.77, 4.45]);
  const payload = prepareReceiptConfirmation(filled, new Set(['1', '2']));
  assert.deepEqual(payload.invalidLineIds, []);
  assert.deepEqual(payload.confirmation.lines.map((r) => r.qty), [0.2, 0.4]);
  assert.deepEqual(prefillReceiptCandidateRows(filled, catalog), filled);
  const [edited] = prefillReceiptCandidateRows([{ ...filled[0], quantityKg: 0.35, quantityEdited: true }], catalog);
  assert.equal(edited.quantityKg, 0.35);

  // If a vetted rate becomes available, use that instead of the rough default.
  const [priced] = prefillReceiptCandidateRows([filled[0]], [{ ...catalog[0], minPurchasePriceRmPer100g: 0.2 }]);
  assert.equal(priced.quantityKg, 0.4);
  assert.equal(priced.quantityPriceEstimated, true);
  assert.equal(priced.quantityHeuristicEstimated, false);
  const [different] = replaceReceiptRowFood(filled, '1', { foodId: 'SF079', name: 'unknown veg' });
  assert.equal(different.quantityKg, null);
  assert.equal(different.quantityHeuristicEstimated, false);
});

test('rough defaults preserve explicit receipt amounts and respect purchase counts', () => {
  const catalog = [{ foodId: 'SF160', name: 'sliced bread', soldByWeight: false }];
  const makeBread = (overrides) => buildReceiptReviewRows([{
    ...line('1', null), name_raw: 'SOMERSET COTTAGE', qty: 1, unit: null, price_rm: 4.45,
    candidates: [{ canonical_food_id: 'SF160', score: 0.9 }], ...overrides,
  }]);
  assert.equal(prefillReceiptCandidateRows(makeBread({ qty: 2 }), catalog)[0].quantityKg, 0.8);
  const printed = prefillReceiptCandidateRows(makeBread({ name_raw: 'SOMERSET COTTAGE 600G' }), catalog)[0];
  assert.equal(printed.quantityKg, 0.6);
  assert.ok(!printed.quantityHeuristicEstimated);
  const explicit = prefillReceiptCandidateRows(makeBread({ qty: 500, unit: 'g' }), catalog)[0];
  assert.deepEqual([explicit.quantityKg, explicit.quantityUnit], [500, 'g']);
  const packs = prefillReceiptCandidateRows(makeBread({ qty: 2, unit: 'pack' }), catalog)[0];
  assert.deepEqual([packs.quantityKg, packs.quantityUnit], [2, 'pack']);
  for (const price_rm of [null, 0, -1, Number.NaN]) {
    assert.equal(prefillReceiptCandidateRows(makeBread({ price_rm }), catalog)[0].quantityKg, null);
  }
  const manual = { ...makeBread({})[0], lineId: null };
  assert.equal(prefillReceiptCandidateRows([manual], catalog)[0].quantityKg, null);
});

test('manual add starts without an invented quantity and switching food clears incompatible OCR unit', () => {
  assert.deepEqual(defaultReceiptManualQuantity({ foodId: 'egg', name: 'Egg',
    soldByWeight: false, subtitle: '10 biji', quantityG: 580 }),
  { quantityKg: null, quantityUnit: null });
  assert.deepEqual(defaultReceiptManualQuantity({ foodId: 'rice', name: 'Rice',
    soldByWeight: false, quantityG: 1000 }),
  { quantityKg: null, quantityUnit: null });
  assert.deepEqual(defaultReceiptManualQuantity({ foodId: 'chili', name: 'Chili',
    soldByWeight: true, quantityG: 250 }),
  { quantityKg: null, quantityUnit: null });
  const [row] = buildReceiptReviewRows([{ ...line('1'), match_basis: 'CANONICAL_EXACT' }]);
  const [changed] = replaceReceiptRowFood([row], '1', {
    foodId: 'egg', name: 'Egg', imageSource: null, soldByWeight: false,
    purchasePriceRmPer100g: 1.5, quantityG: 580, subtitle: '10 biji',
  });
  assert.deepEqual([changed.quantityKg, changed.quantityUnit], [null, null]);
});

test('printed egg carton count wins over a stale catalogue unit price', () => {
  const rows = buildReceiptReviewRows([
    { ...line('1', null), name_raw: 'FARM TABLE EGG A30S', qty: 1, unit: null, price_rm: 9.29,
      candidates: [{ canonical_food_id: 'egg', score: 0.8 }] },
    { ...line('2', null), name_raw: "QL FRESH EGGS 30'S GRADE (C)", qty: 1, unit: null, price_rm: 12.30,
      candidates: [{ canonical_food_id: 'egg', score: 0.8 }] },
  ]);
  const filled = prefillReceiptCandidateRows(rows, [
    { foodId: 'egg', name: 'Eggs', soldByWeight: false, purchasePriceRmPer100g: 0.84,
      quantityG: 580, subtitle: '10 biji' },
  ]);
  assert.deepEqual(filled.map((row) => [row.quantityKg, row.quantityUnit]),
    [[30, 'pcs'], [30, 'pcs']]);
});

test('printed pack mass and count produce useful kg stock for loose vegetables', () => {
  const [row] = buildReceiptReviewRows([{ ...line('1', null),
    name_raw: 'DL KANGKUNG 300G', qty: 2, unit: 'pkt', price_rm: 9,
    candidates: [{ canonical_food_id: 'kangkung', score: 0.8 }] }]);
  const [filled] = prefillReceiptCandidateRows([row], [
    { foodId: 'kangkung', name: 'Kangkung', soldByWeight: true,
      purchasePriceRmPer100g: 2, quantityG: 250 },
  ]);
  assert.deepEqual([filled.quantityKg, filled.quantityUnit], [0.6, 'kg']);
  assert.equal(filled.quantityEstimated, true);
});

test('a price cannot override an explicit OCR amount', () => {
  const [raw] = buildReceiptReviewRows([{ ...line('1', null), qty: 1, unit: 'KG', price_rm: 1.01,
    candidates: [{ canonical_food_id: 'chili', score: 0.9 }] }]);
  const [filled] = prefillReceiptCandidateRows([raw], [
    { foodId: 'chili', name: 'Red chili', soldByWeight: true, purchasePriceRmPer100g: 1.5 },
  ]);
  assert.deepEqual([filled.quantityKg, filled.quantityUnit], [1, 'KG']);
  assert.equal(filled.quantityEstimated, undefined);
});

test('a selected food with unknown amount must be completed before confirmation', () => {
  const [row] = buildReceiptReviewRows([{ ...line('1', null), qty: 1, unit: null,
    candidates: [{ canonical_food_id: 'sprouts', score: 0.8 }] }]);
  const [filled] = prefillReceiptCandidateRows([row], [{ foodId: 'sprouts', name: 'Bean sprouts' }]);
  assert.deepEqual([filled.quantityKg, filled.quantityUnit], [null, null]);
  const { confirmation, invalidLineIds } = prepareReceiptConfirmation([filled], new Set([filled.id]));
  assert.deepEqual(invalidLineIds, [filled.id]);
  assert.deepEqual([confirmation.lines[0].qty, confirmation.lines[0].unit], [null, null]);
  assert.equal(confirmation.lines[0].canonical_food_id, 'sprouts');
  const completed = prepareReceiptConfirmation([
    { ...filled, quantityKg: 0.25, quantityUnit: 'kg', quantityEdited: true },
  ], new Set([filled.id]));
  assert.deepEqual(completed.invalidLineIds, []);
});

test('an incomplete user edit is explained before POST, but unchecked rows never block confirmation', () => {
  const rows = buildReceiptReviewRows([
    { ...line('1'), qty: 1, unit: null },
    { ...line('2'), qty: 1, unit: 'kg' },
  ]);
  const edited = { ...rows[0], quantityKg: 2, quantityEdited: true };
  const selected = prepareReceiptConfirmation([edited, rows[1]], new Set(['1']));
  assert.deepEqual(selected.invalidLineIds, ['1']);
  const unchecked = prepareReceiptConfirmation([edited, rows[1]], new Set(['2']));
  assert.deepEqual(unchecked.invalidLineIds, []);
  assert.deepEqual([unchecked.confirmation.lines[0].qty, unchecked.confirmation.lines[0].unit], [null, null]);
});

test('compact printed G/GM masses survive unmatched review without inventing a food', () => {
  const names = ['HORLICKS32GM', 'BUSTANI THINFILLED ASST500GM', 'PRODUCT100G', 'PRODUCT 32.5GM', 'PRODUCT 0,5KG'];
  const rows = buildReceiptReviewRows(names.map((name_raw, index) => ({
    ...line(String(index + 1), null), name_raw, qty: 1, unit: null,
  })));
  assert.deepEqual(rows.map((row) => [row.quantityKg, row.quantityUnit]),
    [[0.032, 'kg'], [0.5, 'kg'], [0.1, 'kg'], [0.0325, 'kg'], [0.5, 'kg']]);
  assert.ok(rows.every((row) => row.foodId === null && row.name === 'Cannot be matched'));
  assert.deepEqual(initialSelectedReceiptRowIds(rows), []);
  // The existing purchase and its printed amount survive explicit category selection.
  const selected = replaceReceiptRowFood(rows, '2', { foodId: 'chocolate', name: 'Chocolate confectionery', soldByWeight: false });
  assert.equal(selected[1].quantityKg, 0.5);
});

test('compound packs require evidence for a total and never blindly multiply inner packs', () => {
  const names = ['NISSIN CHICKEN RAMEN5PX425G', 'OTHER NOODLES 5PX425G',
    'PRODUCT 5X85G', 'PRODUCT 85G X5', 'PRODUCT 5 PACK X 425G', 'PRODUCT 100G + 50G',
    'PRODUCT 100G*2', 'NISSIN CHICKEN RAMEN5PX425G *2'];
  const rows = buildReceiptReviewRows(names.map((name_raw, index) => ({
    ...line(String(index + 1), null), name_raw, qty: 1, unit: null,
  })));
  assert.deepEqual(rows.map((row) => row.quantityKg), [0.425, null, null, null, null, null, null, null]);
  assert.deepEqual(initialSelectedReceiptRowIds(rows), []);
});

test('ordinary terminal *1 receipt annotations keep their printed package mass', () => {
  const names = ['ARNOTTS LEMON CRISP250G *1', 'LINDT100G*1', 'OTHER NOODLES 5PX425G *1'];
  const rows = buildReceiptReviewRows(names.map((name_raw, index) => ({
    ...line(String(index + 1), null), name_raw, qty: 1, unit: null,
  })));
  assert.deepEqual(rows.map((row) => row.quantityKg), [0.25, 0.1, null]);
  assert.deepEqual(initialSelectedReceiptRowIds(rows), []);
});

test('per-kg price and numeric product-code suffixes are not package weights', () => {
  const names = ['CHILI RM 8.00/KG', 'CHILI 1KG @ RM8.00', 'CHILI @1KG', 'PRODUCT1234567890123G', 'PRODUCT 100GRAM'];
  const rows = buildReceiptReviewRows(names.map((name_raw, index) => ({
    ...line(String(index + 1), null), name_raw, qty: 1, unit: null,
  })));
  assert.ok(rows.every((row) => row.quantityKg === null && row.printedPackageG === null));
});

test('explicit OCR mass, user edits and confirmed quantities win over printed package mass', () => {
  const rows = buildReceiptReviewRows([
    { ...line('1'), name_raw: 'PRODUCT32GM', qty: 1, unit: 'kg', match_basis: 'CANONICAL_EXACT' },
    { ...line('2'), name_raw: 'PRODUCT32GM', qty: 32, unit: 'GM', match_basis: 'CANONICAL_EXACT' },
    { ...line('3'), name_raw: 'PRODUCT32GM', qty: 2, unit: 'pack', status: 'CONFIRMED' },
  ]);
  const filled = prefillReceiptCandidateRows(rows, [{ foodId: 'chicken', name: 'Chicken' }]);
  assert.deepEqual(filled.map((row) => [row.quantityKg, row.quantityUnit]), [[1, 'kg'], [32, 'g'], [2, 'pack']]);
  const edited = { ...rows[0], quantityKg: 0.75, quantityUnit: 'kg', quantityEdited: true };
  assert.equal(replaceReceiptRowFood([edited], '1', { foodId: 'new', name: 'New', soldByWeight: false })[0].quantityKg, 0.75);
  assert.equal(replaceReceiptRowFood([rows[2]], '3', { foodId: 'new', name: 'New' })[0], rows[2]);
});

test('four repeated Cadbury purchases keep four individual printed masses', () => {
  const rows = buildReceiptReviewRows(Array.from({ length: 4 }, (_, index) => ({
    ...line(String(index + 1), null), name_raw: 'CADBURY CHOCOLATE 180G', qty: 1, unit: null,
  })));
  assert.equal(rows.length, 4);
  assert.deepEqual(rows.map((row) => row.quantityKg), [0.18, 0.18, 0.18, 0.18]);
});

test('all printed prefills remain editable through refresh, food replacement and confirmation', () => {
  for (const name_raw of ['NISSIN CHICKEN RAMEN5PX425G *1', 'BUSTANI THINFILLED ASST500GM']) {
    const [row] = buildReceiptReviewRows([{ ...line('1', null), name_raw, qty: 1, unit: null,
      candidates: [{ canonical_food_id: 'food', score: 0.9 }] }]);
    assert.ok(row.quantityKg > 0);
    const [suggested] = prefillReceiptCandidateRows([row], [{ foodId: 'food', name: 'Food' }]);
    const edited = { ...suggested, quantityKg: 3, quantityUnit: 'pack', price: 7.25, quantityEdited: true };
    const refreshed = prefillReceiptCandidateRows([edited], [{ foodId: 'food', name: 'Food' }]);
    assert.deepEqual(initialSelectedReceiptRowIds(refreshed), []);
    const replaced = replaceReceiptRowFood(refreshed, '1', { foodId: 'other', name: 'Other', soldByWeight: true });
    const { confirmation, invalidLineIds } = prepareReceiptConfirmation(replaced, new Set(['1']));
    assert.deepEqual(invalidLineIds, []);
    assert.deepEqual(confirmation.lines[0], { line_id: '1', canonical_food_id: 'other', qty: 3, unit: 'pack', price_rm: 7.25 });
  }
});

test('printed juice volumes survive matching and remain editable without a food assumption', () => {
  const [row] = buildReceiptReviewRows([{ ...line('1', null), name_raw: 'PEEL FRESH ORANGE 2L', qty: 1, unit: null,
    candidates: [{ canonical_food_id: 'juice', score: 0.9 }] }]);
  assert.deepEqual([row.quantityKg, row.quantityUnit], [2, 'L']);
  const [filled] = prefillReceiptCandidateRows([row], [{ foodId: 'juice', name: 'Fruit juice drink' }]);
  assert.deepEqual([filled.quantityKg, filled.quantityUnit], [2, 'L']);
  assert.deepEqual(initialSelectedReceiptRowIds([filled]), []);
  const changed = replaceReceiptRowFood([{ ...filled, quantityKg: 0.75, quantityUnit: 'L', quantityEdited: true }],
    '1', { foodId: 'other', name: 'Other', soldByWeight: true });
  assert.deepEqual([changed[0].quantityKg, changed[0].quantityUnit], [0.75, 'L']);
});

test('unknown backend-grounded chilli and real weighed chicken remain distinct', () => {
  const rows = buildReceiptReviewRows([
    { ...line('1', null), name_raw: 'RED CHILLI KG', qty: null, unit: null, price_rm: 1.01 },
    { ...line('2', null), name_raw: 'ABF CHICKEN DRUMSTIC', qty: 0.556, unit: 'kg' },
    { ...line('3', null), name_raw: 'ABF CHICKEN DRUMSTIC', qty: 0.516, unit: 'kg' },
    { ...line('4', null), name_raw: 'JUICE250ML', qty: 2, unit: 'pack' },
  ]);
  assert.deepEqual(rows.map((row) => [row.quantityKg, row.quantityUnit]),
    [[null, null], [0.556, 'kg'], [0.516, 'kg'], [0.5, 'L']]);
});
