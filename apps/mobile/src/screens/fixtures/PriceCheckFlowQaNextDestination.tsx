import { StyleSheet, Text, View } from 'react-native';
import { PriceCheckHeader } from '../../components/price-check';
import { priceCheckLocationTokens } from '../../components/price-check/priceCheckLocationTokens';
import type { PriceCheckSelectedItem } from '../priceCheckItemVariantConfirmationContent';

interface PriceCheckFlowQaNextDestinationProps {
  selectedItem: PriceCheckSelectedItem;
  onBack: () => void;
  status: 'confirmed-selection' | 'skipped-confirmation';
}

/**
 * VISUAL / FLOW QA ONLY.
 *
 * This is not a Price Comparison screen. It only proves that an item with no
 * required variant confirmation leaves the confirmation step.
 */
export function PriceCheckFlowQaNextDestination({
  onBack,
  selectedItem,
  status,
}: PriceCheckFlowQaNextDestinationProps) {
  const confirmationMessage = status === 'skipped-confirmation'
    ? 'Confirmation was skipped for this selected product.'
    : 'Variant confirmation completed for this selected product.';

  return (
    <View style={styles.screen}>
      <PriceCheckHeader onBack={onBack} />
      <View style={styles.content}>
        <Text accessibilityRole="header" style={styles.eyebrow}>
          QA only
        </Text>
        <Text style={styles.heading}>Next destination</Text>
        <Text style={styles.description}>{confirmationMessage}</Text>
        <View style={styles.card}>
          <Text style={styles.cardLabel}>Selected product</Text>
          <Text style={styles.productName}>{selectedItem.name}</Text>
          {selectedItem.subtitle ? (
            <Text style={styles.productSubtitle}>{selectedItem.subtitle}</Text>
          ) : null}
          <Text style={styles.note}>
            A real Price Comparison destination is not implemented yet.
          </Text>
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: priceCheckLocationTokens.colors.cardCream,
    borderRadius: 24,
    marginTop: 28,
    padding: 20,
  },
  cardLabel: {
    color: priceCheckLocationTokens.colors.secondaryText,
    fontFamily: priceCheckLocationTokens.fonts.bodySemibold,
    fontSize: 14,
    lineHeight: 19,
  },
  content: {
    paddingHorizontal: 24,
    paddingTop: 34,
  },
  description: {
    color: priceCheckLocationTokens.colors.secondaryText,
    fontFamily: priceCheckLocationTokens.fonts.body,
    fontSize: 17,
    lineHeight: 24,
    marginTop: 10,
  },
  eyebrow: {
    color: priceCheckLocationTokens.colors.orange,
    fontFamily: priceCheckLocationTokens.fonts.bodySemibold,
    fontSize: 14,
    lineHeight: 19,
    textTransform: 'uppercase',
  },
  heading: {
    color: priceCheckLocationTokens.colors.deepTeal,
    fontFamily: priceCheckLocationTokens.fonts.heading,
    fontSize: 34,
    lineHeight: 41,
    marginTop: 4,
  },
  note: {
    color: priceCheckLocationTokens.colors.secondaryText,
    fontFamily: priceCheckLocationTokens.fonts.body,
    fontSize: 14,
    lineHeight: 20,
    marginTop: 22,
  },
  productName: {
    color: priceCheckLocationTokens.colors.deepTeal,
    fontFamily: priceCheckLocationTokens.fonts.cardTitle,
    fontSize: 24,
    lineHeight: 30,
    marginTop: 6,
  },
  productSubtitle: {
    color: priceCheckLocationTokens.colors.secondaryText,
    fontFamily: priceCheckLocationTokens.fonts.body,
    fontSize: 16,
    lineHeight: 22,
    marginTop: 2,
  },
  screen: {
    backgroundColor: priceCheckLocationTokens.colors.background,
    flex: 1,
  },
});
