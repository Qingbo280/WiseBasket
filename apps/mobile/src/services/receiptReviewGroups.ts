import type { ReceiptReviewLine } from '../screens/ReceiptReviewScreen';

export type ReceiptReviewGroup = ReceiptReviewLine & { sourceRowIds: readonly string[] };

const UNITS: Record<string, [string, number]> = {
  kg: ['kg', 1], kilogram: ['kg', 1], kilograms: ['kg', 1],
  g: ['kg', 0.001], gram: ['kg', 0.001], grams: ['kg', 0.001],
  l: ['L', 1], litre: ['L', 1], liter: ['L', 1],
  ml: ['L', 0.001], millilitre: ['L', 0.001], milliliter: ['L', 0.001],
  pc: ['pcs', 1], pcs: ['pcs', 1], piece: ['pcs', 1], pieces: ['pcs', 1], biji: ['pcs', 1], unit: ['pcs', 1],
  pack: ['pack', 1], packet: ['pack', 1], pkt: ['pack', 1],
};
const round = (value: number) => Math.round(value * 1_000_000) / 1_000_000;

/** A single checkbox represents the whole displayed food, never a hidden subset.
 * If exact and suggested matches meet, require the user to accept the group;
 * do not silently accept its previously unselected candidate purchases. */
export function selectedReceiptGroupRowIds(
  lines: readonly ReceiptReviewLine[], selectedIds: ReadonlySet<string>,
): Set<string> {
  return new Set(groupReceiptReviewRows(lines)
    .filter((group) => group.sourceRowIds.every((id) => selectedIds.has(id)))
    .flatMap((group) => [...group.sourceRowIds]));
}

/** Group the displayed catalogue identity even before candidate acceptance.
 * Original purchases survive for confirmation. Locked stock stays separate. */
export function groupReceiptReviewRows(
  lines: readonly ReceiptReviewLine[],
): ReceiptReviewGroup[] {
  const groups = new Map<string, ReceiptReviewLine[]>();
  for (const line of lines) {
    // No catalogue identity means there is no supported food to review or stock.
    // Keep the raw line outside this projection so confirmation can skip it.
    if (!line.foodId) continue;
    const key = JSON.stringify([line.foodId, line.reviewStatus === 'CONFIRMED']);
    const members = groups.get(key) ?? [];
    members.push(line);
    groups.set(key, members);
  }
  return [...groups.values()].map((members) => {
    const first = members[0];
    const sourceRowIds = members.map((line) => line.id);
    if (members.length === 1) return { ...first, sourceRowIds };
    const units = members.map((line) => UNITS[line.quantityUnit?.trim().toLowerCase() ?? '']);
    const comparable = units.every((unit) => unit && unit[0] === units[0]?.[0]);
    const sameUnit = members.every((line) => line.quantityUnit === first.quantityUnit);
    const known = (comparable || sameUnit) && members.every((line) => line.quantityKg !== null && Number.isFinite(line.quantityKg));
    const quantityUnit = comparable ? (sameUnit ? first.quantityUnit : units[0][0]) : null;
    const quantityKg = known ? round(members.reduce((sum, line, index) => (
      sum + (line.quantityKg as number) * (sameUnit ? 1 : units[index][1])
    ), 0)) : null;
    const input = first.aggregateInput?.memberKey === JSON.stringify(sourceRowIds) ? first.aggregateInput : undefined;
    return {
      ...first, sourceRowIds, quantityKg, quantityUnit,
      suggestedOnly: members.some((line) => line.suggestedOnly),
      candidateFoodIds: [...new Set(members.flatMap((line) => line.candidateFoodIds ?? []))],
      price: members.every((line) => line.price !== null)
        ? Math.round(members.reduce((sum, line) => sum + (line.price as number), 0) * 100) / 100 : null,
      quantityInput: input?.quantityInput, priceInput: input?.priceInput,
      quantityEstimated: members.some((line) => line.quantityEstimated),
      quantityPriceEstimated: members.some((line) => line.quantityPriceEstimated),
      quantityHeuristicEstimated: members.some((line) => line.quantityHeuristicEstimated),
    };
  });
}

/** Allocate an edited total at DB precision; the residual prevents rounding drift. */
function splitTotal(total: number | null, weights: number[], precision: number, positive = false): (number | null)[] {
  if (total === null || !Number.isFinite(total)) return weights.map(() => null);
  const scale = 10 ** precision;
  const ticks = Math.round(total * scale);
  const minimum = positive && ticks >= weights.length ? 1 : 0;
  const distributable = ticks - minimum * weights.length;
  const sum = weights.reduce((value, weight) => value + Math.max(0, weight), 0);
  let left = ticks;
  return weights.map((weight, index) => {
    const share = index === weights.length - 1 ? left
      : minimum + Math.floor(distributable * (sum > 0 ? Math.max(0, weight) / sum : 1 / weights.length));
    left -= share;
    return share / scale;
  });
}

export function updateReceiptReviewGroup(
  lines: readonly ReceiptReviewLine[], group: ReceiptReviewGroup, patch: Partial<ReceiptReviewLine>,
): ReceiptReviewLine[] {
  const ids = new Set(group.sourceRowIds);
  const members = lines.filter((line) => ids.has(line.id));
  if (members.length === 1) return lines.map((line) => ids.has(line.id) ? { ...line, ...patch } : line);
  const editsQuantity = 'quantityKg' in patch || 'quantityUnit' in patch;
  const unit = 'quantityUnit' in patch ? patch.quantityUnit : group.quantityUnit;
  const total = 'quantityKg' in patch ? patch.quantityKg : group.quantityKg;
  const weights = members.map((line) => {
    const source = UNITS[line.quantityUnit?.trim().toLowerCase() ?? ''];
    return source && line.quantityKg !== null ? line.quantityKg * source[1] : 0;
  });
  const quantities = splitTotal(total ?? null, weights, 3, true);
  const prices = splitTotal(patch.price ?? null, members.map((line) => line.price ?? 0), 2);
  const memberKey = JSON.stringify(group.sourceRowIds);
  const oldInput = members[0].aggregateInput?.memberKey === memberKey ? members[0].aggregateInput : {};
  const aggregateInput = {
    ...oldInput, memberKey,
    ...('quantityInput' in patch ? { quantityInput: patch.quantityInput } : {}),
    ...('priceInput' in patch ? { priceInput: patch.priceInput } : {}),
  };
  return lines.map((line) => {
    if (!ids.has(line.id)) return line;
    const index = members.indexOf(line);
    return {
      ...line, ...patch,
      quantityInput: undefined, priceInput: undefined,
      ...(editsQuantity ? { quantityKg: quantities[index], quantityUnit: unit ?? null } : {}),
      ...('price' in patch ? { price: prices[index] } : {}),
      aggregateInput: index === 0 ? aggregateInput : undefined,
    };
  });
}
