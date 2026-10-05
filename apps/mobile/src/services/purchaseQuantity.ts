/** Render a priced purchase in the catalogue's selling unit when its pack mass matches. */
export function purchaseQuantity(
  purchaseKg: number,
  purchaseUnits: number | undefined,
  food?: { pack_grams?: number | null; pack_label?: string },
): { quantity: number; unit: string; packLabel: string; displayQuantity: string } {
  const units = purchaseUnits && purchaseUnits > 0 ? purchaseUnits : 1;
  const gramsPerUnit = (purchaseKg * 1000) / units;
  const catalogueMassMatches = food?.pack_grams != null
    && food.pack_grams > 0
    && Math.abs(food.pack_grams - gramsPerUnit) <= Math.max(1, food.pack_grams * 0.01);
  const packLabel = catalogueMassMatches && food?.pack_label?.trim()
    ? food.pack_label.trim()
    : gramsPerUnit >= 1000 && Number.isInteger(gramsPerUnit / 1000)
      ? `${gramsPerUnit / 1000} kg`
      : `${Math.round(gramsPerUnit * 100) / 100} g`;
  const tray = /^tray of (\d+)$/i.exec(packLabel);
  if (tray) {
    const quantity = Number(tray[1]) * units;
    return { quantity, unit: 'biji', packLabel, displayQuantity: `${quantity} biji` };
  }
  const match = /^(\d+(?:[.,]\d+)?)\s*(.+)$/.exec(packLabel);
  if (match) {
    const amount = Number.parseFloat(match[1].replace(',', '.')) * units;
    const labelUnit = match[2].trim();
    const quantity = /^(g|gram|grams)$/i.test(labelUnit) ? amount / 1000 : amount;
    const unit = /^(g|gram|grams)$/i.test(labelUnit) ? 'kg' : labelUnit;
    return { quantity, unit, packLabel, displayQuantity: `${quantity} ${unit}` };
  }
  return { quantity: units, unit: packLabel, packLabel, displayQuantity: `${units} ${packLabel}` };
}
