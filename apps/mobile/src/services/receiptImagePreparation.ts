import { manipulateAsync, SaveFormat } from 'expo-image-manipulator';
import type { ImagePickerAsset } from 'expo-image-picker';

/** Largest side retained for OCR: enough receipt detail without multi-megabyte uploads. */
export const MAX_RECEIPT_IMAGE_EDGE = 2000;

/**
 * Converts every selected receipt image (including iPhone HEIC) to JPEG and
 * shrinks only images that exceed the OCR upload limit.
 */
export async function prepareReceiptImage(asset: ImagePickerAsset) {
  const actions = asset.width > MAX_RECEIPT_IMAGE_EDGE || asset.height > MAX_RECEIPT_IMAGE_EDGE
    ? [asset.width >= asset.height
      ? { resize: { width: MAX_RECEIPT_IMAGE_EDGE } }
      : { resize: { height: MAX_RECEIPT_IMAGE_EDGE } }]
    : [];

  return manipulateAsync(asset.uri, actions, {
    compress: 0.8,
    format: SaveFormat.JPEG,
  });
}
