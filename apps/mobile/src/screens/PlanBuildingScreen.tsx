import { MaterialCommunityIcons } from '@expo/vector-icons';
import { useFonts } from 'expo-font';
import { ActivityIndicator, Image, Pressable, StyleSheet, Text, View } from 'react-native';
import { priceCheckLocationFontAssets, priceCheckLocationTokens } from '../components/price-check/priceCheckLocationTokens';

const LOGO = require('../../assets/images/brand/wisebasket-logo-horizontal.png');

export interface PlanBuildingScreenProps {
  buildBusy: boolean;
  buildError?: string | null;
  onBack: () => void;
  onRetry: () => void;
}

export function PlanBuildingScreen({
  buildBusy,
  buildError = null,
  onBack,
  onRetry,
}: PlanBuildingScreenProps) {
  const [fontsLoaded] = useFonts(priceCheckLocationFontAssets);

  if (!fontsLoaded) {
    return <View style={styles.fontLoading} />;
  }

  const hasError = !buildBusy && Boolean(buildError);

  return (
    <View style={styles.screen}>
      <View style={styles.content}>
        <Image
          accessibilityLabel="WiseBasket"
          resizeMode="contain"
          source={LOGO}
          style={styles.logo}
        />

        {hasError ? (
          <View style={styles.stateBlock}>
            <View style={styles.errorIcon}>
              <MaterialCommunityIcons color={COLORS.coral} name="alert-outline" size={40} />
            </View>
            <Text accessibilityRole="header" style={styles.title}>We couldn&apos;t build your plan</Text>
            <Text style={styles.subtitle}>{buildError}</Text>
            <Pressable
              accessibilityLabel="Retry building your plan"
              accessibilityRole="button"
              onPress={onRetry}
              style={({ pressed }) => [styles.retryButton, pressed && styles.pressed]}
            >
              <Text style={styles.retryText}>Try again</Text>
              <MaterialCommunityIcons color={COLORS.white} name="refresh" size={23} />
            </Pressable>
            <Pressable
              accessibilityLabel="Back to plan review"
              accessibilityRole="button"
              onPress={onBack}
              style={({ pressed }) => [styles.backButton, pressed && styles.pressed]}
            >
              <Text style={styles.backText}>Back to review</Text>
            </Pressable>
          </View>
        ) : (
          <View accessibilityLabel="Building your basket" style={styles.stateBlock}>
            <ActivityIndicator accessibilityLabel="Building your basket" color={COLORS.primary} size="large" />
            <Text accessibilityRole="header" style={styles.title}>Building your basket</Text>
            <Text style={styles.subtitle}>
              We&apos;re using your preferences to find groceries that fit your week and budget.
            </Text>
          </View>
        )}
      </View>
    </View>
  );
}

const COLORS = {
  background: priceCheckLocationTokens.colors.background,
  coral: '#D95D4C',
  deepTeal: priceCheckLocationTokens.colors.deepTeal,
  muted: priceCheckLocationTokens.colors.secondaryText,
  primary: '#087C7E',
  white: '#FFFFFF',
} as const;

const styles = StyleSheet.create({
  backButton: {
    alignItems: 'center',
    minHeight: 48,
    justifyContent: 'center',
    marginTop: 4,
  },
  backText: {
    color: COLORS.deepTeal,
    fontFamily: priceCheckLocationTokens.fonts.bodySemibold,
    fontSize: 16,
    lineHeight: 22,
  },
  content: {
    alignItems: 'center',
    flex: 1,
    justifyContent: 'center',
    paddingHorizontal: 28,
  },
  errorIcon: {
    alignItems: 'center',
    backgroundColor: '#FDECE8',
    borderRadius: 38,
    height: 76,
    justifyContent: 'center',
    marginBottom: 19,
    width: 76,
  },
  fontLoading: {
    backgroundColor: COLORS.background,
    flex: 1,
  },
  logo: {
    height: 68,
    marginBottom: 38,
    width: 220,
  },
  pressed: {
    opacity: 0.78,
  },
  retryButton: {
    alignItems: 'center',
    backgroundColor: COLORS.primary,
    borderRadius: 25,
    flexDirection: 'row',
    gap: 8,
    justifyContent: 'center',
    marginTop: 23,
    minHeight: 50,
    paddingHorizontal: 24,
  },
  retryText: {
    color: COLORS.white,
    fontFamily: priceCheckLocationTokens.fonts.cardTitle,
    fontSize: 17,
    lineHeight: 23,
  },
  screen: {
    backgroundColor: COLORS.background,
    flex: 1,
  },
  stateBlock: {
    alignItems: 'center',
    maxWidth: 340,
  },
  subtitle: {
    color: COLORS.muted,
    fontFamily: priceCheckLocationTokens.fonts.body,
    fontSize: 16,
    lineHeight: 23,
    marginTop: 9,
    textAlign: 'center',
  },
  title: {
    color: COLORS.deepTeal,
    fontFamily: priceCheckLocationTokens.fonts.heading,
    fontSize: 30,
    lineHeight: 37,
    marginTop: 20,
    textAlign: 'center',
  },
});
