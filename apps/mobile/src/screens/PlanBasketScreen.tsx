import { MaterialCommunityIcons } from '@expo/vector-icons';
import { useFonts } from 'expo-font';
import { useEffect, useMemo, useState, type ComponentProps, type ReactNode } from 'react';
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import Svg, { Defs, LinearGradient as SvgLinearGradient, Rect, Stop } from 'react-native-svg';
import {
  addManualBasketItem,
  addBasketSuggestedRecommendation,
  getBasketSummary,
  getNeedItems,
  removeBasketItem,
  setBasketItemChoice,
  type BasketDraftItem,
  type BasketItemChoice,
  type BasketProposal,
  type BasketProposalItem,
  type BasketProposalRecommendation,
} from './basketContent';
import type { PlanDraft } from './planFlowContent';
import { PlanSummary } from './PlanSummary';
import {
  getPlanQuestionThreeProducts,
  PLAN_QUESTION_THREE_CATEGORIES,
} from './planQuestionThreeContent';
import { BasketItemImage } from '../components/BasketItemImage';
import {
  priceCheckLocationFontAssets,
  priceCheckLocationFonts,
  priceCheckLocationTokens,
} from '../components/price-check/priceCheckLocationTokens';

const BASKET_COLORS = {
  background: priceCheckLocationTokens.colors.background,
  card: '#FFFEFC',
  deepTeal: priceCheckLocationTokens.colors.deepTeal,
  muted: priceCheckLocationTokens.colors.secondaryText,
  softGreen: '#F1FAF6',
  softGreenStrong: '#E1F4E9',
  softYellow: '#FFF9E8',
  control: '#EFF3F4',
  primary: '#087C7E',
  white: '#FFFFFF',
} as const;

const BASKET_FONTS = priceCheckLocationFonts;
const BASKET_FONT_ASSETS = priceCheckLocationFontAssets;
const RECOMMENDATIONS_COLLAPSED_LIMIT = 3;

type BasketView = 'edit' | 'review';

export interface PlanBasketScreenProps {
  basketDraft: readonly BasketDraftItem[];
  basketProposal: BasketProposal;
  onBack?: () => void;
  onBasketDraftChange: (draft: readonly BasketDraftItem[]) => void;
  onCheckPrices?: (items: readonly BasketDraftItem[]) => void;
  /** Transient planner failure (e.g. the confirm-time budget block). */
  buildError?: string | null;
  /** True while the basket is being re-solved and price-checked. */
  checkPriceBusy?: boolean;
  /** Confirm-time budget block message - shown as a centered dialog. */
  budgetBlockMessage?: string | null;
  onBudgetBlockDismiss?: () => void;
  planDraft: PlanDraft;
}

function formatQuantity(item: BasketProposalItem | BasketDraftItem): string {
  return `${item.suggestedQuantity} ${item.unit}`;
}

function userFacingBuildError(message: string): string {
  if (/https?:\/\/|\bapi\b|network|fetch failed|connection failed/i.test(message)) {
    return "Couldn't refresh the latest plan. Please try again.";
  }
  return message;
}

function Header({
  onAddItem,
  onBack,
}: {
  onAddItem: () => void;
  onBack?: () => void;
}) {
  return (
    <View style={styles.header}>
      <View style={styles.headerTopRow}>
        <Pressable
          accessibilityLabel="Go back"
          accessibilityRole="button"
          onPress={onBack}
          style={({ pressed }) => [styles.iconButton, pressed && styles.pressed]}
        >
          <MaterialCommunityIcons color={BASKET_COLORS.deepTeal} name="arrow-left" size={28} />
        </Pressable>
        <View style={styles.headerCopy}>
          <Text accessibilityRole="header" style={styles.pageTitle}>My Basket</Text>
        </View>
        <Pressable
          accessibilityLabel="Add item"
          accessibilityRole="button"
          onPress={onAddItem}
          style={({ pressed }) => [styles.addItemButton, pressed && styles.pressed]}
        >
          <MaterialCommunityIcons color={BASKET_COLORS.deepTeal} name="plus-circle" size={20} />
          <Text style={styles.addItemText}>Add item</Text>
        </Pressable>
      </View>
      <Text style={styles.pageSubtitle}>Review and adjust this week’s plan.</Text>
    </View>
  );
}

function SectionHeader({
  accent,
  count,
  icon,
  isExpanded,
  onToggle,
  title,
}: {
  accent: 'usuals' | 'recommendations';
  count: number;
  icon: ComponentProps<typeof MaterialCommunityIcons>['name'];
  isExpanded: boolean;
  onToggle: () => void;
  title: string;
}) {
  return (
    <View style={styles.sectionHeader}>
      <View style={styles.sectionIcon}>
        <MaterialCommunityIcons
          color={accent === 'usuals' ? '#EC5360' : '#3C9A6C'}
          name={icon}
          size={24}
        />
      </View>
      <View style={styles.sectionTitleWrap}>
        <View style={styles.sectionTitleLine}>
          <Text style={styles.sectionTitle}>{title}</Text>
          <View style={styles.countBadge}>
            <Text style={styles.countBadgeText}>{count} items</Text>
          </View>
        </View>
      </View>
      <Pressable
        accessibilityLabel={`${isExpanded ? 'Collapse' : 'Expand'} ${title}`}
        accessibilityRole="button"
        onPress={onToggle}
        style={({ pressed }) => [styles.smallIconButton, pressed && styles.pressed]}
      >
        <MaterialCommunityIcons
          color={BASKET_COLORS.deepTeal}
          name={isExpanded ? 'chevron-up' : 'chevron-down'}
          size={25}
        />
      </Pressable>
    </View>
  );
}

function ChoiceButton({
  choice,
  isSelected,
  onPress,
}: {
  choice: BasketItemChoice;
  isSelected: boolean;
  onPress: () => void;
}) {
  return (
    <Pressable
      accessibilityLabel={choice[0].toUpperCase() + choice.slice(1)}
      accessibilityRole="button"
      accessibilityState={{ selected: isSelected }}
      onPress={onPress}
      style={({ pressed }) => [
        styles.choiceButton,
        isSelected && styles.choiceButtonSelected,
        !isSelected && styles.choiceButtonUnselected,
        pressed && styles.pressed,
      ]}
    >
      <Text style={[styles.choiceText, isSelected ? styles.choiceTextSelected : styles.choiceTextUnselected]}>
        {choice[0].toUpperCase() + choice.slice(1)}
      </Text>
    </Pressable>
  );
}

function BasketItemRow({
  item,
  onChoiceChange,
  showManualTag = false,
}: {
  item: BasketDraftItem;
  onChoiceChange: (choice: BasketItemChoice) => void;
  showManualTag?: boolean;
}) {
  return (
    <View style={styles.basketItemRow}>
      <View style={styles.itemImageWrap}>
        <BasketItemImage imageSource={item.imageSource} name={item.name} style={styles.itemImage} />
      </View>
      <View style={styles.itemCopy}>
        <View style={styles.itemNameLine}>
          {showManualTag ? (
            <View style={styles.manualTag}>
              <Text style={styles.manualTagText}>Added</Text>
            </View>
          ) : null}
          <Text numberOfLines={2} style={styles.itemName}>{item.name}</Text>
        </View>
        <Text style={styles.itemQuantity}>{formatQuantity(item)}</Text>
      </View>
      <View style={styles.choiceGroup}>
        <ChoiceButton choice="need" isSelected={item.choice === 'need'} onPress={() => onChoiceChange('need')} />
        <ChoiceButton choice="have" isSelected={item.choice === 'have'} onPress={() => onChoiceChange('have')} />
        <ChoiceButton choice="skip" isSelected={item.choice === 'skip'} onPress={() => onChoiceChange('skip')} />
      </View>
    </View>
  );
}

function RecommendationRow({
  isAdded,
  onPress,
  recommendation,
}: {
  isAdded: boolean;
  onPress: () => void;
  recommendation: BasketProposalRecommendation;
}) {
  return (
    <View style={styles.recommendationRow}>
      <View style={styles.itemImageWrap}>
        <BasketItemImage imageSource={recommendation.imageSource} name={recommendation.name} style={styles.itemImage} />
      </View>
      <View style={styles.recommendationCopy}>
        <Text numberOfLines={2} style={[styles.itemName, styles.recommendationName]}>
          {recommendation.name}
        </Text>
      </View>
      <Pressable
        accessibilityLabel={isAdded ? `Remove ${recommendation.name}` : recommendation.needsSpace ? `No room for ${recommendation.name}` : `Add ${recommendation.name}`}
        accessibilityRole="button"
        accessibilityState={{ disabled: recommendation.needsSpace === true, selected: isAdded }}
        disabled={recommendation.needsSpace === true}
        onPress={onPress}
        style={({ pressed }) => [
          styles.recommendationAction,
          isAdded && styles.recommendationActionAdded,
          pressed && styles.pressed,
        ]}
      >
        <MaterialCommunityIcons
          color={isAdded ? BASKET_COLORS.primary : '#3C9A6C'}
          name={isAdded ? 'check' : 'plus'}
          size={20}
        />
        <Text style={styles.recommendationActionText}>{isAdded ? 'Added' : recommendation.needsSpace ? 'No room' : 'Add'}</Text>
      </Pressable>
    </View>
  );
}

function ExpandButton({
  label,
  onPress,
}: {
  label: string;
  onPress: () => void;
}) {
  return (
    <Pressable
      accessibilityLabel={label}
      accessibilityRole="button"
      onPress={onPress}
      style={({ pressed }) => [styles.expandButton, pressed && styles.pressed]}
    >
      <Text style={styles.expandButtonText}>{label}</Text>
      <MaterialCommunityIcons color={BASKET_COLORS.deepTeal} name="chevron-down" size={24} />
    </Pressable>
  );
}

function BasketStickyFooter({
  onReview,
  summary,
}: {
  onReview: () => void;
  summary: ReturnType<typeof getBasketSummary>;
}) {
  return (
    <View style={styles.stickyFooter}>
      <View style={styles.footerSummary}>
        <Text numberOfLines={2} style={styles.footerCount}>{[
          `${summary.needCount} need`,
          summary.haveCount > 0 ? `${summary.haveCount} have` : null,
          summary.skippedCount > 0 ? `${summary.skippedCount} skipped` : null,
        ].filter((part): part is string => part !== null).join(' · ')}</Text>
      </View>
      <Pressable
        accessibilityLabel="Review basket"
        accessibilityRole="button"
        accessibilityState={{ disabled: summary.count === 0 }}
        disabled={summary.count === 0}
        onPress={onReview}
        style={({ pressed }) => [
          styles.reviewButton,
          summary.count === 0 && styles.reviewButtonDisabled,
          pressed && styles.pressed,
        ]}
      >
        <Text style={styles.reviewButtonText}>Review basket</Text>
        <MaterialCommunityIcons color={BASKET_COLORS.white} name="arrow-right" size={25} />
      </Pressable>
    </View>
  );
}

function SheetShell({
  children,
  variant = 'default',
}: {
  children: ReactNode;
  variant?: 'default' | 'addItem';
}) {
  return (
    <View style={styles.sheetOverlay}>
      <View style={styles.sheetScrim} />
      <View style={[styles.sheet, variant === 'addItem' && styles.addItemSheet]}>{children}</View>
    </View>
  );
}

function SheetHandle() {
  return <View accessibilityElementsHidden style={styles.sheetHandle} />;
}

function ReviewBasketSheet({
  basketDraft,
  busy,
  hasError,
  onClose,
  onConfirm,
  onRemove,
  onAddMoreItems,
}: {
  basketDraft: readonly BasketDraftItem[];
  busy: boolean;
  hasError: boolean;
  onAddMoreItems: () => void;
  onClose: () => void;
  onConfirm: () => void;
  onRemove: (productId: string) => void;
}) {
  const needItems = getNeedItems(basketDraft);

  return (
    <SheetShell>
      <SheetHandle />
      <View style={styles.sheetHeader}>
        <Text accessibilityRole="header" style={styles.sheetTitle}>Review your basket</Text>
        <Pressable
          accessibilityLabel="Close review basket"
          accessibilityRole="button"
          accessibilityState={{ disabled: busy }}
          disabled={busy}
          onPress={onClose}
          style={({ pressed }) => [styles.reviewCloseButton, pressed && styles.pressed]}
        >
          <View style={styles.reviewCloseVisual}>
            <MaterialCommunityIcons color={BASKET_COLORS.deepTeal} name="close" size={22} />
          </View>
        </Pressable>
      </View>
      <Text style={styles.sheetCount}>{needItems.length} items to buy</Text>
      <Text style={styles.sheetHelper}>We&apos;ll check prices for these items.</Text>
      <ScrollView
        contentContainerStyle={styles.sheetScrollContent}
        showsVerticalScrollIndicator={false}
      >
        {needItems.map((item) => (
          <View key={item.productId} style={styles.reviewItemRow}>
            <View style={styles.itemImageWrap}>
              <BasketItemImage imageSource={item.imageSource} name={item.name} style={styles.itemImage} />
            </View>
            <View style={styles.reviewItemCopy}>
              <Text numberOfLines={2} style={styles.itemName}>{item.name}</Text>
              <Text style={styles.itemQuantity}>{formatQuantity(item)}</Text>
            </View>
            <Pressable
              accessibilityLabel={`Remove ${item.name} from basket`}
              accessibilityRole="button"
              onPress={() => onRemove(item.productId)}
              style={({ pressed }) => [styles.trashButton, pressed && styles.pressed]}
            >
              <MaterialCommunityIcons color="#82918A" name="delete-outline" size={21} />
            </Pressable>
          </View>
        ))}
        <Pressable
          accessibilityLabel="Add more items"
          accessibilityRole="button"
          accessibilityState={{ disabled: busy }}
          disabled={busy}
          onPress={onAddMoreItems}
          style={({ pressed }) => [styles.addMoreButton, pressed && styles.pressed]}
        >
          <MaterialCommunityIcons color={BASKET_COLORS.deepTeal} name="plus" size={23} />
          <Text style={styles.addMoreText}>Add more items</Text>
        </Pressable>
        <View style={styles.reviewFinalSummary}>
          <Text style={styles.reviewFinalTitle}>
            {busy ? 'Checking prices near you…' : hasError ? 'Couldn’t check prices right now.' : 'Ready to compare?'}
          </Text>
          <Text style={styles.reviewFinalCopy}>
            {busy
              ? `Comparing your ${needItems.length} items across nearby stores.`
              : hasError
                ? 'Please try again.'
                : `We’ll check prices for these ${needItems.length} items.`}
          </Text>
        </View>
        <Pressable
          accessibilityLabel={busy ? 'Checking prices' : hasError ? 'Try checking prices again' : 'Confirm and check prices'}
          accessibilityRole="button"
          onPress={onConfirm}
          disabled={busy}
          accessibilityState={{ busy, disabled: busy }}
          style={({ pressed }) => [
            styles.sheetPrimaryButton,
            busy && styles.sheetPrimaryButtonDisabled,
            pressed && styles.pressed,
          ]}
        >
          {busy ? (
            <>
              <ActivityIndicator color={BASKET_COLORS.white} size="small" />
              <Text style={styles.sheetPrimaryText}>Checking prices…</Text>
            </>
          ) : (
            <>
              <Text style={styles.sheetPrimaryText}>{hasError ? 'Try again' : 'Confirm & check prices'}</Text>
              <MaterialCommunityIcons color={BASKET_COLORS.white} name="arrow-right" size={26} />
            </>
          )}
        </Pressable>
        {hasError && !busy ? (
          <Pressable
            accessibilityLabel="Back to basket"
            accessibilityRole="button"
            onPress={onClose}
            style={({ pressed }) => [styles.reviewBackButton, pressed && styles.pressed]}
          >
            <Text style={styles.reviewBackText}>Back to basket</Text>
          </Pressable>
        ) : null}
      </ScrollView>
    </SheetShell>
  );
}

function AddItemSheet({
  basketDraft,
  onAdd,
  onClose,
}: {
  basketDraft: readonly BasketDraftItem[];
  onAdd: (item: BasketProposalItem) => void;
  onClose: () => void;
}) {
  const [searchQuery, setSearchQuery] = useState('');
  const normalizedQuery = searchQuery.trim().toLowerCase();
  const basketProductIds = new Set(basketDraft.map((item) => item.productId));
  const matchingProducts = getPlanQuestionThreeProducts()
    .filter((product) => !basketProductIds.has(product.id))
    .filter((product) => !normalizedQuery || product.name.toLowerCase().includes(normalizedQuery))
    .slice(0, normalizedQuery ? 20 : 10);

  return (
    <SheetShell variant="addItem">
      <SheetHandle />
      <View style={[styles.sheetHeader, styles.addItemSheetHeader]}>
        <View style={styles.addItemSheetTitleWrap}>
          <Text accessibilityRole="header" style={[styles.sheetTitle, styles.addItemSheetTitle]}>Add item</Text>
          <Text style={styles.addItemSheetHelper}>Search from your usual food catalogue.</Text>
        </View>
        <Pressable
          accessibilityLabel="Close add item"
          accessibilityRole="button"
          onPress={onClose}
          style={({ pressed }) => [styles.closeButton, pressed && styles.pressed]}
        >
          <MaterialCommunityIcons color={BASKET_COLORS.deepTeal} name="close" size={25} />
        </Pressable>
      </View>
      <View style={styles.searchField}>
        <MaterialCommunityIcons color={BASKET_COLORS.muted} name="magnify" size={24} />
        <TextInput
          autoCapitalize="none"
          autoCorrect={false}
          accessibilityLabel="Search foods"
          placeholder="Search foods"
          placeholderTextColor="#7A9495"
          onChangeText={setSearchQuery}
          style={styles.searchInput}
          value={searchQuery}
        />
        {searchQuery ? (
          <Pressable
            accessibilityLabel="Clear food search"
            accessibilityRole="button"
            onPress={() => setSearchQuery('')}
            style={({ pressed }) => [styles.clearSearchButton, pressed && styles.pressed]}
          >
            <MaterialCommunityIcons color={BASKET_COLORS.deepTeal} name="close-circle" size={21} />
          </Pressable>
        ) : null}
      </View>
      <ScrollView
        contentContainerStyle={styles.catalogResultsContent}
        keyboardShouldPersistTaps="handled"
        style={styles.catalogResults}
        showsVerticalScrollIndicator={false}
      >
        {matchingProducts.length > 0 ? matchingProducts.map((product) => {
          const isAlreadyInBasket = basketDraft.some((item) => item.productId === product.id);
          const proposalItem: BasketProposalItem = {
            productId: product.id,
            name: product.name,
            imageSource: product.imageSource,
            suggestedQuantity: 1,
            // Placeholder only - the re-solve replaces it with the real
            // purchase unit from the planner response (never the generic
            // "item", 2026-09-14 user rule).
            unit: 'pack',
          };

          return (
            <View key={product.id} style={styles.catalogRow}>
              <View style={styles.catalogImageWrap}>
                <BasketItemImage imageSource={proposalItem.imageSource} name={proposalItem.name} style={styles.catalogImage} />
              </View>
              <Text numberOfLines={2} style={styles.catalogName}>{product.name}</Text>
              <Pressable
                accessibilityLabel={isAlreadyInBasket ? `${product.name} already added` : `Add ${product.name}`}
                accessibilityRole="button"
                disabled={isAlreadyInBasket}
                onPress={() => onAdd(proposalItem)}
                style={({ pressed }) => [
                  styles.catalogAction,
                  isAlreadyInBasket && styles.catalogActionAdded,
                  pressed && styles.pressed,
                ]}
              >
                <MaterialCommunityIcons
                  color={isAlreadyInBasket ? BASKET_COLORS.primary : BASKET_COLORS.deepTeal}
                  name={isAlreadyInBasket ? 'check' : 'plus'}
                  size={19}
                />
                <Text style={styles.catalogActionText}>{isAlreadyInBasket ? 'Added' : 'Add'}</Text>
              </Pressable>
            </View>
          );
        }) : (
          <Text style={styles.noCatalogResults}>No foods match that search.</Text>
        )}
      </ScrollView>
    </SheetShell>
  );
}

function BudgetBlockDialog({
  message,
  onDismiss,
}: {
  message: string;
  onDismiss: () => void;
}) {
  return (
    <View style={styles.dialogOverlay}>
      <View style={styles.dialogScrim} />
      <View style={styles.dialogCard}>
        <MaterialCommunityIcons color="#B3261E" name="alert-circle-outline" size={34} />
        <Text accessibilityRole="header" style={styles.dialogTitle}>Over your budget</Text>
        <Text style={styles.dialogMessage}>{message}</Text>
        <Pressable
          accessibilityLabel="Back to edit basket"
          accessibilityRole="button"
          onPress={onDismiss}
          style={({ pressed }) => [styles.sheetPrimaryButton, pressed && styles.pressed]}
        >
          <Text style={styles.sheetPrimaryText}>Back to edit basket</Text>
        </Pressable>
      </View>
    </View>
  );
}

export function PlanBasketScreen({
  basketDraft,
  basketProposal,
  onBack,
  onBasketDraftChange,
  onCheckPrices,
  buildError,
  checkPriceBusy = false,
  budgetBlockMessage,
  onBudgetBlockDismiss,
  planDraft,
}: PlanBasketScreenProps) {
  const [fontsLoaded] = useFonts(BASKET_FONT_ASSETS);
  const [basketView, setBasketView] = useState<BasketView>('edit');
  const [isAddItemOpen, setIsAddItemOpen] = useState(false);
  const [isSubmittingPriceCheck, setIsSubmittingPriceCheck] = useState(false);
  // Week plan rows keep the draft's stable order within their catalogue group.
  const allUsualItems = basketDraft.filter(
    (item) => item.source === 'usual'
      || item.source === 'manual'
      || item.source === 'recommendation',
  );
  const foodCategories = getPlanQuestionThreeProducts();
  const categoryByProductId = useMemo(
    () => new Map(foodCategories.map((food) => [food.id, food.category])),
    [foodCategories],
  );
  const categoryGroups = useMemo(() => {
    const groups = PLAN_QUESTION_THREE_CATEGORIES.map((category) => ({
      ...category,
      items: [] as BasketDraftItem[],
    }));
    const groupById = new Map(groups.map((group) => [group.id, group]));
    for (const item of allUsualItems) {
      const categoryId = categoryByProductId.get(item.productId) ?? 'other';
      (groupById.get(categoryId) ?? groupById.get('other')!).items.push(item);
    }
    return groups.filter((group) => group.items.length > 0);
  }, [allUsualItems, categoryByProductId]);
  const [expandedCategories, setExpandedCategories] = useState<Set<string> | null>(null);
  const [isRecommendationsExpanded, setIsRecommendationsExpanded] = useState(false);

  const bannerMessage = buildError ?? null;
  useEffect(() => {
    if (bannerMessage || budgetBlockMessage) {
      setIsSubmittingPriceCheck(false);
    }
  }, [bannerMessage, budgetBlockMessage]);

  const summary = getBasketSummary(basketDraft);
  // 2026-09-17 user rule (A6 completion): the week plan renders in DRAFT
  // ORDER. The old source grouping ([...usuals, ...manuals, ...added])
  // reshuffled the list on every re-solve - a worth-added item promoted
  // from 'recommendation' to 'usual' jumped groups ("点击 Have 之后跳到最
  // 下面" persisted after the A6 draft-order fix because the RENDER layer
  // re-grouped by source). Draft order is stabilised by the A6 stable sort
  // in App.tsx; positions must survive all the way to the screen.
  const effectiveExpandedCategories = expandedCategories
    ?? new Set(categoryGroups.slice(0, 1).map((group) => group.id));
  const weekPlanIds = new Set(allUsualItems.map((item) => item.productId));
  const availableRecommendations = basketProposal.recommendations.filter(
    (recommendation) => !weekPlanIds.has(recommendation.productId),
  );
  const visibleRecommendations = isRecommendationsExpanded
    ? availableRecommendations
    : availableRecommendations.slice(0, RECOMMENDATIONS_COLLAPSED_LIMIT);
  const recommendationsRemaining = Math.max(
    0,
    availableRecommendations.length - visibleRecommendations.length,
  );

  const updateChoice = (productId: string, choice: BasketItemChoice) => {
    onBasketDraftChange(setBasketItemChoice(basketDraft, productId, choice));
  };

  const toggleRecommendation = (recommendation: BasketProposalRecommendation) => {
    const existing = basketDraft.find((item) => item.productId === recommendation.productId);

    onBasketDraftChange(existing
      ? removeBasketItem(basketDraft, recommendation.productId)
      : addBasketSuggestedRecommendation(basketDraft, recommendation, basketProposal));
  };

  const openAddItemSheet = () => {
    setBasketView('edit');
    setIsAddItemOpen(true);
  };

  const addManualItem = (item: BasketProposalItem) => {
    onBasketDraftChange(addManualBasketItem(basketDraft, item));
  };

  if (!fontsLoaded) {
    return <View style={styles.fontLoading} />;
  }

  return (
    <View style={styles.screen}>
      <Svg height="100%" preserveAspectRatio="none" style={StyleSheet.absoluteFill} width="100%">
        <Defs>
          <SvgLinearGradient id="planBasketPageGradient" x1="0" x2="0" y1="0" y2="1">
            <Stop offset="0%" stopColor="#D8F1E5" stopOpacity="0.98" />
            <Stop offset="18%" stopColor="#F0F8EF" stopOpacity="0.95" />
            <Stop offset="57%" stopColor="#FBFBF6" stopOpacity="0.86" />
            <Stop offset="100%" stopColor="#FFF6E7" stopOpacity="0.76" />
          </SvgLinearGradient>
        </Defs>
        <Rect fill="url(#planBasketPageGradient)" height="100%" width="100%" />
      </Svg>
      <ScrollView
        contentContainerStyle={styles.content}
        showsVerticalScrollIndicator={false}
      >
        <Header onAddItem={() => setIsAddItemOpen(true)} onBack={onBack} />
        <PlanSummary planDraft={planDraft} />
        {bannerMessage ? (
          <View style={styles.banner}>
            <MaterialCommunityIcons color="#9B554C" name="alert-circle-outline" size={17} />
            <Text style={styles.bannerText}>{userFacingBuildError(bannerMessage)}</Text>
          </View>
        ) : null}

        <View style={[styles.section, styles.usualsSection]}>
          <View style={styles.sectionHeader}>
            <View style={styles.sectionIcon}>
            <MaterialCommunityIcons color={BASKET_COLORS.deepTeal} name="calendar-check" size={24} />
            </View>
            <View style={styles.sectionTitleWrap}>
              <View style={styles.sectionTitleLine}>
                <Text style={styles.sectionTitle}>Week plan</Text>
                <View style={styles.countBadge}>
                  <Text style={styles.countBadgeText}>{allUsualItems.length} items</Text>
                </View>
              </View>
            </View>
          </View>
          <View style={styles.weekPlanHelper}>
            <Text style={styles.weekPlanHelperText}>Based on your budget and usual habits.</Text>
            <Text style={styles.weekPlanHelperText}>Mark each item as Need, Have, or Skip.</Text>
          </View>
          {categoryGroups.map((group) => {
            const isExpanded = effectiveExpandedCategories.has(group.id);
            return (
              <View key={group.id}>
                <Pressable
                  accessibilityLabel={`${isExpanded ? 'Collapse' : 'Expand'} ${group.label}, ${group.items.length} items`}
                  accessibilityRole="button"
                  accessibilityState={{ expanded: isExpanded }}
                  onPress={() => setExpandedCategories((current) => {
                    const next = new Set(current ?? effectiveExpandedCategories);
                    if (next.has(group.id)) next.delete(group.id);
                    else next.add(group.id);
                    return next;
                  })}
                  style={({ pressed }) => [
                    styles.categoryHeader,
                    isExpanded && styles.categoryHeaderExpanded,
                    pressed && styles.pressed,
                  ]}
                >
                  <Text style={styles.categoryTitle}>{group.label}</Text>
                  <Text style={styles.categoryCount}>{group.items.length} items</Text>
                  <MaterialCommunityIcons
                    color={BASKET_COLORS.deepTeal}
                    name={isExpanded ? 'chevron-up' : 'chevron-down'}
                    size={23}
                  />
                </Pressable>
                {isExpanded ? (
                  <View style={styles.expandedCategoryItems}>
                    {group.items.map((item) => (
                  <BasketItemRow
                    item={item}
                    key={item.productId}
                    onChoiceChange={(choice) => updateChoice(item.productId, choice)}
                    showManualTag={item.source === 'manual'}
                  />
                    ))}
                  </View>
                ) : null}
              </View>
            );
          })}
        </View>

        <View style={[styles.section, styles.recommendationSection]}>
          <SectionHeader
            accent="recommendations"
            count={availableRecommendations.length}
            icon="sprout"
            isExpanded={isRecommendationsExpanded}
            onToggle={() => setIsRecommendationsExpanded((expanded) => !expanded)}
            title="Worth considering"
          />
          <Text style={styles.sectionHelper}>Other foods that could also fit your plan.</Text>
          {availableRecommendations.length === 0 && !buildError ? (
            <Text style={styles.sectionHelper}>No new safe, priced food idea is available right now.</Text>
          ) : null}
          {visibleRecommendations.map((recommendation) => {
            const isAdded = basketDraft.some(
              (item) => item.productId === recommendation.productId && item.source === 'recommendation',
            );

            return (
              <RecommendationRow
                isAdded={isAdded}
                key={recommendation.productId}
                onPress={() => toggleRecommendation(recommendation)}
                recommendation={recommendation}
              />
            );
          })}
          {recommendationsRemaining > 0 ? (
            <ExpandButton
              label={`See ${recommendationsRemaining} more items`}
              onPress={() => setIsRecommendationsExpanded(true)}
            />
          ) : isRecommendationsExpanded && availableRecommendations.length > RECOMMENDATIONS_COLLAPSED_LIMIT ? (
            <ExpandButton label="See fewer items" onPress={() => setIsRecommendationsExpanded(false)} />
          ) : null}
        </View>
      </ScrollView>

      <BasketStickyFooter onReview={() => setBasketView('review')} summary={summary} />

      {basketView === 'review' ? (
        <ReviewBasketSheet
          basketDraft={basketDraft}
          busy={isSubmittingPriceCheck || checkPriceBusy}
          hasError={Boolean(bannerMessage)}
          onAddMoreItems={openAddItemSheet}
          onClose={() => setBasketView('edit')}
          onConfirm={() => {
            if (isSubmittingPriceCheck || checkPriceBusy || !onCheckPrices) return;
            setIsSubmittingPriceCheck(true);
            onCheckPrices(getNeedItems(basketDraft));
          }}
          onRemove={(productId) => {
            onBasketDraftChange(removeBasketItem(basketDraft, productId));
          }}
        />
      ) : null}

      {isAddItemOpen ? (
        <AddItemSheet
          basketDraft={basketDraft}
          onAdd={addManualItem}
          onClose={() => setIsAddItemOpen(false)}
        />
      ) : null}

      {budgetBlockMessage ? (
        <BudgetBlockDialog
          message={budgetBlockMessage}
          onDismiss={() => {
            onBudgetBlockDismiss?.();
            setBasketView('edit'); // the block asks for Skip edits
          }}
        />
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  addItemSheet: {
    maxHeight: '78%',
    minHeight: 500,
    paddingBottom: 14,
  },
  addItemSheetHeader: {
    alignItems: 'center',
    minHeight: 68,
  },
  addItemButton: {
    alignItems: 'center',
    borderColor: '#D6E1DF',
    borderRadius: 24,
    borderWidth: 1,
    flexDirection: 'row',
    gap: 6,
    height: 42,
    justifyContent: 'center',
    paddingHorizontal: 12,
  },
  addItemText: {
    color: BASKET_COLORS.deepTeal,
    fontFamily: BASKET_FONTS.body,
    fontSize: 14,
    lineHeight: 18,
  },
  addItemSheetHelper: {
    color: BASKET_COLORS.muted,
    fontFamily: BASKET_FONTS.body,
    fontSize: 13,
    lineHeight: 18,
    marginTop: 1,
  },
  addItemSheetTitle: {
    flex: 0,
    flexShrink: 0,
    fontSize: 30,
    lineHeight: 38,
    minHeight: 38,
  },
  addItemSheetTitleWrap: {
    flex: 1,
    minWidth: 0,
  },
  addMoreButton: {
    alignItems: 'center',
    borderColor: '#D8E3DE',
    borderRadius: 28,
    borderWidth: 1,
    flexDirection: 'row',
    height: 52,
    justifyContent: 'center',
    marginTop: 16,
  },
  addMoreText: {
    color: BASKET_COLORS.deepTeal,
    fontFamily: BASKET_FONTS.body,
    fontSize: 15,
    lineHeight: 20,
  },
  basketItemRow: {
    alignItems: 'center',
    borderTopColor: '#F0EDE7',
    borderTopWidth: 1,
    flexDirection: 'row',
    minHeight: 72,
    paddingVertical: 6,
  },
  closeButton: {
    alignItems: 'center',
    backgroundColor: '#EAF3F7',
    borderRadius: 20,
    height: 40,
    justifyContent: 'center',
    width: 40,
  },
  reviewCloseButton: {
    alignItems: 'center',
    height: 48,
    justifyContent: 'center',
    width: 48,
  },
  reviewCloseVisual: {
    alignItems: 'center',
    backgroundColor: '#F1F5F5',
    borderRadius: 18,
    height: 36,
    justifyContent: 'center',
    width: 36,
  },
  catalogAction: {
    alignItems: 'center',
    backgroundColor: BASKET_COLORS.softGreenStrong,
    borderRadius: 11,
    flexDirection: 'row',
    height: 48,
    justifyContent: 'center',
    minWidth: 64,
    paddingHorizontal: 7,
  },
  catalogActionAdded: {
    backgroundColor: '#E7F2EC',
  },
  catalogActionText: {
    color: BASKET_COLORS.deepTeal,
    fontFamily: BASKET_FONTS.bodySemibold,
    fontSize: 13,
    lineHeight: 17,
    marginLeft: 2,
  },
  catalogImage: {
    height: 46,
    resizeMode: 'contain',
    width: 46,
  },
  catalogImageWrap: {
    alignItems: 'center',
    backgroundColor: '#FBFCFA',
    borderRadius: 11,
    height: 50,
    justifyContent: 'center',
    overflow: 'hidden',
    width: 50,
  },
  catalogName: {
    color: BASKET_COLORS.deepTeal,
    flex: 1,
    fontFamily: BASKET_FONTS.bodySemibold,
    fontSize: 14,
    lineHeight: 18,
    marginHorizontal: 10,
    minWidth: 0,
  },
  catalogResults: {
    maxHeight: 500,
    marginTop: 10,
  },
  catalogResultsContent: {
    paddingBottom: 4,
  },
  catalogRow: {
    alignItems: 'center',
    borderTopColor: '#E8EFEA',
    borderTopWidth: 1,
    flexDirection: 'row',
    minHeight: 64,
    paddingVertical: 6,
  },
  content: {
    paddingBottom: 12,
    paddingHorizontal: 16,
    paddingTop: 18,
  },
  choiceButton: {
    alignItems: 'center',
    borderRadius: 12,
    flex: 1,
    height: 40,
    justifyContent: 'center',
    marginLeft: 0,
    minWidth: 0,
    paddingHorizontal: 1,
  },
  choiceButtonUnselected: {
    backgroundColor: 'transparent',
  },
  choiceButtonSelected: {
    backgroundColor: BASKET_COLORS.deepTeal,
  },
  choiceGroup: {
    alignItems: 'center',
    backgroundColor: '#F2F5F1',
    borderRadius: 14,
    flexDirection: 'row',
    marginLeft: 0,
    padding: 2,
    width: 154,
  },
  choiceText: {
    fontFamily: BASKET_FONTS.body,
    fontSize: 12,
    lineHeight: 16,
  },
  choiceTextUnselected: {
    color: '#66756F',
  },
  choiceTextSelected: {
    color: BASKET_COLORS.white,
  },
  countBadge: {
    backgroundColor: '#F1F5F3',
    borderRadius: 12,
    marginLeft: 8,
    paddingHorizontal: 9,
    paddingVertical: 5,
  },
  countBadgeText: {
    color: BASKET_COLORS.deepTeal,
    fontFamily: BASKET_FONTS.bodySemibold,
    fontSize: 12,
    lineHeight: 15,
  },
  expandButton: {
    alignItems: 'center',
    backgroundColor: BASKET_COLORS.softGreen,
    borderRadius: 18,
    flexDirection: 'row',
    height: 48,
    justifyContent: 'center',
    marginTop: 8,
  },
  expandButtonText: {
    color: BASKET_COLORS.deepTeal,
    fontFamily: BASKET_FONTS.bodySemibold,
    fontSize: 15,
    lineHeight: 20,
  },
  footerCount: {
    color: BASKET_COLORS.muted,
    fontFamily: BASKET_FONTS.body,
    fontSize: 14,
    lineHeight: 19,
  },
  footerCountRow: {
    alignItems: 'center',
    flexDirection: 'row',
  },
  footerOverflow: {
    alignItems: 'center',
    backgroundColor: '#EDF3F7',
    borderRadius: 9,
    height: 36,
    justifyContent: 'center',
    marginLeft: 3,
    width: 36,
  },
  footerOverflowText: {
    color: BASKET_COLORS.deepTeal,
    fontFamily: BASKET_FONTS.bodySemibold,
    fontSize: 14,
    lineHeight: 18,
  },
  footerSummary: {
    flex: 1,
    justifyContent: 'center',
    paddingLeft: 4,
  },
  footerThumbRow: {
    alignItems: 'center',
    flexDirection: 'row',
    marginTop: 5,
  },
  footerThumbnail: {
    alignItems: 'center',
    backgroundColor: '#F8FBF9',
    borderRadius: 9,
    height: 36,
    justifyContent: 'center',
    marginRight: 3,
    overflow: 'hidden',
    width: 36,
  },
  footerThumbnailImage: {
    height: 32,
    resizeMode: 'contain',
    width: 32,
  },
  footerBasketArt: {
    height: 28,
    resizeMode: 'contain',
    width: 30,
  },
  fontLoading: {
    backgroundColor: BASKET_COLORS.background,
    flex: 1,
  },
  header: {
    paddingBottom: 8,
  },
  headerTopRow: {
    alignItems: 'center',
    flexDirection: 'row',
    minHeight: 48,
  },
  headerCopy: {
    flex: 1,
    marginLeft: 3,
  },
  iconButton: {
    alignItems: 'center',
    height: 48,
    justifyContent: 'center',
    width: 48,
  },
  householdArt: {
    alignItems: 'flex-end',
    flexDirection: 'row',
    height: 32,
    justifyContent: 'center',
    width: 32,
  },
  householdArtChild: {
    marginLeft: -4,
  },
  householdArtImage: {
    height: 25,
    resizeMode: 'contain',
    width: 21,
  },
  itemCopy: {
    flex: 1,
    minWidth: 0,
    paddingHorizontal: 7,
  },
  itemImage: {
    height: 54,
    resizeMode: 'contain',
    width: 54,
  },
  itemImageWrap: {
    alignItems: 'center',
    backgroundColor: '#FBFCFA',
    borderRadius: 12,
    height: 56,
    justifyContent: 'center',
    overflow: 'hidden',
    width: 56,
  },
  itemName: {
    color: BASKET_COLORS.deepTeal,
    fontFamily: BASKET_FONTS.bodySemibold,
    flex: 1,
    fontSize: 14,
    lineHeight: 18,
  },
  itemNameLine: {
    alignItems: 'center',
    flexDirection: 'row',
    minWidth: 0,
  },
  itemQuantity: {
    color: BASKET_COLORS.muted,
    fontFamily: BASKET_FONTS.body,
    fontSize: 13,
    lineHeight: 18,
    marginTop: 1,
  },
  manualTag: {
    backgroundColor: BASKET_COLORS.softGreenStrong,
    borderRadius: 6,
    marginRight: 4,
    paddingHorizontal: 5,
    paddingVertical: 2,
  },
  manualTagText: {
    color: BASKET_COLORS.deepTeal,
    fontFamily: BASKET_FONTS.bodySemibold,
    fontSize: 10,
    lineHeight: 13,
  },
  pageSubtitle: {
    color: BASKET_COLORS.muted,
    fontFamily: BASKET_FONTS.body,
    fontSize: 16,
    lineHeight: 21,
    marginLeft: 51,
    marginTop: 3,
  },
  pageTitle: {
    color: BASKET_COLORS.deepTeal,
    fontFamily: BASKET_FONTS.heading,
    fontSize: 32,
    lineHeight: 38,
  },
  pressed: {
    opacity: 0.72,
  },
  recommendationAction: {
    alignItems: 'center',
    backgroundColor: BASKET_COLORS.softGreenStrong,
    borderRadius: 11,
    flexDirection: 'row',
    height: 48,
    justifyContent: 'center',
    minWidth: 76,
    paddingHorizontal: 8,
  },
  recommendationActionAdded: {
    backgroundColor: '#E4F5EC',
  },
  recommendationActionText: {
    color: BASKET_COLORS.deepTeal,
    fontFamily: BASKET_FONTS.bodySemibold,
    fontSize: 14,
    lineHeight: 18,
    marginLeft: 2,
  },
  recommendationCopy: {
    flex: 1,
    justifyContent: 'center',
    minWidth: 0,
    paddingHorizontal: 7,
  },
  recommendationName: {
    flex: 0,
  },
  recommendationRow: {
    alignItems: 'center',
    borderTopColor: '#E8EFEA',
    borderTopWidth: 1,
    flexDirection: 'row',
    minHeight: 72,
    paddingVertical: 6,
  },
  recommendationSection: {
    backgroundColor: BASKET_COLORS.softYellow,
  },
  noCatalogResults: {
    color: BASKET_COLORS.muted,
    fontFamily: BASKET_FONTS.body,
    fontSize: 15,
    lineHeight: 20,
    paddingVertical: 24,
    textAlign: 'center',
  },
  reviewButton: {
    alignItems: 'center',
    backgroundColor: BASKET_COLORS.primary,
    borderRadius: 27,
    flexDirection: 'row',
    gap: 5,
    height: 58,
    justifyContent: 'center',
    minWidth: 158,
    paddingHorizontal: 13,
  },
  reviewButtonDisabled: {
    backgroundColor: '#D8DFDD',
  },
  reviewButtonText: {
    color: BASKET_COLORS.white,
    fontFamily: BASKET_FONTS.bodySemibold,
    fontSize: 16,
    lineHeight: 21,
  },
  reviewItemCopy: {
    flex: 1,
    minWidth: 0,
    paddingHorizontal: 8,
  },
  reviewItemRow: {
    alignItems: 'center',
    borderBottomColor: '#F0EDE7',
    borderBottomWidth: 1,
    flexDirection: 'row',
    minHeight: 66,
    paddingVertical: 5,
  },
  reviewBackButton: {
    alignItems: 'center',
    height: 48,
    justifyContent: 'center',
    marginTop: 4,
  },
  reviewBackText: {
    color: BASKET_COLORS.muted,
    fontFamily: BASKET_FONTS.bodySemibold,
    fontSize: 14,
    lineHeight: 19,
  },
  section: {
    borderRadius: 20,
    marginTop: 14,
    paddingHorizontal: 10,
    paddingVertical: 10,
  },
  sectionHeader: {
    alignItems: 'center',
    flexDirection: 'row',
    minHeight: 44,
  },
  categoryHeader: {
    alignItems: 'center',
    backgroundColor: '#FBF9F5',
    borderRadius: 10,
    flexDirection: 'row',
    minHeight: 46,
    marginTop: 2,
    paddingHorizontal: 9,
    paddingVertical: 0,
  },
  categoryHeaderExpanded: {
    backgroundColor: '#F7F3EC',
  },
  categoryTitle: {
    color: BASKET_COLORS.deepTeal,
    flex: 1,
    fontFamily: BASKET_FONTS.bodySemibold,
    fontSize: 16,
    lineHeight: 21,
  },
  categoryCount: {
    color: BASKET_COLORS.muted,
    fontFamily: BASKET_FONTS.body,
    fontSize: 13,
    lineHeight: 18,
    marginRight: 7,
  },
  expandedCategoryItems: {
    paddingTop: 8,
  },
  weekPlanHelper: {
    marginBottom: 7,
    marginLeft: 42,
    marginTop: -2,
  },
  weekPlanHelperText: {
    color: BASKET_COLORS.muted,
    fontFamily: BASKET_FONTS.body,
    fontSize: 13,
    lineHeight: 18,
  },
  banner: {
    alignItems: 'flex-start',
    backgroundColor: '#FCE8E6',
    borderColor: '#B3261E',
    borderRadius: 10,
    borderWidth: 1,
    flexDirection: 'row',
    gap: 8,
    marginBottom: 10,
    marginTop: 10,
    paddingHorizontal: 12,
    paddingVertical: 10,
  },
  bannerText: {
    color: '#7A271A',
    flex: 1,
    fontFamily: BASKET_FONTS.body,
    fontSize: 14,
    lineHeight: 19,
  },
  sectionHelper: {
    color: BASKET_COLORS.muted,
    fontFamily: BASKET_FONTS.body,
    fontSize: 14,
    lineHeight: 19,
    marginBottom: 7,
    marginLeft: 42,
    marginTop: -2,
  },
  sectionIcon: {
    alignItems: 'center',
    borderRadius: 18,
    height: 36,
    justifyContent: 'center',
    width: 36,
  },
  sectionTitle: {
    color: BASKET_COLORS.deepTeal,
    fontFamily: BASKET_FONTS.heading,
    fontSize: 20,
    lineHeight: 25,
  },
  sectionTitleLine: {
    alignItems: 'center',
    flexDirection: 'row',
    flexWrap: 'wrap',
  },
  sectionTitleWrap: {
    flex: 1,
    marginLeft: 7,
    minWidth: 0,
  },
  sheet: {
    backgroundColor: BASKET_COLORS.card,
    borderTopLeftRadius: 26,
    borderTopRightRadius: 26,
    maxHeight: '92%',
    minHeight: 310,
    paddingHorizontal: 16,
    paddingTop: 11,
  },
  sheetCount: {
    color: BASKET_COLORS.deepTeal,
    fontFamily: BASKET_FONTS.cardTitle,
    fontSize: 21,
    lineHeight: 27,
    marginTop: 14,
  },
  sheetHandle: {
    alignSelf: 'center',
    backgroundColor: '#CBD9DE',
    borderRadius: 4,
    height: 6,
    width: 62,
  },
  sheetHeader: {
    alignItems: 'center',
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: 12,
  },
  searchField: {
    alignItems: 'center',
    backgroundColor: '#F2F7F5',
    borderColor: '#D9E8E2',
    borderRadius: 14,
    borderWidth: 1,
    flexDirection: 'row',
    height: 52,
    marginTop: 14,
    paddingHorizontal: 12,
  },
  searchInput: {
    color: BASKET_COLORS.deepTeal,
    flex: 1,
    fontFamily: BASKET_FONTS.body,
    fontSize: 16,
    height: 50,
    lineHeight: 21,
    marginLeft: 7,
    minWidth: 0,
    paddingVertical: 0,
  },
  clearSearchButton: {
    alignItems: 'center',
    height: 40,
    justifyContent: 'center',
    width: 40,
  },
  sheetHelper: {
    color: BASKET_COLORS.muted,
    fontFamily: BASKET_FONTS.body,
    fontSize: 15,
    lineHeight: 21,
    marginTop: 3,
  },
  sheetOverlay: {
    bottom: 0,
    justifyContent: 'flex-end',
    left: 0,
    position: 'absolute',
    right: 0,
    top: 0,
  },
  sheetPrimaryButton: {
    alignItems: 'center',
    alignSelf: 'stretch',
    backgroundColor: BASKET_COLORS.primary,
    borderRadius: 28,
    flexDirection: 'row',
    gap: 7,
    height: 58,
    justifyContent: 'center',
    marginBottom: 8,
    marginTop: 11,
  },
  sheetPrimaryText: {
    color: BASKET_COLORS.white,
    fontFamily: BASKET_FONTS.bodySemibold,
    fontSize: 17,
    lineHeight: 22,
  },
  sheetPrimaryButtonDisabled: {
    opacity: 0.6,
  },
  dialogOverlay: {
    alignItems: 'center',
    bottom: 0,
    justifyContent: 'center',
    left: 0,
    position: 'absolute',
    right: 0,
    top: 0,
  },
  dialogScrim: {
    backgroundColor: 'rgba(11, 34, 31, 0.58)',
    bottom: 0,
    left: 0,
    position: 'absolute',
    right: 0,
    top: 0,
  },
  dialogCard: {
    alignItems: 'center',
    backgroundColor: BASKET_COLORS.white,
    borderRadius: 20,
    gap: 12,
    maxWidth: '85%',
    paddingHorizontal: 22,
    paddingVertical: 24,
  },
  dialogTitle: {
    color: BASKET_COLORS.deepTeal,
    fontFamily: BASKET_FONTS.bodySemibold,
    fontSize: 19,
    lineHeight: 24,
  },
  dialogMessage: {
    color: BASKET_COLORS.deepTeal,
    fontFamily: BASKET_FONTS.body,
    fontSize: 14,
    lineHeight: 20,
    textAlign: 'center',
  },
  sheetScrim: {
    backgroundColor: 'rgba(11, 34, 31, 0.58)',
    bottom: 0,
    left: 0,
    position: 'absolute',
    right: 0,
    top: 0,
  },
  sheetScrollContent: {
    paddingBottom: 18,
    paddingTop: 12,
  },
  reviewFinalSummary: {
    marginTop: 20,
  },
  reviewFinalTitle: {
    color: BASKET_COLORS.deepTeal,
    fontFamily: BASKET_FONTS.bodySemibold,
    fontSize: 16,
    lineHeight: 21,
  },
  reviewFinalCopy: {
    color: BASKET_COLORS.muted,
    fontFamily: BASKET_FONTS.body,
    fontSize: 14,
    lineHeight: 19,
    marginTop: 5,
  },
  sheetTitle: {
    color: BASKET_COLORS.deepTeal,
    flex: 1,
    fontFamily: BASKET_FONTS.heading,
    fontSize: 28,
    lineHeight: 34,
  },
  screen: {
    backgroundColor: BASKET_COLORS.background,
    flex: 1,
  },
  smallIconButton: {
    alignItems: 'center',
    height: 48,
    justifyContent: 'center',
    width: 42,
  },
  stickyFooter: {
    alignItems: 'center',
    backgroundColor: BASKET_COLORS.white,
    borderTopColor: '#E6ECE8',
    borderTopWidth: 1,
    flexDirection: 'row',
    minHeight: 86,
    paddingHorizontal: 16,
    paddingVertical: 10,
  },
  thumbnailSummary: {
    alignItems: 'center',
    flexDirection: 'row',
  },
  trashButton: {
    alignItems: 'center',
    height: 48,
    justifyContent: 'center',
    width: 42,
  },
  usualsSection: {
    backgroundColor: '#FFFCF8',
    marginTop: 0,
  },
});
