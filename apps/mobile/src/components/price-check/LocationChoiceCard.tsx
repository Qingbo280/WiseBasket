import type { ImageSourcePropType } from 'react-native';
import { Image, Pressable, StyleSheet, Text, View } from 'react-native';
import { priceCheckLocationTokens } from './priceCheckLocationTokens';

const CHEVRON_IMAGE = require('../../../assets/images/price-check-reference/chevron-right.png');

interface LocationChoiceCardProps {
  accessibilityLabel: string;
  compact?: boolean;
  imageSource: ImageSourcePropType;
  onPress: () => void;
  subtitle: string;
  title: string;
}

export function LocationChoiceCard({
  accessibilityLabel,
  compact = false,
  imageSource,
  onPress,
  subtitle,
  title,
}: LocationChoiceCardProps) {
  return (
    <Pressable
      accessibilityLabel={accessibilityLabel}
      accessibilityRole="button"
      onPress={onPress}
      style={({ pressed }) => [styles.card, compact && styles.compactCard, pressed && styles.cardPressed]}
    >
      <Image
        accessibilityElementsHidden
        source={imageSource}
        style={[styles.artwork, compact && styles.compactArtwork]}
      />
      <View style={styles.copy}>
        <Text style={[styles.title, compact && styles.compactTitle]}>{title}</Text>
        <Text style={[styles.subtitle, compact && styles.compactSubtitle]}>{subtitle}</Text>
      </View>
      <Image
        accessibilityElementsHidden
        source={CHEVRON_IMAGE}
        style={[styles.chevron, compact && styles.compactChevron]}
      />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  artwork: {
    height: priceCheckLocationTokens.iconSizes.artworkHeight,
    resizeMode: 'contain',
    width: priceCheckLocationTokens.iconSizes.artworkWidth,
  },
  card: {
    alignItems: 'center',
    backgroundColor: priceCheckLocationTokens.colors.cardCream,
    borderRadius: priceCheckLocationTokens.radius.card,
    elevation: priceCheckLocationTokens.shadow.elevation,
    flexDirection: 'row',
    gap: priceCheckLocationTokens.spacing.cardInnerGap,
    minHeight: 90,
    paddingHorizontal: priceCheckLocationTokens.spacing.cardPaddingHorizontal,
    paddingVertical: priceCheckLocationTokens.spacing.cardPaddingVertical,
    shadowColor: priceCheckLocationTokens.shadow.color,
    shadowOffset: priceCheckLocationTokens.shadow.offset,
    shadowOpacity: priceCheckLocationTokens.shadow.opacity,
    shadowRadius: priceCheckLocationTokens.shadow.radius,
  },
  cardPressed: {
    opacity: 0.82,
    transform: [{ scale: 0.99 }],
  },
  compactArtwork: {
    height: 60,
    width: 92,
  },
  compactCard: {
    minHeight: 78,
    paddingVertical: 8,
  },
  compactChevron: {
    height: 30,
    width: 30,
  },
  compactSubtitle: {
    fontSize: 14,
    lineHeight: 18,
  },
  compactTitle: {
    fontSize: 17,
    lineHeight: 21,
  },
  chevron: {
    height: priceCheckLocationTokens.iconSizes.chevron,
    marginLeft: 2,
    resizeMode: 'contain',
    width: priceCheckLocationTokens.iconSizes.chevron,
  },
  copy: {
    flex: 1,
    minWidth: 0,
  },
  subtitle: {
    color: priceCheckLocationTokens.colors.secondaryText,
    fontFamily: priceCheckLocationTokens.fonts.body,
    fontSize: 15,
    lineHeight: 20,
    marginTop: priceCheckLocationTokens.spacing.cardTitleSubtitleGap,
  },
  title: {
    color: priceCheckLocationTokens.colors.deepTeal,
    fontFamily: priceCheckLocationTokens.fonts.cardTitle,
    fontSize: 19,
    lineHeight: 23,
  },
});
