import { ApiError, apiRequest } from './api';
import { File } from 'expo-file-system';
import { Platform } from 'react-native';

export type ReceiptStatus = 'PENDING' | 'PROCESSING' | 'DONE' | 'FAILED';

// The backend ends each receipt within 240 s; allow a little network slack.
const RECEIPT_QUEUE_WAIT_TIMEOUT_MS = 260_000;

export interface ReceiptFood {
  canonical_food_id: string;
  name: string;
  name_ms: string | null;
  category: string;
}

export interface ReceiptLine {
  line_id: string;
  client_line_id?: string | null;
  display_order: number;
  name_raw: string;
  expanded_name: string | null;
  qty: number | null;
  unit: string | null;
  price_rm: number | null;
  proposed_food: ReceiptFood | null;
  match_score: number | null;
  candidates: readonly { canonical_food_id: string; score: number }[];
  status: string;
  match_basis?: string | null;
}

export interface Receipt {
  receipt_id: string;
  household_id: number;
  status: ReceiptStatus;
  error: string | null;
  created_at: string;
  processed_at: string | null;
  lines: ReceiptLine[];
  duplicate_of_receipt_id?: string | null;
}

export interface ReceiptLineConfirmation {
  line_id: string;
  canonical_food_id: string | null;
  price_rm: number | null;
  qty?: number | null;
  unit?: string | null;
}

export interface ReceiptAddedLine {
  client_line_id?: string;
  canonical_food_id: string;
  name_raw?: string | null;
  qty?: number | null;
  unit?: string | null;
  price_rm?: number | null;
}

export function newReceiptClientLineId(): string {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
  // Expo's JS runtime does not guarantee Web Crypto on every device.
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (digit) => {
    const random = Math.floor(Math.random() * 16);
    return (digit === 'x' ? random : (random & 3) | 8).toString(16);
  });
}

export interface ReceiptConfirmation {
  lines: ReceiptLineConfirmation[];
  added_lines: ReceiptAddedLine[];
}

function receiptImageName(uri: string) {
  const value = uri.split(/[?#]/)[0]?.split('/').pop();
  return value && /\.[a-z0-9]+$/i.test(value) ? value : 'receipt.jpg';
}

export async function uploadReceipt(householdId: number, imageUri: string): Promise<Receipt> {
  const body = new FormData();
  const name = receiptImageName(imageUri);
  if (Platform.OS === 'web') {
    const imageResponse = await fetch(imageUri);
    if (!imageResponse.ok) throw new ApiError('The selected receipt image could not be opened.', 0);
    const imageBlob = await imageResponse.blob();
    body.append('file', imageBlob, name);
  } else {
    body.append('file', new File(imageUri), name);
  }
  return apiRequest<Receipt>(`/api/v1/households/${householdId}/receipts`, {
    body,
    method: 'POST',
    timeoutMs: 60_000,
  });
}

export async function getReceipt(householdId: number, receiptId: string): Promise<Receipt> {
  return apiRequest<Receipt>(`/api/v1/households/${householdId}/receipts/${receiptId}`, {
    method: 'GET',
  });
}

export async function waitForReceipt(
  householdId: number,
  receiptId: string,
  shouldContinue: () => boolean = () => true,
): Promise<Receipt> {
  const deadline = Date.now() + RECEIPT_QUEUE_WAIT_TIMEOUT_MS;
  while (shouldContinue() && Date.now() < deadline) {
    const receipt = await getReceipt(householdId, receiptId);
    if (receipt.status === 'DONE') return receipt;
    if (receipt.status === 'FAILED') {
      throw new ApiError(receipt.error || 'The receipt could not be read.', 422);
    }
    await new Promise((resolve) => setTimeout(resolve, 1_000));
  }
  if (!shouldContinue()) throw new ApiError('Receipt processing was cancelled.', 0);
  throw new ApiError('Receipt processing is not complete. Please check it again shortly.', 0);
}

export async function confirmReceipt(
  householdId: number,
  receiptId: string,
  confirmation: ReceiptConfirmation,
): Promise<Receipt> {
  return apiRequest<Receipt>(
    `/api/v1/households/${householdId}/receipts/${receiptId}/confirm`,
    { body: confirmation, method: 'POST' },
  );
}
