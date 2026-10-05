export const PANTRY_QUANTITY_UNITS = ['kg', 'g', 'L', 'ml', 'pcs', 'pack'] as const;

export interface PantryQuantityInput {
  quantity: number | null;
  unit: string | null;
}

/** An empty amount explicitly restores unknown stock; zero is not removal. */
export function parsePantryQuantity(value: string, unit: string): PantryQuantityInput {
  const normalized = value.trim().replace(',', '.');
  if (!normalized) return { quantity: null, unit: null };
  if (!/^\d+(?:\.\d*)?$|^\.\d+$/.test(normalized)) {
    throw new Error('Enter a positive remaining amount, or leave it blank if unknown.');
  }
  const quantity = Number(normalized);
  if (quantity === 0) throw new Error('Use Mark as eaten or Remove for an empty item.');
  if (!Number.isFinite(quantity) || quantity <= 0 || quantity > 100_000) {
    throw new Error('Enter an amount greater than 0 and no more than 100,000.');
  }
  if (!PANTRY_QUANTITY_UNITS.some((option) => option === unit)) {
    throw new Error('Choose a unit for the remaining amount.');
  }
  return { quantity, unit };
}
