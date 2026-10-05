import { MaterialCommunityIcons } from '@expo/vector-icons';
import { useFonts } from 'expo-font';
import * as ImagePicker from 'expo-image-picker';
import { useState } from 'react';
import { Image, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import {
  priceCheckLocationFontAssets,
  priceCheckLocationTokens,
} from '../components/price-check/priceCheckLocationTokens';

const OCR_BANNER_VISUAL = require('../../assets/images/my-basket/ocr-banner-cropped.png');

export interface ReceiptCaptureScreenProps {
  hideIntroBanner?: boolean;
  onBack?: () => void;
  onImageSelected?: (asset: ImagePicker.ImagePickerAsset) => void;
}

function StepIndicator() {
  return (
    <View accessibilityLabel="Receipt step 1 of 3" style={styles.stepIndicator}>
      <View style={[styles.step, styles.activeStep]}>
        <Text style={[styles.stepText, styles.activeStepText]}>1</Text>
        <Text style={[styles.stepLabel, styles.activeStepText]}>Capture</Text>
      </View>
      <View style={styles.stepLine} />
      <View style={styles.step}>
        <Text style={styles.stepText}>2</Text>
        <Text style={styles.stepLabel}>Review</Text>
      </View>
      <View style={styles.stepLine} />
      <View style={styles.step}>
        <Text style={styles.stepText}>3</Text>
        <Text style={styles.stepLabel}>Confirm</Text>
      </View>
    </View>
  );
}

export function ReceiptCaptureScreen({
  hideIntroBanner = false,
  onBack,
  onImageSelected,
}: ReceiptCaptureScreenProps) {
  const [fontsLoaded] = useFonts(priceCheckLocationFontAssets);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const openCamera = async () => {
    setErrorMessage(null);
    try {
      const permission = await ImagePicker.requestCameraPermissionsAsync();
      if (!permission.granted) {
        setErrorMessage(
          permission.canAskAgain
            ? 'Camera permission is needed to photograph a receipt. Please allow it and try again.'
            : 'Camera access is disabled. Enable it for WiseBasket in your phone Settings.',
        );
        return;
      }
      const result = await ImagePicker.launchCameraAsync({ quality: 0.85 });
      if (!result.canceled && result.assets[0]) onImageSelected?.(result.assets[0]);
    } catch {
      setErrorMessage('Camera could not be opened. Please try uploading a receipt image.');
    }
  };

  const openLibrary = async () => {
    setErrorMessage(null);
    try {
      const result = await ImagePicker.launchImageLibraryAsync({ quality: 0.85 });
      if (!result.canceled && result.assets[0]) onImageSelected?.(result.assets[0]);
    } catch {
      setErrorMessage('Your photo library could not be opened. Please try again.');
    }
  };

  if (!fontsLoaded) {
    return <View style={styles.fontLoading} />;
  }

  return (
    <View style={styles.wrapper}>
      <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
        <View style={styles.header}>
          <Pressable
            accessibilityLabel="Back to My Basket"
            accessibilityRole="button"
            onPress={onBack}
            style={({ pressed }) => [styles.headerButton, pressed && styles.pressed]}
          >
            <MaterialCommunityIcons color={COLORS.deepTeal} name="arrow-left" size={27} />
          </Pressable>
          <Text style={styles.headerTitle}>Add a receipt</Text>
          <View style={styles.headerButton} />
        </View>

        <StepIndicator />

        <View style={styles.headingBlock}>
          <Text accessibilityRole="header" style={styles.pageTitle}>Scan a grocery receipt</Text>
          <Text style={styles.pageSubtitle}>
            We&apos;ll identify the groceries and add them to What You Have.
          </Text>
        </View>

        {!hideIntroBanner ? (
          <View style={styles.visualCard}>
            <Image
              accessibilityElementsHidden
              resizeMode="contain"
              source={OCR_BANNER_VISUAL}
              style={styles.visual}
            />
          </View>
        ) : null}

        <View style={styles.infoCard}>
          <View style={styles.infoIcon}>
            <MaterialCommunityIcons color={COLORS.green} name="shield-check-outline" size={24} />
          </View>
          <View style={styles.infoCopy}>
            <Text style={styles.infoTitle}>You stay in control</Text>
            <Text style={styles.infoBody}>
              OCR will identify the items, but nothing is added until you review and confirm it.
            </Text>
          </View>
        </View>

        <Text style={styles.sectionTitle}>Choose how to add your receipt</Text>
        <Pressable
          accessibilityLabel="Take photo"
          accessibilityRole="button"
          onPress={() => void openCamera()}
          style={({ pressed }) => [styles.primaryButton, pressed && styles.pressed]}
        >
          <MaterialCommunityIcons color={COLORS.white} name="camera-outline" size={24} />
          <Text style={styles.primaryButtonText}>Take photo</Text>
        </Pressable>
        <Pressable
          accessibilityLabel="Upload image"
          accessibilityRole="button"
          onPress={() => void openLibrary()}
          style={({ pressed }) => [styles.secondaryButton, pressed && styles.pressed]}
        >
          <MaterialCommunityIcons color={COLORS.deepTeal} name="image-outline" size={23} />
          <Text style={styles.secondaryButtonText}>Upload image</Text>
        </Pressable>
        {errorMessage ? <Text style={styles.errorText}>{errorMessage}</Text> : null}
        <Text style={styles.helperText}>Use a clear photo with the whole receipt in frame.</Text>
      </ScrollView>
    </View>
  );
}

const COLORS = {
  background: priceCheckLocationTokens.colors.background,
  deepTeal: priceCheckLocationTokens.colors.deepTeal,
  green: '#2D806B',
  mint: '#E8F8EF',
  muted: priceCheckLocationTokens.colors.secondaryText,
  paleMint: '#F1F8F4',
  white: '#FFFFFF',
} as const;

const styles = StyleSheet.create({
  activeStep: {
    backgroundColor: COLORS.deepTeal,
  },
  activeStepText: {
    color: COLORS.white,
  },
  content: {
    paddingBottom: 36,
    paddingHorizontal: 24,
  },
  errorText: {
    color: '#B34A3A',
    fontFamily: priceCheckLocationTokens.fonts.bodySemibold,
    fontSize: 13,
    lineHeight: 18,
    marginTop: 12,
    textAlign: 'center',
  },
  fontLoading: {
    backgroundColor: COLORS.background,
    flex: 1,
  },
  header: {
    alignItems: 'center',
    flexDirection: 'row',
    justifyContent: 'space-between',
    minHeight: 64,
  },
  headerButton: {
    alignItems: 'center',
    height: 48,
    justifyContent: 'center',
    width: 48,
  },
  headerTitle: {
    color: COLORS.deepTeal,
    fontFamily: priceCheckLocationTokens.fonts.bodySemibold,
    fontSize: 16,
  },
  headingBlock: {
    paddingTop: 24,
  },
  helperText: {
    color: COLORS.muted,
    fontFamily: priceCheckLocationTokens.fonts.body,
    fontSize: 13,
    lineHeight: 18,
    marginTop: 12,
    textAlign: 'center',
  },
  infoBody: {
    color: COLORS.muted,
    fontFamily: priceCheckLocationTokens.fonts.body,
    fontSize: 13,
    lineHeight: 18,
    marginTop: 2,
  },
  infoCard: {
    alignItems: 'flex-start',
    backgroundColor: COLORS.mint,
    borderRadius: 18,
    flexDirection: 'row',
    gap: 12,
    marginTop: 14,
    padding: 16,
  },
  infoCopy: {
    flex: 1,
  },
  infoIcon: {
    alignItems: 'center',
    backgroundColor: COLORS.white,
    borderRadius: 18,
    height: 36,
    justifyContent: 'center',
    width: 36,
  },
  infoTitle: {
    color: COLORS.deepTeal,
    fontFamily: priceCheckLocationTokens.fonts.bodySemibold,
    fontSize: 15,
    lineHeight: 20,
  },
  pageSubtitle: {
    color: COLORS.muted,
    fontFamily: priceCheckLocationTokens.fonts.body,
    fontSize: 16,
    lineHeight: 22,
    marginTop: 6,
  },
  pageTitle: {
    color: COLORS.deepTeal,
    fontFamily: priceCheckLocationTokens.fonts.heading,
    fontSize: 29,
    lineHeight: 36,
  },
  pressed: {
    opacity: 0.8,
  },
  primaryButton: {
    alignItems: 'center',
    backgroundColor: COLORS.deepTeal,
    borderRadius: 17,
    flexDirection: 'row',
    gap: 10,
    justifyContent: 'center',
    minHeight: 56,
    paddingHorizontal: 16,
  },
  primaryButtonText: {
    color: COLORS.white,
    fontFamily: priceCheckLocationTokens.fonts.bodySemibold,
    fontSize: 16,
  },
  secondaryButton: {
    alignItems: 'center',
    backgroundColor: COLORS.paleMint,
    borderColor: '#D6EAE0',
    borderRadius: 17,
    borderWidth: 1,
    flexDirection: 'row',
    gap: 10,
    justifyContent: 'center',
    marginTop: 10,
    minHeight: 56,
    paddingHorizontal: 16,
  },
  secondaryButtonText: {
    color: COLORS.deepTeal,
    fontFamily: priceCheckLocationTokens.fonts.bodySemibold,
    fontSize: 16,
  },
  sectionTitle: {
    color: COLORS.deepTeal,
    fontFamily: priceCheckLocationTokens.fonts.cardTitle,
    fontSize: 18,
    lineHeight: 24,
    marginBottom: 10,
    marginTop: 24,
  },
  step: {
    alignItems: 'center',
    backgroundColor: COLORS.paleMint,
    borderRadius: 16,
    flexDirection: 'row',
    gap: 5,
    minHeight: 32,
    paddingHorizontal: 9,
  },
  stepIndicator: {
    alignItems: 'center',
    flexDirection: 'row',
    justifyContent: 'center',
    marginTop: 4,
  },
  stepLabel: {
    color: COLORS.muted,
    fontFamily: priceCheckLocationTokens.fonts.bodySemibold,
    fontSize: 11,
  },
  stepLine: {
    backgroundColor: '#DCEBE1',
    height: 1,
    marginHorizontal: 6,
    width: 18,
  },
  stepText: {
    color: COLORS.muted,
    fontFamily: priceCheckLocationTokens.fonts.bodySemibold,
    fontSize: 12,
  },
  visual: {
    aspectRatio: 1761 / 732,
    height: undefined,
    width: '100%',
  },
  visualCard: {
    backgroundColor: COLORS.mint,
    borderRadius: 22,
    marginTop: 20,
    overflow: 'hidden',
  },
  wrapper: {
    backgroundColor: COLORS.background,
    flex: 1,
  },
});
