import type { ReceiptLine } from './receiptApi';
import type { ReceiptConfirmation } from './receiptApi';
import type { ReceiptReviewLine } from '../screens/ReceiptReviewScreen';

type ReferencePricedFood = {
  foodId: string;
  name: string;
  imageSource?: ReceiptReviewLine['imageSource'];
  purchasePriceRmPer100g?: number | null;
  minPurchasePriceRmPer100g?: number | null;
  soldByWeight?: boolean;
  quantityG?: number;
  subtitle?: string;
};

/** A manually added purchase has no trustworthy receipt quantity. */
export function defaultReceiptManualQuantity(food: ReferencePricedFood):
  Pick<ReceiptReviewLine, 'quantityKg' | 'quantityUnit'> {
  // The catalogue describes a product, not what this household bought.
  // A manually added line has no receipt quantity evidence.
  void food;
  return { quantityKg: null, quantityUnit: null };
}

const VALID_RECEIPT_UNITS = new Set([
  'g', 'gram', 'grams', 'kg', 'kilogram', 'kilograms',
  'ml', 'millilitre', 'milliliter', 'l', 'litre', 'liter',
  'pc', 'pcs', 'piece', 'pieces', 'biji', 'unit',
  'pack', 'packet', 'pkt',
]);

/** Unit choices offered by the review-screen dropdown. Every option must stay
 * inside VALID_RECEIPT_UNITS and the backend UNIT_ALIASES canonical set. */
export const RECEIPT_UNIT_OPTIONS = ['kg', 'g', 'L', 'ml', 'pcs', 'pack'] as const;

function printedEggCount(label: string): number | null {
  if (!/\b(?:eggs?|telur)\b/i.test(label)) return null;
  const match = /(?:^|[^A-Z0-9])(?:[A-D])?(\d{1,2})\s*(?:'?S|PCS?|BIJI)\b/i.exec(label);
  const count = match ? Number(match[1]) : 0;
  return count >= 4 && count <= 60 ? count : null;
}

function printedPackageMeasure(receiptLabel: string): { quantity: number; unit: 'kg' | 'L' } | null {
  // A terminal *1 adds no ambiguity or multiplier (common retailer syntax).
  // Other *counts still require review: inner packs vs purchases is unclear.
  const label = receiptLabel.replace(/\s*\*+\s*1\s*$/, '');
  // NxM may print either the total pack mass or each inner pack's mass.
  // Only this reviewed product has evidence for a total: Nissin JAN
  // 4902105051108, https://www.nissin.com/jp/product/items/13426/ (425g/5 servings).
  const verifiedTotal = /^(?:\d{7,}\s+)?NISSIN\s+CHICKEN\s+RAMEN\s*5\s*P\s*X\s*425\s*G\s*$/i.test(label.trim());
  if (!verifiedTotal && /\d\s*(?:P(?:ACKS?)?\s*)?[X×*]\s*\d|(?:KG|GM|G|ML|L)\s*[X×*]\s*\d/i.test(label)) return null;
  // Price-rate annotations are not purchased mass. Compact product100G is
  // allowed, but never take a numeric suffix of a barcode/decimal.
  if (/(?:\/|\bPER\b|@)\s*(?:\d+(?:[.,]\d+)?\s*)?(?:KG|GM|G|ML|L)\b|\b\d+(?:[.,]\d+)?\s*(?:KG|GM|G|ML|L)\s*(?:@|\/|PER\b)/i.test(label)) return null;
  const matches = [...label.matchAll(/(?<![\d.,])(\d+(?:[.,]\d+)?)\s*(KG|GM|G|ML|L)\b/gi)];
  if (matches.length !== 1) return null;
  const match = matches[0];
  const printedUnit = match[2].toLowerCase();
  const quantity = Number(match[1].replace(',', '.')) / (['g', 'gm', 'ml'].includes(printedUnit) ? 1000 : 1);
  return Number.isFinite(quantity) && quantity >= 0.005 && quantity <= 20
    ? { quantity, unit: ['l', 'ml'].includes(printedUnit) ? 'L' : 'kg' } : null;
}

// User-approved rough receipt defaults (2026-09-30), NOT observed weights or
// invented market prices. Sprouts use a modest 200 g purchase assumption;
// sliced bread uses the catalogue's 400 g reference loaf. Keep this allowlist
// narrow: do not extrapolate a generic pack weight to unrelated foods.
const ROUGH_RECEIPT_GRAMS: Readonly<Record<string, number>> = {
  SF076: 200,
  SF160: 400,
};

/** Printed amounts take priority, then vetted minimum prices, then explicitly
 * approved rough defaults. All non-printed estimates remain editable. */
function referenceQuantity(line: ReceiptReviewLine, food: ReferencePricedFood):
  Pick<ReceiptReviewLine, 'quantityKg' | 'quantityUnit' | 'quantityEstimated' | 'quantityPriceEstimated' | 'quantityHeuristicEstimated'> | null {
  if (line.printedPackCount && /\b(?:eggs?|telur)\b/i.test(food.name)) {
    return { quantityKg: line.printedPackCount, quantityUnit: 'pcs', quantityEstimated: true };
  }
  // A printed 300G with "2 pkt" is stronger evidence than a stale average
  // catalogue price. Keep the original count separately from displayed stock.
  if (line.printedPackageG && !/^(?:\d+(?:[.,]\d+)?)\s*(?:biji|pcs?|pieces?|units?)\b/i.test(food.subtitle?.trim() ?? '')) {
    const unit = line.quantityUnit?.trim().toLowerCase();
    if (!unit || ['pc', 'pcs', 'piece', 'pieces', 'biji', 'unit', 'pack', 'packet', 'pkt'].includes(unit)) {
      const count = line.purchaseCountHint ?? 1;
      return { quantityKg: Math.round(line.printedPackageG * count * 1000) / 1_000_000,
        quantityUnit: 'kg', quantityEstimated: true };
    }
  }
  const rate = food.minPurchasePriceRmPer100g;
  const price = line.price;
  if (food.soldByWeight === true && typeof rate === 'number' && Number.isFinite(rate) && rate > 0 &&
      typeof price === 'number' && Number.isFinite(price) && price > 0) {
    const hundredGramUnits = price / rate;
    // Each unit is 100 g. The small epsilon avoids binary-float noise
    // turning an exact 1.2 kg result into 1.3 kg.
    if (Number.isFinite(hundredGramUnits) && hundredGramUnits <= 1000) {
      return { quantityKg: Math.ceil(hundredGramUnits - 1e-9) / 10,
        quantityUnit: 'kg', quantityEstimated: true, quantityPriceEstimated: true };
    }
  }
  const roughGrams = ROUGH_RECEIPT_GRAMS[food.foodId];
  if (roughGrams && typeof line.lineId === 'string' &&
      typeof price === 'number' && Number.isFinite(price) && price > 0) {
    const hint = line.purchaseCountHint;
    const count = typeof hint === 'number' && Number.isInteger(hint) && hint >= 1 && hint <= 20 ? hint : 1;
    return { quantityKg: roughGrams * count / 1000, quantityUnit: 'kg',
      quantityEstimated: true, quantityHeuristicEstimated: true };
  }
  return null;
}

function withReferenceQuantity(line: ReceiptReviewLine, food: ReferencePricedFood): ReceiptReviewLine {
  if (line.quantityEdited || line.reviewStatus === 'CONFIRMED') return line;
  // A label-only mass is useful even while the food is unmatched. Selecting
  // a catalogue category must not erase that independently printed evidence.
  if (line.quantityEstimated && ((line.printedPackageG && line.quantityUnit === 'kg') || line.quantityUnit === 'L')) return line;
  const estimate = referenceQuantity(line, food);
  if (line.quantityKg !== null && !line.quantityEstimated) {
    const rawUnit = line.quantityUnit?.trim().toLowerCase();
    // "2 pkt" + printed "300G" means 600g, not two kg. Otherwise
    // An explicit mass always wins over a package-label fallback.
    const printedCountWithMass = line.printedPackageG !== null && line.printedPackageG !== undefined &&
      estimate?.quantityUnit === 'kg' &&
      ['pc', 'pcs', 'piece', 'pieces', 'biji', 'unit', 'pack', 'packet', 'pkt'].includes(rawUnit ?? '');
    if (!printedCountWithMass) return line;
  }
  return {
    ...line,
    quantityKg: estimate?.quantityKg ?? null,
    quantityUnit: estimate?.quantityUnit ?? null,
    quantityEstimated: estimate !== null,
    quantityPriceEstimated: estimate?.quantityPriceEstimated === true,
    quantityHeuristicEstimated: estimate?.quantityHeuristicEstimated === true,
  };
}

/** Matching changes a row's food, never its identity or the number of purchases. */
export function buildReceiptReviewRows(lines: readonly ReceiptLine[]): ReceiptReviewLine[] {
  return lines.map((line) => {
    const printedMeasure = printedPackageMeasure(line.name_raw);
    const printedPackageG = printedMeasure?.unit === 'kg' ? printedMeasure.quantity * 1000 : null;
    const purchaseCountHint = line.qty !== null && Number.isInteger(line.qty) && line.qty >= 1 && line.qty <= 20
      ? line.qty : null;
    const rawUnit = line.unit?.trim().toLowerCase();
    const packageQuantity = line.status !== 'CONFIRMED' && printedMeasure !== null &&
      (!rawUnit || ['pack', 'packet', 'pkt', 'pc', 'pcs', 'piece', 'pieces', 'unit'].includes(rawUnit))
      ? Math.round(printedMeasure.quantity * (purchaseCountHint ?? 1) * 1_000_000) / 1_000_000 : null;
    return {
      id: line.line_id,
      lineId: line.line_id,
      clientLineId: line.client_line_id ?? null,
      reviewStatus: line.status,
      foodId: (
        line.status === 'CONFIRMED' ||
        line.match_basis === 'CANONICAL_EXACT' ||
        line.match_basis === 'RETAILER_ALIAS_EXACT'
      ) ? (line.proposed_food?.canonical_food_id ?? null) : null,
      name: line.proposed_food?.name ?? 'Cannot be matched',
      price: line.price_rm,
      // A bare OCR count such as "1" with no unit is not a usable stock amount.
      // It must not make the whole confirmation fail validation.
      quantityKg: packageQuantity ?? (line.qty !== null && line.unit?.trim() ? line.qty : null),
      quantityUnit: packageQuantity !== null ? printedMeasure?.unit ?? null
        : line.qty !== null && line.unit?.trim() ? (rawUnit === 'gm' ? 'g' : line.unit) : null,
      ...(packageQuantity !== null ? { quantityEstimated: true } : {}),
      rawName: undefined,
      printedPackCount: printedEggCount(line.name_raw),
      printedPackageG,
      purchaseCountHint,
      suggestedOnly: line.status === 'SKIPPED' || !(
        line.status === 'CONFIRMED' ||
        line.match_basis === 'CANONICAL_EXACT' ||
        line.match_basis === 'RETAILER_ALIAS_EXACT'
      ),
      candidateFoodIds: [...line.candidates]
        .sort((left, right) => right.score - left.score)
        .map((candidate) => candidate.canonical_food_id),
    };
  });
}

/** Resolve catalogue entries in descending match-score order, not catalogue display order. */
export function rankedReceiptCandidateEntries<T extends { foodId: string }>(
  catalog: readonly T[],
  candidateFoodIds: readonly string[],
): T[] {
  const byFoodId = new Map(catalog.map((entry) => [entry.foodId, entry]));
  const seen = new Set<string>();
  const ranked: T[] = [];
  for (const foodId of candidateFoodIds) {
    if (seen.has(foodId)) continue;
    seen.add(foodId);
    const entry = byFoodId.get(foodId);
    if (entry) ranked.push(entry);
  }
  return ranked;
}

/** Only an exact/previously confirmed match is included before user review. */
export function initialSelectedReceiptRowIds(lines: readonly ReceiptReviewLine[]): string[] {
  return lines.filter((line) => (
    line.foodId !== null && !line.suggestedOnly && line.reviewStatus !== 'SKIPPED'
  )).map((line) => line.id);
}

/** Confirmed stock cannot be undone or remapped through receipt review. */
export function isLockedConfirmedReceiptRow(line: ReceiptReviewLine): boolean {
  return line.reviewStatus === 'CONFIRMED';
}

/** The payload must not turn a visible suggestion into an accepted food. */
export function confirmedReceiptFoodId(
  line: ReceiptReviewLine, selectedIds: ReadonlySet<string>,
): string | null {
  if (isLockedConfirmedReceiptRow(line)) return line.foodId;
  return selectedIds.has(line.id) ? line.foodId : null;
}

/** Show the highest-ranked food as an initial value, without selecting it.
 *
 * ReceiptReviewScreen keeps its separate selectedIds set unchanged. An
 * untouched model candidate therefore remains excluded from confirmation;
 * the user must tick its checkbox or explicitly pick another food.
 */
export function prefillReceiptCandidateRows<T extends ReferencePricedFood>(
  lines: readonly ReceiptReviewLine[], catalog: readonly T[],
): ReceiptReviewLine[] {
  let changed = false;
  const filled = lines.map((line) => {
    // An exact match is already selected, but its OCR amount may still be a
    // bare count with no unit. Fill only the editable amount; never change
    // its food or the user's confirmation state.
    if (!line.suggestedOnly && line.foodId !== null) {
      if (line.reviewStatus === 'CONFIRMED') return line;
      const matchingFood = catalog.find((entry) => entry.foodId === line.foodId);
      if (!matchingFood) return line;
      const filled = withReferenceQuantity(line, matchingFood);
      if (filled.quantityKg === line.quantityKg && filled.quantityUnit === line.quantityUnit &&
          Boolean(filled.quantityEstimated) === Boolean(line.quantityEstimated) &&
          Boolean(filled.quantityPriceEstimated) === Boolean(line.quantityPriceEstimated) &&
          Boolean(filled.quantityHeuristicEstimated) === Boolean(line.quantityHeuristicEstimated)) return line;
      changed = true;
      return filled;
    }
    // A provisional Top-2 match may be visible while the full (hidden-food)
    // catalogue is still loading. Re-rank only untouched suggestions when it arrives.
    if (!line.candidateFoodIds?.length) return line;
    const best = rankedReceiptCandidateEntries(catalog, line.candidateFoodIds)[0];
    if (!best) return line;
    const filled = withReferenceQuantity({
      ...line, foodId: best.foodId, name: best.name,
      imageSource: best.imageSource ?? null, suggestedOnly: true,
    }, best);
    if (line.foodId === filled.foodId && line.name === filled.name &&
        line.imageSource === filled.imageSource && line.quantityKg === filled.quantityKg &&
        line.quantityUnit === filled.quantityUnit &&
        Boolean(line.quantityEstimated) === Boolean(filled.quantityEstimated) &&
        Boolean(line.quantityPriceEstimated) === Boolean(filled.quantityPriceEstimated) &&
        Boolean(line.quantityHeuristicEstimated) === Boolean(filled.quantityHeuristicEstimated)) return line;
    changed = true;
    return filled;
  });
  return changed ? filled : lines as ReceiptReviewLine[];
}

/** An explicit checkbox tap accepts the displayed candidate; catalog refreshes may not replace it. */
export function markReceiptRowReviewed(lines: readonly ReceiptReviewLine[], rowId: string): ReceiptReviewLine[] {
  let changed = false;
  const reviewed = lines.map((line) => {
    if (line.id !== rowId || !line.suggestedOnly) return line;
    changed = true;
    return { ...line, suggestedOnly: false };
  });
  return changed ? reviewed : lines as ReceiptReviewLine[];
}

export function replaceReceiptRowFood(
  lines: readonly ReceiptReviewLine[],
  rowId: string,
  food: Pick<ReceiptReviewLine, 'foodId' | 'name' | 'imageSource'> &
    Partial<Pick<ReceiptReviewLine, 'suggestedOnly'>> & Partial<ReferencePricedFood>,
): ReceiptReviewLine[] {
  return lines.map((line) => {
    if (line.id !== rowId) return line;
    if (line.reviewStatus === 'CONFIRMED') return line;
    const previousUnit = line.quantityUnit?.trim().toLowerCase();
    const incompatibleUnit = line.foodId !== food.foodId && food.soldByWeight !== undefined && (
      food.soldByWeight ? ['pc', 'pcs', 'piece', 'pieces', 'biji', 'pack', 'packet', 'pkt'].includes(previousUnit ?? '')
        : ['g', 'gram', 'grams', 'kg', 'kilogram', 'kilograms'].includes(previousUnit ?? '')
    );
    const replaced = {
      ...line,
      foodId: food.foodId, name: food.name, imageSource: food.imageSource,
      suggestedOnly: food.suggestedOnly ?? line.suggestedOnly,
      ...(incompatibleUnit && !line.quantityEdited ? {
        quantityKg: null, quantityUnit: null, quantityEdited: false, quantityEstimated: false,
        quantityPriceEstimated: false,
        quantityHeuristicEstimated: false,
      } : {}),
    };
    return withReferenceQuantity(replaced, food);
  });
}

/** Every newly accepted purchase needs an explicit positive amount and unit.
 * Unknown amounts remain visible for review but cannot enter pantry stock. */
export function prepareReceiptConfirmation(
  lines: readonly ReceiptReviewLine[], selectedIds: ReadonlySet<string>,
): { confirmation: ReceiptConfirmation; invalidLineIds: string[] } {
  const invalidLineIds: string[] = [];
  const quantityPair = (line: ReceiptReviewLine): { qty: number | null; unit: string | null } => {
    const unit = line.quantityUnit?.trim() || null;
    const qty = line.quantityKg;
    if (selectedIds.has(line.id) && !isLockedConfirmedReceiptRow(line) &&
        (qty === null || unit === null || !Number.isFinite(qty) || qty <= 0 ||
         !VALID_RECEIPT_UNITS.has(unit.toLowerCase()))) {
      invalidLineIds.push(line.id);
    }
    return qty !== null && Number.isFinite(qty) && qty > 0 && unit !== null &&
      VALID_RECEIPT_UNITS.has(unit.toLowerCase())
      ? { qty, unit }
      : { qty: null, unit: null };
  };
  return {
    confirmation: {
      lines: lines.filter((line) => line.lineId !== null).map((line) => ({
        line_id: line.lineId as string,
        canonical_food_id: confirmedReceiptFoodId(line, selectedIds),
        price_rm: line.price,
        ...(isLockedConfirmedReceiptRow(line) ? {} : quantityPair(line)),
      })),
      added_lines: lines.filter((line) => line.lineId === null && selectedIds.has(line.id) && line.foodId !== null)
        .map((line) => ({
          client_line_id: line.clientLineId ?? line.id,
          canonical_food_id: line.foodId as string,
          name_raw: line.rawName,
          price_rm: line.price,
          ...quantityPair(line),
        })),
    },
    invalidLineIds,
  };
}
