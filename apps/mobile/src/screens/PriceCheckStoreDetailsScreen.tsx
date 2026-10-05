import { Ionicons } from '@expo/vector-icons';
import { useFonts } from 'expo-font';
import { Image } from 'expo-image';
import { type ComponentProps, useEffect, useState } from 'react';
import {
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
import { shopLogoForLocation } from '../data/shopAssetManifest';
import { getStoreDisplayName } from './storeDisplayName';
import {
  formatStoreDetailsDistance,
  getPremiseInitial,
  getStoreDetailsPriceBasis,
  getStoreDetailsPriceLabel,
  priceCheckStoreDetailsLayout,
  type PriceCheckStoreDetailsData,
} from './priceCheckStoreDetailsContent';

type IoniconName = ComponentProps<typeof Ionicons>['name'];

export interface PriceCheckStoreDetailsScreenProps {
  data: PriceCheckStoreDetailsData;
  onBack?: () => void;
  onNext?: () => void;
}

function StoreHero({ data }: { data: PriceCheckStoreDetailsData }) {
  const { width } = useWindowDimensions();
  const [imageFailed, setImageFailed] = useState(false);
  const mappedShopImageUri = shopLogoForLocation(data.selectedPriceResult.premiseName)?.uri;
  const storeImage = data.storeImage ?? (mappedShopImageUri ? { uri: mappedShopImageUri } : undefined);
  const isMappedShopLogo = !data.storeImage && Boolean(mappedShopImageUri);
  const heroHeight = Math.min(
    120,
    Math.max(105, Math.round((width / 412) * priceCheckStoreDetailsLayout.heroHeightAt412)),
  );

  useEffect(() => {
    setImageFailed(false);
  }, [data.storeImage, mappedShopImageUri]);

  if (storeImage && !imageFailed) {
    return (
      <Image
        accessibilityLabel={`${data.selectedPriceResult.premiseName} ${isMappedShopLogo ? 'logo' : 'storefront'}`}
        cachePolicy="memory-disk"
        contentFit={isMappedShopLogo ? 'contain' : 'cover'}
        onError={() => setImageFailed(true)}
        source={storeImage}
        style={[styles.storeHero, { height: heroHeight }]}
      />
    );
  }

  return (
    <View style={[styles.storeHero, styles.storeHeroFallback, { height: heroHeight }]}>
      <Ionicons
        accessibilityElementsHidden
        color={priceCheckLocationTokens.colors.green}
        name="storefront-outline"
        size={44}
      />
      <Text style={styles.storeHeroFallbackText}>Store photo unavailable</Text>
    </View>
  );
}

function StoreSummary({ data }: { data: PriceCheckStoreDetailsData }) {
  const premise = data.selectedPriceResult;
  const storeName = getStoreDisplayName(premise.premiseName);

  return (
    <View style={styles.storeSummaryCard}>
      <View style={styles.premiseAvatar}>
        <Text style={styles.premiseInitial}>
          {getPremiseInitial(premise.premiseName)}
        </Text>
      </View>
      <View style={styles.storeSummaryCopy}>
        <Text numberOfLines={2} style={styles.premiseName}>{storeName.displayName}</Text>
        {storeName.branch ? <Text style={styles.premiseDistance}>{storeName.branch}</Text> : null}
        <Text style={styles.premiseDistance}>
          {formatStoreDetailsDistance(premise.distanceKm)}
        </Text>
        {premise.address ? <Text style={styles.premiseAddress}>{premise.address}</Text> : null}
      </View>
    </View>
  );
}

function StoreProductPriceCard({ data }: { data: PriceCheckStoreDetailsData }) {
  const { width } = useWindowDimensions();
  const artworkSize = Math.min(
    84,
    Math.max(76, Math.round((width / 412) * priceCheckStoreDetailsLayout.productArtworkSizeAt412)),
  );
  const priceBasis = getStoreDetailsPriceBasis(data);
  const priceLabel = getStoreDetailsPriceLabel(data);
  const selectedBasis = data.selectedVariant?.label ?? data.selectedItem.subtitle;

  return (
    <View style={styles.productPriceCard}>
      <Image
        accessibilityLabel={`${data.selectedItem.name} product illustration`}
        cachePolicy="memory-disk"
        contentFit="contain"
        source={data.selectedItem.imageSource}
        style={{ height: artworkSize, width: artworkSize }}
      />
      <View style={styles.productTextColumn}>
        <Text numberOfLines={2} style={styles.productName}>
          {data.selectedItem.name}
        </Text>
        {selectedBasis ? (
          <Text numberOfLines={2} style={styles.productVariant}>
            {selectedBasis}
          </Text>
        ) : null}
      </View>
      <View style={styles.priceHighlight}>
        <Text numberOfLines={1} style={styles.priceLabel}>
          {priceLabel}
        </Text>
        <Text numberOfLines={2} style={styles.priceBasis}>
          {priceBasis}
        </Text>
      </View>
    </View>
  );
}

function PriceInformationRow({
  icon,
  label,
  value,
  multiline = false,
}: {
  icon: IoniconName;
  label: string;
  value: string;
  multiline?: boolean;
}) {
  return (
    <View style={[styles.informationRow, multiline && styles.informationNoteRow]}>
      <View style={styles.informationIcon}>
        <Ionicons
          accessibilityElementsHidden
          color={priceCheckLocationTokens.colors.deepTeal}
          name={icon}
          size={21}
        />
      </View>
      <Text style={styles.informationLabel}>{label}</Text>
      <Text style={styles.informationValue}>{value}</Text>
    </View>
  );
}

function PriceInformation({ data }: { data: PriceCheckStoreDetailsData }) {
  return (
    <View style={styles.informationSection}>
      <Text style={styles.sectionTitle}>Price information</Text>
      <View style={styles.informationTable}>
        <PriceInformationRow
          icon="calendar-outline"
          label="Last updated"
          value={data.metadata.updatedDate ?? 'Not available'}
        />
        <PriceInformationRow
          icon="pricetag-outline"
          label="Source"
          value={data.metadata.dataSource}
        />
        {data.metadata.note ? (
          <PriceInformationRow
            icon="information-circle-outline"
            label="Note"
            value={data.metadata.note}
            multiline
          />
        ) : null}
      </View>
    </View>
  );
}

export function PriceCheckStoreDetailsScreen({
  data,
  onBack,
  onNext,
}: PriceCheckStoreDetailsScreenProps) {
  const [fontsLoaded] = useFonts(priceCheckLocationFontAssets);

  if (!fontsLoaded) {
    return <View style={styles.loadingScreen} />;
  }

  return (
    <View style={styles.screen}>
      <PriceCheckHeader compact onBack={onBack} />
      <ScrollView
        contentContainerStyle={styles.content}
        showsVerticalScrollIndicator={false}
      >
        <Text accessibilityRole="header" style={styles.pageTitle}>
          Store details
        </Text>
        <StoreHero data={data} />
        <StoreSummary data={data} />
        <StoreProductPriceCard data={data} />
        <PriceInformation data={data} />
        <View style={styles.nextActionArea}>
          <Pressable
            accessibilityLabel="Next"
            accessibilityRole="button"
            disabled={!onNext}
            onPress={onNext}
            style={({ pressed }) => [styles.nextButton, pressed && styles.pressed]}
          >
            <Text style={styles.nextButtonLabel}>Next</Text>
            <Ionicons
              accessibilityElementsHidden
              color="#FFFFFF"
              name="arrow-forward"
              size={22}
            />
          </Pressable>
        </View>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: {
    backgroundColor: priceCheckLocationTokens.colors.background,
    flex: 1,
  },
  loadingScreen: {
    backgroundColor: priceCheckLocationTokens.colors.background,
    flex: 1,
  },
  content: {
    flexGrow: 1,
    paddingBottom: priceCheckStoreDetailsLayout.bottomPadding,
    paddingHorizontal: priceCheckLocationTokens.spacing.pageHorizontal,
  },
  pageTitle: {
    color: priceCheckLocationTokens.colors.deepTeal,
    fontFamily: priceCheckLocationTokens.fonts.heading,
    fontSize: priceCheckStoreDetailsLayout.pageTitleFontSize,
    lineHeight: 34,
    marginBottom: 8,
  },
  storeHero: {
    backgroundColor: '#EAF5D9',
    borderRadius: 20,
    overflow: 'hidden',
    width: '100%',
  },
  storeHeroFallback: {
    alignItems: 'center',
    backgroundColor: '#EAF5D9',
    justifyContent: 'center',
  },
  storeHeroFallbackText: {
    color: priceCheckLocationTokens.colors.secondaryText,
    fontFamily: priceCheckLocationTokens.fonts.bodySemibold,
    fontSize: 14,
    marginTop: 6,
  },
  storeSummaryCard: {
    alignItems: 'center',
    backgroundColor: '#FFFFFF',
    borderRadius: 26,
    elevation: 2,
    flexDirection: 'row',
    marginHorizontal: 4,
    marginTop: -16,
    paddingHorizontal: 16,
    paddingVertical: 13,
    shadowColor: priceCheckLocationTokens.shadow.color,
    shadowOffset: priceCheckLocationTokens.shadow.offset,
    shadowOpacity: priceCheckLocationTokens.shadow.opacity,
    shadowRadius: priceCheckLocationTokens.shadow.radius,
    zIndex: 1,
  },
  premiseAvatar: {
    alignItems: 'center',
    backgroundColor: priceCheckLocationTokens.colors.orange,
    borderRadius: 16,
    height: priceCheckStoreDetailsLayout.summaryAvatarSize,
    justifyContent: 'center',
    marginRight: 14,
    width: priceCheckStoreDetailsLayout.summaryAvatarSize,
  },
  premiseInitial: {
    color: '#FFFFFF',
    fontFamily: priceCheckLocationTokens.fonts.heading,
    fontSize: 32,
    lineHeight: 36,
  },
  storeSummaryCopy: {
    flex: 1,
    minWidth: 0,
  },
  premiseName: {
    color: priceCheckLocationTokens.colors.deepTeal,
    fontFamily: priceCheckLocationTokens.fonts.cardTitle,
    fontSize: 21,
    lineHeight: 25,
  },
  premiseDistance: {
    color: priceCheckLocationTokens.colors.secondaryText,
    fontFamily: priceCheckLocationTokens.fonts.body,
    fontSize: 15,
    lineHeight: 19,
    marginTop: 0,
  },
  premiseAddress: {
    color: priceCheckLocationTokens.colors.secondaryText,
    fontFamily: priceCheckLocationTokens.fonts.body,
    fontSize: 14,
    lineHeight: 18,
    marginTop: 0,
  },
  productPriceCard: {
    alignItems: 'center',
    backgroundColor: '#F0F8F1',
    borderRadius: 20,
    flexDirection: 'row',
    gap: priceCheckStoreDetailsLayout.productCardGap,
    marginTop: 20,
    minHeight: 124,
    paddingHorizontal: priceCheckStoreDetailsLayout.productCardHorizontalPadding,
    paddingVertical: 16,
  },
  productTextColumn: {
    flex: 1,
    justifyContent: 'center',
    minWidth: 0,
  },
  productName: {
    color: priceCheckLocationTokens.colors.deepTeal,
    fontFamily: priceCheckLocationTokens.fonts.cardTitle,
    fontSize: 21,
    lineHeight: 25,
  },
  productVariant: {
    color: priceCheckLocationTokens.colors.secondaryText,
    fontFamily: priceCheckLocationTokens.fonts.body,
    fontSize: 14,
    lineHeight: 18,
    marginTop: 0,
  },
  priceHighlight: {
    alignItems: 'flex-end',
    backgroundColor: '#DDF2E4',
    borderRadius: 12,
    flexShrink: 0,
    paddingHorizontal: priceCheckStoreDetailsLayout.priceBlockHorizontalPadding,
    paddingVertical: priceCheckStoreDetailsLayout.priceBlockVerticalPadding,
  },
  priceLabel: {
    color: priceCheckLocationTokens.colors.green,
    fontFamily: priceCheckLocationTokens.fonts.cardTitle,
    fontSize: 24,
    lineHeight: 28,
  },
  priceBasis: {
    color: priceCheckLocationTokens.colors.green,
    fontFamily: priceCheckLocationTokens.fonts.bodySemibold,
    fontSize: 14,
    lineHeight: 18,
    marginTop: 0,
  },
  informationSection: {
    marginTop: 22,
  },
  sectionTitle: {
    color: priceCheckLocationTokens.colors.deepTeal,
    fontFamily: priceCheckLocationTokens.fonts.cardTitle,
    fontSize: 21,
    lineHeight: 26,
    marginBottom: 4,
  },
  informationTable: {
    borderTopColor: '#DCE4E1',
    borderTopWidth: StyleSheet.hairlineWidth,
  },
  informationRow: {
    alignItems: 'flex-start',
    borderBottomColor: '#DCE4E1',
    borderBottomWidth: StyleSheet.hairlineWidth,
    flexDirection: 'row',
    minHeight: priceCheckStoreDetailsLayout.informationRowMinHeight,
    paddingVertical: 6,
  },
  informationNoteRow: {
    paddingVertical: priceCheckStoreDetailsLayout.informationNotePaddingVertical,
  },
  informationIcon: {
    alignItems: 'flex-start',
    justifyContent: 'flex-start',
    width: 34,
  },
  informationLabel: {
    color: priceCheckLocationTokens.colors.secondaryText,
    fontFamily: priceCheckLocationTokens.fonts.bodySemibold,
    fontSize: 14,
    lineHeight: 18,
    paddingRight: 6,
    width: 104,
  },
  informationValue: {
    color: priceCheckLocationTokens.colors.secondaryText,
    flex: 1,
    fontFamily: priceCheckLocationTokens.fonts.body,
    fontSize: 14,
    lineHeight: 18,
    minWidth: 0,
  },
  nextActionArea: {
    marginTop: 'auto',
    paddingTop: 28,
  },
  nextButton: {
    alignItems: 'center',
    backgroundColor: priceCheckLocationTokens.colors.green,
    borderRadius: 30,
    flexDirection: 'row',
    gap: 9,
    justifyContent: 'center',
    minHeight: priceCheckStoreDetailsLayout.nextButtonHeight,
    paddingHorizontal: 20,
  },
  nextButtonLabel: {
    color: '#FFFFFF',
    fontFamily: priceCheckLocationTokens.fonts.cardTitle,
    fontSize: 20,
    lineHeight: 25,
  },
  pressed: {
    opacity: 0.82,
  },
});
