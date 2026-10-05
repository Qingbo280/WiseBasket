import { Ionicons } from '@expo/vector-icons';
import { useFonts } from 'expo-font';
import { Image } from 'expo-image';
import { useState } from 'react';
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  useWindowDimensions,
  View,
} from 'react-native';
import { PriceCheckHeader } from '../components/price-check';
import {
  priceCheckLocationFontAssets,
  priceCheckLocationTokens,
} from '../components/price-check/priceCheckLocationTokens';
import {
  getDefaultVariantId,
  shouldRenderPriceCheckVariantConfirmation,
  type PriceCheckSelectedItem,
  type PriceCheckVariantConfirmationConfig,
  type PriceCheckVariantOption,
} from './priceCheckItemVariantConfirmationContent';

export interface PriceCheckItemVariantConfirmationScreenProps {
  selectedItem: PriceCheckSelectedItem;
  variantConfirmation: PriceCheckVariantConfirmationConfig;
  onBack?: () => void;
  onSelectVariant?: (option: PriceCheckVariantOption) => void;
  onCheckPrices?: (option: PriceCheckVariantOption) => void;
}

interface VariantOptionCardProps {
  option: PriceCheckVariantOption;
  selected: boolean;
  onPress: () => void;
}

function VariantOptionCard({ onPress, option, selected }: VariantOptionCardProps) {
  return (
    <Pressable
      accessibilityLabel={`${option.primaryLabel}${option.secondaryLabel ? `, ${option.secondaryLabel}` : ''}`}
      accessibilityRole="button"
      accessibilityState={{ selected }}
      onPress={onPress}
      style={({ pressed }) => [
        styles.variantOption,
        selected && styles.variantOptionSelected,
        pressed && styles.pressed,
      ]}
    >
      <View style={styles.variantOptionCopy}>
        <Text style={styles.variantOptionPrimary}>{option.primaryLabel}</Text>
        {option.secondaryLabel ? (
          <Text style={styles.variantOptionSecondary}>{option.secondaryLabel}</Text>
        ) : null}
      </View>
      <View style={[styles.selectionIndicator, selected && styles.selectionIndicatorSelected]}>
        {selected ? (
          <Ionicons accessibilityElementsHidden color="#FFFFFF" name="checkmark" size={16} />
        ) : null}
      </View>
    </Pressable>
  );
}

export function PriceCheckItemVariantConfirmationScreen({
  onBack,
  onCheckPrices,
  onSelectVariant,
  selectedItem,
  variantConfirmation,
}: PriceCheckItemVariantConfirmationScreenProps) {
  const { width } = useWindowDimensions();
  const [fontsLoaded] = useFonts(priceCheckLocationFontAssets);
  const [selectedVariantId, setSelectedVariantId] = useState(() =>
    getDefaultVariantId(variantConfirmation),
  );
  const horizontalPadding = width <= 360 ? 20 : width <= 384 ? 22 : 24;
  const artworkHeight = width <= 360 ? 164 : width <= 384 ? 180 : 196;
  const selectedOption = variantConfirmation.options.find(
    (option) => option.variantId === selectedVariantId,
  ) ?? variantConfirmation.options[0];

  if (!fontsLoaded) {
    return (
      <View accessibilityLiveRegion="polite" style={styles.fontLoading}>
        <ActivityIndicator color={priceCheckLocationTokens.colors.green} size="small" />
      </View>
    );
  }

  if (!shouldRenderPriceCheckVariantConfirmation(selectedItem) || !selectedOption) {
    return null;
  }

  const handleSelectVariant = (option: PriceCheckVariantOption) => {
    setSelectedVariantId(option.variantId);
    onSelectVariant?.(option);
  };

  return (
    <KeyboardAvoidingView
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      style={styles.screen}
    >
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        keyboardDismissMode="on-drag"
        keyboardShouldPersistTaps="handled"
        showsVerticalScrollIndicator={false}
      >
        <PriceCheckHeader onBack={onBack} />

        <View style={[styles.pageContent, { paddingHorizontal: horizontalPadding }]}> 
          <Text accessibilityRole="header" style={styles.heading}>
            Price check
          </Text>
          <Text style={styles.description}>See prices from nearby stores.</Text>

          <Image
            accessibilityLabel={`${selectedItem.name} product illustration`}
            cachePolicy="memory-disk"
            contentFit="contain"
            source={selectedItem.imageSource}
            style={[styles.productArtwork, { height: artworkHeight }]}
          />

          <View style={styles.productSummary}>
            <Text style={styles.productName}>{selectedItem.name}</Text>
            {selectedItem.subtitle ? (
              <Text style={styles.productSubtitle}>{selectedItem.subtitle}</Text>
            ) : null}
          </View>

          <View style={styles.confirmationPanel}>
            <Text style={styles.question}>{variantConfirmation.question}</Text>
            <View style={styles.variantOptions}>
              {variantConfirmation.options.map((option) => (
                <VariantOptionCard
                  key={option.variantId}
                  onPress={() => handleSelectVariant(option)}
                  option={option}
                  selected={option.variantId === selectedOption.variantId}
                />
              ))}
            </View>
            {variantConfirmation.disclaimer ? (
              <View style={styles.disclaimerRow}>
                <Ionicons
                  accessibilityElementsHidden
                  color={priceCheckLocationTokens.colors.secondaryText}
                  name="information-circle-outline"
                  size={19}
                />
                <Text style={styles.disclaimer}>{variantConfirmation.disclaimer}</Text>
              </View>
            ) : null}
          </View>

          <Pressable
            accessibilityLabel="Check prices near you"
            accessibilityRole="button"
            onPress={() => onCheckPrices?.(selectedOption)}
            style={({ pressed }) => [styles.primaryCta, pressed && styles.pressed]}
          >
            <Text style={styles.primaryCtaLabel}>Check prices near you</Text>
            <Ionicons
              accessibilityElementsHidden
              color="#FFFFFF"
              name="arrow-forward"
              size={22}
            />
          </Pressable>

          <View style={styles.infoMessage}>
            <View style={styles.infoIconBubble}>
              <Ionicons
                accessibilityElementsHidden
                color={priceCheckLocationTokens.colors.orange}
                name="bulb-outline"
                size={24}
              />
            </View>
            <Text style={styles.infoMessageText}>{variantConfirmation.infoMessage}</Text>
          </View>
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  confirmationPanel: {
    backgroundColor: priceCheckLocationTokens.colors.cardCream,
    borderRadius: 24,
    marginTop: 16,
    paddingHorizontal: 16,
    paddingVertical: 17,
    shadowColor: priceCheckLocationTokens.shadow.color,
    shadowOffset: priceCheckLocationTokens.shadow.offset,
    shadowOpacity: priceCheckLocationTokens.shadow.opacity,
    shadowRadius: priceCheckLocationTokens.shadow.radius,
    elevation: priceCheckLocationTokens.shadow.elevation,
  },
  description: {
    color: priceCheckLocationTokens.colors.secondaryText,
    fontFamily: priceCheckLocationTokens.fonts.body,
    fontSize: 17,
    lineHeight: 23,
    marginTop: 4,
    textAlign: 'center',
  },
  disclaimer: {
    color: priceCheckLocationTokens.colors.secondaryText,
    flex: 1,
    fontFamily: priceCheckLocationTokens.fonts.body,
    fontSize: 13,
    lineHeight: 18,
    marginLeft: 7,
  },
  disclaimerRow: {
    alignItems: 'flex-start',
    flexDirection: 'row',
    marginTop: 14,
    minHeight: 24,
  },
  fontLoading: {
    alignItems: 'center',
    backgroundColor: priceCheckLocationTokens.colors.background,
    flex: 1,
    justifyContent: 'center',
  },
  heading: {
    color: priceCheckLocationTokens.colors.deepTeal,
    fontFamily: priceCheckLocationTokens.fonts.heading,
    fontSize: 35,
    lineHeight: 42,
    textAlign: 'center',
  },
  infoIconBubble: {
    alignItems: 'center',
    backgroundColor: '#FFF0D9',
    borderRadius: 22,
    height: 44,
    justifyContent: 'center',
    width: 44,
  },
  infoMessage: {
    alignItems: 'center',
    backgroundColor: '#FFF8ED',
    borderRadius: 20,
    flexDirection: 'row',
    marginTop: 16,
    minHeight: 78,
    paddingHorizontal: 14,
    paddingVertical: 12,
  },
  infoMessageText: {
    color: priceCheckLocationTokens.colors.primaryText,
    flex: 1,
    fontFamily: priceCheckLocationTokens.fonts.bodySemibold,
    fontSize: 14,
    lineHeight: 19,
    marginLeft: 11,
  },
  pageContent: {
    paddingBottom: 24,
    paddingTop: 22,
  },
  pressed: {
    opacity: 0.78,
  },
  primaryCta: {
    alignItems: 'center',
    backgroundColor: priceCheckLocationTokens.colors.green,
    borderRadius: 30,
    flexDirection: 'row',
    justifyContent: 'center',
    marginTop: 18,
    minHeight: 56,
    paddingHorizontal: 20,
    shadowColor: priceCheckLocationTokens.colors.green,
    shadowOffset: { height: 5, width: 0 },
    shadowOpacity: 0.16,
    shadowRadius: 12,
    elevation: 2,
  },
  primaryCtaLabel: {
    color: '#FFFFFF',
    fontFamily: priceCheckLocationTokens.fonts.cardTitle,
    fontSize: 17,
    lineHeight: 22,
    marginRight: 12,
  },
  productArtwork: {
    alignSelf: 'center',
    marginTop: 10,
    width: '100%',
  },
  productName: {
    color: priceCheckLocationTokens.colors.deepTeal,
    fontFamily: priceCheckLocationTokens.fonts.cardTitle,
    fontSize: 23,
    lineHeight: 29,
    textAlign: 'center',
  },
  productSubtitle: {
    color: priceCheckLocationTokens.colors.secondaryText,
    fontFamily: priceCheckLocationTokens.fonts.body,
    fontSize: 15,
    lineHeight: 21,
    marginTop: 2,
    textAlign: 'center',
  },
  productSummary: {
    alignItems: 'center',
    marginTop: 2,
  },
  question: {
    color: priceCheckLocationTokens.colors.deepTeal,
    fontFamily: priceCheckLocationTokens.fonts.cardTitle,
    fontSize: 18,
    lineHeight: 24,
    textAlign: 'center',
  },
  screen: {
    backgroundColor: priceCheckLocationTokens.colors.background,
    flex: 1,
  },
  scrollContent: {
    paddingBottom: 2,
  },
  selectionIndicator: {
    alignItems: 'center',
    borderColor: '#BFCAC1',
    borderRadius: 12,
    borderWidth: 1.5,
    height: 24,
    justifyContent: 'center',
    marginLeft: 8,
    width: 24,
  },
  selectionIndicatorSelected: {
    backgroundColor: priceCheckLocationTokens.colors.green,
    borderColor: priceCheckLocationTokens.colors.green,
  },
  variantOption: {
    alignItems: 'center',
    backgroundColor: '#FFFCF6',
    borderColor: '#E7DFD1',
    borderRadius: 16,
    borderWidth: 1,
    flexBasis: 132,
    flexGrow: 1,
    flexDirection: 'row',
    minHeight: 82,
    minWidth: 132,
    paddingHorizontal: 12,
    paddingVertical: 10,
  },
  variantOptionCopy: {
    flex: 1,
    minWidth: 0,
  },
  variantOptionPrimary: {
    color: priceCheckLocationTokens.colors.deepTeal,
    fontFamily: priceCheckLocationTokens.fonts.cardTitle,
    fontSize: 16,
    lineHeight: 21,
  },
  variantOptionSecondary: {
    color: priceCheckLocationTokens.colors.secondaryText,
    fontFamily: priceCheckLocationTokens.fonts.body,
    fontSize: 13,
    lineHeight: 18,
    marginTop: 2,
  },
  variantOptionSelected: {
    backgroundColor: '#F3FAF4',
    borderColor: priceCheckLocationTokens.colors.green,
    borderWidth: 2,
  },
  variantOptions: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
    marginTop: 13,
  },
});
