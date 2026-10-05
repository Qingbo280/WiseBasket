import { Ionicons } from '@expo/vector-icons';
import { useFonts } from 'expo-font';
import { useState } from 'react';
import {
  Image,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import Svg, { Defs, LinearGradient as SvgLinearGradient, Rect, Stop } from 'react-native-svg';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { BasketItemImage } from '../components/BasketItemImage';
import {
  priceCheckLocationFontAssets,
  priceCheckLocationTokens,
} from '../components/price-check/priceCheckLocationTokens';
import type { PlanDraft } from './planFlowContent';
import { PlanSummary } from './PlanSummary';
import type {
  CheckPriceComparedItem,
  CheckPricePrototype,
  CheckPricePrototypeItem,
  CheckPriceStoreFixture,
} from './fixtures/demoPriceCalculator';
import type { BasketDraftItem } from './basketContent';
import { getStoreDisplayName } from './storeDisplayName';

const COLORS = {
  background: '#FBFBF6',
  softGreen: '#EFF9F1',
  green: '#0F8A83',
  deepTeal: '#012C2D',
  muted: '#486264',
  border: '#D9E9E4',
  white: '#FFFFFF',
} as const;

const HERO_BASKET_IMAGE = require('../../assets/price-check/cheerful_grocery_basket_mascot.png');
const COMPARE_STORES_IMAGE = require('../../assets/price-check/glossy_price_search_shop_mascot.png');
const LOWEST_PRICE_IMAGE = require('../../assets/price-check/cheerful_mint_price_tag_mascot.png');
const NO_RECENT_PRICE_IMAGE = require('../../assets/price-check/curious_magnifying_glass_tag.png');
const SHOPPING_LIST_IMAGE = require('../../assets/price-check/cheerful_grocery_list_basket_icon.png');
const BACK_CHEVRON_IMAGE = require('../../assets/images/price-check-reference/chevron-right.png');

export interface CheckPricesScreenProps {
  basketItems: readonly BasketDraftItem[];
  onAddAllToShoppingList?: () => void;
  onBack?: () => void;
  onSelectedStoreIdChange: (storeId: string | null) => void;
  planDraft: PlanDraft;
  prototype: CheckPricePrototype;
  selectedStoreId: string | null;
}

function formatCurrency(value: number | null): string {
  return value === null ? '—' : `RM ${value.toFixed(2)}`;
}

function formatItemPrice(item: CheckPricePrototypeItem): string {
  if (!item.hasRecentPrice || (item.priceMin === null && item.priceMax === null)) {
    return 'No recent price';
  }

  if (item.priceMin !== null && item.priceMax !== null && item.priceMin !== item.priceMax) {
    return `${item.priceMin.toFixed(2)} – ${item.priceMax.toFixed(2)}`;
  }

  return (item.priceMin ?? item.priceMax)!.toFixed(2);
}

function formatQuantity(item: { suggestedQuantity: number; unit: string }): string {
  return `${item.suggestedQuantity} ${item.unit}`;
}

function CheckPricesHero({ onBack }: { onBack?: () => void }) {
  return (
    <View style={styles.heroRegion}>
      <View pointerEvents="none" style={styles.heroGlow} />
      <View style={styles.heroHeader}>
        <Pressable
          accessibilityLabel="Go back"
          accessibilityRole="button"
          disabled={!onBack}
          onPress={onBack}
          style={({ pressed }) => [styles.heroBackButton, pressed && styles.pressed]}
        >
          <Image accessibilityElementsHidden source={BACK_CHEVRON_IMAGE} style={styles.heroBackIcon} />
        </Pressable>
        <Text accessibilityRole="header" style={styles.heroTitle}>Check Prices</Text>
        <View pointerEvents="none" style={styles.heroDecorationSlot}>
          <Image accessibilityElementsHidden resizeMode="contain" source={HERO_BASKET_IMAGE} style={styles.heroDecoration} />
        </View>
      </View>
    </View>
  );
}

interface CommonItemPricePreview {
  productId: string;
  name: string;
  imageSource: CheckPriceComparedItem['imageSource'];
  suggestedQuantity: number;
  unit: string;
  prices: readonly number[];
  spread: number;
}

interface OrderedCommonItemPricePreview extends CommonItemPricePreview {
  order: number;
}

function getCommonItemPricePreview(
  prototype: CheckPricePrototype,
  limit = 3,
): CommonItemPricePreview[] {
  if (prototype.stores.length === 0) return [];
  const basketItems = new Map(prototype.items.map((item) => [item.productId, item]));
  const candidates: OrderedCommonItemPricePreview[] = [];
  for (const [order, productId] of prototype.commonComparedItemIds.entries()) {
    const item = basketItems.get(productId);
    const storePrices = prototype.stores.map((store) =>
      store.comparedItems.find((comparedItem) => comparedItem.productId === productId),
    );
    if (!item || storePrices.some((comparedItem) => comparedItem === undefined)) continue;
    const prices = storePrices.map((comparedItem) => comparedItem!.price);
    candidates.push({
      productId,
      name: item.name,
      imageSource: item.imageSource,
      suggestedQuantity: item.suggestedQuantity,
      unit: item.unit,
      prices,
      spread: Math.max(...prices) - Math.min(...prices),
      order,
    });
  }
  return candidates
    .sort((left, right) => right.spread - left.spread || left.order - right.order)
    .slice(0, limit)
    .map(({ order: _order, ...item }) => item);
}

interface LowestPriceWins {
  counts: Record<string, number>;
  tiedItemCount: number;
}

function getUniqueLowestItemCounts(prototype: CheckPricePrototype): LowestPriceWins | null {
  if (prototype.commonComparedItemIds.length === 0 || prototype.stores.length < 2) return null;
  const counts = Object.fromEntries(prototype.stores.map((store) => [store.id, 0])) as Record<string, number>;
  let tiedItemCount = 0;
  for (const productId of prototype.commonComparedItemIds) {
    const prices = prototype.stores.map((store) =>
      store.comparedItems.find((item) => item.productId === productId)?.price,
    );
    if (prices.some((price) => price === undefined)) return null;
    const min = Math.min(...prices as number[]);
    const lowestIndexes = prototype.stores
      .map((store, index) => ({ store, index }))
      .filter(({ index }) => prices[index] === min);
    if (lowestIndexes.length !== 1) {
      tiedItemCount += 1;
      continue;
    }
    counts[lowestIndexes[0].store.id] += 1;
  }
  return { counts, tiedItemCount };
}

function YourItemsCard({ items }: { items: readonly CheckPricePrototypeItem[] }) {
  const [isExpanded, setIsExpanded] = useState(false);
  const pricedItems = items.filter((item) => item.hasRecentPrice);
  const noRecentPriceItems = items.filter((item) => !item.hasRecentPrice);

  return (
    <View style={styles.yourItemsCard}>
      <Pressable
        accessibilityRole="button"
        accessibilityState={{ expanded: isExpanded }}
        onPress={() => setIsExpanded((current) => !current)}
        style={({ pressed }) => [styles.yourItemsHeader, pressed && styles.pressed]}
      >
        <View>
          <View style={styles.basketHeadingRow}>
            <Text style={styles.cardHeading}>Your basket</Text>
            <Text style={styles.basketItemCount}>· {items.length} items</Text>
          </View>
          <Text style={styles.cardHelper}>{pricedItems.length} have recent prices</Text>
        </View>
        <View style={styles.viewPricesAction}>
          <Text style={styles.viewPricesText}>View prices</Text>
          <Ionicons
            color={COLORS.deepTeal}
            name={isExpanded ? 'chevron-up' : 'chevron-down'}
            size={20}
          />
        </View>
      </Pressable>
      {isExpanded ? (
        <View style={styles.itemPriceList}>
          {items.length === 0 ? <Text style={styles.emptyText}>No items in your basket yet.</Text> : null}
          {pricedItems.length > 0 ? <Text style={styles.detailGroupTitle}>Items with recent prices</Text> : null}
          {pricedItems.map((item) => (
            <View key={item.productId} style={styles.itemPriceRow}>
              <BasketItemImage
                imageSource={item.imageSource}
                name={item.name}
                resizeMode="contain"
                style={styles.itemThumbnail}
              />
              <View style={styles.itemPriceCopy}>
                <Text style={styles.itemName}>{item.name}</Text>
                <Text style={styles.itemQuantity}>{formatQuantity(item)}</Text>
              </View>
              <Text numberOfLines={1} style={styles.itemPrice}>
                {formatItemPrice(item)}
              </Text>
            </View>
          ))}
          {noRecentPriceItems.length > 0 ? (
            <View style={styles.basketMissingGroup}>
              <View style={styles.missingPriceHeading}>
                <Image accessibilityElementsHidden resizeMode="contain" source={NO_RECENT_PRICE_IMAGE} style={styles.missingPriceImage} />
                <View style={styles.missingPriceCopy}>
                  <Text style={styles.detailGroupTitle}>{noRecentPriceItems.length} items without recent prices</Text>
                  <Text style={styles.unpricedNote}>No recent price doesn’t necessarily mean the item isn’t sold here.</Text>
                </View>
              </View>
              {noRecentPriceItems.map((item) => (
                <View key={item.productId} style={styles.unmatchedPriceRow}>
                  <BasketItemImage imageSource={item.imageSource} name={item.name} resizeMode="contain" style={styles.comparedThumbnail} />
                  <View style={styles.comparedCopy}>
                    <Text style={styles.sheetProductName}>{item.name}</Text>
                    <Text style={styles.sheetQuantity}>{formatQuantity(item)}</Text>
                  </View>
                </View>
              ))}
            </View>
          ) : null}
        </View>
      ) : null}
    </View>
  );
}

function StoreCard({
  lowestTotal,
  onViewDetails,
  store,
}: {
  lowestTotal: number | null;
  onViewDetails: () => void;
  store: CheckPriceStoreFixture;
}) {
  const total = store.comparedTotal;
  const { displayName, branch } = getStoreDisplayName(store.name);
  const priceDifference = total !== null && lowestTotal !== null
    ? Math.max(0, Math.round((total - lowestTotal + Number.EPSILON) * 100) / 100)
    : null;

  return (
    <Pressable
      accessibilityLabel={`View ${store.name} details`}
      accessibilityRole="button"
      onPress={onViewDetails}
      style={({ pressed }) => [
        styles.storeColumn,
        store.isLowestComparedTotal && styles.storeColumnLowest,
        pressed && styles.pressed,
      ]}
    >
      <Text numberOfLines={2} style={styles.storeName}>{displayName}</Text>
      <View style={styles.storeBranchSlot}>
        {branch ? <Text numberOfLines={1} style={styles.storeBranch}>{branch}</Text> : null}
      </View>
      <Text numberOfLines={1} style={styles.storeDistance}>{store.distance}</Text>
      <View style={styles.storeColumnTotalBlock}>
        <Text adjustsFontSizeToFit minimumFontScale={0.8} numberOfLines={1} style={styles.storeTotal}>
          {formatCurrency(total)}
        </Text>
        <View style={styles.storeColumnDifferenceSlot}>
          {store.isLowestComparedTotal ? (
            <Text style={styles.lowestTotalLabel}>Lowest total</Text>
          ) : priceDifference !== null && priceDifference > 0 ? (
            <Text adjustsFontSizeToFit minimumFontScale={0.8} numberOfLines={1} style={styles.comparisonDifference}>
              + RM {priceDifference.toFixed(2)}
            </Text>
          ) : null}
        </View>
      </View>
      <View style={styles.storeColumnCoverage}>
        <Text style={styles.coverageCount}>
          {store.basketMatchedItemCount} / {store.totalBasketItemCount} priced
        </Text>
      </View>
      <View style={[styles.detailsButton, store.isLowestComparedTotal && styles.detailsButtonLowest]}>
        <Text style={[styles.detailsButtonText, store.isLowestComparedTotal && styles.detailsButtonTextLowest]}>View details</Text>
        <Ionicons color={store.isLowestComparedTotal ? COLORS.white : COLORS.deepTeal} name="chevron-forward" size={15} />
      </View>
    </Pressable>
  );
}

function CommonItemPriceRow({
  item,
  stores,
}: {
  item: CommonItemPricePreview;
  stores: readonly CheckPriceStoreFixture[];
}) {
  const lowestPrice = Math.min(...item.prices);
  const storePrices = stores.map((store) => ({
    store,
    item: store.comparedItems.find((priceItem) => priceItem.productId === item.productId)!,
  }));

  return (
    <View style={styles.commonItemPriceRow}>
      <View style={styles.commonItemIdentity}>
        <BasketItemImage
          imageSource={item.imageSource}
          name={item.name}
          resizeMode="contain"
          style={styles.commonItemThumbnail}
        />
        <View style={styles.commonItemCopy}>
          <Text numberOfLines={1} style={styles.commonItemName}>{item.name}</Text>
          <Text style={styles.commonItemQuantity}>{formatQuantity(item)}</Text>
        </View>
      </View>
      <View style={styles.itemPriceMatrix}>
        {storePrices.map(({ store, item: comparedItem }) => {
          const isLowest = comparedItem.price === lowestPrice;
          return (
            <View key={store.id} style={[styles.itemPriceMatrixCell, isLowest && styles.itemPriceMatrixCellLowest]}>
              <Text numberOfLines={1} style={[styles.itemPriceStoreName, isLowest && styles.itemPriceLowest]}>
                {getStoreDisplayName(store.name).displayName}
              </Text>
              <Text style={[styles.itemPriceMatrixPrice, isLowest && styles.itemPriceLowest]}>
                {formatCurrency(comparedItem.price)}
              </Text>
              {isLowest ? <Text style={styles.itemPriceLowestPill}>Lowest</Text> : null}
            </View>
          );
        })}
      </View>
    </View>
  );
}

function WhyLowestStoreSection({
  itemCount,
  lowestStore,
  onViewAllPrices,
  stores,
  lowestPriceWins,
  lowestTotal,
}: {
  itemCount: number;
  lowestStore: CheckPriceStoreFixture;
  onViewAllPrices: () => void;
  stores: readonly CheckPriceStoreFixture[];
  lowestPriceWins: LowestPriceWins | null;
  lowestTotal: number;
}) {
  const displayName = getStoreDisplayName(lowestStore.name).displayName;
  const currentWins = lowestPriceWins?.counts[lowestStore.id] ?? null;

  return (
    <View style={styles.whyLowestSection}>
      <View style={styles.whyHeadingRow}>
        <Image accessibilityElementsHidden resizeMode="contain" source={LOWEST_PRICE_IMAGE} style={styles.whyLowestImage} />
        <View style={styles.whyHeadingCopy}>
          <Text style={styles.whyLowestTitle}>Why {displayName} is lowest</Text>
          <Text style={styles.whyLowestSummary}>
            {formatCurrency(lowestTotal)} for the same {itemCount} items{currentWins !== null ? ` · lowest on ${currentWins} of ${itemCount}` : ''}{lowestPriceWins && lowestPriceWins.tiedItemCount > 0 ? ` · ${lowestPriceWins.tiedItemCount} tied` : ''}
          </Text>
        </View>
      </View>
      {lowestPriceWins ? (
        <View style={styles.lowestWinsSurface}>
          <View style={styles.lowestWinsBlock}>
            <Text style={styles.lowestWinsTitle}>Lowest-price wins</Text>
            {stores.map((store) => {
              const count = lowestPriceWins.counts[store.id];
              const width = count > 0 && itemCount > 0
                ? `${Math.max(4, (count / itemCount) * 100)}%` as `${number}%`
                : '0%';
              const isLowestTotal = store.id === lowestStore.id;
              return (
                <View key={store.id} style={styles.lowestWinsRow}>
                  <Text numberOfLines={1} style={styles.lowestWinsStore}>{getStoreDisplayName(store.name).displayName}</Text>
                  <View style={styles.lowestWinsTrack}>
                    <View style={[styles.lowestWinsFill, { width }, isLowestTotal ? styles.lowestWinsFillPrimary : styles.lowestWinsFillMuted]} />
                  </View>
                  <Text style={styles.lowestWinsCount}>{count}</Text>
                </View>
              );
            })}
          </View>
          {lowestPriceWins.tiedItemCount > 0 ? (
            <Text style={styles.lowestWinsTieNote}>
              {lowestPriceWins.tiedItemCount} {lowestPriceWins.tiedItemCount === 1 ? 'item has' : 'items have'} tied lowest prices
            </Text>
          ) : null}
        </View>
      ) : null}
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={`View all ${itemCount} compared prices`}
        hitSlop={7}
        onPress={onViewAllPrices}
        style={({ pressed }) => [styles.viewAllPricesButton, pressed && styles.pressed]}
      >
        <Text style={styles.viewAllPricesText}>View all {itemCount} compared prices</Text>
        <Ionicons color={COLORS.green} name="chevron-forward" size={18} />
      </Pressable>
    </View>
  );
}

function AllComparedPricesSheet({
  itemCount,
  onClose,
  previewItems,
  stores,
}: {
  itemCount: number;
  onClose: () => void;
  previewItems: readonly CommonItemPricePreview[];
  stores: readonly CheckPriceStoreFixture[];
}) {
  const insets = useSafeAreaInsets();
  return (
    <View style={styles.sheetOverlay}>
      <Pressable accessibilityLabel="Close compared prices" onPress={onClose} style={styles.sheetBackdrop} />
      <View style={styles.allComparedSheetCard}>
        <View style={styles.stickyComparedHeader}>
          <View style={styles.sheetHandle} />
          <View style={styles.sheetHeader}>
            <View style={styles.sheetIdentityCopy}>
              <Text style={styles.sheetTitle}>All compared prices</Text>
              <Text style={styles.sheetSubtitle}>{itemCount} items priced at all {stores.length} stores</Text>
            </View>
            <Pressable accessibilityLabel="Close compared prices" accessibilityRole="button" onPress={onClose} style={styles.sheetCloseButton}>
              <Ionicons color={COLORS.deepTeal} name="close" size={25} />
            </Pressable>
          </View>
        </View>
        <ScrollView
          contentContainerStyle={[styles.allComparedContent, { paddingBottom: Math.max(insets.bottom, 16) }]}
          showsVerticalScrollIndicator={false}
          style={styles.allComparedScroll}
        >
          {previewItems.map((item) => <CommonItemPriceRow item={item} key={item.productId} stores={stores} />)}
        </ScrollView>
      </View>
    </View>
  );
}

function StoreDetailsSheet({
  items,
  onChooseStore,
  onClose,
  store,
}: {
  items: readonly CheckPricePrototypeItem[];
  onChooseStore: () => void;
  onClose: () => void;
  store: CheckPriceStoreFixture;
}) {
  const insets = useSafeAreaInsets();
  const [showUnpriced, setShowUnpriced] = useState(false);
  const pricedIds = new Set([
    ...store.comparedItems.map((item) => item.productId),
    ...store.additionalMatchedItems.map((item) => item.productId),
  ]);
  const pricedItems = items.filter((item) => pricedIds.has(item.productId));
  const storeName = getStoreDisplayName(store.name);
  const hasEstimates = (store.basketEstimateCount ?? 0) > 0;
  const hasPricedSubtotal = !hasEstimates && store.basketTotalRm !== null && store.basketTotalRm !== undefined;
  return (
    <View style={styles.sheetOverlay}>
      <Pressable accessibilityLabel="Close store details" onPress={onClose} style={styles.sheetBackdrop} />
      <View style={[styles.sheetCard, { paddingBottom: Math.max(insets.bottom, 10) }]}>
        <ScrollView
          contentContainerStyle={styles.sheetScrollContent}
          showsVerticalScrollIndicator={false}
        >
          <View style={styles.sheetHandle} />
          <View style={styles.sheetHeader}>
            <View style={styles.sheetIdentityCopy}>
              <Text style={styles.sheetTitle}>{storeName.displayName}</Text>
              {storeName.branch ? <Text style={styles.sheetBranch}>{storeName.branch}</Text> : null}
              <Text style={styles.sheetSubtitle}>{store.distance} away</Text>
              <Text style={styles.sheetAddress}>{store.address}</Text>
            </View>
            <Pressable
              accessibilityLabel="Close store details"
              accessibilityRole="button"
              onPress={onClose}
              style={styles.sheetCloseButton}
            >
              <Ionicons color={COLORS.deepTeal} name="close" size={25} />
            </Pressable>
          </View>
          <Text style={styles.sheetCoverage}>
            {pricedItems.length} items with recent prices
          </Text>
          {pricedItems.map((item) => {
            const price = store.comparedItems.find((entry) => entry.productId === item.productId)?.price
              ?? store.additionalMatchedItems.find((entry) => entry.productId === item.productId)?.price
              ?? null;
            return (
              <View key={item.productId} style={styles.itemPriceRow}>
                <BasketItemImage imageSource={item.imageSource} name={item.name} resizeMode="contain" style={styles.itemThumbnail} />
                <View style={styles.itemPriceCopy}>
                  <Text style={styles.sheetProductName}>{item.name}</Text>
                  <Text style={styles.sheetQuantity}>{formatQuantity(item)}</Text>
                </View>
                <Text style={styles.sheetPrice}>{formatCurrency(price)}</Text>
              </View>
            );
          })}
          {store.unmatchedItems.length > 0 ? (
            <View style={styles.unmatchedBlock}>
              <Pressable accessibilityRole="button" accessibilityState={{ expanded: showUnpriced }} onPress={() => setShowUnpriced((expanded) => !expanded)} style={styles.unmatchedToggle}>
                <Image accessibilityElementsHidden resizeMode="contain" source={NO_RECENT_PRICE_IMAGE} style={styles.missingPriceImage} />
                <View style={styles.missingPriceCopy}>
                  <Text style={styles.unmatchedCount}>{store.unmatchedItems.length} items without recent prices</Text>
                </View>
                <Ionicons color={COLORS.deepTeal} name={showUnpriced ? 'chevron-up' : 'chevron-down'} size={18} />
              </Pressable>
              {showUnpriced ? <Text style={styles.unpricedNote}>No recent price doesn’t necessarily mean the item isn’t sold here.</Text> : null}
              {showUnpriced ? store.unmatchedItems.map((item) => (
                <View key={item.productId} style={styles.unmatchedPriceRow}>
                  <BasketItemImage imageSource={item.imageSource} name={item.name} resizeMode="contain" style={[styles.comparedThumbnail, styles.comparedThumbnailSheet]} />
                  <View style={styles.comparedCopy}>
                    <Text style={styles.sheetProductName}>{item.name}</Text>
                    <Text style={styles.sheetQuantity}>{formatQuantity(item)}</Text>
                  </View>
                </View>
              )) : null}
            </View>
          ) : null}
          <View style={styles.sheetTotalBlock}>
            <Text style={styles.sheetTotalLabel}>
              {hasEstimates ? 'Basket total' : hasPricedSubtotal ? 'Priced-items subtotal' : 'Same-item total'}
            </Text>
            <Text style={styles.sheetTotal}>{formatCurrency(store.basketTotalRm ?? store.comparedTotal)}</Text>
            <Text style={styles.sheetTotalCaption}>
              {hasEstimates
                ? `Full basket · ${store.basketEstimateCount} estimated`
                : hasPricedSubtotal
                  ? `for ${pricedItems.length} items with recent prices`
                  : `for ${store.comparedItems.length} same items`}
            </Text>
          </View>
          <Pressable
            accessibilityRole="button"
            onPress={onChooseStore}
            style={({ pressed }) => [styles.chooseStoreButton, pressed && styles.pressed]}
          >
            <Text style={styles.chooseStoreButtonText}>Choose this store</Text>
          </Pressable>
        </ScrollView>
      </View>
    </View>
  );
}

export function CheckPricesScreen({
  basketItems,
  onAddAllToShoppingList,
  onBack,
  onSelectedStoreIdChange,
  planDraft,
  prototype,
  selectedStoreId,
}: CheckPricesScreenProps) {
  const [fontsLoaded] = useFonts(priceCheckLocationFontAssets);
  const [detailsStoreId, setDetailsStoreId] = useState<string | null>(null);
  const [showAllComparedPrices, setShowAllComparedPrices] = useState(false);
  const [shoppingListReady, setShoppingListReady] = useState(false);
  const selectedDetailsStore = prototype.stores.find((store) => store.id === detailsStoreId) ?? null;
  const selectedStore = prototype.stores.find((store) => store.id === selectedStoreId) ?? null;
  const sortedStores = [...prototype.stores].sort((left, right) => {
    if (left.comparedTotal === null) return right.comparedTotal === null ? 0 : 1;
    if (right.comparedTotal === null) return -1;
    return left.comparedTotal - right.comparedTotal;
  });
  const lowestComparedStore = sortedStores.find((store) => store.isLowestComparedTotal)
    ?? sortedStores.find((store) => store.comparedTotal !== null);
  const lowestTotal = lowestComparedStore?.comparedTotal ?? null;
  const hasUniqueLowestTotal = Boolean(
    lowestComparedStore
    && lowestComparedStore.comparedTotal !== null
    && prototype.stores
      .filter((store) => store.id !== lowestComparedStore.id)
      .every((store) => store.comparedTotal !== null && lowestComparedStore.comparedTotal! < store.comparedTotal),
  );
  const [showComparisonHelp, setShowComparisonHelp] = useState(false);
  const uniqueLowestItemCounts = getUniqueLowestItemCounts(prototype);
  const recentPriceItemCount = prototype.items.filter((item) => item.hasRecentPrice).length;
  if (!fontsLoaded) {
    return <View style={styles.loadingScreen} />;
  }

  return (
    <View style={styles.screen}>
      <Svg height="100%" preserveAspectRatio="none" style={StyleSheet.absoluteFill} width="100%">
        <Defs>
          <SvgLinearGradient id="checkPricesPageGradient" x1="0" x2="0" y1="0" y2="1">
            <Stop offset="0%" stopColor="#D8F1E5" stopOpacity="0.98" />
            <Stop offset="18%" stopColor="#F0F8EF" stopOpacity="0.95" />
            <Stop offset="57%" stopColor="#FBFBF6" stopOpacity="0.86" />
            <Stop offset="100%" stopColor="#FFF6E7" stopOpacity="0.76" />
          </SvgLinearGradient>
        </Defs>
        <Rect fill="url(#checkPricesPageGradient)" height="100%" width="100%" />
      </Svg>
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        <CheckPricesHero onBack={onBack} />
        <View style={styles.content}>
          <PlanSummary planDraft={planDraft} variant="checkPrices" />
          <YourItemsCard items={prototype.items} />

          <View style={styles.nearbyHeader}>
            <View style={styles.compareHeadingCopy}>
              <View style={styles.compareTitleRow}>
                <Image accessibilityElementsHidden resizeMode="contain" source={COMPARE_STORES_IMAGE} style={styles.compareStoresImage} />
                <Text style={styles.sectionTitle}>Compare stores</Text>
              </View>
              <Text style={styles.sectionSubtitle}>
                Comparing the same {prototype.commonComparedItemIds.length} items across all {prototype.stores.length} stores.
              </Text>
              <Pressable
                accessibilityRole="button"
                accessibilityState={{ expanded: showComparisonHelp }}
                hitSlop={5}
                onPress={() => setShowComparisonHelp((expanded) => !expanded)}
                style={({ pressed }) => [styles.comparisonHelpToggle, pressed && styles.pressed]}
              >
                <Ionicons color={COLORS.green} name="information-circle-outline" size={16} />
                <Text style={styles.comparisonHelpLabel}>How comparison works</Text>
                <Ionicons color={COLORS.muted} name={showComparisonHelp ? 'chevron-up' : 'chevron-down'} size={14} />
              </Pressable>
              {showComparisonHelp ? (
                <View style={styles.comparisonHelpCopy}>
                  <Text style={styles.comparisonHelpText}>Your basket has {prototype.items.length} items.</Text>
                  <Text style={styles.comparisonHelpText}>{recentPriceItemCount} have recent prices.</Text>
                  <Text style={styles.comparisonHelpText}>Each store may have prices for different items.</Text>
                  <Text style={styles.comparisonHelpText}>
                    For a fair comparison, we use the {prototype.commonComparedItemIds.length} items that have recent prices at all {prototype.stores.length} stores.
                  </Text>
                </View>
              ) : null}
            </View>
          </View>

          <View style={styles.storeComparison}>
            {sortedStores.map((store) => (
              <StoreCard
                key={store.id}
                lowestTotal={lowestTotal}
                onViewDetails={() => setDetailsStoreId(store.id)}
                store={store}
              />
            ))}
          </View>

          {lowestComparedStore
            && hasUniqueLowestTotal
            && prototype.commonComparedItemIds.length > 0 ? (
              <WhyLowestStoreSection
                itemCount={prototype.commonComparedItemIds.length}
                lowestStore={lowestComparedStore}
                onViewAllPrices={() => setShowAllComparedPrices(true)}
                stores={sortedStores}
                lowestPriceWins={uniqueLowestItemCounts}
                lowestTotal={lowestTotal!}
              />
            ) : null}

          <View style={[styles.shoppingListAction, selectedStore && styles.shoppingListActionSelected]}>
            <View style={styles.shoppingListIntro}>
              <Image accessibilityElementsHidden resizeMode="contain" source={SHOPPING_LIST_IMAGE} style={styles.shoppingListImage} />
              <View style={styles.shoppingListCopy}>
                {selectedStoreId !== null && selectedStore ? (
                  <Text numberOfLines={1} style={styles.selectedStoreLabel}>{getStoreDisplayName(selectedStore.name).displayName} selected</Text>
                ) : (
                  <>
                    <Text style={styles.shoppingListTitle}>Not seeing a store that works for you?</Text>
                    <Text style={styles.shoppingListHelper}>
                      Add all {basketItems.length} items to your shopping list and choose where to shop yourself.
                    </Text>
                  </>
                )}
              </View>
            </View>
            <Pressable
              accessibilityRole="button"
              disabled={shoppingListReady}
              onPress={() => {
                setShoppingListReady(true);
                onAddAllToShoppingList?.();
              }}
              style={({ pressed }) => [
                styles.shoppingListButton,
                shoppingListReady && styles.shoppingListButtonReady,
                pressed && styles.pressed,
              ]}
            >
              {shoppingListReady ? (
                <Text style={styles.shoppingListButtonText}>Added all {basketItems.length} items to my shopping list</Text>
              ) : (
                <Text style={styles.shoppingListButtonText}>Add all {basketItems.length} items to my shopping list</Text>
              )}
            </Pressable>
          </View>
          <Text style={styles.disclaimer}>
            Prices are estimates. Missing prices don’t mean items aren’t sold. Check in store.
          </Text>
        </View>
      </ScrollView>

      {selectedDetailsStore ? (
        <StoreDetailsSheet
          items={prototype.items}
          onChooseStore={() => {
            onSelectedStoreIdChange(selectedDetailsStore.id);
            setDetailsStoreId(null);
          }}
          onClose={() => setDetailsStoreId(null)}
          store={selectedDetailsStore}
        />
      ) : null}
      {showAllComparedPrices ? (
        <AllComparedPricesSheet
          itemCount={prototype.commonComparedItemIds.length}
          onClose={() => setShowAllComparedPrices(false)}
          previewItems={getCommonItemPricePreview(prototype, prototype.commonComparedItemIds.length)}
          stores={sortedStores}
        />
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  screen: {
    backgroundColor: COLORS.background,
    flex: 1,
  },
  heroRegion: {
    height: 68,
    justifyContent: 'flex-start',
    overflow: 'hidden',
    position: 'relative',
  },
  heroGlow: {
    backgroundColor: 'rgba(255, 255, 255, 0.54)',
    borderRadius: 100,
    height: 138,
    position: 'absolute',
    right: -48,
    top: -78,
    width: 188,
  },
  heroHeader: {
    alignItems: 'center',
    flexDirection: 'row',
    minHeight: 58,
    paddingHorizontal: 20,
    paddingTop: 1,
  },
  heroBackButton: {
    alignItems: 'center',
    backgroundColor: 'rgba(255, 255, 255, 0.82)',
    borderRadius: 24,
    height: 48,
    justifyContent: 'center',
    width: 48,
    zIndex: 1,
  },
  heroBackIcon: {
    height: 30,
    resizeMode: 'contain',
    transform: [{ rotate: '180deg' }],
    width: 30,
  },
  heroTitle: {
    color: COLORS.deepTeal,
    flexShrink: 1,
    fontFamily: priceCheckLocationTokens.fonts.heading,
    fontSize: 28,
    lineHeight: 34,
    marginLeft: 8,
  },
  heroDecoration: {
    bottom: -6,
    height: 66,
    position: 'absolute',
    right: 6,
    width: 66,
  },
  heroDecorationSlot: {
    height: 54,
    marginLeft: 'auto',
    position: 'relative',
    width: 54,
  },
  loadingScreen: {
    backgroundColor: COLORS.background,
    flex: 1,
  },
  scrollContent: {
    paddingBottom: 28,
  },
  content: {
    gap: 12,
    paddingHorizontal: 20,
    paddingTop: 0,
  },
  pressed: {
    opacity: 0.72,
  },
  cardHeading: {
    color: COLORS.deepTeal,
    fontFamily: priceCheckLocationTokens.fonts.bodySemibold,
    fontSize: 18,
    lineHeight: 23,
  },
  cardHelper: {
    color: COLORS.muted,
    fontFamily: priceCheckLocationTokens.fonts.body,
    fontSize: 13,
    lineHeight: 17,
    marginTop: 5,
  },
  detailGroupTitle: {
    color: COLORS.deepTeal,
    fontFamily: priceCheckLocationTokens.fonts.bodySemibold,
    fontSize: 14,
    lineHeight: 18,
  },
  basketItemCount: {
    color: COLORS.muted,
    fontFamily: priceCheckLocationTokens.fonts.body,
    fontSize: 13,
    lineHeight: 17,
    marginTop: 1,
  },
  basketHeadingRow: {
    alignItems: 'baseline',
    flexDirection: 'row',
    gap: 5,
  },
  yourItemsCard: {
    backgroundColor: COLORS.white,
    borderColor: '#EAF0E8',
    borderRadius: 22,
    borderWidth: 1,
    boxShadow: '0px 4px 12px rgba(37, 72, 51, 0.06)',
    paddingHorizontal: 12,
    paddingVertical: 10,
  },
  yourItemsHeader: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 15,
    minHeight: 0,
  },
  viewPricesAction: {
    alignItems: 'center',
    backgroundColor: '#F4FAF6',
    borderColor: '#E6F0E8',
    borderRadius: 20,
    borderWidth: 1,
    flexDirection: 'row',
    gap: 4,
    marginLeft: 'auto',
    minHeight: 40,
    paddingHorizontal: 9,
  },
  viewPricesText: {
    color: COLORS.green,
    fontFamily: priceCheckLocationTokens.fonts.bodySemibold,
    fontSize: 14,
  },
  itemPriceList: {
    borderTopColor: COLORS.border,
    borderTopWidth: 1,
    gap: 8,
    marginTop: 12,
    paddingTop: 12,
  },
  basketMissingGroup: {
    borderTopColor: COLORS.border,
    borderTopWidth: StyleSheet.hairlineWidth,
    marginTop: 8,
    paddingTop: 8,
  },
  missingPriceHeading: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 8,
    minHeight: 48,
  },
  missingPriceImage: {
    height: 46,
    width: 46,
  },
  missingPriceCopy: {
    flex: 1,
    minWidth: 0,
  },
  unmatchedCount: {
    color: COLORS.deepTeal,
    fontFamily: priceCheckLocationTokens.fonts.bodySemibold,
    fontSize: 14,
    lineHeight: 18,
  },
  itemPriceRow: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 10,
    minHeight: 56,
  },
  itemThumbnail: {
    backgroundColor: COLORS.white,
    borderRadius: 14,
    height: 52,
    width: 52,
  },
  itemPriceCopy: {
    flex: 1,
  },
  itemName: {
    color: COLORS.deepTeal,
    fontFamily: priceCheckLocationTokens.fonts.bodySemibold,
    fontSize: 15,
    lineHeight: 20,
  },
  itemQuantity: {
    color: COLORS.muted,
    fontFamily: priceCheckLocationTokens.fonts.body,
    fontSize: 13,
    lineHeight: 18,
  },
  itemPrice: {
    color: COLORS.deepTeal,
    flexShrink: 0,
    fontFamily: priceCheckLocationTokens.fonts.bodySemibold,
    fontSize: 15,
    lineHeight: 20,
    maxWidth: 142,
    textAlign: 'right',
  },
  emptyText: {
    color: COLORS.muted,
    fontFamily: priceCheckLocationTokens.fonts.body,
    fontSize: 14,
  },
  nearbyHeader: {
    alignItems: 'center',
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: -8,
    paddingHorizontal: 2,
    paddingTop: 2,
  },
  compareHeadingCopy: {
    flex: 1,
    gap: 2,
  },
  compareTitleRow: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 5,
  },
  compareStoresImage: {
    height: 48,
    width: 48,
  },
  sectionTitle: {
    color: COLORS.deepTeal,
    fontFamily: priceCheckLocationTokens.fonts.heading,
    fontSize: 24,
    lineHeight: 29,
  },
  sectionSubtitle: {
    color: COLORS.muted,
    fontFamily: priceCheckLocationTokens.fonts.body,
    fontSize: 13,
    lineHeight: 17,
    marginTop: 0,
  },
  comparisonHelpToggle: {
    alignItems: 'center',
    alignSelf: 'flex-start',
    flexDirection: 'row',
    gap: 4,
    minHeight: 22,
    paddingRight: 8,
  },
  comparisonHelpLabel: {
    color: COLORS.muted,
    fontFamily: priceCheckLocationTokens.fonts.body,
    fontSize: 11,
    lineHeight: 14,
  },
  comparisonHelpCopy: {
    backgroundColor: '#F5F8F4',
    borderRadius: 12,
    gap: 3,
    marginTop: 2,
    paddingHorizontal: 10,
    paddingVertical: 8,
  },
  comparisonHelpText: {
    color: COLORS.muted,
    fontFamily: priceCheckLocationTokens.fonts.body,
    fontSize: 12,
    lineHeight: 16,
  },
  storeComparison: {
    alignItems: 'stretch',
    flexDirection: 'row',
    gap: 7,
    marginTop: 0,
    minWidth: 0,
  },
  storeColumn: {
    alignItems: 'stretch',
    backgroundColor: '#FFFFFF',
    borderColor: '#E8EFE8',
    borderRadius: 20,
    borderWidth: 1,
    boxShadow: '0px 3px 11px rgba(34, 72, 50, 0.06)',
    elevation: 1,
    flex: 1,
    justifyContent: 'flex-start',
    minWidth: 0,
    paddingHorizontal: 5,
    paddingVertical: 6,
  },
  storeColumnLowest: {
    backgroundColor: '#F0FBF5',
    borderColor: '#9AD6BA',
    borderRadius: 21,
    borderWidth: 1,
    boxShadow: '0px 5px 16px rgba(15, 138, 131, 0.16)',
    elevation: 4,
  },
  storeName: {
    color: COLORS.deepTeal,
    fontFamily: priceCheckLocationTokens.fonts.bodySemibold,
    fontSize: 14,
    lineHeight: 17,
    minHeight: 30,
    textAlign: 'center',
    transform: [{ translateY: 4 }],
  },
  storeBranchSlot: {
    height: 10,
    justifyContent: 'center',
  },
  storeBranch: {
    color: COLORS.muted,
    fontFamily: priceCheckLocationTokens.fonts.body,
    fontSize: 9,
    lineHeight: 11,
    textAlign: 'center',
  },
  storeDistance: {
    color: COLORS.muted,
    fontFamily: priceCheckLocationTokens.fonts.body,
    fontSize: 9,
    lineHeight: 11,
    textAlign: 'center',
  },
  comparedThumbnail: {
    height: 18,
    width: 18,
  },
  comparedCopy: {
    flex: 1,
    minWidth: 0,
  },
  storeColumnTotalBlock: {
    alignItems: 'center',
    marginTop: 2,
  },
  storeTotal: {
    color: COLORS.deepTeal,
    fontFamily: priceCheckLocationTokens.fonts.bodySemibold,
    fontSize: 19,
    lineHeight: 24,
    includeFontPadding: false,
    textAlign: 'center',
  },
  storeColumnDifferenceSlot: {
    alignItems: 'center',
    height: 13,
    justifyContent: 'center',
    width: '100%',
  },
  comparisonDifference: {
    color: COLORS.muted,
    fontFamily: priceCheckLocationTokens.fonts.body,
    fontSize: 10,
    lineHeight: 13,
    textAlign: 'center',
  },
  lowestTotalLabel: {
    backgroundColor: '#E0F3E7',
    borderRadius: 10,
    color: '#197451',
    fontFamily: priceCheckLocationTokens.fonts.bodySemibold,
    fontSize: 10,
    lineHeight: 13,
    overflow: 'hidden',
    paddingHorizontal: 8,
    paddingVertical: 2,
    textAlign: 'center',
  },
  storeColumnCoverage: {
    alignItems: 'center',
    height: 20,
    justifyContent: 'center',
    marginTop: 0,
  },
  coverageCount: {
    color: '#73827B',
    fontFamily: priceCheckLocationTokens.fonts.body,
    fontSize: 9,
    lineHeight: 12,
    textAlign: 'center',
  },
  detailsButton: {
    alignItems: 'center',
    backgroundColor: '#F4F8F4',
    borderColor: '#E6EEE7',
    borderRadius: 15,
    borderWidth: 1,
    flexDirection: 'row',
    gap: 1,
    height: 30,
    justifyContent: 'center',
    marginTop: 0,
    paddingHorizontal: 2,
  },
  detailsButtonLowest: {
    backgroundColor: '#0F8A83',
    borderColor: '#0F8A83',
    boxShadow: '0px 2px 6px rgba(15, 138, 131, 0.2)',
  },
  detailsButtonText: {
    color: COLORS.deepTeal,
    fontFamily: priceCheckLocationTokens.fonts.body,
    fontSize: 11,
    lineHeight: 15,
  },
  detailsButtonTextLowest: {
    color: COLORS.white,
    fontFamily: priceCheckLocationTokens.fonts.bodySemibold,
  },
  whyLowestSection: {
    backgroundColor: '#FFF9EC',
    borderColor: '#F3EBDD',
    borderRadius: 24,
    borderWidth: 1,
    boxShadow: '0px 5px 16px rgba(102, 77, 35, 0.08)',
    elevation: 2,
    marginTop: 1,
    padding: 8,
  },
  whyHeadingRow: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 6,
  },
  whyHeadingCopy: {
    flex: 1,
    minWidth: 0,
  },
  whyLowestImage: {
    height: 40,
    width: 40,
  },
  whyLowestTitle: {
    color: COLORS.deepTeal,
    fontFamily: priceCheckLocationTokens.fonts.bodySemibold,
    fontSize: 15,
    lineHeight: 19,
  },
  whyLowestSummary: {
    color: '#73827B',
    fontFamily: priceCheckLocationTokens.fonts.body,
    fontSize: 10,
    lineHeight: 13,
    marginTop: 1,
  },
  lowestWinsBlock: {
    marginTop: 0,
  },
  lowestWinsSurface: {
    backgroundColor: 'rgba(255, 255, 255, 0.72)',
    borderColor: 'rgba(255, 255, 255, 0.8)',
    borderRadius: 17,
    borderWidth: 1,
    marginTop: 4,
    paddingHorizontal: 7,
    paddingVertical: 4,
  },
  lowestWinsTitle: {
    color: COLORS.deepTeal,
    fontFamily: priceCheckLocationTokens.fonts.bodySemibold,
    fontSize: 11,
    lineHeight: 14,
    marginBottom: 2,
  },
  lowestWinsRow: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 8,
    minHeight: 17,
  },
  lowestWinsStore: {
    color: COLORS.muted,
    fontFamily: priceCheckLocationTokens.fonts.bodySemibold,
    fontSize: 11,
    width: 70,
  },
  lowestWinsTrack: {
    backgroundColor: '#EEECE5',
    borderRadius: 4,
    flex: 1,
    height: 7,
    overflow: 'hidden',
  },
  lowestWinsFill: {
    borderRadius: 4,
    height: 7,
  },
  lowestWinsFillPrimary: {
    backgroundColor: COLORS.green,
  },
  lowestWinsFillMuted: {
    backgroundColor: '#B8C4BE',
  },
  lowestWinsCount: {
    color: COLORS.deepTeal,
    fontFamily: priceCheckLocationTokens.fonts.bodySemibold,
    fontSize: 11,
    textAlign: 'right',
    width: 14,
  },
  lowestWinsTieNote: {
    color: COLORS.muted,
    fontFamily: priceCheckLocationTokens.fonts.body,
    fontSize: 10,
    lineHeight: 13,
    marginTop: 3,
  },
  commonItemPriceRow: {
    borderBottomColor: '#EEE6D9',
    borderBottomWidth: StyleSheet.hairlineWidth,
    paddingVertical: 9,
  },
  commonItemIdentity: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 8,
  },
  commonItemThumbnail: {
    height: 52,
    width: 52,
  },
  commonItemCopy: {
    flex: 1,
    minWidth: 0,
  },
  commonItemName: {
    color: COLORS.deepTeal,
    fontFamily: priceCheckLocationTokens.fonts.bodySemibold,
    fontSize: 15,
    lineHeight: 19,
  },
  commonItemQuantity: {
    color: COLORS.muted,
    fontFamily: priceCheckLocationTokens.fonts.body,
    fontSize: 12,
    lineHeight: 16,
  },
  itemPriceMatrix: {
    flexDirection: 'row',
    gap: 4,
    marginTop: 8,
  },
  itemPriceMatrixCell: {
    alignItems: 'center',
    borderRadius: 10,
    flex: 1,
    gap: 1,
    minWidth: 0,
    paddingVertical: 4,
  },
  itemPriceMatrixCellLowest: {
    backgroundColor: '#EFF8F0',
  },
  itemPriceStoreName: {
    color: COLORS.muted,
    alignSelf: 'stretch',
    fontFamily: priceCheckLocationTokens.fonts.bodySemibold,
    fontSize: 10,
    lineHeight: 14,
    minWidth: 0,
    textAlign: 'center',
  },
  itemPriceMatrixPrice: {
    color: COLORS.deepTeal,
    fontFamily: priceCheckLocationTokens.fonts.bodySemibold,
    fontSize: 12,
    lineHeight: 16,
    textAlign: 'center',
  },
  itemPriceLowestPill: {
    backgroundColor: '#D8EFDF',
    borderRadius: 8,
    color: '#197451',
    fontFamily: priceCheckLocationTokens.fonts.bodySemibold,
    fontSize: 9,
    lineHeight: 13,
    overflow: 'hidden',
    paddingHorizontal: 5,
    textAlign: 'center',
  },
  itemPriceLowest: {
    color: COLORS.green,
  },
  viewAllPricesButton: {
    alignItems: 'center',
    backgroundColor: 'rgba(255, 255, 255, 0.46)',
    borderRadius: 14,
    flexDirection: 'row',
    justifyContent: 'space-between',
    minHeight: 32,
    marginTop: 2,
    paddingHorizontal: 5,
  },
  viewAllPricesText: {
    color: COLORS.muted,
    fontFamily: priceCheckLocationTokens.fonts.bodySemibold,
    fontSize: 11,
    lineHeight: 14,
  },
  shoppingListAction: {
    backgroundColor: '#F5FBF8',
    borderColor: '#E2F0E7',
    borderRadius: 24,
    borderWidth: 1,
    boxShadow: '0px 3px 10px rgba(30, 82, 64, 0.06)',
    elevation: 1,
    padding: 8,
  },
  shoppingListActionSelected: {
    paddingVertical: 12,
  },
  selectedStoreLabel: {
    color: COLORS.green,
    fontFamily: priceCheckLocationTokens.fonts.bodySemibold,
    fontSize: 14,
    lineHeight: 19,
    marginBottom: 8,
  },
  shoppingListTitle: {
    color: COLORS.deepTeal,
    fontFamily: priceCheckLocationTokens.fonts.bodySemibold,
    fontSize: 14,
    lineHeight: 18,
    marginBottom: 1,
  },
  shoppingListHelper: {
    color: COLORS.muted,
    fontFamily: priceCheckLocationTokens.fonts.body,
    fontSize: 12,
    lineHeight: 16,
  },
  shoppingListIntro: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 6,
    marginBottom: 5,
  },
  shoppingListImage: {
    height: 48,
    width: 48,
  },
  shoppingListCopy: {
    flex: 1,
    minWidth: 0,
  },
  shoppingListButton: {
    alignItems: 'center',
    backgroundColor: COLORS.green,
    borderRadius: 24,
    justifyContent: 'center',
    minHeight: 48,
    paddingHorizontal: 14,
  },
  shoppingListButtonReady: {
    backgroundColor: COLORS.deepTeal,
  },
  shoppingListButtonText: {
    color: COLORS.white,
    fontFamily: priceCheckLocationTokens.fonts.bodySemibold,
    fontSize: 15,
    lineHeight: 20,
    textAlign: 'center',
  },
  disclaimer: {
    color: COLORS.muted,
    fontFamily: priceCheckLocationTokens.fonts.body,
    fontSize: 11,
    lineHeight: 15,
    paddingHorizontal: 5,
    textAlign: 'center',
  },
  sheetOverlay: {
    bottom: 0,
    left: 0,
    position: 'absolute',
    right: 0,
    top: 0,
    zIndex: 10,
  },
  sheetBackdrop: {
    backgroundColor: 'rgba(1, 44, 45, 0.34)',
    bottom: 0,
    left: 0,
    position: 'absolute',
    right: 0,
    top: 0,
  },
  sheetCard: {
    backgroundColor: COLORS.background,
    borderTopLeftRadius: 28,
    borderTopRightRadius: 28,
    bottom: 0,
    left: 0,
    maxHeight: '88%',
    padding: 0,
    position: 'absolute',
    right: 0,
  },
  allComparedSheetCard: {
    backgroundColor: COLORS.background,
    borderTopLeftRadius: 28,
    borderTopRightRadius: 28,
    bottom: 0,
    display: 'flex',
    height: '88%',
    left: 0,
    overflow: 'hidden',
    position: 'absolute',
    right: 0,
  },
  stickyComparedHeader: {
    backgroundColor: COLORS.background,
    borderBottomColor: '#E9EAE3',
    borderBottomWidth: StyleSheet.hairlineWidth,
    paddingHorizontal: 16,
    paddingTop: 12,
    paddingBottom: 6,
    zIndex: 1,
  },
  allComparedScroll: {
    flex: 1,
    minHeight: 0,
  },
  allComparedContent: {
    paddingHorizontal: 16,
    paddingTop: 4,
  },
  sheetHandle: {
    alignSelf: 'center',
    backgroundColor: '#C6D6D9',
    borderRadius: 4,
    height: 5,
    marginBottom: 8,
    width: 58,
  },
  sheetHeader: {
    alignItems: 'flex-start',
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  sheetScrollContent: {
    padding: 16,
    paddingBottom: 24,
  },
  sheetIdentityCopy: {
    flex: 1,
    minWidth: 0,
  },
  sheetTitle: {
    color: COLORS.deepTeal,
    fontFamily: priceCheckLocationTokens.fonts.heading,
    fontSize: 26,
    lineHeight: 32,
  },
  sheetSubtitle: {
    color: COLORS.muted,
    fontFamily: priceCheckLocationTokens.fonts.body,
    fontSize: 14,
    lineHeight: 19,
  },
  sheetBranch: {
    color: COLORS.muted,
    fontFamily: priceCheckLocationTokens.fonts.bodySemibold,
    fontSize: 13,
    lineHeight: 17,
  },
  sheetAddress: {
    color: COLORS.muted,
    fontFamily: priceCheckLocationTokens.fonts.body,
    fontSize: 12,
    lineHeight: 17,
    marginTop: 2,
  },
  sheetCloseButton: {
    alignItems: 'center',
    height: 48,
    justifyContent: 'center',
    width: 48,
  },
  sheetCoverage: {
    color: COLORS.green,
    fontFamily: priceCheckLocationTokens.fonts.bodySemibold,
    fontSize: 15,
    lineHeight: 20,
    marginTop: 10,
  },
  sheetSectionHeading: {
    color: COLORS.deepTeal,
    fontFamily: priceCheckLocationTokens.fonts.cardTitle,
    fontSize: 15,
    lineHeight: 20,
    marginBottom: 5,
    marginTop: 10,
  },
  additionalMatchedBlock: {
    borderTopColor: COLORS.border,
    borderTopWidth: 1,
    marginTop: 4,
  },
  additionalPriceRow: {
    alignItems: 'center',
    flexDirection: 'row',
    justifyContent: 'space-between',
    minHeight: 48,
  },
  unmatchedBlock: {
    borderTopColor: COLORS.border,
    borderTopWidth: 1,
    marginTop: 4,
  },
  unmatchedToggle: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 8,
    justifyContent: 'space-between',
    minHeight: 52,
  },
  unpricedNote: {
    color: COLORS.muted,
    fontFamily: priceCheckLocationTokens.fonts.body,
    fontSize: 12,
    lineHeight: 16,
    marginBottom: 6,
  },
  unmatchedPriceRow: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 8,
    minHeight: 52,
  },
  unmatchedPriceText: {
    color: COLORS.muted,
    flexShrink: 1,
    fontFamily: priceCheckLocationTokens.fonts.body,
    fontSize: 13,
    lineHeight: 17,
    maxWidth: 132,
    textAlign: 'right',
  },
  sheetProductName: {
    color: COLORS.deepTeal,
    fontFamily: priceCheckLocationTokens.fonts.bodySemibold,
    fontSize: 15,
    lineHeight: 19,
  },
  comparedThumbnailSheet: {
    height: 30,
    width: 30,
  },
  sheetPrice: {
    color: COLORS.deepTeal,
    fontFamily: priceCheckLocationTokens.fonts.bodySemibold,
    fontSize: 15,
    lineHeight: 20,
    marginLeft: 8,
    textAlign: 'right',
  },
  sheetQuantity: {
    color: COLORS.muted,
    fontFamily: priceCheckLocationTokens.fonts.body,
    fontSize: 13,
    lineHeight: 17,
  },
  sheetTotalBlock: {
    borderTopColor: COLORS.border,
    borderTopWidth: 1,
    marginTop: 10,
    paddingTop: 8,
  },
  sheetTotalLabel: {
    color: COLORS.muted,
    fontFamily: priceCheckLocationTokens.fonts.bodySemibold,
    fontSize: 14,
    lineHeight: 18,
  },
  sheetTotal: {
    color: COLORS.deepTeal,
    fontFamily: priceCheckLocationTokens.fonts.bodySemibold,
    fontSize: 27,
    lineHeight: 33,
  },
  sheetTotalCaption: {
    color: COLORS.muted,
    fontFamily: priceCheckLocationTokens.fonts.body,
    fontSize: 13,
    lineHeight: 17,
  },
  chooseStoreButton: {
    alignItems: 'center',
    backgroundColor: COLORS.green,
    borderRadius: 18,
    justifyContent: 'center',
    marginTop: 14,
    minHeight: 52,
  },
  chooseStoreButtonText: {
    color: COLORS.white,
    fontFamily: priceCheckLocationTokens.fonts.bodySemibold,
    fontSize: 16,
  },
});
