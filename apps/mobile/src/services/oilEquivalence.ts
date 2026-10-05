const OIL_IDS = new Set(['SF120', 'SF121', 'SF123']);

export function oilGroup(foodId: string): string {
  return OIL_IDS.has(foodId) ? 'OIL_EQUIVALENT' : foodId;
}

export function oilRawGrams(foodId: string, quantity: number, unit: string): number | null {
  if (!OIL_IDS.has(foodId) || !Number.isFinite(quantity) || quantity <= 0) return null;
  const normalized = unit.trim().toLowerCase();
  if (normalized === 'kg') return quantity * 1000;
  if (normalized === 'g') return quantity;
  if (normalized === 'ml') return quantity * 0.92;
  if (normalized === 'l') return quantity * 920;
  return null;
}
