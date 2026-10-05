import { Image, StyleSheet, Text, useWindowDimensions, View } from 'react-native';
import { priceCheckLocationTokens } from './priceCheckLocationTokens';

const TITLE_ACCENT_IMAGE = require('../../../assets/images/price-check-reference/title-accent.png');

export function PriceCheckHeading({ compact = false }: { compact?: boolean }) {
  const { width } = useWindowDimensions();

  return (
    <View>
      <View style={styles.headingWrap}>
        <Text style={[styles.heading, compact && styles.compactHeading]}>
          Find better{`\n`}prices around{`\n`}you
        </Text>
        {width >= 384 ? (
          <Image
            accessibilityElementsHidden
            source={TITLE_ACCENT_IMAGE}
            style={[styles.titleAccent, compact && styles.compactTitleAccent]}
          />
        ) : null}
      </View>
      <Text style={[styles.description, compact && styles.compactDescription]}>
        We’ll show you nearby supermarkets and minimarkets with better prices for the items you need.
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  description: {
    color: priceCheckLocationTokens.colors.primaryText,
    fontFamily: priceCheckLocationTokens.fonts.body,
    fontSize: 19,
    lineHeight: 26,
    marginTop: priceCheckLocationTokens.spacing.descriptionTop,
  },
  heading: {
    color: priceCheckLocationTokens.colors.deepTeal,
    fontFamily: priceCheckLocationTokens.fonts.heading,
    fontSize: 50,
    letterSpacing: -0.5,
    lineHeight: 50,
  },
  compactDescription: {
    fontSize: 17,
    lineHeight: 23,
    marginTop: 12,
  },
  compactHeading: {
    fontSize: 46,
    lineHeight: 46,
  },
  headingWrap: {
    position: 'relative',
  },
  titleAccent: {
    height: priceCheckLocationTokens.iconSizes.titleAccentHeight,
    position: 'absolute',
    right: 0,
    resizeMode: 'contain',
    top: 68,
    width: priceCheckLocationTokens.iconSizes.titleAccentWidth,
  },
  compactTitleAccent: {
    top: 58,
  },
});
