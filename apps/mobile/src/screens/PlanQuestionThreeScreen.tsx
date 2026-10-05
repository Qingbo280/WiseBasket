import { MaterialCommunityIcons } from '@expo/vector-icons';
import { useFonts } from 'expo-font';
import { useEffect, useState } from 'react';
import {
  Image,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  type ImageSourcePropType,
  View,
} from 'react-native';
import {
  getVisibleProducts,
  isBuildBasketDisabled,
  PLAN_QUESTION_THREE_CATEGORIES,
  PLAN_QUESTION_THREE_DEFAULTS,
  toggleProductSelection,
  type PlanQuestionThreeCategoryId,
  type PlanQuestionThreeProduct,
  type PlanQuestionThreeProductId,
} from './planQuestionThreeContent';
import {
  priceCheckLocationFontAssets,
  priceCheckLocationFonts,
  priceCheckLocationTokens,
} from '../components/price-check/priceCheckLocationTokens';
import { BasketItemImage } from '../components/BasketItemImage';

const CATEGORY_ART: Record<PlanQuestionThreeCategoryId, ImageSourcePropType> = {
  carbs: require('../../assets/images/price-check-search/categories/carbs.png'),
  fruit: require('../../assets/images/price-check-search/categories/fruit.png'),
  other: require('../../assets/images/price-check-search/categories/other.png'),
  protein: require('../../assets/images/price-check-search/categories/protein.png'),
  vege: require('../../assets/images/price-check-search/categories/vegetables.png'),
};

const CATEGORY_TINTS: Record<PlanQuestionThreeCategoryId, string> = {
  carbs: '#FFF8E9',
  fruit: '#FFF9E8',
  other: '#F5F1FF',
  protein: '#F0FFF4',
  vege: '#F1FAF6',
};

const PLAN_QUESTION_THREE_COLORS = {
  background: priceCheckLocationTokens.colors.background,
  buttonTeal: '#087C7E',
  card: '#FFFEFC',
  deepTeal: priceCheckLocationTokens.colors.deepTeal,
  muted: priceCheckLocationTokens.colors.secondaryText,
  progressInactive: '#E9EDEC',
  selectedBorder: '#56C997',
  selectedCard: '#EFF9F3',
  selectedCheck: '#16885D',
  summaryPanel: '#F1FAF6',
  white: '#FFFFFF',
} as const;

const PLAN_QUESTION_THREE_FONT_ASSETS = priceCheckLocationFontAssets;
const PLAN_QUESTION_THREE_FONTS = priceCheckLocationFonts;

export interface PlanQuestionThreeScreenProps {
  isEditingPersonalization?: boolean;
  isEditingSection?: boolean;
  initialSelectedProductIds?: readonly PlanQuestionThreeProductId[];
  catalogStatus?: 'loading' | 'ready' | 'error';
  catalogMessage?: string | null;
  buildBusy?: boolean;
  buildError?: string | null;
  onBack?: () => void;
  onBuildBasket?: () => void;
  onCatalogRetry?: () => void;
  onSelectionChange?: (selectedProductIds: PlanQuestionThreeProductId[]) => void;
}

function QuestionnaireProgress() {
  return (
    <View
      accessibilityLabel="Step 3 of 3"
      accessibilityRole="progressbar"
      accessibilityValue={{ max: 3, min: 0, now: 3 }}
      style={styles.progress}
    >
      {Array.from({ length: 3 }, (_, index) => (
        <View
          key={`questionnaire-step-${index + 1}`}
          style={[styles.progressSegment, index < 3 && styles.progressSegmentActive]}
        />
      ))}
    </View>
  );
}

function CategoryOption({
  category,
  isSelected,
  onPress,
}: {
  category: (typeof PLAN_QUESTION_THREE_CATEGORIES)[number];
  isSelected: boolean;
  onPress: () => void;
}) {
  return (
    <Pressable
      accessibilityLabel={`${category.label} category`}
      accessibilityRole="button"
      accessibilityState={{ selected: isSelected }}
      onPress={onPress}
      style={({ pressed }) => [
        styles.categoryOption,
        { backgroundColor: CATEGORY_TINTS[category.id] },
        isSelected && styles.categoryOptionSelected,
        pressed && styles.pressed,
      ]}
    >
      <Image
        accessibilityElementsHidden
        source={CATEGORY_ART[category.id]}
        style={styles.categoryArt}
      />
      <Text style={styles.categoryLabel}>{category.label}</Text>
    </Pressable>
  );
}

function ProductCard({
  isSelected,
  onPress,
  product,
}: {
  isSelected: boolean;
  onPress: () => void;
  product: PlanQuestionThreeProduct;
}) {
  return (
    <Pressable
      accessibilityLabel={product.name}
      accessibilityRole="button"
      accessibilityState={{ selected: isSelected }}
      onPress={onPress}
      style={({ pressed }) => [
        styles.productCard,
        isSelected && styles.productCardSelected,
        pressed && styles.pressed,
      ]}
    >
      <BasketItemImage
        imageSource={product.imageSource}
        name={product.name}
        resizeMode="contain"
        style={styles.productArt}
      />
      <Text numberOfLines={2} style={styles.productName}>{product.name}</Text>
      {isSelected ? (
        <View accessibilityElementsHidden style={styles.productCheck}>
          <MaterialCommunityIcons color={PLAN_QUESTION_THREE_COLORS.white} name="check" size={17} />
        </View>
      ) : null}
    </Pressable>
  );
}

export function PlanQuestionThreeScreen({
  isEditingPersonalization = false,
  isEditingSection = false,
  initialSelectedProductIds = PLAN_QUESTION_THREE_DEFAULTS.selectedProductIds,
  catalogStatus = 'ready',
  catalogMessage = null,
  buildBusy = false,
  buildError = null,
  onBack,
  onBuildBasket,
  onCatalogRetry,
  onSelectionChange,
}: PlanQuestionThreeScreenProps) {
  const [fontsLoaded] = useFonts(PLAN_QUESTION_THREE_FONT_ASSETS);
  const [selectedCategory, setSelectedCategory] = useState<PlanQuestionThreeCategoryId>(
    PLAN_QUESTION_THREE_DEFAULTS.selectedCategory,
  );
  const [selectedProductIds, setSelectedProductIds] = useState<PlanQuestionThreeProductId[]>(
    [...initialSelectedProductIds],
  );
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    if (isEditingSection) {
      setSelectedCategory(PLAN_QUESTION_THREE_DEFAULTS.selectedCategory);
    }
  }, [isEditingSection]);

  useEffect(() => {
    onSelectionChange?.(selectedProductIds);
  }, [onSelectionChange, selectedProductIds]);

  const visibleProducts = getVisibleProducts(selectedCategory, searchQuery);
  const continueDisabled =
    isBuildBasketDisabled(selectedProductIds)
    || buildBusy;
  const isSearching = searchQuery.trim().length > 0;
  const selectedCategoryLabel = PLAN_QUESTION_THREE_CATEGORIES.find(
    (category) => category.id === selectedCategory,
  )?.label ?? selectedCategory;
  const productHeading = isSearching ? 'Search results' : selectedCategoryLabel;
  const continueLabel = isEditingSection ? 'Save changes' : isEditingPersonalization ? 'Save personalization' : 'Build my plan';
  const selectedCountLabel = selectedProductIds.length === 0
    ? 'Choose at least 1 food'
    : `${selectedProductIds.length} ${selectedProductIds.length === 1 ? 'food' : 'foods'} selected`;

  const toggleProduct = (productId: PlanQuestionThreeProductId) => {
    setSelectedProductIds((currentIds) => toggleProductSelection(currentIds, productId));
  };

  if (!fontsLoaded) {
    return <View style={styles.fontLoading} />;
  }

  return (
    <View style={styles.screen}>
      <View style={styles.topContent}>
        <View style={styles.header}>
          <Pressable
            accessibilityLabel="Go back"
            accessibilityRole="button"
            onPress={onBack}
            style={({ pressed }) => [styles.headerButton, pressed && styles.pressed]}
          >
            <MaterialCommunityIcons color={PLAN_QUESTION_THREE_COLORS.deepTeal} name="arrow-left" size={28} />
          </Pressable>
          <View style={styles.headerCenter}>
            <Text style={styles.stepText}>Step 3 of 3</Text>
            <QuestionnaireProgress />
          </View>
        </View>

        <View style={styles.pageCopy}>
          <Text accessibilityRole="header" style={styles.pageTitle}>What usually goes in your basket?</Text>
          <Text style={styles.pageSubtitle}>
            Pick the foods you buy most often so we can keep your plan familiar.
          </Text>
        </View>

        <View style={styles.searchBar}>
          <MaterialCommunityIcons
            color={PLAN_QUESTION_THREE_COLORS.muted}
            name="magnify"
            size={22}
          />
          <TextInput
            accessibilityLabel="Search foods"
            onChangeText={setSearchQuery}
            placeholder="Search foods"
            placeholderTextColor={PLAN_QUESTION_THREE_COLORS.muted}
            style={styles.searchInput}
            value={searchQuery}
          />
          {searchQuery.length > 0 ? (
            <Pressable
              accessibilityLabel="Clear food search"
              accessibilityRole="button"
              onPress={() => setSearchQuery('')}
              style={({ pressed }) => [styles.clearSearchButton, pressed && styles.pressed]}
            >
              <MaterialCommunityIcons color={PLAN_QUESTION_THREE_COLORS.muted} name="close" size={20} />
            </Pressable>
          ) : null}
        </View>

        <View style={styles.categoryRow}>
          {PLAN_QUESTION_THREE_CATEGORIES.map((category) => (
            <CategoryOption
              category={category}
              isSelected={selectedCategory === category.id}
              key={category.id}
              onPress={() => setSelectedCategory(category.id)}
            />
          ))}
        </View>
      </View>

      <View style={styles.productRegion}>
        <View style={styles.productHeadingRow}>
          <Text accessibilityRole="header" style={styles.productHeading}>{productHeading}</Text>
        </View>

        <ScrollView
          contentContainerStyle={styles.productScrollContent}
          showsVerticalScrollIndicator={false}
          style={styles.productScroll}
        >
          {visibleProducts.length > 0 ? (
            <View style={styles.productGrid}>
              {visibleProducts.map((product) => (
                <ProductCard
                  isSelected={selectedProductIds.includes(product.id)}
                  key={product.id}
                  onPress={() => toggleProduct(product.id)}
                  product={product}
                />
              ))}
            </View>
          ) : catalogStatus === 'loading' ? (
            <View style={styles.emptySearchState}>
              <Text style={styles.emptySearchText}>Loading foods…</Text>
            </View>
          ) : catalogStatus === 'error' ? (
            <View style={styles.emptySearchState}>
              <MaterialCommunityIcons
                color={PLAN_QUESTION_THREE_COLORS.muted}
                name="cloud-off-outline"
                size={32}
              />
              <Text style={styles.emptySearchText}>
                {catalogMessage ?? 'Food catalogue is unavailable.'}
              </Text>
              <Pressable
                accessibilityLabel="Retry food catalogue"
                accessibilityRole="button"
                onPress={onCatalogRetry}
                style={({ pressed }) => [styles.retryButton, pressed && styles.pressed]}
              >
                <Text style={styles.retryButtonText}>Try again</Text>
              </Pressable>
            </View>
          ) : (
            <View style={styles.emptySearchState}>
              <MaterialCommunityIcons
                color={PLAN_QUESTION_THREE_COLORS.muted}
                name="food-off-outline"
                size={32}
              />
              <Text style={styles.emptySearchText}>No matching foods found.</Text>
            </View>
          )}
        </ScrollView>
      </View>

      <View style={styles.footer}>
        <View style={styles.footerActionRow}>
          <Text accessibilityLiveRegion="polite" numberOfLines={2} style={styles.footerSelectedCount}>
            {selectedCountLabel}
          </Text>
          <Pressable
            accessibilityLabel={continueLabel}
            accessibilityRole="button"
            accessibilityState={{ disabled: continueDisabled }}
            disabled={continueDisabled}
            onPress={onBuildBasket}
            style={({ pressed }) => [
              styles.continueButton,
              continueDisabled && styles.continueButtonDisabled,
              pressed && styles.continueButtonPressed,
            ]}
          >
            <Text numberOfLines={1} style={styles.continueText}>
              {buildBusy
                ? (isEditingSection || isEditingPersonalization ? 'Saving your preferences…' : 'Building your plan…')
                : continueLabel}
            </Text>
          <MaterialCommunityIcons color={PLAN_QUESTION_THREE_COLORS.white} name="arrow-right" size={28} />
          </Pressable>
        </View>
        {buildError ? <Text style={styles.buildErrorText}>{buildError}</Text> : null}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  categoryRow: {
    flexDirection: 'row',
    gap: 5,
    marginTop: 9,
  },
  categoryLabel: {
    color: PLAN_QUESTION_THREE_COLORS.deepTeal,
    fontFamily: PLAN_QUESTION_THREE_FONTS.bodySemibold,
    fontSize: 12,
    lineHeight: 15,
    textAlign: 'center',
  },
  categoryArt: {
    height: 28,
    marginBottom: 1,
    resizeMode: 'contain',
    width: 34,
  },
  categoryOption: {
    alignItems: 'center',
    backgroundColor: PLAN_QUESTION_THREE_COLORS.card,
    borderColor: 'transparent',
    borderRadius: 14,
    borderWidth: 2,
    flex: 1,
    height: 58,
    justifyContent: 'center',
    minWidth: 0,
    paddingHorizontal: 1,
  },
  categoryOptionSelected: {
    backgroundColor: PLAN_QUESTION_THREE_COLORS.selectedCard,
    borderColor: PLAN_QUESTION_THREE_COLORS.selectedBorder,
  },
  clearSearchButton: {
    alignItems: 'center',
    height: 48,
    justifyContent: 'center',
    width: 48,
  },
  emptySearchState: {
    alignItems: 'center',
    gap: 8,
    justifyContent: 'center',
    minHeight: 150,
    paddingHorizontal: 20,
  },
  emptySearchText: {
    color: PLAN_QUESTION_THREE_COLORS.muted,
    fontFamily: PLAN_QUESTION_THREE_FONTS.bodySemibold,
    fontSize: 16,
    lineHeight: 20,
    textAlign: 'center',
  },
  footer: {
    backgroundColor: PLAN_QUESTION_THREE_COLORS.background,
    paddingBottom: 10,
    paddingHorizontal: 12,
    paddingTop: 8,
  },
  footerActionRow: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 10,
  },
  footerSelectedCount: {
    color: PLAN_QUESTION_THREE_COLORS.deepTeal,
    flex: 1,
    fontFamily: PLAN_QUESTION_THREE_FONTS.bodySemibold,
    fontSize: 14,
    lineHeight: 18,
    minWidth: 0,
  },
  buildErrorText: {
    color: '#B3261E',
    fontFamily: PLAN_QUESTION_THREE_FONTS.bodySemibold,
    fontSize: 12,
    lineHeight: 16,
    marginTop: 8,
    textAlign: 'center',
  },
  continueButton: {
    alignItems: 'center',
    backgroundColor: PLAN_QUESTION_THREE_COLORS.buttonTeal,
    borderRadius: 34,
    flexDirection: 'row',
    flex: 1,
    gap: 8,
    height: 58,
    justifyContent: 'center',
    minWidth: 0,
    paddingHorizontal: 12,
  },
  continueButtonDisabled: {
    backgroundColor: '#D8DFDD',
  },
  continueButtonPressed: {
    opacity: 0.86,
  },
  continueText: {
    color: PLAN_QUESTION_THREE_COLORS.white,
    fontFamily: PLAN_QUESTION_THREE_FONTS.bodySemibold,
    fontSize: 18,
    lineHeight: 22,
  },
  fontLoading: {
    backgroundColor: PLAN_QUESTION_THREE_COLORS.background,
    flex: 1,
  },
  header: {
    alignItems: 'center',
    flexDirection: 'row',
    height: 58,
    justifyContent: 'center',
    position: 'relative',
  },
  headerButton: {
    alignItems: 'center',
    height: 48,
    justifyContent: 'center',
    left: 0,
    position: 'absolute',
    top: 5,
    width: 48,
  },
  headerCenter: {
    alignItems: 'center',
    gap: 4,
  },
  pageCopy: {
    marginHorizontal: 8,
    marginTop: 6,
  },
  pageSubtitle: {
    color: PLAN_QUESTION_THREE_COLORS.muted,
    fontFamily: PLAN_QUESTION_THREE_FONTS.body,
    fontSize: 15,
    lineHeight: 20,
    marginTop: 5,
  },
  pageTitle: {
    color: PLAN_QUESTION_THREE_COLORS.deepTeal,
    fontFamily: PLAN_QUESTION_THREE_FONTS.heading,
    fontSize: 28,
    lineHeight: 34,
  },
  pressed: {
    opacity: 0.72,
  },
  productArt: {
    height: 58,
    marginTop: 2,
    resizeMode: 'contain',
    width: '80%',
  },
  productCard: {
    alignItems: 'center',
    backgroundColor: PLAN_QUESTION_THREE_COLORS.card,
    borderColor: 'transparent',
    borderRadius: 15,
    borderWidth: 2,
    flexBasis: '31.5%',
    flexGrow: 1,
    height: 116,
    minWidth: 0,
    paddingHorizontal: 6,
    position: 'relative',
  },
  productArtFallback: {
    alignItems: 'center',
    backgroundColor: PLAN_QUESTION_THREE_COLORS.summaryPanel,
    justifyContent: 'center',
  },
  productArtFallbackText: {
    color: PLAN_QUESTION_THREE_COLORS.deepTeal,
    fontFamily: PLAN_QUESTION_THREE_FONTS.bodySemibold,
    fontSize: 18,
  },
  productCardSelected: {
    backgroundColor: PLAN_QUESTION_THREE_COLORS.selectedCard,
    borderColor: PLAN_QUESTION_THREE_COLORS.selectedBorder,
  },
  productCheck: {
    alignItems: 'center',
    backgroundColor: PLAN_QUESTION_THREE_COLORS.selectedCheck,
    borderRadius: 13,
    height: 25,
    justifyContent: 'center',
    position: 'absolute',
    right: 5,
    top: 5,
    width: 25,
  },
  productGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 7,
    marginTop: 10,
  },
  productHeading: {
    color: PLAN_QUESTION_THREE_COLORS.deepTeal,
    fontFamily: PLAN_QUESTION_THREE_FONTS.heading,
    fontSize: 20,
    lineHeight: 25,
  },
  productHeadingRow: {
    alignItems: 'flex-end',
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: 13,
    paddingHorizontal: 2,
  },
  productName: {
    color: PLAN_QUESTION_THREE_COLORS.deepTeal,
    fontFamily: PLAN_QUESTION_THREE_FONTS.bodySemibold,
    fontSize: 13,
    lineHeight: 16,
    marginBottom: 5,
    textAlign: 'center',
  },
  productRegion: {
    flex: 1,
    minHeight: 0,
    paddingHorizontal: 12,
  },
  productScroll: {
    flex: 1,
  },
  productScrollContent: {
    // The footer is a sibling in the screen's flex layout (not an overlay),
    // and App.tsx applies the device bottom safe area. Keep extra scroll room
    // so the last row clears the footer with comfortable breathing space.
    paddingBottom: 24,
  },
  progress: {
    flexDirection: 'row',
    gap: 6,
    height: 8,
    width: 174,
  },
  progressSegment: {
    backgroundColor: PLAN_QUESTION_THREE_COLORS.progressInactive,
    borderRadius: 5,
    flex: 1,
  },
  progressSegmentActive: {
    backgroundColor: priceCheckLocationTokens.colors.green,
  },
  retryButton: {
    alignItems: 'center',
    backgroundColor: PLAN_QUESTION_THREE_COLORS.deepTeal,
    borderRadius: 14,
    marginTop: 12,
    paddingHorizontal: 18,
    paddingVertical: 9,
  },
  retryButtonText: {
    color: PLAN_QUESTION_THREE_COLORS.card,
    fontFamily: PLAN_QUESTION_THREE_FONTS.bodySemibold,
    fontSize: 14,
    lineHeight: 18,
  },
  searchBar: {
    alignItems: 'center',
    backgroundColor: PLAN_QUESTION_THREE_COLORS.card,
    borderColor: '#DCE8E1',
    borderRadius: 16,
    borderWidth: 1,
    flexDirection: 'row',
    height: 50,
    marginTop: 13,
    paddingLeft: 12,
  },
  searchInput: {
    color: PLAN_QUESTION_THREE_COLORS.deepTeal,
    flex: 1,
    fontFamily: PLAN_QUESTION_THREE_FONTS.body,
    fontSize: 16,
    height: 48,
    lineHeight: 20,
    paddingHorizontal: 8,
    paddingVertical: 0,
  },
  screen: {
    backgroundColor: PLAN_QUESTION_THREE_COLORS.background,
    flex: 1,
  },
  stepText: {
    color: PLAN_QUESTION_THREE_COLORS.muted,
    fontFamily: PLAN_QUESTION_THREE_FONTS.bodySemibold,
    fontSize: 16,
    lineHeight: 20,
  },
  pageSecondarySubtitle: {
    color: PLAN_QUESTION_THREE_COLORS.muted,
    fontFamily: PLAN_QUESTION_THREE_FONTS.body,
    fontSize: 14,
    lineHeight: 18,
    marginTop: 2,
  },
  topContent: {
    flexShrink: 0,
    paddingHorizontal: 12,
    paddingTop: 2,
  },
});
