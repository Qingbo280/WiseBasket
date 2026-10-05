import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

function readSource(fileName) {
  return fs.readFileSync(path.resolve(process.cwd(), 'src/screens', fileName), 'utf8');
}

const captureSource = readSource('ReceiptCaptureScreen.tsx');
const processingSource = readSource('ReceiptProcessingScreen.tsx');
const reviewSource = readSource('ReceiptReviewScreen.tsx');
const reviewRowsSource = fs.readFileSync(path.resolve(process.cwd(), 'src/services/receiptReviewRows.ts'), 'utf8');
const appSource = fs.readFileSync(path.resolve(process.cwd(), 'App.tsx'), 'utf8');
const basketSource = readSource('MyBasketMainScreen.tsx');
const appConfig = JSON.parse(fs.readFileSync(path.resolve(process.cwd(), 'app.json'), 'utf8'));

test('builds a three-step receipt capture flow in the current WiseBasket visual language', () => {
  assert.match(captureSource, /Scan a grocery receipt/);
  assert.match(captureSource, /Take photo/);
  assert.match(captureSource, /Upload image/);
  assert.match(captureSource, /OCR will identify/);
  assert.match(captureSource, /launchCameraAsync/);
  assert.match(captureSource, /requestCameraPermissionsAsync/);
  assert.match(captureSource, /launchImageLibraryAsync/);
  assert.match(captureSource, /onImageSelected/);

  assert.match(processingSource, /Reading your receipt/);
  assert.match(processingSource, /OCR ready/);
  assert.doesNotMatch(processingSource, /onContinue/);
  assert.doesNotMatch(processingSource, /Review extracted items/);
  assert.match(processingSource, /ActivityIndicator/);
  assert.doesNotMatch(processingSource, /setTimeout/);

  assert.match(reviewSource, /Check what we found/);
  assert.match(reviewSource, /BasketItemImage/);
  assert.match(reviewSource, /foodImageUriForBackendId/);
  assert.match(reviewSource, /Add missing item/);
  assert.match(reviewSource, /Confirm purchase/);
  assert.match(reviewSource, /selected/);
  assert.match(reviewSource, /Modify items/);
  assert.match(reviewSource, /TextInput/);
  assert.match(reviewSource, /filterPriceCheckCatalog/);
  assert.match(reviewSource, /catalogItems/);
  assert.match(reviewSource, /onConfirm\?\.\(/);
  assert.match(reviewSource, /initialLines/);
  assert.match(reviewSource, /ReceiptConfirmation/);
  assert.doesNotMatch(reviewSource, /RECEIPT_REVIEW_FIXTURE/);
  assert.match(reviewSource, /quantityUnit/);
  assert.match(reviewSource, /accessibilityLabel={`Choose unit for \$\{line.name\}`}/);
  assert.match(reviewSource, /RECEIPT_UNIT_OPTIONS/);
  assert.match(reviewSource, /FloatingUnitMenu/);
  assert.match(reviewSource, /measureInWindow/);
  assert.match(reviewSource, /unitOptionRow/);
  assert.match(reviewSource, /unitPickerLineId/);
  assert.match(reviewSource, /line\.quantityUnit \?\? 'Select'/);
  assert.doesNotMatch(reviewSource, /styles\.unitInput/);
  assert.match(reviewSource, /<Text style={styles.inputUnit}>RM<\/Text>/);
  assert.match(reviewSource, /quantityInput/);
  assert.match(reviewSource, /priceInput/);
  assert.match(reviewSource, /parseOptionalDecimal/);
  assert.match(reviewSource, /candidateFoodIds/);
  assert.match(reviewSource, /Change item/);
  assert.match(reviewSource, /Search for the correct food/);
  assert.match(reviewSource, /replaceLineFood/);
});

test('wires the receipt screens from My Basket without changing the backend contract', () => {
  assert.match(basketSource, /onTakePhoto/);
  assert.match(basketSource, /onUploadImage/);
  assert.match(basketSource, /onPress={onTakePhoto}/);
  assert.match(basketSource, /onPress={onUploadImage}/);
  assert.match(appSource, /'receipt-capture'/);
  assert.match(appSource, /'receipt-processing'/);
  assert.match(appSource, /'receipt-review'/);
  assert.match(appSource, /<ReceiptCaptureScreen/);
  assert.match(appSource, /<ReceiptProcessingScreen/);
  assert.match(appSource, /<ReceiptReviewScreen/);
  assert.match(appSource, /launchCameraAsync/);
  assert.match(appSource, /requestCameraPermissionsAsync/);
  assert.match(appSource, /launchImageLibraryAsync/);
  assert.match(appSource, /onReceiptTakePhotoPress/);
  assert.match(appSource, /onReceiptUploadImagePress/);
  assert.match(appSource, /setScreen\('receipt-review'\)/);
  assert.match(appSource, /setScreen\('my-basket-main'\)/);
  assert.match(appSource, /uploadReceipt/);
  assert.match(appSource, /waitForReceipt/);
  assert.match(appSource, /receiptScanFailureMessage/);
  assert.match(appSource, /confirmReceipt/);
  assert.match(appSource, /initialLines=\{receiptReviewLines\}/);
  assert.match(appSource, /buildReceiptReviewRows\(receipt\?\.lines \?\? \[\]\)/);
  assert.doesNotMatch(reviewSource, /<Text style=\{styles\.rawName\}>/);
  assert.match(appSource, /receiptHaveItems/);
  assert.match(appSource, /onImageSelected/);
  assert.match(appSource, /catalogItems=\{pantryCatalogItems\.length > 0 \? pantryCatalogItems : catalogItems\}/);
  assert.match(basketSource, /receiptHaveItems/);
});

test('requests and declares camera access for receipt photographs', () => {
  const imagePickerPlugin = appConfig.expo.plugins.find((plugin) => Array.isArray(plugin)
    && plugin[0] === 'expo-image-picker');

  assert.ok(imagePickerPlugin, 'expo-image-picker must configure native permissions');
  assert.match(imagePickerPlugin[1].cameraPermission, /camera/i);
  assert.ok(appConfig.expo.android.permissions.includes('android.permission.CAMERA'));
});

test('routes What You Have capture failures to retry controls without the reused OCR banner', () => {
  assert.match(captureSource, /hideIntroBanner\??: boolean/);
  assert.match(captureSource, /!hideIntroBanner/);
  assert.match(appSource, /setReceiptCaptureHideIntroBanner\(true\)/);
  assert.match(appSource, /hideIntroBanner=\{receiptCaptureHideIntroBanner\}/);
});

test('hides the intro banner when returning from receipt processing', () => {
  const processingBack = appSource.match(/const handleReceiptProcessingBack = \(\) => \{([\s\S]*?)\n  \};/u)?.[1] ?? '';

  assert.match(processingBack, /setReceiptCaptureHideIntroBanner\(true\)/);
  assert.match(processingBack, /setScreen\('receipt-capture'\)/);
});

test('keeps previously confirmed receipt foods immutable in the review controls and payload', () => {
  assert.match(reviewSource, /isLockedConfirmedReceiptRow\(line\)/);
  assert.match(reviewSource, /disabled=\{line\.foodId === null \|\| confirmed\}/);
  assert.match(reviewSource, /disabled=\{confirmed\}/);
  assert.match(reviewSource, /editable=\{!confirmed\}/);
  assert.match(reviewSource, /prepareReceiptConfirmation\(lines, selectedIdSet\)/);
  assert.match(reviewRowsSource, /isLockedConfirmedReceiptRow\(line\) \? \{\} : quantityPair\(line\)/);
  assert.match(reviewRowsSource, /confirmedReceiptFoodId\(line, selectedIds\)/);
});
