import { MaterialCommunityIcons } from '@expo/vector-icons';
import { useFonts } from 'expo-font';
import { useRef, useState, type ComponentProps } from 'react';
import {
  Alert,
  Image,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
  type ImageSourcePropType,
} from 'react-native';
import {
  priceCheckLocationFontAssets,
  priceCheckLocationTokens,
} from '../components/price-check/priceCheckLocationTokens';
import { BasketItemImage } from '../components/BasketItemImage';
import { FloatingUnitMenu, type UnitMenuAnchor } from '../components/FloatingUnitMenu';
import { DashboardBottomNavigation } from './HomeDashboardScreen';
import { PlanSummary } from './PlanSummary';
import { getStoreDisplayName } from './storeDisplayName';
import type { BasketDraftItem } from './basketContent';
import { foodImageUriForBackendId } from '../data/foodAssetManifest';
import type { RecipeFood } from '../services/recipeApi';
import type { CheckPricePrototype, CheckPriceStoreFixture } from './fixtures/demoPriceCalculator';
import type { PlanDraft } from './planFlowContent';
import type { MealIdea } from './MealIdeasScreen';
import { PANTRY_QUANTITY_UNITS, parsePantryQuantity, type PantryQuantityInput } from '../services/pantryQuantity';

const MAX_VISIBLE_THUMBNAILS = 4;

/** Supplied visual reference for the complete Plan next week card. */
const PLAN_NEXT_WEEK_VISUAL: ImageSourcePropType = require('../../assets/images/my-basket/plan-next-week.png');
/** Supplied visual for the What You Have OCR receipt banner. */
const OCR_BANNER_VISUAL: ImageSourcePropType = require('../../assets/images/my-basket/ocr-banner-cropped.png');

export type ProductPreviewItem = Pick<
  BasketDraftItem,
  'productId' | 'name' | 'imageSource' | 'suggestedQuantity' | 'unit'
>;
type IconName = ComponentProps<typeof MaterialCommunityIcons>['name'];
type DetailView = 'shopping-list' | 'what-you-have' | null;

function formatGeneralItemPrice(productId: string, pricePrototype: CheckPricePrototype): string {
  const item = pricePrototype.items.find((candidate) => candidate.productId === productId);

  if (!item || !item.hasRecentPrice || (item.priceMin === null && item.priceMax === null)) {
    return 'No recent price';
  }

  if (item.priceMin !== null && item.priceMax !== null && item.priceMin !== item.priceMax) {
    return `RM ${item.priceMin.toFixed(2)} – ${item.priceMax.toFixed(2)}`;
  }

  const formatted = `RM ${(item.priceMin ?? item.priceMax)!.toFixed(2)}`;
  // A2.5 (2026-09-17): a lone store quote is labelled as what it is.
  return item.quotingStoreCount === 1 ? `${formatted} · 1 store only` : formatted;
}

function getStoreItemPrice(
  productId: string,
  selectedStore: CheckPriceStoreFixture,
): number | null {
  const comparedItem = selectedStore.comparedItems.find((item) => item.productId === productId);
  const additionalItem = selectedStore.additionalMatchedItems.find((item) => item.productId === productId);

  return comparedItem?.price ?? additionalItem?.price ?? null;
}

function formatStoreItemPrice(
  productId: string,
  pricePrototype: CheckPricePrototype,
  selectedStore: CheckPriceStoreFixture | null,
): string {
  if (!selectedStore) {
    return formatGeneralItemPrice(productId, pricePrototype);
  }

  const price = getStoreItemPrice(productId, selectedStore);
  return price === null ? 'No recent price' : `RM ${price.toFixed(2)}`;
}

export interface MyBasketMainScreenProps {
  basketItems: readonly BasketDraftItem[];
  /** Persisted AVAILABLE pantry records, mapped to display items by App. */
  pantryItems: readonly BasketDraftItem[];
  editablePantryFoodIds?: readonly string[];
  onPantryQuantitySave?: (item: ProductPreviewItem, input: PantryQuantityInput) => Promise<void>;
  onPantryItemRemove?: (item: ProductPreviewItem) => Promise<void>;
  onHomePress?: () => void;
  onPlanNextWeek?: () => void;
  onPriceCheckPress: () => void;
  onProfilePress?: () => void;
  onReceiptTakePhotoPress?: () => void;
  onReceiptUploadImagePress?: () => void;
  onPurchasedShoppingItemsChange?: (items: readonly ProductPreviewItem[]) => void;
  onSeeAllMealIdeas?: () => void;
  recipeSuggestions?: readonly MealIdea[];
  onRecipePress?: (recipe: MealIdea) => void;
  persistedPurchasedShoppingItems?: readonly ProductPreviewItem[];
  receiptHaveItems?: readonly ProductPreviewItem[];
  recipeHaveItems?: readonly Pick<RecipeFood, 'canonical_food_id' | 'name'>[];
  recipeShoppingListItems?: readonly Pick<RecipeFood, 'canonical_food_id' | 'name'>[];
  planDraft: PlanDraft;
  planNextWeekVisual?: ImageSourcePropType | null;
  pricePrototype: CheckPricePrototype;
  selectedStoreId: string | null;
}

/**
 * Older households can contain duplicate pantry rows created before the
 * server-side merge was introduced. A food ID is the identity used by this
 * screen, so keep one display entry until the migration has consolidated
 * those historical records.
 */
function uniqueItemsByProductId(items: readonly BasketDraftItem[]): BasketDraftItem[] {
  const seenProductIds = new Set<string>();

  return items.filter((item) => {
    if (seenProductIds.has(item.productId)) return false;
    seenProductIds.add(item.productId);
    return true;
  });
}

function ProductThumbnailStrip({ items }: { items: readonly ProductPreviewItem[] }) {
  const visibleItems = items.slice(0, MAX_VISIBLE_THUMBNAILS);
  const overflowCount = Math.max(0, items.length - visibleItems.length);

  return (
    <ScrollView
      contentContainerStyle={styles.thumbnailStrip}
      horizontal
      showsHorizontalScrollIndicator={false}
    >
      {visibleItems.map((item, index) => (
        <View key={`${item.productId}-${index}`} style={styles.thumbnailCell}>
          <View style={styles.thumbnailImageFrame}>
            <BasketItemImage
              imageSource={item.imageSource}
              name={item.name}
              resizeMode="contain"
              style={styles.thumbnailImage}
            />
          </View>
          <Text numberOfLines={1} style={styles.thumbnailLabel}>{item.name}</Text>
        </View>
      ))}
      {overflowCount > 0 ? (
        <View style={[styles.thumbnailCell, styles.overflowCell]}>
          <Text style={styles.overflowCount}>+{overflowCount}</Text>
          <Text style={styles.overflowLabel}>more</Text>
        </View>
      ) : null}
    </ScrollView>
  );
}

function DashboardCardHeader({
  icon,
  iconColor,
  subtitle,
  title,
}: {
  icon: IconName;
  iconColor: string;
  subtitle: string;
  title: string;
}) {
  return (
    <View style={styles.dashboardCardHeader}>
      <View style={[styles.sectionIcon, { backgroundColor: iconColor }]}>
        <MaterialCommunityIcons color={COLORS.white} name={icon} size={27} />
      </View>
      <View style={styles.dashboardCardCopy}>
        <Text style={styles.dashboardCardTitle}>{title}</Text>
        <Text style={styles.dashboardCardSubtitle}>{subtitle}</Text>
      </View>
      <MaterialCommunityIcons color={COLORS.deepTeal} name="chevron-right" size={29} />
    </View>
  );
}

function ProductDashboardCard({
  icon,
  iconColor,
  items,
  onPress,
  subtitle,
  title,
  tone,
}: {
  icon: IconName;
  iconColor: string;
  items: readonly ProductPreviewItem[];
  onPress: () => void;
  subtitle: string;
  title: string;
  tone: 'green' | 'peach';
}) {
  return (
    <Pressable
      accessibilityLabel={title}
      accessibilityRole="button"
      onPress={onPress}
      style={({ pressed }) => [
        styles.dashboardCard,
        tone === 'green' ? styles.shoppingListCard : styles.whatYouHaveCard,
        pressed && styles.pressed,
      ]}
    >
      <DashboardCardHeader icon={icon} iconColor={iconColor} subtitle={subtitle} title={title} />
      {items.length > 0 ? <ProductThumbnailStrip items={items} /> : null}
    </Pressable>
  );
}

type RecipeCardProps = {
  onPress?: () => void;
  imageSource?: ImageSourcePropType | null;
  tags: readonly string[];
  time: string;
  title: string;
  uses: string;
};

function RecipeCard({ imageSource, tags, time, title, uses, onPress }: RecipeCardProps) {
  return (
    <Pressable accessibilityLabel={title} accessibilityRole="button" onPress={onPress} style={styles.recipeCard}>
      {imageSource ? (
        <Image accessibilityElementsHidden resizeMode="cover" source={imageSource} style={styles.recipeImage} />
      ) : (
        <View accessibilityElementsHidden style={styles.recipeImagePlaceholder} />
      )}
      <View style={styles.recipeCardContent}>
        <Text style={styles.recipeCardTitle}>{title}</Text>
        <View style={styles.recipeMetadata}>
          <View style={styles.recipeMetadataItem}>
            <MaterialCommunityIcons color={COLORS.deepTeal} name="clock-outline" size={15} />
            <Text style={styles.recipeMetadataText}>{time}</Text>
          </View>
          <View style={styles.recipeMetadataDivider} />
          <View style={[styles.recipeMetadataItem, styles.recipeMetadataUses]}>
            <Text style={styles.recipeMetadataText}>{uses}</Text>
          </View>
        </View>
        <View style={styles.recipeTags}>
          {tags.map((tag, index) => (
            <View key={tag} style={[styles.recipeTag, index === 0 ? styles.recipeTagGreen : styles.recipeTagBlue]}>
              <Text style={styles.recipeTagText}>{tag}</Text>
            </View>
          ))}
        </View>
      </View>
    </Pressable>
  );
}

function RecipeSuggestionSection({
  onSeeAllMealIdeas,
  onRecipePress,
  recipes,
}: {
  onSeeAllMealIdeas?: () => void;
  onRecipePress?: (recipe: MealIdea) => void;
  recipes: readonly MealIdea[];
}) {

  return (
    <View accessibilityLabel="Recipe suggestions" style={styles.recipeSection}>
      <View style={styles.recipeSectionHeader}>
        <View style={styles.recipeSectionCopy}>
          <Text style={styles.recipeSectionTitle}>Not sure what to cook?</Text>
          <Text style={styles.recipeSectionSubtitle}>Meal ideas using what you have.</Text>
        </View>
        <Pressable
          accessibilityLabel="See all meal ideas"
          accessibilityRole="button"
          onPress={onSeeAllMealIdeas}
          style={({ pressed }) => [styles.recipeSeeAll, pressed && styles.pressed]}
        >
          <Text style={styles.recipeSeeAllText}>See all</Text>
          <MaterialCommunityIcons color={COLORS.deepTeal} name="chevron-right" size={21} />
        </Pressable>
      </View>
      <View style={styles.recipeCards}>
        {recipes.slice(0, 2).map((recipe) => (
          <RecipeCard
            onPress={() => onRecipePress?.(recipe)}
            imageSource={recipe.imageSource}
            key={recipe.recipeId}
            tags={[recipe.tag]}
            time={recipe.time}
            title={recipe.title}
            uses={recipe.ingredientCount === undefined ? 'Ingredients' : `${recipe.ingredientCount} items`}
          />
        ))}
      </View>
    </View>
  );
}

function PlanNextWeekCard({
  onPress,
  visual,
  compactTopSpacing = false,
}: {
  onPress?: () => void;
  visual: ImageSourcePropType;
  compactTopSpacing?: boolean;
}) {
  const [visualFrameWidth, setVisualFrameWidth] = useState(0);

  return (
    <Pressable
      accessibilityLabel="Plan next week"
      accessibilityRole="button"
      onPress={onPress}
      style={({ pressed }) => [styles.planCard, compactTopSpacing && styles.planCardAfterRecipes, pressed && styles.pressed]}
    >
      <View
        accessibilityElementsHidden
        onLayout={(event) => setVisualFrameWidth(event.nativeEvent.layout.width)}
        style={styles.planVisualFrame}
      >
        {visualFrameWidth > 0 ? (
          <Image
            resizeMode="stretch"
            source={visual}
            style={[
              styles.planVisual,
              {
                height: visualFrameWidth * 1.14 * (887 / 1774),
                left: visualFrameWidth * -0.07,
                top: visualFrameWidth * -0.183,
                width: visualFrameWidth * 1.14,
              },
            ]}
          />
        ) : null}
      </View>
    </Pressable>
  );
}

function OcrReceiptBanner({
  onTakePhoto,
  onUploadImage,
}: {
  onTakePhoto?: () => void;
  onUploadImage?: () => void;
}) {
  return (
    <View accessibilityLabel="Scan a grocery receipt" style={styles.ocrBanner}>
      <Image
        accessibilityElementsHidden
        resizeMode="contain"
        source={OCR_BANNER_VISUAL}
        style={styles.ocrBannerImage}
      />
      <Pressable
        accessibilityLabel="Take photo"
        accessibilityRole="button"
        onPress={onTakePhoto}
        style={styles.ocrTakePhotoHitArea}
      />
      <Pressable
        accessibilityLabel="Upload image"
        accessibilityRole="button"
        onPress={onUploadImage}
        style={styles.ocrUploadImageHitArea}
      />
    </View>
  );
}

function RemainingQuantityEditor({ item, onSave }: {
  item: ProductPreviewItem;
  onSave: (item: ProductPreviewItem, input: PantryQuantityInput) => Promise<void>;
}) {
  const [editing, setEditing] = useState(false);
  const [quantity, setQuantity] = useState('');
  const [unit, setUnit] = useState('');
  const [unitMenuOpen, setUnitMenuOpen] = useState(false);
  const [unitMenuAnchor, setUnitMenuAnchor] = useState<UnitMenuAnchor | null>(null);
  const unitTriggerRef = useRef<View>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const beginEditing = () => {
    setQuantity(item.suggestedQuantity > 0 ? String(item.suggestedQuantity) : '');
    const normalizedUnit = item.unit.trim().toLowerCase();
    setUnit(PANTRY_QUANTITY_UNITS.find((option) => option.toLowerCase() === normalizedUnit) ?? '');
    setError(null);
    setUnitMenuOpen(false);
    setEditing(true);
  };
  const save = async () => {
    if (saving) return;
    setSaving(true);
    setError(null);
    try {
      await onSave(item, parsePantryQuantity(quantity, unit));
      setEditing(false);
      setUnitMenuOpen(false);
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'Could not save. Please try again.');
    } finally {
      setSaving(false);
    }
  };
  if (!editing) return (
    <View>
      <Text style={styles.detailQuantity}>{item.suggestedQuantity > 0 ? `${item.suggestedQuantity} ${item.unit}` : 'Amount unknown'}</Text>
      <Pressable accessibilityLabel={`Edit remaining amount for ${item.name}`} accessibilityRole="button" onPress={beginEditing} style={styles.detailEditAction}>
        <Text style={styles.detailModifyText}>Edit remaining</Text>
      </Pressable>
    </View>
  );
  return (
    <View style={styles.remainingEditor}>
      <View style={styles.detailEditableQuantity}>
        <TextInput accessibilityLabel={`Remaining quantity for ${item.name}`} editable={!saving}
          keyboardType="decimal-pad" onChangeText={setQuantity} placeholder="Unknown"
          selectTextOnFocus style={styles.detailQuantityInput} value={quantity} />
        <Pressable accessibilityLabel={`Choose remaining unit for ${item.name}`} accessibilityRole="button"
          ref={unitTriggerRef}
          accessibilityState={{ expanded: unitMenuOpen }} disabled={saving}
          onPress={() => unitTriggerRef.current?.measureInWindow((x, y, width, height) => {
            setUnitMenuAnchor({ x, y, width, height });
            setUnitMenuOpen(true);
          })} style={styles.remainingUnitButton}>
          <Text style={styles.detailQuantityUnit}>{unit || 'Unit'}</Text>
          <MaterialCommunityIcons color={COLORS.muted} name={unitMenuOpen ? 'chevron-up' : 'chevron-down'} size={16} />
        </Pressable>
      </View>
      {unitMenuOpen && unitMenuAnchor ? (
        <FloatingUnitMenu anchor={unitMenuAnchor} label={`Remaining units for ${item.name}`} onClose={() => setUnitMenuOpen(false)}>
          {PANTRY_QUANTITY_UNITS.map((option) => (
            <Pressable key={option} accessibilityLabel={`Set ${item.name} remaining unit to ${option}`} accessibilityRole="button"
              disabled={saving} onPress={() => { setUnit(option); setUnitMenuOpen(false); }} style={styles.remainingUnitOption}>
              <Text style={styles.detailModifyText}>{option}</Text>
            </Pressable>
          ))}
        </FloatingUnitMenu>
      ) : null}
      <Text style={styles.detailQuantity}>Leave blank if unknown.</Text>
      {error ? <Text accessibilityRole="alert" style={styles.remainingError}>{error}</Text> : null}
      <View style={styles.remainingActions}>
        <Pressable accessibilityLabel={`Save remaining amount for ${item.name}`} accessibilityRole="button" disabled={saving}
          onPress={() => void save()} style={styles.detailModify}>
          <Text style={styles.detailModifyText}>{saving ? 'Saving…' : 'Save'}</Text>
        </Pressable>
        <Pressable accessibilityLabel={`Cancel remaining amount for ${item.name}`} accessibilityRole="button" disabled={saving}
          onPress={() => { setEditing(false); setUnitMenuOpen(false); setError(null); }} style={styles.detailModify}>
          <Text style={styles.detailModifyText}>Cancel</Text>
        </Pressable>
      </View>
    </View>
  );
}

function DetailPanel({
  items,
  onClose,
  onItemConsumed,
  onPantryQuantitySave,
  editablePantryFoodIds,
  onItemRemoved,
  onItemPurchased,
  onReceiptTakePhotoPress,
  onReceiptUploadImagePress,
  purchasedShoppingItemIds,
  pricePrototype,
  selectedStore,
  title,
}: {
  items: readonly ProductPreviewItem[];
  onClose: () => void;
  onItemConsumed?: (item: ProductPreviewItem) => Promise<void>;
  onPantryQuantitySave?: (item: ProductPreviewItem, input: PantryQuantityInput) => Promise<void>;
  editablePantryFoodIds: ReadonlySet<string>;
  onItemRemoved?: (item: ProductPreviewItem) => Promise<void>;
  onItemPurchased?: (item: ProductPreviewItem) => void;
  onReceiptTakePhotoPress?: () => void;
  onReceiptUploadImagePress?: () => void;
  purchasedShoppingItemIds: ReadonlySet<string>;
  pricePrototype: CheckPricePrototype;
  selectedStore: CheckPriceStoreFixture | null;
  title: string;
}) {
  const isShoppingList = title === 'Shopping list';
  const [isModifyMode, setIsModifyMode] = useState(false);
  const pendingRemovalIds = useRef(new Set<string>());
  const [removingIds, setRemovingIds] = useState<ReadonlySet<string>>(new Set());
  const [removalError, setRemovalError] = useState<string | null>(null);
  const removeItem = async (item: ProductPreviewItem, action?: (item: ProductPreviewItem) => Promise<void>) => {
    if (pendingRemovalIds.current.has(item.productId)) return;
    pendingRemovalIds.current.add(item.productId);
    setRemovingIds(new Set(pendingRemovalIds.current));
    setRemovalError(null);
    try {
      if (!action) throw new Error('Sign in to save changes to What you have.');
      await action(item);
    } catch (error) {
      setRemovalError(`${item.name} could not be removed. ${error instanceof Error ? error.message : 'Please try again.'}`);
    } finally {
      pendingRemovalIds.current.delete(item.productId);
      setRemovingIds(new Set(pendingRemovalIds.current));
    }
  };
  const confirmRemoval = (item: ProductPreviewItem, eaten: boolean) => {
    if (pendingRemovalIds.current.has(item.productId)) return;
    const title = eaten ? 'Mark as eaten?' : 'Remove item?';
    const message = eaten ? `Once confirmed, ${item.name} will be marked as eaten.` : `Remove ${item.name} from What You Have?`;
    const apply = () => void removeItem(item, eaten ? onItemConsumed : onItemRemoved);
    if (Platform.OS === 'web') {
      if (window.confirm(`${title}\n\n${message}`)) apply();
    } else {
      Alert.alert(title, message, [
        { text: 'Cancel', style: 'cancel' },
        { text: eaten ? 'Confirm' : 'Remove', style: eaten ? 'default' : 'destructive', onPress: apply },
      ]);
    }
  };
  const quantityLabel = (item: ProductPreviewItem) => (
    item.suggestedQuantity > 0
      ? `${item.suggestedQuantity} ${item.unit}`
      : 'Amount unknown'
  );
  const confirmItemConsumed = (item: ProductPreviewItem) => {
    confirmRemoval(item, true);
  };
  const confirmItemRemoval = (item: ProductPreviewItem) => {
    confirmRemoval(item, false);
  };
  const selectedStoreName = selectedStore ? getStoreDisplayName(selectedStore.name) : null;
  const selectedStoreLabel = selectedStoreName
    ? [selectedStoreName.displayName, selectedStoreName.branch].filter(Boolean).join(' · ')
    : '';

  return (
    <View style={styles.detailPanel}>
      <View style={styles.detailHeader}>
        <Text accessibilityRole="header" style={styles.detailTitle}>{title}</Text>
        <View style={styles.detailHeaderActions}>
          <Pressable
            accessibilityLabel="Back to My Basket"
            accessibilityRole="button"
            onPress={onClose}
            style={({ pressed }) => [styles.detailClose, pressed && styles.pressed]}
          >
            <MaterialCommunityIcons color={COLORS.deepTeal} name="close" size={24} />
          </Pressable>
        </View>
      </View>
      {isShoppingList ? (
        selectedStore ? (
          <View style={styles.storeSummary}>
            <Text style={styles.storeSummaryEyebrow}>Shopping at</Text>
            <Text numberOfLines={2} style={styles.storeSummaryName}>
              {selectedStoreLabel}
            </Text>
            <Text style={styles.storeSummaryDistance}>{selectedStore.distance} away</Text>
            <Text style={styles.storeSummaryAddress}>{selectedStore.address}</Text>
            <Text style={styles.storeSummaryLabel}>Estimated prices from this store</Text>
          </View>
        ) : (
          <View style={styles.storeNotSelected}>
            <Text style={styles.storeNotSelectedTitle}>Store not selected</Text>
            <Text style={styles.storeNotSelectedCopy}>Choose where to shop when you&apos;re ready.</Text>
          </View>
        )
      ) : null}
      {!isShoppingList ? (
        <OcrReceiptBanner
          onTakePhoto={onReceiptTakePhotoPress}
          onUploadImage={onReceiptUploadImagePress}
        />
      ) : null}
      <View style={styles.detailSectionHeader}>
        <Text style={styles.detailSectionHeading}>{isShoppingList ? 'Items' : 'Foods at home'}</Text>
        {!isShoppingList ? (
          <Pressable
            accessibilityLabel="Modify What You Have"
            accessibilityRole="button"
            onPress={() => setIsModifyMode((current) => !current)}
            style={({ pressed }) => [styles.detailModify, pressed && styles.pressed]}
          >
            <MaterialCommunityIcons
              color={COLORS.deepTeal}
              name={isModifyMode ? 'check' : 'pencil-outline'}
              size={17}
            />
            {isModifyMode ? <Text style={styles.detailModifyText}>Done</Text> : <Text style={styles.detailModifyText}>Modify</Text>}
          </Pressable>
        ) : null}
      </View>
      {removalError ? <Text accessibilityRole="alert" style={styles.detailEmpty}>{removalError}</Text> : null}
      {items.length === 0 ? (
        <Text style={styles.detailEmpty}>No items here yet.</Text>
      ) : (
        items.map((item, index) => {
          const isPurchased = purchasedShoppingItemIds.has(item.productId);
          const isCompletedShoppingListItem = isShoppingList && isPurchased;

          return (
            <View key={`${item.productId}-${index}`} style={styles.detailRow}>
              {isShoppingList ? (
                <Pressable
                  accessibilityLabel={`${item.name}, ${isPurchased ? 'purchased' : 'not purchased'}`}
                  accessibilityRole="checkbox"
                  accessibilityState={{ checked: isPurchased }}
                  onPress={() => onItemPurchased?.(item)}
                  style={({ pressed }) => [styles.detailCheckbox, pressed && styles.pressed]}
                >
                  <MaterialCommunityIcons
                    color={isPurchased ? COLORS.green : COLORS.muted}
                    name={isPurchased ? 'checkbox-marked' : 'checkbox-blank-outline'}
                    size={30}
                  />
                </Pressable>
              ) : isModifyMode ? (
                <Pressable
                  accessibilityLabel={`Remove ${item.name}`}
                  accessibilityRole="button"
                  accessibilityState={{ disabled: removingIds.has(item.productId), busy: removingIds.has(item.productId) }}
                  disabled={removingIds.has(item.productId)}
                  onPress={() => confirmItemRemoval(item)}
                  style={({ pressed }) => [styles.detailRemoveButton, pressed && styles.pressed]}
                >
                  <MaterialCommunityIcons color={COLORS.coral} name="trash-can-outline" size={27} />
                </Pressable>
              ) : (
                <Pressable
                  accessibilityLabel={`Mark ${item.name} as eaten`}
                  accessibilityRole="button"
                  accessibilityState={{ disabled: removingIds.has(item.productId), busy: removingIds.has(item.productId) }}
                  disabled={removingIds.has(item.productId)}
                  onPress={() => confirmItemConsumed(item)}
                  style={({ pressed }) => [styles.detailConsumedButton, pressed && styles.pressed]}
                >
                  <MaterialCommunityIcons color={COLORS.green} name="check-circle-outline" size={28} />
                </Pressable>
              )}
              <BasketItemImage
                imageSource={item.imageSource}
                name={item.name}
                resizeMode="contain"
                style={styles.detailImage}
              />
              <View style={styles.detailCopy}>
                <Text
                  style={[
                    styles.detailProductName,
                    isCompletedShoppingListItem && styles.detailCompletedText,
                  ]}
                >
                  {item.name}
                </Text>
                {isModifyMode && !isShoppingList && onPantryQuantitySave && editablePantryFoodIds.has(item.productId) ? (
                  <RemainingQuantityEditor item={item} onSave={onPantryQuantitySave} />
                ) : (
                  <Text
                    style={[
                      styles.detailQuantity,
                      isCompletedShoppingListItem && styles.detailCompletedText,
                    ]}
                  >
                    {quantityLabel(item)}
                  </Text>
                )}
              </View>
              {isShoppingList ? (
                <Text
                  numberOfLines={1}
                  style={[
                    styles.detailPrice,
                    isCompletedShoppingListItem && styles.detailCompletedText,
                  ]}
                >
                  {formatStoreItemPrice(item.productId, pricePrototype, selectedStore)}
                </Text>
              ) : null}
            </View>
          );
        })
      )}
    </View>
  );
}

export function MyBasketMainScreen({
  basketItems,
  pantryItems,
  editablePantryFoodIds = [],
  onPantryQuantitySave,
  onPantryItemRemove,
  onHomePress,
  onPlanNextWeek,
  onPriceCheckPress,
  onProfilePress,
  onReceiptTakePhotoPress,
  onReceiptUploadImagePress,
  onPurchasedShoppingItemsChange,
  onSeeAllMealIdeas,
  recipeSuggestions = [],
  onRecipePress,
  persistedPurchasedShoppingItems,
  receiptHaveItems = [],
  recipeHaveItems = [],
  recipeShoppingListItems = [],
  planDraft,
  planNextWeekVisual,
  pricePrototype,
  selectedStoreId,
}: MyBasketMainScreenProps) {
  const [fontsLoaded] = useFonts(priceCheckLocationFontAssets);
  const [detailView, setDetailView] = useState<DetailView>(null);
  const [purchasedShoppingItems, setPurchasedShoppingItems] = useState<readonly ProductPreviewItem[]>([]);
  const resolvedPlanNextWeekVisual = planNextWeekVisual ?? PLAN_NEXT_WEEK_VISUAL;
  const displayedPurchasedShoppingItems = persistedPurchasedShoppingItems ?? purchasedShoppingItems;
  const purchasedShoppingItemIds = new Set(displayedPurchasedShoppingItems.map((item) => item.productId));
  const shoppingListItems = basketItems.filter((item) => item.choice === 'need');
  shoppingListItems.push(
    ...recipeShoppingListItems
      .filter((food) => !shoppingListItems.some((item) => item.productId === food.canonical_food_id))
      .map((food) => ({
        productId: food.canonical_food_id,
        name: food.name,
        imageSource: (() => {
          const uri = foodImageUriForBackendId(food.canonical_food_id);
          return uri ? { uri } : null;
        })(),
        suggestedQuantity: 0,
        unit: 'amount unknown',
        source: 'manual' as const,
        choice: 'need' as const,
      })),
  );
  const remainingShoppingListItems = shoppingListItems.filter(
    (item) => !purchasedShoppingItemIds.has(item.productId),
  );
  // Pantry, not the temporary basket draft, is the source of truth here.
  // A basket "Have at home" choice creates a pantry record; receipt and
  // manual pantry entries appear here too.
  const uniquePantryItems = uniqueItemsByProductId(pantryItems);
  const pantryProductIds = new Set(uniquePantryItems.map((item) => item.productId));
  const existingWhatYouHaveNames = new Set([
    ...uniquePantryItems.map((item) => item.name),
    ...displayedPurchasedShoppingItems.map((item) => item.name),
  ]);
  const receiptItemsToAdd = receiptHaveItems
    .filter((item, index, items) => items.findIndex((candidate) => candidate.productId === item.productId) === index)
    .filter((item) => !pantryProductIds.has(item.productId))
    .filter((item) => !existingWhatYouHaveNames.has(item.name));
  const whatYouHaveNamesIncludingReceipts = new Set([
    ...existingWhatYouHaveNames,
    ...receiptItemsToAdd.map((item) => item.name),
  ]);
  const whatYouHaveItems = [
    ...uniquePantryItems,
    ...displayedPurchasedShoppingItems.filter((item) => !pantryProductIds.has(item.productId)),
    ...receiptItemsToAdd,
    ...recipeHaveItems
      .filter((food, index, items) => items.findIndex((item) => item.canonical_food_id === food.canonical_food_id) === index)
      .filter((food) => !pantryProductIds.has(food.canonical_food_id) &&
        !whatYouHaveNamesIncludingReceipts.has(food.name))
      .map((food) => ({
        productId: food.canonical_food_id,
        name: food.name,
        imageSource: (() => {
          const uri = foodImageUriForBackendId(food.canonical_food_id);
          return uri ? { uri } : null;
        })(),
        suggestedQuantity: 0,
        unit: 'amount unknown',
        source: 'manual' as const,
        choice: 'have' as const,
      })),
  ];
  const selectedStore = pricePrototype.stores.find((store) => store.id === selectedStoreId) ?? null;

  const handleShoppingListItemPurchased = (item: ProductPreviewItem) => {
    const current = persistedPurchasedShoppingItems ?? purchasedShoppingItems;
    const isAlreadyPurchased = current.some(
      (purchasedItem) => purchasedItem.productId === item.productId,
    );
    const next = isAlreadyPurchased
      ? current.filter((purchasedItem) => purchasedItem.productId !== item.productId)
      : [...current, item];

    setPurchasedShoppingItems(next);
    onPurchasedShoppingItemsChange?.(next);
  };


  if (!fontsLoaded) {
    return <View style={styles.fontLoading} />;
  }

  return (
    <View style={styles.screen}>
      <ScrollView
        contentContainerStyle={styles.content}
        showsVerticalScrollIndicator={false}
      >
        <View style={styles.header}>
          <View style={styles.headerCopy}>
            <Text accessibilityRole="header" style={styles.pageTitle}>My Basket</Text>
            <Text style={styles.pageSubtitle}>Your week, your way.</Text>
          </View>
          <Pressable
            accessibilityLabel="Profile"
            accessibilityRole="button"
            onPress={onProfilePress}
            style={({ pressed }) => [styles.avatar, pressed && styles.pressed]}
          >
            <MaterialCommunityIcons color={COLORS.deepTeal} name="account-circle-outline" size={34} />
          </Pressable>
        </View>

        <PlanSummary planDraft={planDraft} />

        {detailView ? (
          <DetailPanel
            items={detailView === 'shopping-list' ? shoppingListItems : whatYouHaveItems}
            onClose={() => setDetailView(null)}
            onItemConsumed={onPantryItemRemove}
            onPantryQuantitySave={onPantryQuantitySave}
            editablePantryFoodIds={new Set(editablePantryFoodIds)}
            onItemRemoved={onPantryItemRemove}
            onItemPurchased={handleShoppingListItemPurchased}
            onReceiptTakePhotoPress={onReceiptTakePhotoPress}
            onReceiptUploadImagePress={onReceiptUploadImagePress}
            purchasedShoppingItemIds={purchasedShoppingItemIds}
            pricePrototype={pricePrototype}
            selectedStore={selectedStore}
            title={detailView === 'shopping-list' ? 'Shopping list' : 'What you have'}
          />
        ) : (
          <>
            <ProductDashboardCard
              icon="cart-outline"
              iconColor={COLORS.green}
              items={remainingShoppingListItems}
              onPress={() => setDetailView('shopping-list')}
              subtitle={`${remainingShoppingListItems.length} items left to buy.`}
              title="Shopping list"
              tone="green"
            />
            <ProductDashboardCard
              icon="home-heart"
              iconColor={COLORS.coral}
              items={whatYouHaveItems}
              onPress={() => setDetailView('what-you-have')}
              subtitle={whatYouHaveItems.length === 0 ? 'Nothing added yet' : `${whatYouHaveItems.length} foods at home.`}
              title="What you have"
              tone="peach"
            />
            <RecipeSuggestionSection onSeeAllMealIdeas={onSeeAllMealIdeas} onRecipePress={onRecipePress} recipes={recipeSuggestions} />
            <PlanNextWeekCard
              onPress={onPlanNextWeek}
              visual={resolvedPlanNextWeekVisual}
              compactTopSpacing={recipeSuggestions.length > 0}
            />
          </>
        )}
      </ScrollView>

      <DashboardBottomNavigation
        activeTab="basket"
        devUI={null}
        onHomePress={onHomePress}
        onPriceCheckPress={onPriceCheckPress}
      />
    </View>
  );
}

const COLORS = {
  background: '#FAF7F2',
  coral: '#F26A4F',
  deepTeal: '#183F36',
  green: '#1E8B68',
  muted: '#66766F',
  paleGreen: '#EFF8F1',
  palePeach: '#FFF3E7',
  palePink: '#FDECEF',
  surface: '#FFFFFF',
  white: '#FFFFFF',
} as const;

const styles = StyleSheet.create({
  avatar: {
    alignItems: 'center',
    backgroundColor: '#E5F3EA',
    borderRadius: 28,
    height: 56,
    justifyContent: 'center',
    width: 56,
  },
  content: {
    gap: 12,
    paddingBottom: 26,
    paddingHorizontal: 20,
    paddingTop: 18,
  },
  dashboardCard: {
    borderRadius: 24,
    padding: 14,
  },
  dashboardCardCopy: {
    flex: 1,
    minWidth: 0,
  },
  dashboardCardHeader: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 12,
  },
  dashboardCardSubtitle: {
    color: COLORS.muted,
    fontFamily: priceCheckLocationTokens.fonts.body,
    fontSize: 14,
    lineHeight: 18,
    marginTop: 1,
  },
  dashboardCardTitle: {
    color: COLORS.deepTeal,
    fontFamily: priceCheckLocationTokens.fonts.cardTitle,
    fontSize: 21,
    lineHeight: 26,
  },
  detailCheckbox: {
    alignItems: 'center',
    height: 48,
    justifyContent: 'center',
    width: 48,
  },
  detailConsumedButton: {
    alignItems: 'center',
    height: 48,
    justifyContent: 'center',
    width: 48,
  },
  detailClose: {
    alignItems: 'center',
    height: 48,
    justifyContent: 'center',
    width: 48,
  },
  detailCopy: {
    flex: 1,
    minWidth: 0,
  },
  detailCompletedText: {
    color: COLORS.muted,
    textDecorationLine: 'line-through',
  },
  detailEmpty: {
    color: COLORS.muted,
    fontFamily: priceCheckLocationTokens.fonts.body,
    fontSize: 15,
    lineHeight: 20,
  },
  detailHeader: {
    alignItems: 'center',
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 8,
  },
  detailHeaderActions: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 6,
  },
  detailImage: {
    height: 42,
    width: 42,
  },
  detailPanel: {
    backgroundColor: COLORS.surface,
    borderColor: '#DCEBE1',
    borderRadius: 24,
    borderWidth: 1,
    gap: 7,
    padding: 16,
  },
  ocrBanner: {
    alignSelf: 'center',
    // Browser sizing fix only; Android/iOS retain their original layout.
    ...Platform.select({ web: { aspectRatio: 1761 / 732 } }),
    overflow: 'hidden',
    position: 'relative',
    width: '94%',
  },
  ocrBannerImage: {
    aspectRatio: 1761 / 732,
    height: undefined,
    width: '100%',
    // Browser sizing fix only; native image sizing above is unchanged.
    ...Platform.select({ web: {
      position: 'absolute' as const,
      left: 0,
      top: 0,
      height: '100%' as const,
    } }),
  },
  ocrTakePhotoHitArea: {
    backgroundColor: 'transparent',
    height: '23%',
    left: '33.5%',
    position: 'absolute',
    top: '47.5%',
    width: '31%',
  },
  ocrUploadImageHitArea: {
    backgroundColor: 'transparent',
    height: '23%',
    left: '66.4%',
    position: 'absolute',
    top: '47.5%',
    width: '30.8%',
  },
  detailProductName: {
    color: COLORS.deepTeal,
    fontFamily: priceCheckLocationTokens.fonts.cardTitle,
    fontSize: 15,
    lineHeight: 19,
  },
  detailQuantity: {
    color: COLORS.muted,
    fontFamily: priceCheckLocationTokens.fonts.body,
    fontSize: 12,
    lineHeight: 16,
  },
  detailEditableQuantity: {
    alignItems: 'center',
    backgroundColor: '#F2F7F4',
    borderColor: '#DCEBE1',
    borderRadius: 8,
    borderWidth: 1,
    flexDirection: 'row',
    maxWidth: 138,
    minHeight: 32,
    paddingHorizontal: 8,
  },
  detailQuantityInput: {
    color: COLORS.deepTeal,
    flex: 1,
    fontFamily: priceCheckLocationTokens.fonts.body,
    fontSize: 13,
    minWidth: 0,
    width: 0,
    paddingVertical: 3,
  },
  detailQuantityUnit: {
    color: COLORS.muted,
    fontFamily: priceCheckLocationTokens.fonts.body,
    fontSize: 12,
    marginLeft: 4,
  },
  detailEditAction: { alignSelf: 'flex-start', minHeight: 32, justifyContent: 'center' },
  remainingEditor: { gap: 5, paddingVertical: 5 },
  remainingUnitButton: { alignItems: 'center', flexDirection: 'row', minHeight: 36, minWidth: 48 },
  remainingUnitOption: { justifyContent: 'center', minHeight: 44, paddingHorizontal: 10 },
  remainingActions: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  remainingError: { color: '#A33026', fontSize: 12 },
  detailRow: {
    alignItems: 'center',
    borderTopColor: '#E5EEE9',
    borderTopWidth: 1,
    flexDirection: 'row',
    gap: 10,
    minHeight: 52,
    paddingTop: 6,
  },
  detailTitle: {
    color: COLORS.deepTeal,
    fontFamily: priceCheckLocationTokens.fonts.cardTitle,
    fontSize: 21,
    lineHeight: 26,
  },
  detailPrice: {
    color: COLORS.deepTeal,
    flexShrink: 0,
    fontFamily: priceCheckLocationTokens.fonts.bodySemibold,
    fontSize: 14,
    lineHeight: 19,
    maxWidth: 122,
    textAlign: 'right',
  },
  detailModify: {
    alignItems: 'center',
    backgroundColor: COLORS.paleGreen,
    borderRadius: 12,
    flexDirection: 'row',
    gap: 4,
    minHeight: 36,
    paddingHorizontal: 10,
  },
  detailModifyText: {
    color: COLORS.deepTeal,
    fontFamily: priceCheckLocationTokens.fonts.bodySemibold,
    fontSize: 12,
  },
  detailRemoveButton: {
    alignItems: 'center',
    height: 48,
    justifyContent: 'center',
    width: 48,
  },
  detailSectionHeading: {
    color: COLORS.deepTeal,
    fontFamily: priceCheckLocationTokens.fonts.bodySemibold,
    fontSize: 14,
    lineHeight: 18,
  },
  detailSectionHeader: {
    alignItems: 'center',
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: 2,
  },
  storeNotSelected: {
    backgroundColor: '#F2F7F4',
    borderRadius: 14,
    gap: 2,
    paddingHorizontal: 12,
    paddingVertical: 9,
  },
  storeNotSelectedCopy: {
    color: COLORS.muted,
    fontFamily: priceCheckLocationTokens.fonts.body,
    fontSize: 13,
    lineHeight: 17,
  },
  storeNotSelectedTitle: {
    color: COLORS.deepTeal,
    fontFamily: priceCheckLocationTokens.fonts.bodySemibold,
    fontSize: 14,
    lineHeight: 18,
  },
  storeSummary: {
    backgroundColor: '#F2F7F4',
    borderRadius: 14,
    gap: 1,
    paddingHorizontal: 12,
    paddingVertical: 9,
  },
  storeSummaryAddress: {
    color: COLORS.muted,
    fontFamily: priceCheckLocationTokens.fonts.body,
    fontSize: 12,
    lineHeight: 16,
    marginTop: 1,
  },
  storeSummaryDistance: {
    color: COLORS.muted,
    fontFamily: priceCheckLocationTokens.fonts.body,
    fontSize: 13,
    lineHeight: 17,
  },
  storeSummaryEyebrow: {
    color: COLORS.muted,
    fontFamily: priceCheckLocationTokens.fonts.body,
    fontSize: 12,
    lineHeight: 16,
  },
  storeSummaryLabel: {
    color: COLORS.green,
    fontFamily: priceCheckLocationTokens.fonts.bodySemibold,
    fontSize: 12,
    lineHeight: 16,
    marginTop: 4,
  },
  storeSummaryName: {
    color: COLORS.deepTeal,
    fontFamily: priceCheckLocationTokens.fonts.cardTitle,
    fontSize: 18,
    lineHeight: 22,
  },
  planCard: {
    alignItems: 'center',
    borderRadius: 24,
    marginTop: -12,
    overflow: 'hidden',
  },
  planCardAfterRecipes: {
    marginTop: -4,
  },
  planVisualFrame: {
    alignSelf: 'stretch',
    aspectRatio: 3.5,
    overflow: 'hidden',
    position: 'relative',
  },
  planVisual: {
    position: 'absolute',
  },
  fontLoading: {
    backgroundColor: COLORS.background,
    flex: 1,
  },
  header: {
    alignItems: 'center',
    flexDirection: 'row',
    justifyContent: 'space-between',
    minHeight: 66,
  },
  headerCopy: {
    flex: 1,
    minWidth: 0,
  },
  pageSubtitle: {
    color: COLORS.muted,
    fontFamily: priceCheckLocationTokens.fonts.body,
    fontSize: 18,
    lineHeight: 24,
    marginTop: 1,
  },
  pageTitle: {
    color: COLORS.deepTeal,
    fontFamily: priceCheckLocationTokens.fonts.heading,
    fontSize: 35,
    lineHeight: 42,
  },
  pressed: {
    opacity: 0.82,
  },
  screen: {
    backgroundColor: COLORS.background,
    flex: 1,
  },
  sectionIcon: {
    alignItems: 'center',
    borderRadius: 22,
    height: 44,
    justifyContent: 'center',
    width: 44,
  },
  shoppingListCard: {
    backgroundColor: COLORS.paleGreen,
  },
  thumbnailCell: {
    alignItems: 'center',
    gap: 4,
    width: 46,
  },
  thumbnailImage: {
    height: 44,
    width: 44,
  },
  thumbnailImageFrame: {
    alignItems: 'center',
    backgroundColor: COLORS.white,
    borderRadius: 12,
    height: 48,
    justifyContent: 'center',
    width: 46,
  },
  thumbnailLabel: {
    color: COLORS.deepTeal,
    fontFamily: priceCheckLocationTokens.fonts.bodySemibold,
    fontSize: 10,
    lineHeight: 14,
    textAlign: 'center',
    width: 46,
  },
  thumbnailStrip: {
    alignItems: 'flex-start',
    gap: 5,
    paddingTop: 10,
  },
  overflowCell: {
    backgroundColor: 'rgba(255, 255, 255, 0.6)',
    borderRadius: 14,
    height: 65,
    justifyContent: 'center',
  },
  overflowCount: {
    color: COLORS.deepTeal,
    fontFamily: priceCheckLocationTokens.fonts.cardTitle,
    fontSize: 20,
    lineHeight: 24,
  },
  overflowLabel: {
    color: COLORS.muted,
    fontFamily: priceCheckLocationTokens.fonts.body,
    fontSize: 11,
    lineHeight: 15,
  },
  whatYouHaveCard: {
    backgroundColor: COLORS.palePeach,
  },
  recipeCard: {
    backgroundColor: COLORS.surface,
    borderColor: '#DCEBE1',
    borderRadius: 16,
    borderWidth: 1,
    flex: 1,
    minWidth: 0,
    overflow: 'hidden',
  },
  recipeCardContent: {
    flex: 1,
    gap: 7,
    padding: 10,
  },
  recipeCardTitle: {
    color: COLORS.deepTeal,
    fontFamily: priceCheckLocationTokens.fonts.cardTitle,
    fontSize: 16,
    lineHeight: 19,
  },
  recipeCards: {
    flexDirection: 'row',
    gap: 8,
    marginTop: 12,
  },
  recipeImagePlaceholder: {
    backgroundColor: '#F4F8F3',
    height: 78,
  },
  recipeImage: {
    height: 78,
    width: '100%',
  },
  recipeMetadata: {
    alignItems: 'center',
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 5,
    minHeight: 18,
  },
  recipeMetadataDivider: {
    backgroundColor: '#D7E7DE',
    height: 14,
    width: 1,
  },
  recipeMetadataItem: {
    alignItems: 'center',
    flexDirection: 'row',
    flexShrink: 1,
    gap: 3,
    minWidth: 0,
  },
  recipeMetadataText: {
    color: COLORS.muted,
    flexShrink: 1,
    fontFamily: priceCheckLocationTokens.fonts.body,
    fontSize: 11,
    lineHeight: 15,
  },
  recipeMetadataUses: {
    flexShrink: 1,
  },
  recipeSection: {
    backgroundColor: COLORS.paleGreen,
    borderRadius: 24,
    padding: 14,
  },
  recipeSectionCopy: {
    flex: 1,
    minWidth: 0,
  },
  recipeSectionHeader: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 8,
  },
  recipeSectionSubtitle: {
    color: COLORS.muted,
    fontFamily: priceCheckLocationTokens.fonts.body,
    fontSize: 14,
    lineHeight: 18,
    marginTop: 1,
  },
  recipeSectionTitle: {
    color: COLORS.deepTeal,
    fontFamily: priceCheckLocationTokens.fonts.cardTitle,
    fontSize: 21,
    lineHeight: 26,
  },
  recipeSeeAll: {
    alignItems: 'center',
    flexDirection: 'row',
    flexShrink: 0,
    gap: 1,
  },
  recipeSeeAllText: {
    color: COLORS.deepTeal,
    fontFamily: priceCheckLocationTokens.fonts.bodySemibold,
    fontSize: 14,
    lineHeight: 18,
  },
  recipeTag: {
    borderRadius: 12,
    paddingHorizontal: 8,
    paddingVertical: 5,
  },
  recipeTagBlue: {
    backgroundColor: '#DCEFFA',
  },
  recipeTagGreen: {
    backgroundColor: '#DFF2E8',
  },
  recipeTagText: {
    color: COLORS.deepTeal,
    fontFamily: priceCheckLocationTokens.fonts.bodySemibold,
    fontSize: 10.5,
    lineHeight: 15,
  },
  recipeTags: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 5,
    marginTop: 'auto',
  },
});
