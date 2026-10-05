import { Image, Pressable, StyleSheet, Text, useWindowDimensions, View } from 'react-native';
import { priceCheckLocationTokens } from './priceCheckLocationTokens';

const LOGO_IMAGE = require('../../../assets/images/brand/wisebasket-logo-horizontal.png');
const CHEVRON_IMAGE = require('../../../assets/images/price-check-reference/chevron-right.png');

export function PriceCheckHeader({
  compact = false,
  onBack,
  title,
  titleWeight = 'bold',
  logoSize = 'regular',
}: {
  compact?: boolean;
  onBack?: () => void;
  title?: string;
  titleWeight?: 'bold' | 'semibold';
  logoSize?: 'regular' | 'small';
}) {
  const { width } = useWindowDimensions();
  const logoWidth = logoSize === 'small'
    ? Math.min(158, width - 160)
    : compact
    ? Math.min(226, Math.max(196, width - 132))
    : Math.min(262, Math.max(218, width - 104));
  const headerHeight = compact ? 60 : priceCheckLocationTokens.spacing.headerHeight;

  return (
    <View style={[styles.header, compact && styles.compactHeader, { height: headerHeight }]}>
      <Pressable
        accessibilityLabel="Go back"
        accessibilityRole="button"
        disabled={!onBack}
        onPress={onBack}
        style={({ pressed }) => [
          styles.backButton,
          compact && styles.compactBackButton,
          pressed && styles.backButtonPressed,
        ]}
      >
        <Image
          accessibilityElementsHidden
          source={CHEVRON_IMAGE}
          style={styles.backIcon}
        />
      </Pressable>
      {title ? (
        <Text
          accessibilityRole="header"
          style={[styles.title, titleWeight === 'semibold' && styles.titleSemibold]}
        >
          {title}
        </Text>
      ) : (
        <Image
          accessibilityLabel="WiseBasket logo"
          source={LOGO_IMAGE}
          style={[styles.logo, { height: logoSize === 'small' ? 40 : logoWidth / 3.93, width: logoWidth }]}
        />
      )}
      <View accessibilityElementsHidden style={styles.headerBalance} />
    </View>
  );
}

const styles = StyleSheet.create({
  backButton: {
    alignItems: 'center',
    height: priceCheckLocationTokens.iconSizes.touchTarget,
    justifyContent: 'center',
    left: 12,
    position: 'absolute',
    top: (priceCheckLocationTokens.spacing.headerHeight - priceCheckLocationTokens.iconSizes.touchTarget) / 2,
    width: priceCheckLocationTokens.iconSizes.touchTarget,
    zIndex: 1,
  },
  backButtonPressed: {
    opacity: 0.7,
  },
  compactBackButton: {
    top: 6,
  },
  compactHeader: {
    minHeight: 60,
  },
  backIcon: {
    height: 36,
    resizeMode: 'contain',
    transform: [{ rotate: '180deg' }],
    width: 36,
  },
  header: {
    alignItems: 'center',
    backgroundColor: priceCheckLocationTokens.colors.background,
    height: priceCheckLocationTokens.spacing.headerHeight,
    justifyContent: 'center',
    position: 'relative',
    width: '100%',
  },
  headerBalance: {
    height: priceCheckLocationTokens.iconSizes.touchTarget,
    position: 'absolute',
    right: 12,
    width: priceCheckLocationTokens.iconSizes.touchTarget,
  },
  logo: {
    resizeMode: 'contain',
  },
  title: {
    color: priceCheckLocationTokens.colors.deepTeal,
    fontFamily: priceCheckLocationTokens.fonts.heading,
    fontSize: 30,
    lineHeight: 36,
  },
  titleSemibold: {
    fontFamily: priceCheckLocationTokens.fonts.cardTitle,
  },
});
