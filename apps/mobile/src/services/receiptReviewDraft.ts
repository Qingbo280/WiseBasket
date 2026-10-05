import AsyncStorage from '@react-native-async-storage/async-storage';
import type { ReceiptReviewLine } from '../screens/ReceiptReviewScreen';

const PREFIX = 'wisebasket:receipt-review-draft:v1:';
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

interface ReceiptReviewDraft {
  manualLines: ReceiptReviewLine[];
  selectedManualIds: string[];
}

export async function loadReceiptReviewDraft(receiptId: string): Promise<ReceiptReviewDraft | null> {
  const raw = await AsyncStorage.getItem(PREFIX + receiptId);
  if (!raw) return null;
  try {
    const parsed: unknown = JSON.parse(raw);
    if (!parsed || typeof parsed !== 'object') return null;
    const value = parsed as Partial<ReceiptReviewDraft>;
    if (!Array.isArray(value.manualLines) || !Array.isArray(value.selectedManualIds)) return null;
    const manualLines = value.manualLines.filter((line) => (
      line && UUID.test(line.id) && line.lineId === null &&
      line.clientLineId === line.id && typeof line.foodId === 'string' &&
      typeof line.name === 'string'
    ));
    const ids = new Set(manualLines.map((line) => line.id));
    return {
      manualLines,
      selectedManualIds: value.selectedManualIds.filter((id): id is string => (
        typeof id === 'string' && ids.has(id)
      )),
    };
  } catch {
    return null;
  }
}

export async function saveReceiptReviewDraft(
  receiptId: string,
  manualLines: readonly ReceiptReviewLine[],
  selectedManualIds: readonly string[],
): Promise<void> {
  const rows = manualLines.map((line) => ({
    id: line.id,
    lineId: null,
    clientLineId: line.clientLineId ?? line.id,
    foodId: line.foodId,
    name: line.name,
    price: line.price,
    quantityKg: line.quantityKg,
    quantityUnit: line.quantityUnit,
    rawName: line.rawName,
  }));
  await AsyncStorage.setItem(PREFIX + receiptId, JSON.stringify({
    manualLines: rows,
    selectedManualIds,
  }));
}

export async function clearReceiptReviewDraft(receiptId: string): Promise<void> {
  await AsyncStorage.removeItem(PREFIX + receiptId);
}
