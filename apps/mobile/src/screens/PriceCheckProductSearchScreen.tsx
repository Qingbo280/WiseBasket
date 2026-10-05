import { Ionicons } from '@expo/vector-icons';
import { useFonts } from 'expo-font';
import { Image } from 'expo-image';
import { useMemo, useState } from 'react';
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  type NativeScrollEvent,
  type NativeSyntheticEvent,
  useWindowDimensions,
  View,
} from 'react-native';
import { PriceCheckHeader } from '../components/price-check';
import {
  priceCheckLocationFontAssets,
  priceCheckLocationTokens,
} from '../components/price-check/priceCheckLocationTokens';
import {
  PRICE_CHECK_CATEGORIES,
  PRICE_CHECK_GRID_GAP,
  PRICE_CHECK_POPULAR_BACKEND_IDS,
  PRICE_CHECK_POPULAR_ITEMS,
  getPriceCheckGridTileWidth,
  filterPriceCheckCatalog,
  type PriceCheckCategory,
  type PriceCheckCategoryKey,
  type PriceCheckPopularItem,
} from './priceCheckProductSearchContent';
import type { PriceCheckCatalogEntry } from '../services/priceCheckCatalogApi';
import { foodImageUriForBackendId } from '../data/foodAssetManifest';

const HERO_IMAGE = require('../../assets/images/price-check-search/hero-product-search.png');
const CATALOG_BATCH_SIZE = 30;
const CATALOG_LOAD_MORE_THRESHOLD = 180;

function r2FoodImage(foodId: string, fallback: number) {
  const uri = foodImageUriForBackendId(foodId);
  return uri ? { uri } : fallback;
}

const TILE_IMAGES = {
  carbs: require('../../assets/images/price-check-search/categories/carbs.png'),
  cookingOil: r2FoodImage(
    PRICE_CHECK_POPULAR_BACKEND_IDS.cookingOil,
    require('../../assets/images/price-check-search/products/cooking-oil.png'),
  ),
  dairy: require('../../assets/images/price-check-search/categories/dairy.png'),
  eggs: r2FoodImage(
    PRICE_CHECK_POPULAR_BACKEND_IDS.eggs,
    require('../../assets/images/price-check-search/products/eggs.png'),
  ),
  fruit: require('../../assets/images/price-check-search/categories/fruit.png'),
  milk: r2FoodImage(
    PRICE_CHECK_POPULAR_BACKEND_IDS.milk,
    require('../../assets/images/price-check-search/products/milk.png'),
  ),
  other: require('../../assets/images/price-check-search/categories/other.png'),
  protein: require('../../assets/images/price-check-search/categories/protein.png'),
  rice: r2FoodImage(
    PRICE_CHECK_POPULAR_BACKEND_IDS.rice,
    require('../../assets/images/price-check-search/products/rice.png'),
  ),
  tomato: r2FoodImage(
    PRICE_CHECK_POPULAR_BACKEND_IDS.tomato,
    require('../../assets/images/price-check-search/products/tomato.png'),
  ),
  vegetables: require('../../assets/images/price-check-search/categories/vegetables.png'),
  chicken: r2FoodImage(
    PRICE_CHECK_POPULAR_BACKEND_IDS.chicken,
    require('../../assets/images/price-check-search/products/chicken.png'),
  ),
} as const;

type PriceCheckProductSearchScreenProps = {
  onBack?: () => void;
  onCategoryPress?: (category: PriceCheckCategory) => void;
  onPopularItemPress?: (item: PriceCheckPopularItem) => void;
  onSeeAllCategories?: () => void;
  onSeeAllPopular?: () => void;
  catalogItems?: readonly PriceCheckCatalogEntry[];
  catalogStatus?: 'loading' | 'ready' | 'error';
  catalogMessage?: string;
  onCatalogRetry?: () => void;
  onCatalogItemPress?: (item: PriceCheckCatalogEntry) => void;
};

type SearchTileProps = {
  compact?: boolean;
  item: PriceCheckCategory | PriceCheckPopularItem;
  onPress?: () => void;
  tileWidth: number;
};

function SectionHeader({
  onSeeAll,
  title,
}: {
  onSeeAll?: () => void;
  title: string;
}) {
  return (
    <View style={styles.sectionHeader}>
      <Text style={styles.sectionTitle}>{title}</Text>
      <Pressable
        accessibilityLabel={`See all ${title.toLowerCase()}`}
        accessibilityRole="button"
        onPress={onSeeAll}
        style={({ pressed }) => [styles.seeAllButton, pressed && styles.pressed]}
      >
        <Text style={styles.seeAllText}>See all</Text>
        <Ionicons
          accessibilityElementsHidden
          color={priceCheckLocationTokens.colors.green}
          name="chevron-forward"
          size={19}
        />
      </Pressable>
    </View>
  );
}

function SearchTile({ compact = false, item, onPress, tileWidth }: SearchTileProps) {
  return (
    <Pressable
      accessibilityLabel={`${item.label} price check item`}
      accessibilityRole="button"
      onPress={onPress}
      style={({ pressed }) => [
        styles.searchTile,
        compact && styles.compactSearchTile,
        { width: tileWidth },
        pressed && styles.pressed,
      ]}
    >
      <Image
        accessibilityElementsHidden
        cachePolicy="memory-disk"
        contentFit="contain"
        source={TILE_IMAGES[item.assetKey]}
        style={[styles.tileImage, compact && styles.compactTileImage]}
      />
      <Text numberOfLines={2} style={styles.tileLabel}>
        {item.label}
      </Text>
    </Pressable>
  );
}

export function PriceCheckProductSearchScreen({
  onBack,
  onCategoryPress,
  onPopularItemPress,
  onSeeAllCategories,
  onSeeAllPopular,
  catalogItems = [],
  catalogStatus = 'ready',
  catalogMessage,
  onCatalogRetry,
  onCatalogItemPress,
}: PriceCheckProductSearchScreenProps) {
  const { width } = useWindowDimensions();
  const [fontsLoaded] = useFonts(priceCheckLocationFontAssets);
  const [query, setQuery] = useState('');
  const [activeCategory, setActiveCategory] = useState<PriceCheckCategoryKey>();
  const [showCatalogue, setShowCatalogue] = useState(false);
  const [visibleCatalogCount, setVisibleCatalogCount] = useState(CATALOG_BATCH_SIZE);
  const compact = width >= 412;
  const horizontalPadding = width <= 360 ? 20 : width <= 384 ? 22 : 24;
  const tileWidth = getPriceCheckGridTileWidth(width, horizontalPadding);
  const filteredCatalog = useMemo(
    () => filterPriceCheckCatalog(catalogItems, query, activeCategory),
    [activeCategory, catalogItems, query],
  );
  const isSearching = query.trim().length > 0;
  const showResults = isSearching || showCatalogue;
  const visibleCatalogItems = filteredCatalog.slice(0, visibleCatalogCount);
  const resultsTitle = isSearching
    ? 'Search results'
    : activeCategory
      ? `${PRICE_CHECK_CATEGORIES.find((item) => item.assetKey === activeCategory)?.label ?? 'Category'} items`
      : 'All items';

  const openAllItems = () => {
    setActiveCategory(undefined);
    setQuery('');
    setVisibleCatalogCount(CATALOG_BATCH_SIZE);
    setShowCatalogue(true);
    if (catalogStatus === 'error') onCatalogRetry?.();
  };

  const closeCatalogueResults = () => {
    setActiveCategory(undefined);
    setQuery('');
    setVisibleCatalogCount(CATALOG_BATCH_SIZE);
    setShowCatalogue(false);
  };

  const handleBack = () => {
    if (showResults) {
      closeCatalogueResults();
      return;
    }

    onBack?.();
  };

  const openCategory = (category: PriceCheckCategory) => {
    setActiveCategory(category.assetKey);
    setQuery('');
    setVisibleCatalogCount(CATALOG_BATCH_SIZE);
    setShowCatalogue(true);
    onCategoryPress?.(category);
  };

  const handleQueryChange = (nextQuery: string) => {
    setQuery(nextQuery);
    setVisibleCatalogCount(CATALOG_BATCH_SIZE);
  };

  const handleCatalogueScroll = ({ nativeEvent }: NativeSyntheticEvent<NativeScrollEvent>) => {
    if (!showResults || visibleCatalogCount >= filteredCatalog.length) return;

    const distanceFromBottom = (
      nativeEvent.contentSize.height
      - nativeEvent.layoutMeasurement.height
      - nativeEvent.contentOffset.y
    );
    if (distanceFromBottom > CATALOG_LOAD_MORE_THRESHOLD) return;

    setVisibleCatalogCount((currentCount) => (
      Math.min(currentCount + CATALOG_BATCH_SIZE, filteredCatalog.length)
    ));
  };

  if (!fontsLoaded) {
    return (
      <View accessibilityLiveRegion="polite" style={styles.fontLoading}>
        <ActivityIndicator color={priceCheckLocationTokens.colors.green} size="small" />
      </View>
    );
  }

  return (
    <KeyboardAvoidingView
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      style={styles.screen}
    >
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        keyboardDismissMode="on-drag"
        keyboardShouldPersistTaps="handled"
        onScroll={handleCatalogueScroll}
        scrollEventThrottle={120}
        showsVerticalScrollIndicator={false}
      >
        <PriceCheckHeader compact={compact} onBack={handleBack} title="Price Check" />

        <View style={[styles.pageContent, compact && styles.compactPageContent]}>
          <View style={{ marginHorizontal: horizontalPadding }}>
            <Text style={styles.description}>Search an item to compare nearby prices.</Text>

            <View style={[styles.searchField, compact && styles.compactSearchField]}>
              <Ionicons
                accessibilityElementsHidden
                color={priceCheckLocationTokens.colors.deepTeal}
                name="search-outline"
                size={29}
                style={styles.searchIcon}
              />
              <TextInput
                accessibilityLabel="Search for an item"
                autoCorrect={false}
                onChangeText={handleQueryChange}
                onSubmitEditing={() => {
                  if (filteredCatalog.length === 1) onCatalogItemPress?.(filteredCatalog[0]);
                }}
                placeholder="Search for an item (e.g. eggs, rice)"
                placeholderTextColor={priceCheckLocationTokens.colors.secondaryText}
                returnKeyType="search"
                selectionColor={priceCheckLocationTokens.colors.green}
                style={styles.searchInput}
                value={query}
              />
            </View>

            {showResults ? (
              <View style={styles.catalogResults}>
                <View style={styles.catalogResultsHeader}>
                  <Text style={styles.sectionTitle}>{resultsTitle}</Text>
                  <Pressable
                    accessibilityLabel="Close catalogue results"
                    accessibilityRole="button"
                    onPress={closeCatalogueResults}
                    style={({ pressed }) => [styles.closeResultsButton, pressed && styles.pressed]}
                  >
                    <Text style={styles.closeResultsText}>Close</Text>
                  </Pressable>
                </View>
                {catalogStatus === 'loading' ? (
                  <View accessibilityLiveRegion="polite" style={styles.catalogFeedback}>
                    <ActivityIndicator color={priceCheckLocationTokens.colors.green} size="small" />
                    <Text style={styles.catalogFeedbackText}>Loading food catalogue...</Text>
                  </View>
                ) : catalogStatus === 'error' ? (
                  <View accessibilityLiveRegion="polite" style={styles.catalogErrorContainer}>
                    <Text style={styles.catalogError}>
                      {catalogMessage ?? 'Food catalogue is unavailable right now.'}
                    </Text>
                    <Pressable
                      accessibilityLabel="Try loading the food catalogue again"
                      accessibilityRole="button"
                      onPress={onCatalogRetry}
                      style={({ pressed }) => [styles.catalogRetryButton, pressed && styles.pressed]}
                    >
                      <Text style={styles.catalogRetryText}>Try again</Text>
                    </Pressable>
                  </View>
                ) : filteredCatalog.length === 0 ? (
                  <Text accessibilityLiveRegion="polite" style={styles.catalogFeedbackText}>
                    No matching foods found.
                  </Text>
                ) : (
                  visibleCatalogItems.map((item) => (
                    <Pressable
                      accessibilityLabel={`Check nearby prices for ${item.name}`}
                      accessibilityRole="button"
                      key={item.foodId}
                      onPress={() => onCatalogItemPress?.(item)}
                      style={({ pressed }) => [styles.catalogRow, pressed && styles.pressed]}
                    >
                      <Image
                        cachePolicy="memory-disk"
                        contentFit="contain"
                        source={item.imageSource}
                        style={styles.catalogRowImage}
                      />
                      <View style={styles.catalogRowCopy}>
                        <Text style={styles.catalogRowName}>{item.name}</Text>
                        <Text style={styles.catalogRowMeta}>
                          {[item.nameMs, item.subtitle].filter(Boolean).join(' · ') || 'Price comparison available'}
                        </Text>
                      </View>
                      <Ionicons color={priceCheckLocationTokens.colors.green} name="chevron-forward" size={22} />
                    </Pressable>
                  ))
                )}
              </View>
            ) : (
              <>

            <Image
              accessibilityLabel="WiseBasket grocery basket illustration"
              cachePolicy="memory-disk"
              contentFit="contain"
              source={HERO_IMAGE}
              style={[styles.heroImage, compact && styles.compactHeroImage]}
            />

            <View style={[styles.sectionBlock, compact && styles.compactSectionBlock]}>
              <SectionHeader
                onSeeAll={() => {
                  openAllItems();
                  onSeeAllPopular?.();
                }}
                title="Popular items"
              />
              <View style={styles.tileGrid}>
                {PRICE_CHECK_POPULAR_ITEMS.map((item) => (
                  <SearchTile
                    compact={compact}
                    item={item}
                    key={item.assetKey}
                    onPress={() => onPopularItemPress?.(item)}
                    tileWidth={tileWidth}
                  />
                ))}
              </View>
            </View>

            <View
              style={[
                styles.sectionBlock,
                styles.categorySection,
                compact && styles.compactCategorySection,
              ]}
            >
              <SectionHeader
                onSeeAll={() => {
                  openAllItems();
                  onSeeAllCategories?.();
                }}
                title="Browse by category"
              />
              <View style={styles.tileGrid}>
                {PRICE_CHECK_CATEGORIES.map((category) => (
                  <SearchTile
                    compact={compact}
                    item={category}
                    key={category.assetKey}
                    onPress={() => openCategory(category)}
                    tileWidth={tileWidth}
                  />
                ))}
              </View>
            </View>
              </>
            )}
          </View>
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  catalogError: {
    color: '#A23B32',
    fontFamily: priceCheckLocationTokens.fonts.body,
    fontSize: 15,
  },
  catalogErrorContainer: {
    alignItems: 'flex-start',
    marginTop: 12,
  },
  catalogFeedback: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 9,
    marginTop: 14,
  },
  catalogFeedbackText: {
    color: priceCheckLocationTokens.colors.secondaryText,
    fontFamily: priceCheckLocationTokens.fonts.body,
    fontSize: 15,
    marginTop: 12,
  },
  catalogResults: {
    marginTop: 18,
  },
  catalogResultsHeader: {
    alignItems: 'center',
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  catalogRetryButton: {
    alignItems: 'center',
    backgroundColor: priceCheckLocationTokens.colors.green,
    borderRadius: 18,
    justifyContent: 'center',
    marginTop: 12,
    minHeight: 40,
    paddingHorizontal: 18,
  },
  catalogRetryText: {
    color: '#FFFFFF',
    fontFamily: priceCheckLocationTokens.fonts.bodySemibold,
    fontSize: 15,
  },
  catalogRow: {
    alignItems: 'center',
    backgroundColor: priceCheckLocationTokens.colors.cardCream,
    borderColor: '#F5ECDE',
    borderRadius: 16,
    borderWidth: 1,
    flexDirection: 'row',
    marginTop: 9,
    minHeight: 74,
    paddingHorizontal: 12,
    paddingVertical: 8,
  },
  catalogRowCopy: {
    flex: 1,
    marginHorizontal: 10,
  },
  catalogRowImage: {
    height: 54,
    width: 54,
  },
  catalogRowMeta: {
    color: priceCheckLocationTokens.colors.secondaryText,
    fontFamily: priceCheckLocationTokens.fonts.body,
    fontSize: 13,
    marginTop: 2,
  },
  catalogRowName: {
    color: priceCheckLocationTokens.colors.deepTeal,
    fontFamily: priceCheckLocationTokens.fonts.bodySemibold,
    fontSize: 16,
  },
  closeResultsButton: {
    minHeight: 44,
    justifyContent: 'center',
    paddingLeft: 12,
  },
  closeResultsText: {
    color: priceCheckLocationTokens.colors.green,
    fontFamily: priceCheckLocationTokens.fonts.bodySemibold,
    fontSize: 15,
  },
  categorySection: {
    marginTop: 12,
  },
  compactCategorySection: {
    marginTop: 16,
  },
  description: {
    color: priceCheckLocationTokens.colors.secondaryText,
    fontFamily: priceCheckLocationTokens.fonts.body,
    fontSize: 17,
    lineHeight: 23,
    textAlign: 'center',
  },
  heroImage: {
    alignSelf: 'center',
    height: 166,
    marginTop: 4,
    width: '100%',
  },
  compactHeroImage: {
    height: 150,
    marginTop: 8,
  },
  pageContent: {
    paddingBottom: 24,
    paddingTop: 0,
  },
  compactPageContent: {
    paddingBottom: 16,
  },
  pressed: {
    opacity: 0.78,
  },
  fontLoading: {
    alignItems: 'center',
    backgroundColor: priceCheckLocationTokens.colors.background,
    flex: 1,
    justifyContent: 'center',
  },
  screen: {
    backgroundColor: priceCheckLocationTokens.colors.background,
    flex: 1,
  },
  scrollContent: {
    paddingBottom: 2,
  },
  searchField: {
    alignItems: 'center',
    backgroundColor: '#FFFEFC',
    borderColor: '#EEE8DE',
    borderRadius: 29,
    borderWidth: 1,
    flexDirection: 'row',
    height: 58,
    marginTop: 8,
    paddingHorizontal: 13,
  },
  compactSearchField: {
    height: 54,
  },
  searchIcon: {
    marginHorizontal: 3,
  },
  searchInput: {
    color: priceCheckLocationTokens.colors.deepTeal,
    flex: 1,
    fontFamily: priceCheckLocationTokens.fonts.body,
    fontSize: 17,
    lineHeight: 23,
    minWidth: 0,
    paddingHorizontal: 9,
    paddingVertical: 0,
  },
  searchTile: {
    alignItems: 'center',
    backgroundColor: priceCheckLocationTokens.colors.cardCream,
    borderColor: '#F5ECDE',
    borderRadius: 18,
    borderWidth: 1,
    height: 110,
    justifyContent: 'flex-start',
    minWidth: 0,
    paddingHorizontal: 5,
    paddingTop: 5,
  },
  compactSearchTile: {
    height: 98,
  },
  sectionBlock: {
    marginTop: 2,
  },
  compactSectionBlock: {
    marginTop: 12,
  },
  sectionHeader: {
    alignItems: 'center',
    flexDirection: 'row',
    justifyContent: 'space-between',
    minHeight: 34,
  },
  sectionTitle: {
    color: priceCheckLocationTokens.colors.deepTeal,
    flexShrink: 1,
    fontFamily: priceCheckLocationTokens.fonts.heading,
    fontSize: 22,
    lineHeight: 28,
  },
  seeAllButton: {
    alignItems: 'center',
    flexDirection: 'row',
    minHeight: 48,
    paddingLeft: 8,
    paddingRight: 0,
  },
  seeAllText: {
    color: priceCheckLocationTokens.colors.green,
    fontFamily: priceCheckLocationTokens.fonts.bodySemibold,
    fontSize: 16,
    lineHeight: 21,
  },
  tileGrid: {
    columnGap: PRICE_CHECK_GRID_GAP,
    flexDirection: 'row',
    flexWrap: 'wrap',
    rowGap: PRICE_CHECK_GRID_GAP,
    marginTop: 2,
  },
  tileImage: {
    height: 75,
    width: '100%',
  },
  compactTileImage: {
    height: 58,
  },
  tileLabel: {
    color: priceCheckLocationTokens.colors.deepTeal,
    fontFamily: priceCheckLocationTokens.fonts.cardTitle,
    fontSize: 14,
    lineHeight: 17,
    marginTop: 1,
    textAlign: 'center',
  },
});
