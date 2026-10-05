import { Ionicons } from '@expo/vector-icons';
import { useFonts } from 'expo-font';
import { Image } from 'expo-image';
import type { ComponentProps } from 'react';
import {
  ActivityIndicator,
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
  formatPriceCheckPrice,
  getBestPriceResultId,
  getEffectiveSummaryBanner,
  getProductArtworkAccessibilityLabel,
  type PriceCheckPriceResult,
  type PriceCheckPremiseType,
  type PriceCheckResultsCommonData,
  type PriceCheckResultsData,
  type PriceCheckResultsSuccessData,
} from './priceCheckResultsContent';
import { getStoreDisplayName } from './storeDisplayName';

type IoniconName = ComponentProps<typeof Ionicons>['name'];

const TROPHY_IMAGE = require('../../assets/images/price-check/price-check-results-trophy.png');

export interface PriceCheckResultsScreenProps {
  data: PriceCheckResultsData;
  onBack?: () => void;
  onEditSelection?: () => void;
  onSelectPremise?: (result: PriceCheckPriceResult) => void;
  onOpenPriceInfo?: () => void;
}

function premiseTypeLabel(type: PriceCheckPremiseType): string {
  switch (type) {
    case 'minimarket':
      return 'Minimarket';
    case 'wet-market':
      return 'Wet market';
    case 'hypermarket':
      return 'Hypermarket';
    case 'other':
      return 'Grocery store';
    default:
      return 'Supermarket';
  }
}

function premisePresentation(type: PriceCheckPremiseType): {
  backgroundColor: string;
  iconColor: string;
  iconName: IoniconName;
} {
  switch (type) {
    case 'minimarket':
      return {
        backgroundColor: '#EAF5D9',
        iconColor: '#5C9C2B',
        iconName: 'basket-outline',
      };
    case 'wet-market':
      return {
        backgroundColor: '#FFF0D9',
        iconColor: priceCheckLocationTokens.colors.orange,
        iconName: 'storefront-outline',
      };
    case 'hypermarket':
      return {
        backgroundColor: '#E8F1F6',
        iconColor: '#3E7189',
        iconName: 'cart-outline',
      };
    case 'other':
      return {
        backgroundColor: '#F4ECE1',
        iconColor: priceCheckLocationTokens.colors.secondaryText,
        iconName: 'business-outline',
      };
    default:
      return {
        backgroundColor: '#EAF5D9',
        iconColor: priceCheckLocationTokens.colors.green,
        iconName: 'storefront-outline',
      };
  }
}

function formatDistance(distanceKm: number | null): string {
  return distanceKm === null ? 'Area match' : `${distanceKm.toFixed(1)} km`;
}

function SelectedProductSummary({
  data,
  compact,
  onEditSelection,
}: {
  data: PriceCheckResultsCommonData;
  compact: boolean;
  onEditSelection?: () => void;
}) {
  const selectedBasis = data.selectedVariant?.label ?? data.selectedItem.subtitle;
  const artworkSize = compact ? 88 : 108;

  return (
    <View>
      <View style={styles.productSummaryRow}>
        <Image
          accessibilityLabel={getProductArtworkAccessibilityLabel(data.selectedItem)}
          cachePolicy="memory-disk"
          contentFit="contain"
          source={data.selectedItem.imageSource}
          style={[styles.productArtwork, { height: artworkSize, width: artworkSize }]}
        />
        <View style={styles.productSummaryCopy}>
          <Text numberOfLines={2} style={[styles.productName, compact && styles.productNameCompact]}>
            {data.selectedItem.name}
          </Text>
          {selectedBasis ? (
            <Text numberOfLines={2} style={[styles.productBasis, compact && styles.productBasisCompact]}>
              {selectedBasis}
            </Text>
          ) : null}
        </View>
        <Pressable
          accessibilityLabel="Edit product selection"
          accessibilityRole="button"
          disabled={!onEditSelection}
          onPress={onEditSelection}
          style={({ pressed }) => [
            styles.editButton,
            compact && styles.editButtonCompact,
            pressed && styles.pressed,
          ]}
        >
          <Ionicons
            accessibilityElementsHidden
            color={priceCheckLocationTokens.colors.deepTeal}
            name="pencil"
            size={compact ? 18 : 20}
          />
          <Text style={[styles.editLabel, compact && styles.editLabelCompact]}>Edit</Text>
        </Pressable>
      </View>
      <View style={styles.locationContext}>
        <Ionicons
          accessibilityElementsHidden
          color={priceCheckLocationTokens.colors.orange}
          name="location-sharp"
          size={17}
        />
        <Text numberOfLines={2} style={styles.locationContextText}>
          Near {data.selectedLocation.label}
        </Text>
      </View>
    </View>
  );
}

function ResultSummaryBanner({
  banner,
}: {
  banner: NonNullable<ReturnType<typeof getEffectiveSummaryBanner>>;
}) {
  const isNeutral = banner.tone === 'neutral';

  return (
    <View style={[styles.summaryBanner, isNeutral && styles.summaryBannerNeutral]}>
      <View style={[styles.summaryBannerIcon, isNeutral && styles.summaryBannerIconNeutral]}>
        {isNeutral ? (
          <Ionicons
            accessibilityElementsHidden
            color={priceCheckLocationTokens.colors.green}
            name="analytics-outline"
            size={28}
          />
        ) : (
          <Image
            accessibilityElementsHidden
            cachePolicy="memory-disk"
            contentFit="contain"
            source={TROPHY_IMAGE}
            style={styles.summaryBannerAsset}
          />
        )}
      </View>
      <View style={styles.summaryBannerCopy}>
        <Text style={styles.summaryBannerTitle}>{banner.message}</Text>
        {banner.supportingCopy ? (
          <Text style={styles.summaryBannerSupporting}>{banner.supportingCopy}</Text>
        ) : null}
      </View>
    </View>
  );
}

function PriceResultRow({
  highlighted,
  onPress,
  result,
}: {
  highlighted: boolean;
  onPress?: () => void;
  result: PriceCheckPriceResult;
}) {
  const presentation = premisePresentation(result.premiseType);
  const storeName = getStoreDisplayName(result.premiseName);

  return (
    <Pressable
      accessibilityLabel={`${result.premiseName}, ${formatPriceCheckPrice(result)}, ${formatDistance(result.distanceKm)}`}
      accessibilityRole={onPress ? 'button' : undefined}
      disabled={!onPress}
      onPress={onPress}
      style={({ pressed }) => [styles.resultRow, pressed && styles.pressed]}
    >
      <View style={[styles.premiseAvatar, { backgroundColor: presentation.backgroundColor }]}>
        <Ionicons
          accessibilityElementsHidden
          color={presentation.iconColor}
          name={presentation.iconName}
          size={28}
        />
      </View>
      <View style={styles.resultCopy}>
        <Text numberOfLines={2} style={styles.premiseName}>
          {storeName.displayName}
        </Text>
        <Text numberOfLines={2} style={styles.premiseMeta}>
          {storeName.branch ? `${storeName.branch} · ` : ''}{formatDistance(result.distanceKm)} · {premiseTypeLabel(result.premiseType)}
        </Text>
      </View>
      <View style={[styles.priceBlock, highlighted && styles.priceBlockHighlighted]}>
        <Text adjustsFontSizeToFit numberOfLines={1} style={styles.priceText}>
          {formatPriceCheckPrice(result)}
        </Text>
      </View>
      <Ionicons
        accessibilityElementsHidden
        color={priceCheckLocationTokens.colors.secondaryText}
        name="chevron-forward"
        size={24}
        style={styles.resultChevron}
      />
    </Pressable>
  );
}

function PriceResultsList({
  data,
  onSelectPremise,
}: {
  data: PriceCheckResultsSuccessData;
  onSelectPremise?: (result: PriceCheckPriceResult) => void;
}) {
  const bestResultId = getBestPriceResultId(data.results, data.metadata);

  return (
    <View style={styles.resultsList}>
      {data.results.map((result, index) => (
        <View key={result.premiseId}>
          {index > 0 ? <View style={styles.resultDivider} /> : null}
          <PriceResultRow
            highlighted={result.premiseId === bestResultId}
            onPress={onSelectPremise ? () => onSelectPremise(result) : undefined}
            result={result}
          />
        </View>
      ))}
    </View>
  );
}

function PriceDataFooter({
  data,
  onOpenPriceInfo,
}: {
  data: PriceCheckResultsSuccessData;
  onOpenPriceInfo?: () => void;
}) {
  const updatedCopy = data.metadata.updatedDate
    ? ` · Updated ${data.metadata.updatedDate}`
    : '';

  return (
    <View style={styles.footerRow}>
      <Text style={styles.footerText}>
        Prices from {data.metadata.dataSource}{updatedCopy}
      </Text>
      <Pressable
        accessibilityLabel="About price data"
        accessibilityRole="button"
        disabled={!onOpenPriceInfo}
        onPress={onOpenPriceInfo}
        style={({ pressed }) => [styles.infoButton, pressed && styles.pressed]}
      >
        <Ionicons
          accessibilityElementsHidden
          color={priceCheckLocationTokens.colors.deepTeal}
          name="information-circle-outline"
          size={27}
        />
      </Pressable>
    </View>
  );
}

function ResultStatePanel({ data }: { data: Exclude<PriceCheckResultsData, PriceCheckResultsSuccessData> }) {
  if (data.status === 'loading') {
    return (
      <View accessibilityLiveRegion="polite" style={styles.statePanel}>
        <ActivityIndicator color={priceCheckLocationTokens.colors.green} size="small" />
        <Text style={styles.stateTitle}>Finding nearby prices…</Text>
      </View>
    );
  }

  return (
    <View accessibilityLiveRegion="polite" style={styles.statePanel}>
      <Ionicons
        accessibilityElementsHidden
        color={priceCheckLocationTokens.colors.green}
        name={data.status === 'empty' ? 'search-outline' : 'cloud-offline-outline'}
        size={32}
      />
      <Text style={styles.stateTitle}>
        {data.status === 'empty' ? 'No comparable prices found nearby.' : 'Prices are unavailable right now.'}
      </Text>
      {data.message ? <Text style={styles.stateMessage}>{data.message}</Text> : null}
    </View>
  );
}

export function PriceCheckResultsScreen({
  data,
  onBack,
  onEditSelection,
  onOpenPriceInfo,
  onSelectPremise,
}: PriceCheckResultsScreenProps) {
  const { width } = useWindowDimensions();
  const [fontsLoaded] = useFonts(priceCheckLocationFontAssets);
  const compact = width <= 384;
  const horizontalPadding = width <= 360 ? 20 : width <= 384 ? 22 : 24;

  if (!fontsLoaded) {
    return (
      <View accessibilityLiveRegion="polite" style={styles.fontLoading}>
        <ActivityIndicator color={priceCheckLocationTokens.colors.green} size="small" />
      </View>
    );
  }

  const successData = data.status === 'success' ? data : null;
  const summaryBanner = successData
    ? getEffectiveSummaryBanner(successData.results, successData.metadata)
    : null;

  return (
    <View style={styles.screen}>
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        <PriceCheckHeader onBack={onBack} title="Price Check" titleWeight="semibold" />
        <View style={[styles.pageContent, { paddingHorizontal: horizontalPadding }]}>
          <SelectedProductSummary
            compact={compact}
            data={data}
            onEditSelection={onEditSelection}
          />

          {data.status === 'success' ? (
            <>
              {summaryBanner ? <ResultSummaryBanner banner={summaryBanner} /> : null}
              <Text style={styles.sectionHeading}>Nearby prices</Text>
              <PriceResultsList data={data} onSelectPremise={onSelectPremise} />
              <PriceDataFooter data={data} onOpenPriceInfo={onOpenPriceInfo} />
            </>
          ) : (
            <ResultStatePanel data={data} />
          )}
        </View>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  compactBackButton: {
    top: 6,
  },
  editButton: {
    alignItems: 'center',
    borderColor: '#DCE0DC',
    borderRadius: 25,
    borderWidth: 2,
    flexDirection: 'row',
    justifyContent: 'center',
    minHeight: 52,
    minWidth: 88,
    paddingHorizontal: 10,
  },
  editButtonCompact: {
    minHeight: 48,
    minWidth: 76,
    paddingHorizontal: 8,
  },
  editLabel: {
    color: priceCheckLocationTokens.colors.deepTeal,
    fontFamily: priceCheckLocationTokens.fonts.cardTitle,
    fontSize: 16,
    lineHeight: 20,
    marginLeft: 6,
  },
  editLabelCompact: {
    fontSize: 14,
    lineHeight: 18,
    marginLeft: 4,
  },
  footerRow: {
    alignItems: 'center',
    flexDirection: 'row',
    marginTop: 17,
    minHeight: 48,
  },
  footerText: {
    color: priceCheckLocationTokens.colors.secondaryText,
    flex: 1,
    fontFamily: priceCheckLocationTokens.fonts.body,
    fontSize: 14,
    lineHeight: 20,
  },
  fontLoading: {
    alignItems: 'center',
    backgroundColor: priceCheckLocationTokens.colors.background,
    flex: 1,
    justifyContent: 'center',
  },
  infoButton: {
    alignItems: 'center',
    height: 48,
    justifyContent: 'center',
    marginLeft: 4,
    width: 48,
  },
  locationContext: {
    alignItems: 'center',
    flexDirection: 'row',
    marginTop: 4,
    minHeight: 28,
  },
  locationContextText: {
    color: priceCheckLocationTokens.colors.secondaryText,
    flex: 1,
    fontFamily: priceCheckLocationTokens.fonts.bodySemibold,
    fontSize: 15,
    lineHeight: 20,
    marginLeft: 5,
  },
  pageContent: {
    paddingBottom: 30,
    paddingTop: 10,
  },
  premiseAvatar: {
    alignItems: 'center',
    borderRadius: 16,
    height: 54,
    justifyContent: 'center',
    width: 54,
  },
  premiseMeta: {
    color: priceCheckLocationTokens.colors.secondaryText,
    fontFamily: priceCheckLocationTokens.fonts.body,
    fontSize: 15,
    lineHeight: 20,
    marginTop: 2,
  },
  premiseName: {
    color: priceCheckLocationTokens.colors.deepTeal,
    fontFamily: priceCheckLocationTokens.fonts.bodySemibold,
    fontSize: 18,
    lineHeight: 23,
  },
  priceBlock: {
    alignItems: 'flex-end',
    justifyContent: 'center',
    marginLeft: 6,
    minWidth: 88,
    paddingHorizontal: 4,
    paddingVertical: 8,
  },
  priceBlockHighlighted: {
    backgroundColor: '#EDF8E9',
    borderRadius: 16,
    minWidth: 102,
    paddingHorizontal: 10,
  },
  priceText: {
    color: priceCheckLocationTokens.colors.deepTeal,
    fontFamily: priceCheckLocationTokens.fonts.cardTitle,
    fontSize: 20,
    lineHeight: 26,
    textAlign: 'right',
  },
  productArtwork: {
    flexGrow: 0,
    flexShrink: 0,
  },
  productBasis: {
    color: priceCheckLocationTokens.colors.secondaryText,
    fontFamily: priceCheckLocationTokens.fonts.body,
    fontSize: 18,
    lineHeight: 24,
    marginTop: 2,
  },
  productBasisCompact: {
    fontSize: 15,
    lineHeight: 20,
  },
  productName: {
    color: priceCheckLocationTokens.colors.deepTeal,
    fontFamily: priceCheckLocationTokens.fonts.cardTitle,
    fontSize: 28,
    lineHeight: 34,
  },
  productNameCompact: {
    fontSize: 25,
    lineHeight: 31,
  },
  productSummaryCopy: {
    flex: 1,
    minWidth: 0,
    paddingHorizontal: 8,
  },
  productSummaryRow: {
    alignItems: 'center',
    flexDirection: 'row',
    minHeight: 108,
  },
  pressed: {
    opacity: 0.76,
  },
  resultChevron: {
    flexShrink: 0,
    marginLeft: 1,
  },
  resultCopy: {
    flex: 1,
    minWidth: 0,
    paddingHorizontal: 9,
  },
  resultDivider: {
    backgroundColor: '#F0EBE2',
    height: 1,
    marginLeft: 12,
    marginRight: 12,
  },
  resultRow: {
    alignItems: 'center',
    flexDirection: 'row',
    minHeight: 92,
    paddingHorizontal: 12,
    paddingVertical: 13,
  },
  resultsList: {
    backgroundColor: '#FFFEFC',
    borderColor: '#EEE8DE',
    borderRadius: 22,
    borderWidth: 1,
    marginTop: 10,
    overflow: 'hidden',
  },
  screen: {
    backgroundColor: priceCheckLocationTokens.colors.background,
    flex: 1,
  },
  scrollContent: {
    paddingBottom: 4,
  },
  sectionHeading: {
    color: priceCheckLocationTokens.colors.deepTeal,
    fontFamily: priceCheckLocationTokens.fonts.cardTitle,
    fontSize: 23,
    lineHeight: 29,
    marginTop: 20,
  },
  stateMessage: {
    color: priceCheckLocationTokens.colors.secondaryText,
    fontFamily: priceCheckLocationTokens.fonts.body,
    fontSize: 15,
    lineHeight: 21,
    marginTop: 8,
    textAlign: 'center',
  },
  statePanel: {
    alignItems: 'center',
    backgroundColor: priceCheckLocationTokens.colors.cardCream,
    borderRadius: 24,
    marginTop: 24,
    paddingHorizontal: 20,
    paddingVertical: 30,
  },
  stateTitle: {
    color: priceCheckLocationTokens.colors.deepTeal,
    fontFamily: priceCheckLocationTokens.fonts.cardTitle,
    fontSize: 18,
    lineHeight: 24,
    marginTop: 12,
    textAlign: 'center',
  },
  summaryBanner: {
    alignItems: 'center',
    backgroundColor: '#EDF8E9',
    borderRadius: 24,
    flexDirection: 'row',
    marginTop: 17,
    minHeight: 96,
    paddingHorizontal: 15,
    paddingVertical: 11,
  },
  summaryBannerCopy: {
    flex: 1,
    minWidth: 0,
    paddingLeft: 13,
  },
  summaryBannerIcon: {
    alignItems: 'center',
    backgroundColor: '#FFF1D2',
    borderRadius: 27,
    height: 54,
    justifyContent: 'center',
    width: 54,
  },
  summaryBannerAsset: {
    height: 42,
    width: 42,
  },
  summaryBannerIconNeutral: {
    backgroundColor: '#E0F1E2',
  },
  summaryBannerNeutral: {
    backgroundColor: '#F1F8F0',
  },
  summaryBannerSupporting: {
    color: priceCheckLocationTokens.colors.deepTeal,
    fontFamily: priceCheckLocationTokens.fonts.body,
    fontSize: 15,
    lineHeight: 20,
    marginTop: 3,
  },
  summaryBannerTitle: {
    color: priceCheckLocationTokens.colors.deepTeal,
    fontFamily: priceCheckLocationTokens.fonts.cardTitle,
    fontSize: 21,
    lineHeight: 26,
  },
});
