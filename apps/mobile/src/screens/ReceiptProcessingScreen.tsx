import { MaterialCommunityIcons } from '@expo/vector-icons';
import { useFonts } from 'expo-font';
import { ActivityIndicator, Image, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import {
  priceCheckLocationFontAssets,
  priceCheckLocationTokens,
} from '../components/price-check/priceCheckLocationTokens';

export interface ReceiptProcessingScreenProps {
  imageUri?: string | null;
  onBack?: () => void;
}

function StepIndicator() {
  return (
    <View accessibilityLabel="Receipt step 2 of 3" style={styles.stepIndicator}>
      <View style={[styles.step, styles.completeStep]}>
        <MaterialCommunityIcons color={COLORS.white} name="check" size={15} />
        <Text style={[styles.stepLabel, styles.completeStepText]}>Capture</Text>
      </View>
      <View style={[styles.stepLine, styles.completeStepLine]} />
      <View style={[styles.step, styles.activeStep]}>
        <Text style={[styles.stepText, styles.activeStepText]}>2</Text>
        <Text style={[styles.stepLabel, styles.activeStepText]}>Process</Text>
      </View>
      <View style={styles.stepLine} />
      <View style={styles.step}>
        <Text style={styles.stepText}>3</Text>
        <Text style={styles.stepLabel}>Review</Text>
      </View>
    </View>
  );
}

function StatusRow({ complete, label }: { complete: boolean; label: string }) {
  return (
    <View style={styles.statusRow}>
      <View style={[styles.statusIcon, complete && styles.completeStatusIcon]}>
        <MaterialCommunityIcons
          color={complete ? COLORS.green : COLORS.deepTeal}
          name={complete ? 'check' : 'dots-horizontal'}
          size={18}
        />
      </View>
      <Text style={styles.statusText}>{label}</Text>
      {complete ? <Text style={styles.statusDone}>Done</Text> : <ActivityIndicator color={COLORS.green} size="small" />}
    </View>
  );
}

export function ReceiptProcessingScreen({ imageUri, onBack }: ReceiptProcessingScreenProps) {
  const [fontsLoaded] = useFonts(priceCheckLocationFontAssets);

  if (!fontsLoaded) {
    return <View style={styles.fontLoading} />;
  }

  return (
    <View style={styles.wrapper}>
      <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
        <View style={styles.header}>
          <Pressable
            accessibilityLabel="Back to receipt capture"
            accessibilityRole="button"
            onPress={onBack}
            style={({ pressed }) => [styles.headerButton, pressed && styles.pressed]}
          >
            <MaterialCommunityIcons color={COLORS.deepTeal} name="arrow-left" size={27} />
          </Pressable>
          <Text style={styles.headerTitle}>Receipt scan</Text>
          <View style={styles.headerButton} />
        </View>

        <StepIndicator />

        <View style={styles.headingBlock}>
          <Text accessibilityRole="header" style={styles.pageTitle}>Reading your receipt</Text>
          <Text style={styles.pageSubtitle}>We&apos;re turning the receipt into a list you can check.</Text>
        </View>

        <View style={styles.processingCard}>
          <View style={styles.receiptCircle}>
            {imageUri ? (
              <Image accessibilityLabel="Selected receipt" source={{ uri: imageUri }} style={styles.receiptPreview} />
            ) : (
              <MaterialCommunityIcons color={COLORS.deepTeal} name="receipt-text-outline" size={58} />
            )}
            <View style={styles.spinnerBadge}>
              <ActivityIndicator color={COLORS.white} size="small" />
            </View>
          </View>
          <Text style={styles.processingTitle}>Finding your groceries</Text>
          <Text style={styles.processingBody}>This usually takes a few seconds.</Text>
          <View style={styles.statusList}>
            <StatusRow complete label="Receipt uploaded" />
            <StatusRow complete label="OCR ready" />
            <StatusRow complete={false} label="Matching food items" />
          </View>
        </View>

        <View style={styles.tipCard}>
          <MaterialCommunityIcons color={COLORS.green} name="lightbulb-outline" size={23} />
          <Text style={styles.tipText}>You can edit prices and remove anything that is not food on the next step.</Text>
        </View>

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
  completeStatusIcon: {
    backgroundColor: '#DDF4E5',
  },
  completeStep: {
    backgroundColor: COLORS.green,
  },
  completeStepLine: {
    backgroundColor: COLORS.green,
  },
  completeStepText: {
    color: COLORS.white,
  },
  content: {
    paddingBottom: 36,
    paddingHorizontal: 24,
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
  mint: {
    backgroundColor: COLORS.mint,
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
  processingBody: {
    color: COLORS.muted,
    fontFamily: priceCheckLocationTokens.fonts.body,
    fontSize: 14,
    lineHeight: 20,
    marginTop: 3,
  },
  processingCard: {
    alignItems: 'center',
    backgroundColor: COLORS.white,
    borderColor: '#DCEBE1',
    borderRadius: 24,
    borderWidth: 1,
    marginTop: 26,
    padding: 22,
  },
  processingTitle: {
    color: COLORS.deepTeal,
    fontFamily: priceCheckLocationTokens.fonts.cardTitle,
    fontSize: 20,
    marginTop: 16,
  },
  receiptCircle: {
    alignItems: 'center',
    backgroundColor: COLORS.paleMint,
    borderRadius: 58,
    height: 116,
    justifyContent: 'center',
    position: 'relative',
    width: 116,
  },
  receiptPreview: {
    borderRadius: 52,
    height: 104,
    width: 104,
  },
  spinnerBadge: {
    alignItems: 'center',
    backgroundColor: COLORS.green,
    borderColor: COLORS.white,
    borderRadius: 16,
    borderWidth: 3,
    bottom: 1,
    height: 31,
    justifyContent: 'center',
    position: 'absolute',
    right: 1,
    width: 31,
  },
  statusDone: {
    color: COLORS.green,
    fontFamily: priceCheckLocationTokens.fonts.bodySemibold,
    fontSize: 12,
    marginLeft: 'auto',
  },
  statusIcon: {
    alignItems: 'center',
    backgroundColor: COLORS.paleMint,
    borderRadius: 15,
    height: 30,
    justifyContent: 'center',
    width: 30,
  },
  statusList: {
    alignSelf: 'stretch',
    borderTopColor: '#E4EFE8',
    borderTopWidth: 1,
    marginTop: 22,
  },
  statusRow: {
    alignItems: 'center',
    borderBottomColor: '#E4EFE8',
    borderBottomWidth: 1,
    flexDirection: 'row',
    gap: 10,
    minHeight: 54,
  },
  statusText: {
    color: COLORS.deepTeal,
    fontFamily: priceCheckLocationTokens.fonts.bodySemibold,
    fontSize: 14,
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
  tipCard: {
    alignItems: 'flex-start',
    backgroundColor: COLORS.mint,
    borderRadius: 18,
    flexDirection: 'row',
    gap: 10,
    marginTop: 14,
    padding: 15,
  },
  tipText: {
    color: COLORS.deepTeal,
    flex: 1,
    fontFamily: priceCheckLocationTokens.fonts.body,
    fontSize: 13,
    lineHeight: 18,
  },
  wrapper: {
    backgroundColor: COLORS.background,
    flex: 1,
  },
});
