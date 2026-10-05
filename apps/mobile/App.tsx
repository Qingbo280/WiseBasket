import * as Location from 'expo-location';
import * as ImagePicker from 'expo-image-picker';
import { StatusBar } from 'expo-status-bar';
import { useCallback, useEffect, useMemo, useRef, useState, type MutableRefObject } from 'react';
import { Alert, Platform, StyleSheet, useWindowDimensions } from 'react-native';
import { WebTestingShell } from './src/components/WebTestingShell';
import { SafeAreaProvider, SafeAreaView } from 'react-native-safe-area-context';
import { LocationGetLocationScreen } from './src/screens/LocationGetLocationScreen';
import {
  ManualLocationSearchScreen,
  type ManualLocationSearchSuggestion,
} from './src/screens/ManualLocationSearchScreen';
import { PriceCheckProductSearchScreen } from './src/screens/PriceCheckProductSearchScreen';
import { PriceCheckItemVariantConfirmationScreen } from './src/screens/PriceCheckItemVariantConfirmationScreen';
import { PriceCheckResultsScreen } from './src/screens/PriceCheckResultsScreen';
import { PriceCheckStoreDetailsScreen } from './src/screens/PriceCheckStoreDetailsScreen';
import { PriceCheckNextStepScreen } from './src/screens/PriceCheckNextStepScreen';
import { HomeDashboardScreen } from './src/screens/HomeDashboardScreen';
import { IntroScreen } from './src/screens/IntroScreen';
import { WelcomeScreen } from './src/screens/WelcomeScreen';
import { LoginEntryScreen } from './src/screens/LoginEntryScreen';
import { CreateAccountEntryScreen } from './src/screens/CreateAccountEntryScreen';
import { PlanQuestionOneScreen } from './src/screens/PlanQuestionOneScreen';
import { PlanQuestionTwoScreen } from './src/screens/PlanQuestionTwoScreen';
import { PlanQuestionThreeScreen } from './src/screens/PlanQuestionThreeScreen';
import { PlanConfirmationScreen, type PlanSection } from './src/screens/PlanConfirmationScreen';
import { PlanBuildingScreen } from './src/screens/PlanBuildingScreen';
import { PlanBasketScreen } from './src/screens/PlanBasketScreen';
import { CheckPricesScreen } from './src/screens/CheckPricesScreen';
import {
  MyBasketMainScreen,
  type ProductPreviewItem,
} from './src/screens/MyBasketMainScreen';
import { MealIdeasScreen, type MealIdea } from './src/screens/MealIdeasScreen';
import { recipeImageSourceForId } from './src/data/recipeAssetManifest';
import { saveRecipeHaveItems } from './src/services/recipePantry';
import { recipeIngredientBadge } from './src/services/recipeIngredientBadge';
import { recipePreviewFoods } from './src/services/recipePreview';
import { syncPurchasedPantry } from './src/services/shoppingPantry';
import { buildReceiptReviewRows } from './src/services/receiptReviewRows';
import { clearReceiptReviewDraft } from './src/services/receiptReviewDraft';
import {
  fetchRecipeDetail,
  fetchRecipeSuggestions,
  type RecipeRequestFilters,
  type RecipeDetail,
  type RecipeFood,
} from './src/services/recipeApi';
import {
  RecipeDetailScreen,
  type RecipeDetailIngredientState,
} from './src/screens/RecipeDetailScreen';
import { ReceiptCaptureScreen } from './src/screens/ReceiptCaptureScreen';
import { ReceiptProcessingScreen } from './src/screens/ReceiptProcessingScreen';
import {
  ReceiptReviewScreen,
  type ReceiptReviewItem,
  type ReceiptReviewLine,
} from './src/screens/ReceiptReviewScreen';
import { ProfileScreen, type ProfileDetails } from './src/screens/ProfileScreen';
import { AuthProvider, useAuth } from './src/auth/AuthProvider';
import {
  applyPlanPersonalization,
  PLAN_DRAFT_DEFAULTS,
  UNSET_PLAN_SUMMARY,
  planPersonalizationFromDraft,
  type PlanDraft,
} from './src/screens/planFlowContent';
import { PLAN_QUESTION_ONE_DEFAULTS } from './src/screens/planQuestionOneContent';
import {
  filterProductsByRestrictions,
  mapCatalogFoodToQuestionThreeProduct,
  setPlanQuestionThreeProducts,
} from './src/screens/planQuestionThreeContent';
import {
  applyOptimisticAddQuantity,
  createPlanBasketProposal,
  planRequestFromDraft,
} from './src/screens/planProposal';
import { createPlan, fetchFoodCatalog } from './src/services/plannerApi';
import {
  createPantryItem,
  cachePantryItems,
  fetchConfirmedPantryStock,
  getCachedPantryItems,
  listPantryItems,
  removePantryItem,
  updatePantryItem,
  replaceBasketHaveItems,
  type PantryItem,
  type PlannerPantryStockItem,
} from './src/services/pantryApi';
import type { PantryQuantityInput } from './src/services/pantryQuantity';
import { BasketHaveSyncQueue, reconcileFailedHaveChoices } from './src/services/basketHaveSync';
import { clearRemovedHaveChoice, removePantryFood } from './src/services/pantryRemoval';
import {
  confirmReceipt,
  uploadReceipt,
  waitForReceipt,
  type Receipt,
  type ReceiptConfirmation,
} from './src/services/receiptApi';
import type { FoodInfo, PlanResponse } from './src/api/plannerTypes';
import { cachedFoodImageSourceForBackendId, foodImageUriForBackendId } from './src/data/foodAssetManifest';
import { buildPriceGuideFromStoreComparison } from './src/screens/priceGuideFromPlan';
import { fetchBasketPrices, overBudgetStoreQuote } from './src/services/basketPriceApi';
import {
  createWeeklyPlanSnapshot,
  needsQuantityPolicyRefresh,
  weeklyPlanStorageOwner,
  type WeeklyPlanSnapshot,
} from './src/services/weeklyPlanSnapshot';
import {
  loadWeeklyPlanSnapshot,
  saveWeeklyPlanSnapshot,
  clearWeeklyPlanSnapshot,
} from './src/services/weeklyPlanStorage';
import { buildBasketDraft, getNeedItems, type BasketDraftItem, type BasketProposal } from './src/screens/basketContent';
import type {
  PriceCheckPriceResult,
  PriceCheckResultsData,
  PriceCheckSelectedLocation,
  PriceCheckSelectedVariant,
} from './src/screens/priceCheckResultsContent';
import type { PriceCheckStoreDetailsData } from './src/screens/priceCheckStoreDetailsContent';
import {
  buildPriceCheckVariantConfirmation,
  hasMultiplePriceCheckVariants,
  type PriceCheckSelectedItem,
  type PriceCheckVariantConfirmationConfig,
  type PriceCheckVariantOption,
} from './src/screens/priceCheckItemVariantConfirmationContent';
import { resetPriceCheckItemState } from './src/screens/priceCheckNextStepContent';
import { mapRecentPriceCheck, type DashboardRecentCheck } from './src/screens/homeDashboardContent';
import {
  PriceCheckFlowQaNextDestination,
} from './src/screens/fixtures/PriceCheckFlowQaNextDestination';
import { selectedItemForPopularItem } from './src/screens/fixtures/priceCheckProductSearchFlowFixtures';
import {
  createStoreDetailsFromPriceResult,
  fetchPriceCheckUnits,
  getNearbyFoodPrices,
} from './src/services/priceCheckApi';
import {
  fetchPriceCheckCatalog,
  mapFoodToPriceCheckCatalogEntry,
  selectedItemFromCatalogEntry,
  type PriceCheckCatalogEntry,
} from './src/services/priceCheckCatalogApi';
import { getSavedPlanPersonalization } from './src/services/appProfile';
import { buildRecipeExclusions, buildRecipeNameRestrictions } from './src/services/recipeExclusions';
import { prepareReceiptImage } from './src/services/receiptImagePreparation';
import {
  createConfirmedLocation,
  getLocationDisplayLabel,
  type ConfirmedLocation,
  type LocationCandidate,
} from './src/services/confirmedLocationContent';
import {
  clearRecentLocations,
  loadConfirmedLocation,
  loadRecentLocations,
  saveConfirmedLocation,
  saveRecentLocation,
} from './src/services/confirmedLocationStorage';

type TestScreen =
  | 'intro'
  | 'location-get-location'
  | 'location-typein'
  | 'location-price-check'
  | 'price-check-confirmation'
  | 'price-check-results'
  | 'price-check-store-details'
  | 'price-check-next-step'
  | 'home-dashboard'
  | 'auth-entry'
  | 'login-entry'
  | 'create-account'
  | 'plan-question-1'
  | 'plan-question-2'
  | 'plan-question-3'
  | 'plan-confirmation'
  | 'plan-building'
  | 'plan-basket'
  | 'check-prices'
  | 'my-basket-main'
  | 'receipt-capture'
  | 'receipt-processing'
  | 'receipt-review'
  | 'meal-ideas'
  | 'recipe-detail'
  | 'profile'
  | 'price-check-qa-next';

type QaNextDestinationStatus = 'confirmed-selection' | 'skipped-confirmation';
type LocationPurpose = 'price-check' | 'plan' | 'home';
type PriceCheckEntrySource = 'home-dashboard' | 'my-basket-main' | 'first-use';
type AuthCompletionIntent = 'home-dashboard' | 'plan-next-week';

type PlanQuestionOneEntrySource =
  | 'home-create-plan'
  | 'home-plan-next-week'
  | 'my-basket-plan-next-week'
  | 'price-check-next-step'
  | 'profile-personalization'
  | 'test-flow';
type ProfileReturnScreen = 'home-dashboard' | 'my-basket-main';

type LocationStatus = 'idle' | 'loading' | 'error';

const EMPTY_BASKET_PROPOSAL: BasketProposal = { usuals: [], recommendations: [] };

function readableLocationLabel(address: Location.LocationGeocodedAddress | undefined): string {
  if (!address) return 'Current location';
  const parts = [address.name, address.city ?? address.subregion, address.region]
    .filter((part): part is string => Boolean(part?.trim()))
    .filter((part, index, values) => values.indexOf(part) === index);
  return parts.join(', ') || 'Current location';
}

function priceCheckLocationFromConfirmed(location: ConfirmedLocation): PriceCheckSelectedLocation {
  return {
    label: getLocationDisplayLabel(location),
    latitude: location.latitude ?? null,
    longitude: location.longitude ?? null,
    state: location.state,
    district: location.district,
  };
}

function planningLocationFromConfirmed(location: ConfirmedLocation): PlanDraft['planningLocation'] {
  return {
    source: location.source,
    label: getLocationDisplayLabel(location),
    address: location.address,
    latitude: location.latitude,
    longitude: location.longitude,
    state: location.state,
    district: location.district,
  };
}

function receiptScanFailureMessage(error: unknown): string {
  // Receipt jobs may fail in an infrastructure dependency. Never show an
  // internal database or service error directly in the mobile UI.
  const message = error instanceof Error ? error.message : '';
  if (
    message === 'Please sign in before scanning a receipt.'
    || message === 'A household is required to scan a receipt.'
  ) {
    return message;
  }
  return 'We could not read this receipt. Please try a clearer photo or upload an image from your library.';
}

function TestFlow({ authHandoff }: {
  authHandoff: MutableRefObject<PriceCheckSelectedItem | null>;
}) {
  const {
    isAuthenticated,
    isLoading: authLoading,
    login,
    logout,
    profile,
    profileSaveError,
    register,
    updateProfile,
    ensureHousehold,
    activeHouseholdId,
    appProfileData,
    saveAppProfile,
    user,
    profileLoadError,
    retryProfile,
  } = useAuth();
  const [screen, setScreen] = useState<TestScreen>(isAuthenticated ? 'home-dashboard' : 'intro');
  const [planQuestionOneEntrySource, setPlanQuestionOneEntrySource] =
    useState<PlanQuestionOneEntrySource>('test-flow');
  const [locationPurpose, setLocationPurpose] = useState<LocationPurpose>('price-check');
  const [priceCheckEntrySource, setPriceCheckEntrySource] =
    useState<PriceCheckEntrySource>('first-use');
  const [authCompletionIntent, setAuthCompletionIntent] =
    useState<AuthCompletionIntent>('home-dashboard');
  const [selectedLocation, setSelectedLocation] = useState<PriceCheckSelectedLocation | null>(null);
  const [selectedProduct, setSelectedProduct] = useState<PriceCheckSelectedItem | null>(authHandoff.current);
  const [selectedPriceResult, setSelectedPriceResult] = useState<PriceCheckPriceResult | null>(null);
  const [variantConfirmation, setVariantConfirmation] = useState<PriceCheckVariantConfirmationConfig | null>(null);
  const [resultsData, setResultsData] = useState<PriceCheckResultsData | null>(null);
  const [storeDetailsData, setStoreDetailsData] = useState<PriceCheckStoreDetailsData | null>(null);
  const [locationStatus, setLocationStatus] = useState<LocationStatus>('idle');
  const [locationMessage, setLocationMessage] = useState<string>();
  const [confirmedLocation, setConfirmedLocation] = useState<ConfirmedLocation | null>(null);
  const [recentLocations, setRecentLocations] = useState<ConfirmedLocation[]>([]);
  const [pendingLocation, setPendingLocation] = useState<LocationCandidate | null>(null);
  const [catalogItems, setCatalogItems] = useState<PriceCheckCatalogEntry[]>([]);
  const [catalogStatus, setCatalogStatus] = useState<'loading' | 'ready' | 'error'>('loading');
  const [catalogMessage, setCatalogMessage] = useState<string>();
  const [recentChecks, setRecentChecks] = useState<readonly DashboardRecentCheck[]>([]);
  const [qaNextDestinationStatus, setQaNextDestinationStatus] =
    useState<QaNextDestinationStatus>('skipped-confirmation');
  const [planDraft, setPlanDraft] = useState<PlanDraft>(PLAN_DRAFT_DEFAULTS);
  const [basketDraft, setBasketDraft] = useState<readonly BasketDraftItem[]>([]);
  const [purchasedShoppingItems, setPurchasedShoppingItems] = useState<readonly ProductPreviewItem[]>([]);
  const purchasedSyncQueueRef = useRef<Promise<void>>(Promise.resolve());
  const purchasedPantryIdsRef = useRef(new Map<number, Map<string, number>>());
  const purchasedIntentRef = useRef<readonly ProductPreviewItem[]>([]);
  const savedPurchasedItemsRef = useRef<readonly ProductPreviewItem[]>([]);
  const pantryRemovalQueueRef = useRef<Promise<void>>(Promise.resolve());
  const pantryRemovalPendingRef = useRef(new Map<string, Promise<void>>());
  const removedPantryFoodIdsRef = useRef(new Map<number, Set<string>>());
  const [recipeHaveItems, setRecipeHaveItems] = useState<readonly Pick<RecipeFood, 'canonical_food_id' | 'name'>[]>([]);
  const [recipeShoppingListItems, setRecipeShoppingListItems] = useState<readonly Pick<RecipeFood, 'canonical_food_id' | 'name'>[]>([]);
  const [receiptHaveItems, setReceiptHaveItems] = useState<readonly ReceiptReviewItem[]>([]);
  const [receiptImageUri, setReceiptImageUri] = useState<string | null>(null);
  const [receipt, setReceipt] = useState<Receipt | null>(null);
  // The full receipt banner is useful before a first attempt, but redundant
  // when returning here to retry after a capture or OCR failure.
  const [receiptCaptureHideIntroBanner, setReceiptCaptureHideIntroBanner] = useState(false);
  const [pantryItems, setPantryItems] = useState<readonly PantryItem[]>([]);
  const [checkPriceItems, setCheckPriceItems] = useState<readonly BasketDraftItem[]>([]);
  const [basketStoreComparison, setBasketStoreComparison] = useState<PlanResponse['store_comparison']>([]);
  const [selectedStoreId, setSelectedStoreId] = useState<string | null>(null);
  const [profileReturnScreen, setProfileReturnScreen] = useState<ProfileReturnScreen>('home-dashboard');
  const [planCatalogStatus, setPlanCatalogStatus] = useState<'loading' | 'ready' | 'error'>('loading');
  const [planCatalogMessage, setPlanCatalogMessage] = useState<string | null>(null);
  const [planCatalogFoods, setPlanCatalogFoods] = useState<FoodInfo[] | null>(null);
  const [planResult, setPlanResult] = useState<PlanResponse | null>(null);
  const [planBuild, setPlanBuild] = useState<{ busy: boolean; error: string | null }>({
    busy: false,
    error: null,
  });
  const [planSectionEdit, setPlanSectionEdit] = useState<PlanSection | null>(null);
  // Confirm-time budget block ("minimum purchase over budget") - shown as a
  // centered dialog on the basket screen, never as the week-plan banner.
  const [budgetBlockMessage, setBudgetBlockMessage] = useState<string | null>(null);
  const [selectedMealIdea, setSelectedMealIdea] = useState<MealIdea | null>(null);
  const [selectedRecipeDetail, setSelectedRecipeDetail] = useState<RecipeDetail | null>(null);
  const [mealIdeas, setMealIdeas] = useState<readonly MealIdea[]>([]);
  const mealIdeasRequestRef = useRef(0);
  const mealIdeasSnapshotRef = useRef<{
    householdId: number;
    filters: RecipeRequestFilters;
    hardRestrictionKey: string;
  } | null>(null);
  const [recipeIngredientState, setRecipeIngredientState] =
    useState<RecipeDetailIngredientState | null>(null);
  const [introReturnPage, setIntroReturnPage] = useState(0);
  const [locationReturnToIntro, setLocationReturnToIntro] = useState(false);
  const [personalizationMode, setPersonalizationMode] = useState<'build' | 'edit'>('build');
  const setupProfileDataRef = useRef(appProfileData);
  const activePlanDraft = basketDraft.length > 0 ? planDraft : null;
  const savedPersonalization = getSavedPlanPersonalization(appProfileData);
  const basketSummaryDraft = savedPersonalization
    ? applyPlanPersonalization(UNSET_PLAN_SUMMARY, savedPersonalization)
    : UNSET_PLAN_SUMMARY;
  const plannedRecipeFoodKey = getNeedItems(basketDraft).map((item) => item.productId).sort().join('|');
  const recipeHardRestrictionKey = JSON.stringify([
    buildRecipeExclusions(planDraft), buildRecipeNameRestrictions(planDraft),
  ]);
  // Async recipe requests must compare against the latest render, not the
  // planDraft captured when the request started.
  const recipeHardRestrictionKeyRef = useRef(recipeHardRestrictionKey);
  recipeHardRestrictionKeyRef.current = recipeHardRestrictionKey;
  const recipeHouseholdIdRef = useRef(activeHouseholdId);
  recipeHouseholdIdRef.current = activeHouseholdId;
  const weeklyPlanOwner = weeklyPlanStorageOwner(user?.user_id);
  const confirmedLocationHydrationRef = useRef<Promise<ConfirmedLocation | null> | null>(null);

  useEffect(() => {
    let active = true;
    const hydration = loadConfirmedLocation();
    confirmedLocationHydrationRef.current = hydration;
    void Promise.all([hydration, loadRecentLocations()]).then(([location, recent]) => {
      if (!active) return;
      setConfirmedLocation(location);
      setRecentLocations(recent ?? (location ? [location] : []));
      if (recent === null && location) {
        void saveRecentLocation(location).catch(() => undefined);
      }
    });

    return () => {
      active = false;
    };
  }, []);

  const resolveConfirmedLocation = async (): Promise<ConfirmedLocation | null> => {
    if (confirmedLocation) return confirmedLocation;

    const hydration = confirmedLocationHydrationRef.current ?? loadConfirmedLocation();
    confirmedLocationHydrationRef.current = hydration;
    const location = await hydration;
    if (location) setConfirmedLocation(location);
    return location;
  };
  // 2026-09-14 opt-in journey: reactive mirror of the selected_food_ids set
  // the current planResult was posted with (need items incl. accepted
  // recommendations / manual adds). The basket proposal must be built from
  // THIS set - not the stale Q3 tick list - or accepted items would silently
  // vanish from the rebuilt basket.
  const [postedSelectionIds, setPostedSelectionIds] = useState<readonly string[]>([]);
  const basketProposal = useMemo(
    () => (
      planResult
        ? createPlanBasketProposal(
          planResult,
          planCatalogFoods ?? [],
          postedSelectionIds,
          basketDraft.filter((item) => item.choice === 'need' && item.source !== 'usual')
            .map((item) => item.productId),
        )
        : EMPTY_BASKET_PROPOSAL
    ),
    [basketDraft, planCatalogFoods, postedSelectionIds, planResult],
  );
  const catalogRequestIdRef = useRef(0);
  const planCatalogRequestIdRef = useRef(0);
  // 2026-09-14 opt-in journey: track the selected_food_ids set the current
  // planResult was posted with, plus a draft mirror for the quantity re-solve.
  const selectedFoodIdsRef = useRef<readonly string[]>([]);
  const basketDraftRef = useRef<readonly BasketDraftItem[]>([]);
  const replanTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const planResultRef = useRef<PlanResponse | null>(null);
  const haveSyncQueueRef = useRef(new BasketHaveSyncQueue(replaceBasketHaveItems, listPantryItems));
  const haveIntentIdRef = useRef(0);
  const activeHouseholdIdRef = useRef(activeHouseholdId);
  activeHouseholdIdRef.current = activeHouseholdId;
  useEffect(() => {
    if (!isAuthenticated) haveSyncQueueRef.current.cancelExcept(null);
    else haveSyncQueueRef.current.cancelExcept(activeHouseholdId);
  }, [activeHouseholdId, isAuthenticated]);
  const receiptRequestIdRef = useRef(0);
  const receiptConfirmingRef = useRef(false);
  useEffect(() => () => {
    // Account changes unmount this flow; pending results must not restore it.
    receiptRequestIdRef.current += 1;
    mealIdeasRequestRef.current += 1;
    if (replanTimerRef.current) clearTimeout(replanTimerRef.current);
  }, []);
  useEffect(() => {
    basketDraftRef.current = basketDraft;
  }, [basketDraft]);

  const loadPantry = useCallback(async () => {
    if (!isAuthenticated || activeHouseholdId === null) {
      setPantryItems([]);
      return;
    }

    const cachedItems = await getCachedPantryItems(activeHouseholdId);
    if (cachedItems) {
      setPantryItems(cachedItems);
    }

    try {
      setPantryItems(await listPantryItems(activeHouseholdId));
    } catch {
      // A temporary Pantry read failure must not hide the rest of My Basket.
      // The next basket action or screen entry will retry the fetch.
    }
  }, [activeHouseholdId, isAuthenticated]);

  useEffect(() => {
    void loadPantry();
  }, [loadPantry]);

  const syncHaveChoicesToPantry = async (nextDraft: readonly BasketDraftItem[]) => {
    // Guest planning stays available, but Pantry is account-owned data. Once
    // signed in, the user's "Have at home" choices are persisted immediately.
    if (!isAuthenticated) return;
    const intentId = ++haveIntentIdRef.current;
    const previousDraft = basketDraftRef.current;
    await pantryRemovalQueueRef.current;

    const showFailure = (error: unknown, persistedItems?: PantryItem[]) => {
      if (haveIntentIdRef.current !== intentId || activeHouseholdIdRef.current !== householdId) return;
      if (persistedItems) {
        setPantryItems(persistedItems);
        invalidatePantryStockSnapshot();
        const available = persistedItems.filter((item) => item.status === 'AVAILABLE');
        const reconciled = reconcileFailedHaveChoices(basketDraftRef.current, nextDraft, previousDraft,
          new Set(available.map((item) => item.food.canonical_food_id)),
          new Set(available.filter((item) => item.basket_have_managed).map((item) => item.food.canonical_food_id)));
        basketDraftRef.current = reconciled;
        setBasketDraft(reconciled);
        persistWeeklyPlan(planDraft, reconciled, planResultRef.current, selectedFoodIdsRef.current);
        if (replanTimerRef.current) clearTimeout(replanTimerRef.current);
        if (planResultRef.current) {
          replanTimerRef.current = setTimeout(() => {
            if (haveIntentIdRef.current === intentId) void postPlanForSelection(getNeedItems(reconciled).map((item) => item.productId));
          }, 500);
        }
      }
      const message = `Your Have choices could not be saved. ${persistedItems ? 'The basket now reflects your saved pantry.' : 'The saved pantry could not be checked.'} ${error instanceof Error ? error.message : 'Please try again.'}`;
      const retry = () => {
        // A dismissed old prompt must never overwrite a subsequent intent.
        if (haveIntentIdRef.current !== intentId || activeHouseholdIdRef.current !== householdId) return;
        const choices = new Map(nextDraft.map((item) => [item.productId, item.choice]));
        handleBasketDraftChange(basketDraftRef.current.map((item) => ({ ...item, choice: choices.get(item.productId) ?? item.choice })));
      };
      if (Platform.OS === 'web') {
        if (window.confirm(`${message}\n\nRetry saving these choices?`)) retry();
      } else {
        Alert.alert('Have choices not saved', message, [{ text: 'Not now', style: 'cancel' }, { text: 'Retry', onPress: retry }]);
      }
    };

    let householdId = activeHouseholdId;
    try {
      const household = householdId === null ? await ensureHousehold(planDraft.adults, planDraft.children) : null;
      householdId = household?.id ?? householdId;
      if (householdId === null) throw new Error('A household is required to save ingredients.');
    } catch (error) { showFailure(error); return; }
    if (haveIntentIdRef.current !== intentId) return;

    // An older Have intent may have been waiting while stock was removed.
    await pantryRemovalQueueRef.current;
    if (haveIntentIdRef.current !== intentId || activeHouseholdIdRef.current !== householdId) return;
    const removedIds = removedPantryFoodIdsRef.current.get(householdId);

    const nextHaveIds = [...new Set(
      nextDraft.filter((item) => item.choice === 'have' && !removedIds?.has(item.productId)).map((item) => item.productId),
    )].sort();
    haveSyncQueueRef.current.enqueue({
      householdId,
      foodIds: nextHaveIds,
      onApplied: (items) => {
        if (activeHouseholdIdRef.current !== householdId || haveIntentIdRef.current !== intentId) return;
        setPantryItems(items);
        // A2: the have-sync just mutated pantry; only a completed write
        // invalidates the plan snapshot.
        invalidatePantryStockSnapshot();
      },
      onFailed: showFailure,
    });
  };

  const pantryDisplayItems = useMemo<readonly BasketDraftItem[]>(
    () => pantryItems.filter((item) => item.status === 'AVAILABLE').map((item) => {
      const imageUri = foodImageUriForBackendId(item.food.canonical_food_id);
      // 2026-09-16 user rule: gram-denominated quantities display as kg.
      // Editing uses this displayed quantity/unit pair, so a gram quantity
      // is converted to kg exactly once before a user explicitly saves it.
      const rawUnit = item.unit ?? 'amount unknown';
      const isGrams = ['g', 'gram', 'grams'].includes(rawUnit.trim().toLowerCase());
      return {
        productId: item.food.canonical_food_id,
        name: item.food.name,
        imageSource: imageUri ? { uri: imageUri } : null,
        suggestedQuantity: isGrams && item.quantity != null
          ? item.quantity / 1000
          : item.quantity ?? 0,
        unit: isGrams ? 'kg' : rawUnit,
        source: 'manual',
        choice: 'have',
      };
    }),
    [pantryItems],
  );

  const [pantryCatalogItems, setPantryCatalogItems] = useState<PriceCheckCatalogEntry[]>([]);
  const loadPriceCheckCatalog = useCallback(async () => {
    const requestId = catalogRequestIdRef.current + 1;
    catalogRequestIdRef.current = requestId;
    setCatalogStatus('loading');
    setCatalogMessage(undefined);

    try {
      const items = await fetchPriceCheckCatalog();
      if (catalogRequestIdRef.current !== requestId) return;
      setCatalogItems(items);
      setCatalogStatus('ready');
    } catch (error: unknown) {
      if (catalogRequestIdRef.current !== requestId) return;
      setCatalogStatus('error');
      setCatalogMessage(error instanceof Error ? error.message : 'Food catalogue is unavailable.');
    }
  }, []);

  useEffect(() => {
    void loadPriceCheckCatalog();
    return () => {
      catalogRequestIdRef.current += 1;
    };
  }, [loadPriceCheckCatalog]);

  // What-you-have layer (receipt review / pantry adds): the user can buy
  // catalog_eligible=false foods in a real shop even though we have no
  // trustworthy price, so the pantry catalogue is fetched with
  // include_hidden=true. The planning catalogue (Q3, PlanBasket add-item,
  // worth pool, price check) stays on the default catalogue-eligible set.
  const loadPantryCatalog = useCallback(async () => {
    try {
      const foods = await fetchFoodCatalog({ includeHidden: true, includeMinPurchasePrice: true });
      setPantryCatalogItems(foods.map(mapFoodToPriceCheckCatalogEntry));
    } catch {
      // Receipt review falls back to the default catalogue via its own props.
    }
  }, []);

  useEffect(() => {
    void loadPantryCatalog();
  }, [loadPantryCatalog]);

  const loadPlanCatalog = useCallback(async () => {
    const requestId = planCatalogRequestIdRef.current + 1;
    planCatalogRequestIdRef.current = requestId;
    setPlanCatalogStatus('loading');
    setPlanCatalogMessage(null);

    try {
      const foods = await fetchFoodCatalog();
      if (planCatalogRequestIdRef.current !== requestId) return;
      setPlanCatalogFoods(foods);
      setPlanCatalogStatus('ready');
    } catch (error: unknown) {
      if (planCatalogRequestIdRef.current !== requestId) return;
      setPlanCatalogStatus('error');
      setPlanCatalogMessage(
        error instanceof Error ? error.message : 'Food catalogue is unavailable.',
      );
    }
  }, []);

  useEffect(() => {
    void loadPlanCatalog();
    return () => {
      planCatalogRequestIdRef.current += 1;
    };
  }, [loadPlanCatalog]);

  useEffect(() => {
    const savedPersonalization = getSavedPlanPersonalization(appProfileData);
    setPlanDraft((currentDraft) => savedPersonalization
      ? applyPlanPersonalization(currentDraft, savedPersonalization)
      : { ...PLAN_DRAFT_DEFAULTS });
  }, [appProfileData, user?.user_id]);

  useEffect(() => {
    if (
      !authLoading
      && isAuthenticated
      && (screen === 'auth-entry' || screen === 'login-entry' || screen === 'create-account')
    ) {
      setScreen('home-dashboard');
    }
  }, [authLoading, isAuthenticated, screen]);

  // Keep the Q3 questionnaire (and the PlanBasket add-item sheet, which reads
  // the same module-level catalogue) free of foods the user hard-excluded in
  // Q2. Re-filters when the catalogue loads or the restriction pick changes,
  // and drops any already-selected ids that became restricted.
  useEffect(() => {
    if (!planCatalogFoods) return;
    const mapped = planCatalogFoods.map((food) =>
      mapCatalogFoodToQuestionThreeProduct(food, foodImageUriForBackendId),
    );
    const visible = filterProductsByRestrictions(
      mapped,
      planDraft.selectedRestrictions,
      planDraft.customRestriction,
    );
    setPlanQuestionThreeProducts(visible);

    const visibleIds = new Set(visible.map((product) => product.id));
    setPlanDraft((currentDraft) =>
      currentDraft.usualProductIds.some((id) => !visibleIds.has(id))
        ? { ...currentDraft, usualProductIds: currentDraft.usualProductIds.filter((id) => visibleIds.has(id)) }
        : currentDraft,
    );
  }, [planCatalogFoods, planDraft.selectedRestrictions, planDraft.customRestriction]);

  const handlePlanQuestionOneStateChange = useCallback((state: {
    adults: number;
    children: number;
    customMealCount: number | null;
    selectedMealId: PlanDraft['selectedMealId'];
  }) => {
    setPlanDraft((currentDraft) => ({ ...currentDraft, ...state }));
  }, []);

  const handlePlanQuestionTwoStateChange = useCallback((state: {
    customRestriction: string;
    selectedRestrictions: PlanDraft['selectedRestrictions'];
    weeklyBudget: number | null;
  }) => {
    setPlanDraft((currentDraft) => ({ ...currentDraft, ...state }));
  }, []);

  const handlePlanQuestionThreeSelectionChange = useCallback((selectedProductIds: string[]) => {
    setPlanDraft((currentDraft) => ({ ...currentDraft, usualProductIds: selectedProductIds }));
  }, []);

  const loadPreferencesForSetup = async () => {
    if (!profileLoadError) return appProfileData;
    try {
      return await retryProfile();
    } catch {
      return null;
    }
  };

  const openPlanQuestionOne = async (source: PlanQuestionOneEntrySource) => {
    const loadedProfile = await loadPreferencesForSetup();
    if (!loadedProfile) return;
    setupProfileDataRef.current = loadedProfile;
    setPersonalizationMode('build');
    setPlanSectionEdit(null);
    setPlanQuestionOneEntrySource(source);
    setLocationReturnToIntro(false);
    setLocationPurpose('plan');
    setPendingLocation(null);
    setLocationStatus('idle');
    setLocationMessage(undefined);
    setPlanBuild({ busy: false, error: null });
    const location = await resolveConfirmedLocation();
    const startsFromHome = source === 'home-create-plan' || source === 'home-plan-next-week';
    const savedPersonalization = getSavedPlanPersonalization(loadedProfile);

    // A returning user reuses the saved setup; only clear the previous result
    // before creating the next plan. First-time users continue into setup.
    if (startsFromHome) {
      setPlanDraft({ ...PLAN_DRAFT_DEFAULTS });
      setBasketDraft([]);
      basketDraftRef.current = [];
      setPlanResult(null);
      planResultRef.current = null;
      setPostedSelectionIds([]);
      selectedFoodIdsRef.current = [];
      committedNeedIdsRef.current = [];
      await resetWeeklyPlanForOwner().catch(() => undefined);
    }
    if (location) {
      if (savedPersonalization) {
        const nextDraft: PlanDraft = {
          ...applyPlanPersonalization({
            ...PLAN_DRAFT_DEFAULTS,
            planningLocation: planningLocationFromConfirmed(location),
          }, savedPersonalization),
          planningLocation: planningLocationFromConfirmed(location),
        };
        setPlanDraft(nextDraft);
        setScreen('plan-confirmation');
        return;
      }
      const locationDraft: PlanDraft = {
        ...PLAN_DRAFT_DEFAULTS,
        adults: PLAN_QUESTION_ONE_DEFAULTS.adults,
        children: PLAN_QUESTION_ONE_DEFAULTS.children,
        selectedMealId: PLAN_QUESTION_ONE_DEFAULTS.selectedMealId,
        customMealCount: null,
        weeklyBudget: null,
        selectedRestrictions: [],
        customRestriction: '',
        planningLocation: planningLocationFromConfirmed(location),
      };
      setPlanDraft(locationDraft);
      setScreen('plan-question-1');
      return;
    }
    setScreen('location-typein');
  };

  const openMyBasket = async () => {
    const loadedProfile = await loadPreferencesForSetup();
    if (loadedProfile) setScreen('my-basket-main');
  };

  useEffect(() => {
    if (isAuthenticated && authHandoff.current) {
      authHandoff.current = null;
      void openPlanQuestionOne('price-check-next-step');
    }
  }, [isAuthenticated]);

  const openProfile = (returnScreen: ProfileReturnScreen) => {
    setProfileReturnScreen(returnScreen);
    setScreen('profile');
  };

  const openPersonalizationEditor = async () => {
    const loadedProfile = await loadPreferencesForSetup();
    if (!loadedProfile) return;
    const savedPersonalization = getSavedPlanPersonalization(loadedProfile);
    setPersonalizationMode('edit');
    setPlanSectionEdit(null);
    setPlanQuestionOneEntrySource('profile-personalization');
    setPlanBuild({ busy: false, error: null });
    if (savedPersonalization) {
      setPlanDraft((currentDraft) => applyPlanPersonalization(currentDraft, savedPersonalization));
    }
    setScreen('plan-question-1');
  };

  const handlePlanSectionEdit = (section: PlanSection) => {
    setPlanSectionEdit(section);
    setPlanBuild({ busy: false, error: null });
    setScreen(section === 'household' ? 'plan-question-1' : section === 'budget' ? 'plan-question-2' : 'plan-question-3');
  };

  const handlePlanSectionEditSave = async () => {
    const personalization = planPersonalizationFromDraft(planDraft);
    setPlanBuild({ busy: true, error: null });
    try {
      await saveAppProfile({ personalization });
      setPlanBuild({ busy: false, error: null });
      setPlanSectionEdit(null);
      setScreen('plan-confirmation');
    } catch (error) {
      const message = error instanceof Error
        ? error.message
        : 'Your plan settings could not be saved. Please try again.';
      setPlanBuild({ busy: false, error: message });
      Alert.alert('Could not save changes', message);
    }
  };

  const handlePlanConfirmationBack = () => {
    setPlanSectionEdit(null);

    if (
      planQuestionOneEntrySource === 'home-create-plan'
      || planQuestionOneEntrySource === 'home-plan-next-week'
    ) {
      setScreen('home-dashboard');
      return;
    }

    if (planQuestionOneEntrySource === 'my-basket-plan-next-week') {
      setScreen('my-basket-main');
      return;
    }

    if (planQuestionOneEntrySource === 'price-check-next-step') {
      setScreen('price-check-next-step');
      return;
    }

    setScreen('home-dashboard');
  };

  const handlePlanBasketBack = () => {
    if (
      planQuestionOneEntrySource === 'home-create-plan'
      || planQuestionOneEntrySource === 'home-plan-next-week'
    ) {
      setScreen('home-dashboard');
      return;
    }

    if (planQuestionOneEntrySource === 'my-basket-plan-next-week') {
      setScreen('my-basket-main');
      return;
    }

    if (planQuestionOneEntrySource === 'price-check-next-step') {
      setScreen('price-check-next-step');
      return;
    }

    // Keep the standalone TestFlow entry usable for QA of the previous step.
    if (planQuestionOneEntrySource === 'test-flow') {
      setScreen('plan-question-3');
      return;
    }

    setScreen('home-dashboard');
  };

  const handleProfileLogout = () => {
    void logout().finally(() => setScreen('auth-entry'));
  };

  const handlePlanQuestionOneBack = () => {
    setPendingLocation(null);

    if (planSectionEdit !== null) {
      setPlanSectionEdit(null);
      setScreen('plan-confirmation');
      return;
    }

    if (
      planQuestionOneEntrySource === 'home-create-plan'
      || planQuestionOneEntrySource === 'home-plan-next-week'
    ) {
      setScreen('home-dashboard');
      return;
    }

    if (planQuestionOneEntrySource === 'my-basket-plan-next-week') {
      setScreen('my-basket-main');
      return;
    }

    if (planQuestionOneEntrySource === 'price-check-next-step') {
      setScreen('price-check-next-step');
      return;
    }

    if (planQuestionOneEntrySource === 'profile-personalization') {
      setScreen('profile');
      return;
    }

    setLocationPurpose('plan');
    setScreen('location-typein');
  };

  const handleIntroComplete = (pageIndex: number) => {
    setIntroReturnPage(pageIndex);
    setAuthCompletionIntent('home-dashboard');
    setScreen('auth-entry');
  };

  const handlePlanLocationBack = () => {
    if (
      planQuestionOneEntrySource === 'home-create-plan'
      || planQuestionOneEntrySource === 'home-plan-next-week'
    ) {
      setScreen('home-dashboard');
      return;
    }

    if (planQuestionOneEntrySource === 'my-basket-plan-next-week') {
      setScreen('my-basket-main');
      return;
    }

    if (planQuestionOneEntrySource === 'price-check-next-step') {
      setScreen('price-check-next-step');
    }
  };

  const handlePriceCheckLocationBack = () => {
    if (locationReturnToIntro) {
      setLocationReturnToIntro(false);
      setScreen('intro');
      return;
    }

    setScreen('home-dashboard');
  };

  const handleHomeLocationBack = () => {
    setPendingLocation(null);
    setScreen('home-dashboard');
  };

  const openPriceCheckFromMainArea = async (source: Exclude<PriceCheckEntrySource, 'first-use'>) => {
    setPriceCheckEntrySource(source);
    setLocationReturnToIntro(false);
    setLocationPurpose('price-check');
    setPendingLocation(null);
    setLocationStatus('idle');
    setLocationMessage(undefined);
    const location = await resolveConfirmedLocation();
    if (location) {
      setSelectedLocation(priceCheckLocationFromConfirmed(location));
      setScreen('location-price-check');
      return;
    }
    setScreen('location-typein');
  };

  const openHomeLocationEditor = () => {
    setLocationPurpose('home');
    setPendingLocation(null);
    setLocationStatus('idle');
    setLocationMessage(undefined);
    setScreen('location-typein');
  };

  const handlePriceCheckFinish = () => {
    if (selectedProduct) {
      const completedCheck = mapRecentPriceCheck({ selectedItem: selectedProduct, selectedPriceResult });

      setRecentChecks((currentChecks) => [
        completedCheck,
        ...currentChecks.filter((check) => check.id !== completedCheck.id),
      ]);
    }

    if (priceCheckEntrySource === 'home-dashboard') {
      setScreen('home-dashboard');
      return;
    }

    if (priceCheckEntrySource === 'my-basket-main') {
      setScreen('home-dashboard');
      return;
    }

    setScreen('auth-entry');
  };

  const handlePriceCheckPlanNextWeek = () => {
    if (priceCheckEntrySource === 'first-use') {
      setAuthCompletionIntent('plan-next-week');
      setScreen('auth-entry');
      return;
    }

    void openPlanQuestionOne('price-check-next-step');
  };

  const handleLocationUseForPurpose = async () => {
    setLocationStatus('loading');
    setLocationMessage('Getting your location…');
    try {
      const permission = await Location.requestForegroundPermissionsAsync();
      if (permission.status !== Location.PermissionStatus.GRANTED) {
        setLocationStatus('error');
        setLocationMessage('Location permission was not granted. Enter an address instead.');
        return;
      }

      const position = await Location.getCurrentPositionAsync({
        accuracy: Location.Accuracy.Balanced,
      });
      let address: Location.LocationGeocodedAddress | undefined;
      try {
        [address] = await Location.reverseGeocodeAsync(position.coords);
      } catch {
        // Coordinates remain sufficient for the nearby-price endpoint.
      }
      const label = readableLocationLabel(address);
      setPendingLocation({
        address: label,
        shortLabel: label,
        latitude: position.coords.latitude,
        longitude: position.coords.longitude,
        source: 'gps',
        state: address?.region ?? undefined,
        district: address?.subregion ?? address?.city ?? undefined,
      });
      setLocationStatus('idle');
      setLocationMessage(undefined);
      setScreen('location-get-location');
    } catch (error) {
      setLocationStatus('error');
      setLocationMessage(error instanceof Error ? error.message : 'Unable to get your location.');
    }
  };

  const handleLocationAddressSelection = (suggestion: ManualLocationSearchSuggestion) => {
    setPendingLocation({
      address: suggestion.address,
      shortLabel: suggestion.label,
      latitude: suggestion.latitude ?? undefined,
      longitude: suggestion.longitude ?? undefined,
      source: 'manual',
      state: suggestion.state,
      district: suggestion.district,
    });
    setLocationStatus('idle');
    setLocationMessage(undefined);
    setScreen('location-get-location');
  };

  const handleChangePendingLocation = () => {
    setPendingLocation(null);
    setLocationStatus('idle');
    setLocationMessage(undefined);
    setScreen('location-typein');
  };

  const handleConfirmLocation = async () => {
    if (!pendingLocation) return;

    setLocationStatus('loading');
    setLocationMessage('Saving your shopping location…');
    try {
      const savedLocation = createConfirmedLocation(pendingLocation);
      await saveConfirmedLocation(savedLocation);
      setConfirmedLocation(savedLocation);
      try {
        setRecentLocations(await saveRecentLocation(savedLocation));
      } catch {
        // A recent-history write failure must not block confirming the location.
      }
      setSelectedLocation(priceCheckLocationFromConfirmed(savedLocation));
      setPendingLocation(null);
      setLocationStatus('idle');
      setLocationMessage(undefined);

      if (locationPurpose === 'plan') {
        const savedPersonalization = getSavedPlanPersonalization(setupProfileDataRef.current);
        const locationDraft: PlanDraft = {
          ...PLAN_DRAFT_DEFAULTS,
          adults: PLAN_QUESTION_ONE_DEFAULTS.adults,
          children: PLAN_QUESTION_ONE_DEFAULTS.children,
          selectedMealId: PLAN_QUESTION_ONE_DEFAULTS.selectedMealId,
          planningLocation: planningLocationFromConfirmed(savedLocation),
        };
        const nextDraft = savedPersonalization
          ? {
              ...applyPlanPersonalization(locationDraft, savedPersonalization),
              planningLocation: planningLocationFromConfirmed(savedLocation),
            }
          : locationDraft;
        setPlanDraft(nextDraft);
        if (savedPersonalization) {
          setScreen('plan-confirmation');
          return;
        }
        setScreen('plan-question-1');
        return;
      }

      if (locationPurpose === 'price-check') {
        setScreen('location-price-check');
        return;
      }

      setScreen('home-dashboard');
    } catch (error) {
      setLocationStatus('error');
      setLocationMessage(
        error instanceof Error
          ? error.message
          : 'Your shopping location could not be saved. Please try again.',
      );
    }
  };

  const runPriceCheck = async (
    item: PriceCheckSelectedItem,
    selectedVariant?: PriceCheckSelectedVariant,
  ) => {
    if (!selectedLocation) {
      setScreen('location-typein');
      return;
    }
    setSelectedProduct(item);
    setStoreDetailsData(null);
    setResultsData({ status: 'loading', selectedItem: item, selectedLocation, selectedVariant });
    setScreen('price-check-results');
    try {
      setResultsData(await getNearbyFoodPrices(item, selectedLocation, selectedVariant));
    } catch (error) {
      setResultsData({
        status: 'error',
        selectedItem: item,
        selectedLocation,
        selectedVariant,
        message: error instanceof Error ? error.message : 'Nearby prices are unavailable right now.',
      });
    }
  };

  const handleSelectProduct = async (selectedItem: PriceCheckSelectedItem) => {
    if (!selectedLocation) {
      setScreen('location-typein');
      return;
    }

    try {
      const units = await fetchPriceCheckUnits(selectedItem.foodId);
      const confirmation = buildPriceCheckVariantConfirmation(selectedItem, units);
      if (confirmation && hasMultiplePriceCheckVariants(confirmation)) {
        setSelectedProduct({ ...selectedItem, requiresVariantConfirmation: true });
        setVariantConfirmation(confirmation);
        setStoreDetailsData(null);
        setResultsData(null);
        setScreen('price-check-confirmation');
        return;
      }
      if (confirmation) {
        const onlyOption = confirmation.options[0];
        setVariantConfirmation(null);
        await runPriceCheck(
          { ...selectedItem, requiresVariantConfirmation: false },
          {
            variantId: onlyOption.variantId,
            label: onlyOption.primaryLabel,
            quantityG: onlyOption.quantityG,
            retailQuantity: onlyOption.retailQuantity,
            retailUnit: onlyOption.retailUnit,
          },
        );
        return;
      }
    } catch {
      // A unit lookup should not block the default catalogue-pack price check.
    }

    setVariantConfirmation(null);
    await runPriceCheck({ ...selectedItem, requiresVariantConfirmation: false });
  };

  const handleCheckVariantPrices = async (option: PriceCheckVariantOption) => {
    if (!selectedProduct) return;
    const selectedVariant: PriceCheckSelectedVariant = {
      variantId: option.variantId,
      label: option.primaryLabel,
      quantityG: option.quantityG,
      retailQuantity: option.retailQuantity,
      retailUnit: option.retailUnit,
    };
    await runPriceCheck(selectedProduct, selectedVariant);
  };

  const handleSelectPremise = (result: PriceCheckPriceResult) => {
    if (!resultsData || resultsData.status !== 'success') return;
    const details = createStoreDetailsFromPriceResult(resultsData, result.premiseId);
    if (!details) return;
    setSelectedPriceResult(result);
    setStoreDetailsData(details);
    setScreen('price-check-store-details');
  };

  const handleCheckAnotherItem = () => {
    const nextState = resetPriceCheckItemState({
      qaNextDestinationStatus,
      selectedLocation,
      selectedPriceResult,
      selectedProduct,
    });

    setSelectedProduct(nextState.selectedProduct);
    setSelectedPriceResult(nextState.selectedPriceResult);
    setQaNextDestinationStatus(nextState.qaNextDestinationStatus);
    setVariantConfirmation(null);
    setResultsData(null);
    setStoreDetailsData(null);
    setScreen('location-price-check');
  };

  // Auth screens hand their validated credentials to the real backend; the
  // profile state below is hydrated from the account (auth user + profile
  // blob), never from demo data.
  const handleLogin = async (credentials: { email: string; password: string }) => {
    authHandoff.current = authCompletionIntent === 'plan-next-week' ? selectedProduct : null;
    try {
      await login(credentials.email, credentials.password);
    } catch (error) {
      authHandoff.current = null;
      throw error;
    }
  };

  const handleCreateAccount = async (details: { email: string; name: string; password: string }) => {
    authHandoff.current = authCompletionIntent === 'plan-next-week' ? selectedProduct : null;
    try {
      await register(details.name, details.email, details.password);
    } catch (error) {
      authHandoff.current = null;
      throw error;
    }
  };

  const handleProfileChange = (profile: ProfileDetails) => {
    updateProfile(profile);
  };

  const handleMealIdeaPress = async (recipe: MealIdea) => {
    try {
      if (activeHouseholdId === null) throw new Error('A household is required to view a recipe.');
      const snapshot = mealIdeasSnapshotRef.current;
      if (!snapshot || snapshot.householdId !== recipeHouseholdIdRef.current ||
          snapshot.hardRestrictionKey !== recipeHardRestrictionKeyRef.current) {
        throw new Error('Meal ideas have changed. Please reopen the list.');
      }
      const detail = await fetchRecipeDetail(snapshot.householdId, recipe.recipeId, snapshot.filters);
      if (mealIdeasSnapshotRef.current !== snapshot ||
          snapshot.householdId !== recipeHouseholdIdRef.current ||
          snapshot.hardRestrictionKey !== recipeHardRestrictionKeyRef.current) {
        throw new Error('Meal ideas have changed. Please reopen the list.');
      }
      setSelectedMealIdea(recipe);
      setRecipeIngredientState(null);
      setSelectedRecipeDetail(detail);
      setScreen('recipe-detail');
    } catch (error) {
      Alert.alert('Recipe unavailable', error instanceof Error ? error.message : 'Please try again.');
    }
  };

  const recipeIconForFood = (food: RecipeFood): MealIdea['ingredients'][number]['icon'] => {
    const category = food.category.toLowerCase();
    if (category.includes('protein')) return 'food-drumstick';
    if (category.includes('fruit')) return 'fruit-cherries';
    if (category.includes('carb') || category.includes('staple')) return 'rice';
    return 'leaf';
  };

  const openMealIdeas = async (navigate = true) => {
    const requestId = ++mealIdeasRequestRef.current;
    try {
      const household = activeHouseholdId === null
        ? await ensureHousehold(planDraft.adults, planDraft.children)
        : null;
      const householdId = household?.id ?? activeHouseholdId;
      if (householdId === null) throw new Error('A household is required to view meal ideas.');
      const exclusions = buildRecipeExclusions(planDraft);
      const nameRestrictions = buildRecipeNameRestrictions(planDraft);
      const hardRestrictionKey = JSON.stringify([exclusions, nameRestrictions]);
      const filters: RecipeRequestFilters = {
        exclusions,
        ...nameRestrictions,
        plannedFoodIds: getNeedItems(basketDraft).map((item) => item.productId),
      };
      if (mealIdeasSnapshotRef.current?.hardRestrictionKey !== hardRestrictionKey) {
        // Never leave old potentially forbidden recipes tappable while a new
        // restriction-aware request is in flight or if it fails.
        mealIdeasSnapshotRef.current = null;
        setMealIdeas([]);
      }
      const suggestions = await fetchRecipeSuggestions(householdId, filters);
      if (requestId !== mealIdeasRequestRef.current ||
          hardRestrictionKey !== recipeHardRestrictionKeyRef.current) return;
      mealIdeasSnapshotRef.current = { householdId, filters, hardRestrictionKey };
      setMealIdeas(suggestions.map((recipe) => {
        const title = recipe.name;
        const normalizedTitle = title.toLowerCase();
        const categories = [
          ...(normalizedTitle.includes('stir-fry') ? ['Stir-fry' as const] : []),
          ...(normalizedTitle.includes('soup') ? ['Soup' as const] : []),
          ...(normalizedTitle.includes('rice') ? ['Rice dish' as const] : []),
        ];
        const ingredients = recipePreviewFoods(recipe)
          .map((food) => ({
            icon: recipeIconForFood(food),
            imageSource: cachedFoodImageSourceForBackendId(food.canonical_food_id),
            name: food.name,
          }));
        return {
          categories,
          imageSource: recipeImageSourceForId(recipe.recipe_id),
          ingredientCount: Number.isInteger(recipe.ingredient_count) && (recipe.ingredient_count ?? -1) >= 0
            ? recipe.ingredient_count : undefined,
          ingredients,
          recipeId: recipe.recipe_id,
          ...recipeIngredientBadge(recipe),
          time: 'Recipe',
          title,
        };
      }));
      if (navigate) {
        if (suggestions.length === 0) {
          Alert.alert(
            'No meal ideas available',
            'Check your food restrictions or try again later. You can still add foods to What you have.',
          );
        } else {
          setScreen('meal-ideas');
        }
      }
    } catch (error) {
      if (navigate) {
        Alert.alert('Meal ideas unavailable', error instanceof Error ? error.message : 'Please try again.');
      }
    }
  };

  useEffect(() => {
    if (isAuthenticated && activeHouseholdId !== null) {
      void openMealIdeas(false);
    } else {
      ++mealIdeasRequestRef.current;
      setMealIdeas([]);
    }
  }, [activeHouseholdId, isAuthenticated, pantryItems, plannedRecipeFoodKey, planDraft.selectedRestrictions, planDraft.customRestriction]);

  const handleRecipeNeedItemsAdded = (items: readonly Pick<RecipeFood, 'canonical_food_id' | 'name'>[]) => {
    setRecipeShoppingListItems((current) => {
      const byId = new Map(current.map((item) => [item.canonical_food_id, item]));
      for (const item of items) byId.set(item.canonical_food_id, item);
      return [...byId.values()];
    });
  };

  const handlePurchasedShoppingItemsChange = (items: readonly ProductPreviewItem[]) => {
    const removedIds = activeHouseholdId === null ? undefined : removedPantryFoodIdsRef.current.get(activeHouseholdId);
    for (const item of items) {
      if (!purchasedIntentRef.current.some((previous) => previous.productId === item.productId)
          && !pantryRemovalPendingRef.current.has(item.productId)) removedIds?.delete(item.productId);
    }
    purchasedIntentRef.current = items;
    setPurchasedShoppingItems(items);
    if (!isAuthenticated) return;
    const removalsBeforePurchase = pantryRemovalQueueRef.current;
    purchasedSyncQueueRef.current = purchasedSyncQueueRef.current.then(async () => {
      try {
        await removalsBeforePurchase;
        const household = activeHouseholdId === null
          ? await ensureHousehold(planDraft.adults, planDraft.children) : null;
        const householdId = household?.id ?? activeHouseholdId;
        if (householdId === null) throw new Error('A household is required to save purchased items.');
        let owned = purchasedPantryIdsRef.current.get(householdId);
        if (!owned) {
          owned = new Map();
          purchasedPantryIdsRef.current.set(householdId, owned);
        }
        const savedItems = items.filter((item) => !removedPantryFoodIdsRef.current.get(householdId)?.has(item.productId));
        const updated = await syncPurchasedPantry(householdId, savedItems,
          pantryCatalogItems.length > 0 ? pantryCatalogItems : catalogItems, owned, {
            list: listPantryItems, create: createPantryItem, remove: removePantryItem,
          });
        savedPurchasedItemsRef.current = savedItems;
        setPantryItems(updated);
        await cachePantryItems(householdId, updated);
      } catch (error) {
        if (purchasedIntentRef.current === items) {
          setPurchasedShoppingItems(savedPurchasedItemsRef.current);
        }
        await loadPantry();
        Alert.alert('Purchased items could not be saved', error instanceof Error ? error.message : 'Please try again.');
      }
    });
  };

  const handleRecipeHaveItemsAdded = async (items: readonly Pick<RecipeFood, 'canonical_food_id' | 'name'>[]) => {
    if (activeHouseholdId === null) throw new Error('A household is required to save ingredients.');
    const householdId = activeHouseholdId;
    await pantryRemovalQueueRef.current;
    await haveSyncQueueRef.current.whenIdle();
    if (activeHouseholdIdRef.current !== householdId) throw new Error('The active household changed. Please reopen the recipe.');
    let updated: readonly PantryItem[];
    try {
      updated = await saveRecipeHaveItems(householdId, items.map((item) => item.canonical_food_id), {
        list: listPantryItems, create: createPantryItem,
      });
    } catch (error) {
      // A multi-item save may have persisted earlier rows before failing.
      await loadPantry();
      throw error;
    }
    if (activeHouseholdIdRef.current !== householdId) throw new Error('The active household changed. Please reopen the recipe.');
    setPantryItems(updated);
    invalidatePantryStockSnapshot();
    const ids = new Set(items.map((item) => item.canonical_food_id));
    setRecipeHaveItems((current) => {
      const byId = new Map(current.map((item) => [item.canonical_food_id, item]));
      for (const item of items) byId.set(item.canonical_food_id, item);
      return [...byId.values()];
    });
    setRecipeShoppingListItems((current) => current.filter((item) => !ids.has(item.canonical_food_id)));
    await cachePantryItems(householdId, updated);
    if (selectedRecipeDetail) {
      try {
        const detail = await fetchRecipeDetail(householdId, selectedRecipeDetail.recipe_id, mealIdeasSnapshotRef.current?.filters);
        if (activeHouseholdIdRef.current === householdId) setSelectedRecipeDetail((current) => current?.recipe_id === detail.recipe_id ? detail : current);
      } catch { /* The next entry retries the detail; never claim new amounts locally. */ }
    }
  };

  const handlePantryQuantitySave = async (item: ProductPreviewItem, input: PantryQuantityInput) => {
    const householdId = activeHouseholdId;
    if (!isAuthenticated || householdId === null) throw new Error('Sign in to save remaining amounts.');
    const row = pantryItems.find((candidate) => candidate.status === 'AVAILABLE'
      && candidate.food.canonical_food_id === item.productId);
    if (!row) throw new Error('This food is not saved in your pantry. Refresh and try again.');
    const updated = await updatePantryItem(householdId, row.pantry_item_id, {
      canonical_food_id: row.food.canonical_food_id,
      ...input,
    });
    if (activeHouseholdIdRef.current !== householdId) return;
    // The PATCH response is authoritative even if a follow-up read fails.
    const refreshed = pantryItems.map((candidate) => candidate.pantry_item_id === updated.pantry_item_id ? updated : candidate);
    setPantryItems((current) => current.map((candidate) => candidate.pantry_item_id === updated.pantry_item_id ? updated : candidate));
    invalidatePantryStockSnapshot();
    await cachePantryItems(householdId, refreshed);
    try {
      const items = await listPantryItems(householdId);
      if (activeHouseholdIdRef.current === householdId) setPantryItems(items);
    } catch {
      // Keep the successful write visible; planning re-reads trusted stock.
    }
  };

  const handlePantryItemRemove = (item: ProductPreviewItem): Promise<void> => {
    const pending = pantryRemovalPendingRef.current.get(item.productId);
    if (pending) return pending;
    const householdId = activeHouseholdId;
    if (!isAuthenticated || householdId === null) return Promise.reject(new Error('Sign in to save changes to What you have.'));
    // Capture existing purchases before publishing the barrier: later writes
    // wait for removal, while earlier writes finish before the fresh GET.
    const purchasesBeforeRemoval = purchasedSyncQueueRef.current;
    const operation = pantryRemovalQueueRef.current.then(async () => {
      await purchasesBeforeRemoval;
      await haveSyncQueueRef.current.whenIdle();
      if (activeHouseholdIdRef.current !== householdId) throw new Error('The active household changed. Please reopen What you have.');
      const updated = await removePantryFood(householdId, item.productId, { list: listPantryItems, remove: removePantryItem });
      let removedIds = removedPantryFoodIdsRef.current.get(householdId);
      if (!removedIds) { removedIds = new Set(); removedPantryFoodIdsRef.current.set(householdId, removedIds); }
      removedIds.add(item.productId);
      await cachePantryItems(householdId, updated);
      if (activeHouseholdIdRef.current !== householdId) return;
      setPantryItems(updated);
      const nextDraft = clearRemovedHaveChoice(basketDraftRef.current, item.productId);
      basketDraftRef.current = nextDraft;
      setBasketDraft(nextDraft);
      persistWeeklyPlan(planDraft, nextDraft, planResultRef.current, selectedFoodIdsRef.current);
      setPurchasedShoppingItems((current) => current.filter((candidate) => candidate.productId !== item.productId));
      purchasedIntentRef.current = purchasedIntentRef.current.filter((candidate) => candidate.productId !== item.productId);
      savedPurchasedItemsRef.current = savedPurchasedItemsRef.current.filter((candidate) => candidate.productId !== item.productId);
      purchasedPantryIdsRef.current.get(householdId)?.delete(item.productId);
      setReceiptHaveItems((current) => current.filter((candidate) => candidate.productId !== item.productId));
      setRecipeHaveItems((current) => current.filter((candidate) => candidate.canonical_food_id !== item.productId));
      // Never fall back to pre-removal stock if its next refresh fails.
      pantryStockSnapshotRef.current = pantryStockSnapshotRef.current?.filter((stock) => stock.food_id !== item.productId) ?? null;
      invalidatePantryStockSnapshot();
      setSelectedRecipeDetail(null);
      setRecipeIngredientState(null);
    });
    pantryRemovalQueueRef.current = operation.catch(() => {});
    pantryRemovalPendingRef.current.set(item.productId, operation);
    void operation.finally(() => pantryRemovalPendingRef.current.delete(item.productId)).catch(() => {});
    return operation;
  };

  const handleReceiptImageSelected = async (asset: ImagePicker.ImagePickerAsset) => {
    let uri: string;
    try {
      uri = (await prepareReceiptImage(asset)).uri;
    } catch (error) {
      Alert.alert(
        'Receipt image unavailable',
        error instanceof Error ? error.message : 'The selected image could not be prepared. Please try another photo.',
      );
      return;
    }
    const requestId = receiptRequestIdRef.current + 1;
    receiptRequestIdRef.current = requestId;
    setReceiptImageUri(uri);
    setReceipt(null);
    setScreen('receipt-processing');

    try {
      if (!isAuthenticated) {
        throw new Error('Please sign in before scanning a receipt.');
      }
      const household = activeHouseholdId === null
        ? await ensureHousehold(planDraft.adults, planDraft.children)
        : null;
      const householdId = household?.id ?? activeHouseholdId;
      if (householdId === null) throw new Error('A household is required to scan a receipt.');

      const uploaded = await uploadReceipt(householdId, uri);
      if (receiptRequestIdRef.current !== requestId) return;
      setReceipt(uploaded);
      const processed = uploaded.status === 'DONE'
        ? uploaded
        : await waitForReceipt(
          householdId,
          uploaded.receipt_id,
          () => receiptRequestIdRef.current === requestId,
        );
      if (receiptRequestIdRef.current !== requestId) return;
      if (processed.lines.length === 0) {
        throw new Error('No grocery items were found. Please try a clearer receipt image.');
      }
      setReceipt(processed);
      setScreen('receipt-review');
    } catch (error) {
      if (receiptRequestIdRef.current !== requestId) return;
      setReceiptCaptureHideIntroBanner(true);
      Alert.alert(
        'Receipt scan failed',
        receiptScanFailureMessage(error),
      );
      setScreen('receipt-capture');
    }
  };

  const handleReceiptProcessingBack = () => {
    receiptRequestIdRef.current += 1;
    setReceipt(null);
    setReceiptCaptureHideIntroBanner(true);
    setScreen('receipt-capture');
  };

  const receiptReviewLines = useMemo<readonly ReceiptReviewLine[]>(
    () => buildReceiptReviewRows(receipt?.lines ?? []), [receipt],
  );

  const handleReceiptConfirm = async (
    items: readonly ReceiptReviewItem[],
    confirmation: ReceiptConfirmation,
  ) => {
    if (!receipt || receiptConfirmingRef.current) return;
    receiptConfirmingRef.current = true;
    try {
      const confirmed = await confirmReceipt(
        receipt.household_id,
        receipt.receipt_id,
        confirmation,
      );
      await clearReceiptReviewDraft(receipt.receipt_id).catch(() => {});
      setReceipt(confirmed);
      setReceiptHaveItems(items);
      await loadPantry();
      // A2: receipt confirm rewrote pantry - invalidate the plan snapshot.
      invalidatePantryStockSnapshot();
      setScreen('my-basket-main');
    } catch (error) {
      Alert.alert(
        'Receipt confirmation failed',
        error instanceof Error ? error.message : 'The receipt could not be confirmed. Please try again.',
      );
    } finally {
      receiptConfirmingRef.current = false;
    }
  };

  const openReceiptCamera = async () => {
    try {
      const permission = await ImagePicker.requestCameraPermissionsAsync();
      if (!permission.granted) {
        setReceiptCaptureHideIntroBanner(true);
        setScreen('receipt-capture');
        Alert.alert(
          'Camera permission needed',
          permission.canAskAgain
            ? 'Allow camera access to photograph a receipt, then try again.'
            : 'Camera access is disabled. Enable it for WiseBasket in your phone Settings.',
        );
        return;
      }
      const result = await ImagePicker.launchCameraAsync({ quality: 0.85 });
      if (!result.canceled && result.assets[0]) void handleReceiptImageSelected(result.assets[0]);
    } catch {
      setReceiptCaptureHideIntroBanner(true);
      setScreen('receipt-capture');
      Alert.alert('Camera unavailable', 'Please try uploading a receipt image instead.');
    }
  };

  const openReceiptLibrary = async () => {
    try {
      const result = await ImagePicker.launchImageLibraryAsync({ quality: 0.85 });
      if (!result.canceled && result.assets[0]) void handleReceiptImageSelected(result.assets[0]);
    } catch {
      setReceiptCaptureHideIntroBanner(true);
      setScreen('receipt-capture');
      Alert.alert('Photo library unavailable', 'Please try again.');
    }
  };

  const handleBuildBasket = async (draftOverride: PlanDraft = planDraft) => {
    if (planBuild.busy) return;
    if (draftOverride.weeklyBudget === null) {
      setPlanBuild({ busy: false, error: 'Set your weekly budget first.' });
      return;
    }
    setPlanBuild({ busy: true, error: null });
    setScreen('plan-building');
    if (isAuthenticated) {
      try {
        await ensureHousehold(draftOverride.adults, draftOverride.children);
      } catch (error) {
        setPlanBuild({
          busy: false,
          error: error instanceof Error ? error.message : 'Your household could not be saved.',
        });
        return;
      }
    }
    // Reset the posted-selection tracker so an identical tick set still
    // re-posts on an explicit (re)build. The basket draft resets with it:
    // the Q3 build starts from a clean endorsement state, so no stale
    // skip/add-back from a previous plan may leak into the new request's
    // habit_picks (2026-09-16 worth-Add loop fix).
    selectedFoodIdsRef.current = [];
    setBasketDraft([]);
    basketDraftRef.current = [];
    const ok = await postPlanForSelection(draftOverride.usualProductIds, draftOverride);
    if (ok) {
      setScreen('plan-basket');
    }
  };

  const handlePlanPersonalizationComplete = async () => {
    const personalization = planPersonalizationFromDraft(planDraft);
    setPlanBuild({ busy: true, error: null });
    try {
      await saveAppProfile({ personalization });
      // A stale presentation mode must never send a first Plan build back to
      // Profile. Only the explicit Profile editor entry is allowed to return
      // there after saving.
      if (planQuestionOneEntrySource === 'profile-personalization') {
        setPlanBuild({ busy: false, error: null });
        setScreen('profile');
        return;
      }
      setPlanBuild({ busy: false, error: null });
      void handleBuildBasket(planDraft);
    } catch (error) {
      setPlanBuild({
        busy: false,
        error: error instanceof Error
          ? error.message
          : 'Your personalization could not be saved. Please try again.',
      });
    }
  };

  const handlePlanConfirmationConfirm = () => {
    if (planDraft.weeklyBudget === null) return;
    void handleBuildBasket(planDraft);
  };

  // 2026-09-14 opt-in journey: the shopping list is solved within the user's
  // final selected set only. REMOVING an item changes what the solver must
  // cover -> debounce and re-post with selected_food_ids = the new need set.
  // Additions appear immediately at their purchase floor, then every change
  // to the Need set is re-solved after the debounce so recipe pairings and
  // Worth considering stay aligned with Need, Have and Skip.
  const committedNeedIdsRef = useRef<readonly string[]>([]);
  const postSeqRef = useRef(0);
  const planPostInFlightRef = useRef(false);
  const quantityPolicyRefreshPendingRef = useRef(false);
  const quantityPolicyRefreshInFlightRef = useRef(false);
  const weeklyPlanHydratedOwnerRef = useRef<string | null>(null);

  // Home's Plan entry explicitly starts a new setup and invalidates any
  // persisted result for the current owner.
  const resetWeeklyPlanForOwner = useCallback(async () => {
    weeklyPlanHydratedOwnerRef.current = weeklyPlanOwner;
    quantityPolicyRefreshPendingRef.current = false;
    await clearWeeklyPlanSnapshot(weeklyPlanOwner);
  }, [weeklyPlanOwner]);

  const restoreWeeklyPlanSnapshot = useCallback((snapshot: WeeklyPlanSnapshot) => {
    quantityPolicyRefreshPendingRef.current = needsQuantityPolicyRefresh(snapshot);
    setPlanDraft(snapshot.planDraft);
    setBasketDraft(snapshot.basketDraft);
    basketDraftRef.current = snapshot.basketDraft;
    setPlanResult(snapshot.planResult);
    planResultRef.current = snapshot.planResult;
    setPostedSelectionIds(snapshot.postedSelectionIds);
    selectedFoodIdsRef.current = snapshot.postedSelectionIds;
    committedNeedIdsRef.current = getNeedItems(snapshot.basketDraft)
      .map((item) => item.productId);
    setPlanBuild({ busy: false, error: null });
  }, []);

  useEffect(() => {
    if (authLoading || weeklyPlanHydratedOwnerRef.current === weeklyPlanOwner) return;

    let active = true;
    const previousOwner = weeklyPlanHydratedOwnerRef.current;
    weeklyPlanHydratedOwnerRef.current = weeklyPlanOwner;

    // Switching accounts must never leave another user's active plan on
    // screen while the new account's snapshot is loading.
    setBasketDraft([]);
    basketDraftRef.current = [];
    setPlanResult(null);
    planResultRef.current = null;
    setPostedSelectionIds([]);
    selectedFoodIdsRef.current = [];
    committedNeedIdsRef.current = [];
    quantityPolicyRefreshPendingRef.current = false;
    if (previousOwner !== null) setPlanDraft(PLAN_DRAFT_DEFAULTS);

    void loadWeeklyPlanSnapshot(weeklyPlanOwner).then((snapshot) => {
      if (!active || !snapshot) return;
      restoreWeeklyPlanSnapshot(snapshot);
    });

    return () => {
      active = false;
    };
  }, [authLoading, weeklyPlanOwner]);

  const persistWeeklyPlan = useCallback((
    nextPlanDraft: PlanDraft,
    nextBasketDraft: readonly BasketDraftItem[],
    nextPlanResult: PlanResponse | null,
    nextPostedSelectionIds: readonly string[],
  ) => {
    if (!nextPlanResult || nextBasketDraft.length === 0) return;
    const snapshot = createWeeklyPlanSnapshot({
      planDraft: nextPlanDraft,
      basketDraft: [...nextBasketDraft],
      planResult: nextPlanResult,
      postedSelectionIds: [...nextPostedSelectionIds],
      ...(quantityPolicyRefreshPendingRef.current ? { quantityPolicyVersion: 1 } : {}),
    });
    void saveWeeklyPlanSnapshot(weeklyPlanOwner, snapshot).catch(() => {
      // The in-memory plan remains usable; the next plan edit retries the
      // device snapshot without interrupting the planning journey.
    });
  }, [weeklyPlanOwner]);

  useEffect(() => {
    if (authLoading || weeklyPlanHydratedOwnerRef.current !== weeklyPlanOwner) return;
    persistWeeklyPlan(planDraft, basketDraft, planResult, postedSelectionIds);
  }, [
    authLoading,
    basketDraft,
    persistWeeklyPlan,
    planDraft,
    planResult,
    postedSelectionIds,
    weeklyPlanOwner,
  ]);

  // 2026-09-17 (A2, real-device "basket sometimes loses items"): journey-
  // level pantry snapshot. Re-fetching the stock on EVERY re-solve made the
  // bought basket race (a) the fire-and-forget have-choice pantry writes
  // and (b) any transient fetch failure, which silently degraded to ZERO-
  // stock planning (fetchConfirmedPantryStock returns null -> []): the same
  // journey produced different baskets run-to-run. Fetch once per journey,
  // reuse the snapshot for every re-solve, and invalidate only when a pantry
  // mutation this session has COMPLETED (have-sync, receipt confirm). A
  // failed refresh keeps the last good snapshot - never clears to zero.
  const pantryStockSnapshotRef = useRef<readonly PlannerPantryStockItem[] | null>(null);
  const pantryStockSnapshotDirtyRef = useRef(false);

  const pantryStockForPlan = async (): Promise<readonly PlannerPantryStockItem[]> => {
    if (activeHouseholdId === null) return [];
    const cached = pantryStockSnapshotRef.current;
    if (cached !== null && !pantryStockSnapshotDirtyRef.current) return cached;
    const fresh = await fetchConfirmedPantryStock(activeHouseholdId)
      ?? cached
      ?? [];
    pantryStockSnapshotRef.current = fresh;
    pantryStockSnapshotDirtyRef.current = false;
    return fresh;
  };

  const invalidatePantryStockSnapshot = () => {
    pantryStockSnapshotDirtyRef.current = true;
  };

  const handleBasketDraftChange = (next: readonly BasketDraftItem[]) => {
    // A fresh explicit Have choice can add stock again. Unrelated edits must
    // not resurrect a removed food from an older captured draft.
    const removedIds = activeHouseholdId === null ? undefined : removedPantryFoodIdsRef.current.get(activeHouseholdId);
    for (const item of next) {
      if (item.choice === 'have' && basketDraftRef.current.find((previous) => previous.productId === item.productId)?.choice !== 'have'
          && !pantryRemovalPendingRef.current.has(item.productId)) removedIds?.delete(item.productId);
    }
    void syncHaveChoicesToPantry(next).catch(() => {
      // The item selection remains visible in the draft; a later action or
      // revisit retries persistence instead of silently changing it back.
    });
    if (!planResult) {
      basketDraftRef.current = next;
      setBasketDraft(next);
      return;
    }
    if (planPostInFlightRef.current) {
      // A user can change another item while the previous re-plan is in
      // flight. Invalidate that response before it can replace the newer
      // draft; the current Need set is scheduled below when it differs from
      // the last committed plan.
      postSeqRef.current += 1;
      planPostInFlightRef.current = false;
      setPlanBuild({ busy: false, error: null });
    }
    const committedNeed = committedNeedIdsRef.current;
    const prevDraftIds = new Set(basketDraftRef.current.map((item) => item.productId));
    const nextNeedIds = getNeedItems(next).map((item) => item.productId);
    // Fresh adds (new to the basket entirely) display at the purchase floor
    // until a re-solve fine-tunes; items already in the draft (e.g. a skipped
    // usual flipped back to Need) keep their solver quantity.
    const freshAdds = nextNeedIds.filter(
      (id) => !committedNeed.includes(id) && !prevDraftIds.has(id),
    );
    const committed = freshAdds.length > 0
      ? next.map((item) => item.choice === 'need' && freshAdds.includes(item.productId)
        ? applyOptimisticAddQuantity(item, planCatalogFoods ?? [])
        : item)
      : next;
    basketDraftRef.current = committed;
    setBasketDraft(committed);
    persistWeeklyPlan(
      planDraft,
      committed,
      planResultRef.current,
      selectedFoodIdsRef.current,
    );
    const needSetChanged = committedNeed.length !== nextNeedIds.length
      || committedNeed.some((id) => !nextNeedIds.includes(id));
    if (replanTimerRef.current) {
      clearTimeout(replanTimerRef.current);
      replanTimerRef.current = null;
    }
    // An add followed by an undo before the debounce expires is back at the
    // committed selection. The pending post still contains the added food,
    // so cancel it even though no replacement post is needed.
    if (!needSetChanged) return;
    replanTimerRef.current = setTimeout(() => {
      replanTimerRef.current = null;
      void postPlanForSelection(nextNeedIds);
    }, 500);
  };

  // Guard against out-of-order re-solve responses: only the latest post may
  // commit its result (an older in-flight re-plan must never overwrite a newer
  // one - that race also made accepted items flicker out of the basket).
  const postPlanForSelection = async (
    selectedIds: readonly string[],
    draftOverride: PlanDraft = planDraft,
  ): Promise<boolean> => {
    const seq = ++postSeqRef.current;
    planPostInFlightRef.current = true;
    setPlanBuild({ busy: true, error: null });
    try {
      // W10 (I2 Phase 2 A2): feed the confirmed pantry snapshot into the
      // solve as zero-cost grams (coverage = stock + purchase, cost =
      // purchase only). Any pantry failure plans from scratch - the safe
      // default - and never blocks the plan request itself.
      const pantryStock = await pantryStockForPlan();
      // A1: the set ALREADY shown as the week plan rides as pinned picks -
      // captured before this post, so fresh adds stay curatable (the user
      // can still trade a brand-new add) while previously-shown items can
      // never evaporate in a curated re-solve (bug8: 11 -> 6).
      const pinnedIds = committedNeedIdsRef.current;
      const request = planRequestFromDraft(
        draftOverride,
        draftOverride.usualProductIds,
        planCatalogFoods ?? [],
        selectedIds,
        pantryStock,
        // 2026-09-16 worth-Add loop fix: the solver's demote domain must
        // mirror the user's CURRENTLY endorsed picks - the live draft is
        // the only place skipped ticks and added-back worth items are
        // recorded (an empty draft = the initial Q3 build -> all ticks).
        basketDraftRef.current,
        pinnedIds,
      );
      const result = await createPlan(request, planCatalogFoods ?? []);
      if (seq !== postSeqRef.current) return false; // superseded by a newer post
      planPostInFlightRef.current = false;
      const acceptedBudgetIdeas = basketDraftRef.current.filter(
        (item) => item.choice === 'need' && item.budgetFallback === true,
      );
      const budgetIdeasHaveQuantity = acceptedBudgetIdeas.every(({ productId }) => {
        const minimum = request.minimum_purchase_quantities?.find(({ food_id }) => food_id === productId);
        const planned = result.items.find((item) => item.food_id === productId);
        return minimum !== undefined && planned !== undefined
          && planned.grams / 1000 + 0.000001 >= minimum.purchase_kg;
      });
      if (acceptedBudgetIdeas.length > 0 && (
        (result.exact_total_cost_rm ?? result.total_cost_rm) > request.budget_rm
        || !budgetIdeasHaveQuantity
      )) {
        // Reject an idea only when its own purchase amount cannot fit.
        const blockedIds = new Set(acceptedBudgetIdeas.map((item) => item.productId));
        const restoredDraft = basketDraftRef.current.filter((item) => !blockedIds.has(item.productId));
        basketDraftRef.current = restoredDraft;
        setBasketDraft(restoredDraft);
        setPlanBuild({
          busy: false,
          error: 'This item does not fit your budget at its suggested amount. Remove another item, then try again.',
        });
        return false;
      }
      // The proposal's pick set is the set we just posted with - NOT
      // planDraft.usualProductIds - so accepted recommendations and manually
      // added foods stay in the week plan after the quantity re-solve.
      const proposal = createPlanBasketProposal(
        result,
        planCatalogFoods ?? [],
        request.selected_food_ids,
        basketDraftRef.current.filter((item) => item.choice === 'need' && item.source !== 'usual')
          .map((item) => item.productId),
      );
      if (proposal.usuals.length === 0) {
        // 2026-09-14: INFEASIBLE responses with catalogue fallback still
        // yield a capped week plan (see createPlanBasketProposal), so this
        // branch only fires when there is truly nothing displayable - budget
        // feedback itself is reserved for "Confirm & check prices".
        if (acceptedBudgetIdeas.length > 0) {
          const blockedIds = new Set(acceptedBudgetIdeas.map((item) => item.productId));
          const restoredDraft = basketDraftRef.current.filter((item) => !blockedIds.has(item.productId));
          basketDraftRef.current = restoredDraft;
          setBasketDraft(restoredDraft);
        }
        setPlanBuild({
          busy: false,
          error: result.infeasibility_reason
            ?? 'The planner could not build a basket for this budget. Try a higher budget.',
        });
        return false;
      }
      // Keep the user's explicit per-item choices (have/skip) for surviving
      // items across the quantity re-solve.
      const priorItemById = new Map(
        basketDraftRef.current.map((item) => [item.productId, item]),
      );
      setPlanResult(result);
      planResultRef.current = result;
      const rebuiltDraft = buildBasketDraft(proposal).map((item) => {
        const prior = priorItemById.get(item.productId);
        return {
          ...item,
          ...(prior?.source && prior.source !== 'usual' ? { source: prior.source } : {}),
          ...(prior?.choice && prior.choice !== 'need' ? { choice: prior.choice } : {}),
          ...(prior?.protectedQuantity ? {
            protectedQuantity: true,
            minimumPurchaseKg: prior.minimumPurchaseKg,
          } : {}),
        };
      });
      // 2026-09-16 user rule: a have/skip item must STAY in the week plan
      // list - it is out of the posted need set, so the solver does not
      // return it and the rebuilt proposal drops it. Carry the prior
      // non-need items back into the draft (choice state + last displayed
      // quantity preserved; they never enter getNeedItems, so the buy set,
      // price check and review sheet are unaffected).
      const survivingIds = new Set(rebuiltDraft.map((item) => item.productId));
      const carriedNonNeed = basketDraftRef.current.filter(
        (item) => item.choice !== 'need' && !survivingIds.has(item.productId),
      );
      const finalDraft = [...rebuiltDraft, ...carriedNonNeed];
      // 2026-09-17 user rule: a re-solve must NEVER reshuffle the week plan.
      // Items keep the exact position the user last saw them in - a Have/
      // Skip edit used to carry the item to the bottom via carriedNonNeed
      // once the re-solve response landed ("点击 Have 之后跳到最下面").
      // Stable sort: previously-shown items keep their relative order; brand
      // -new items (no prior position) keep the proposal order after them.
      const prevIndexById = new Map(
        basketDraftRef.current.map((item, index) => [item.productId, index]),
      );
      finalDraft.sort(
        (a, b) =>
          (prevIndexById.get(a.productId) ?? Number.MAX_SAFE_INTEGER) -
          (prevIndexById.get(b.productId) ?? Number.MAX_SAFE_INTEGER),
      );
      // 2026-09-17 stale-ref fix: basketDraftRef otherwise only syncs in the
      // useEffect AFTER React commits - handleConfirmCheckPrices reads it
      // synchronously right after this await to build the check-prices list,
      // and was snapshotting the PRE-rebuild draft. The check-prices / store
      // pages then showed items the rebuilt draft (and the My Basket shopping
      // list) no longer contained - "visible at the store page, gone in My
      // Basket". Sync the ref at the same moment the state is set.
      basketDraftRef.current = finalDraft;
      setBasketDraft(finalDraft);
      // The committed need baseline for optimistic-add detection (see
      // handleBasketDraftChange): exactly what the week plan shows now.
      committedNeedIdsRef.current = getNeedItems(rebuiltDraft).map((item) => item.productId);
      setSelectedStoreId(null);
      selectedFoodIdsRef.current = [...selectedIds];
      setPostedSelectionIds(selectedIds);
      quantityPolicyRefreshPendingRef.current = false;
      persistWeeklyPlan(
        draftOverride,
        finalDraft,
        result,
        request.selected_food_ids,
      );
      setPlanBuild({ busy: false, error: null });
      return true;
    } catch (error) {
      if (seq !== postSeqRef.current) return false;
      planPostInFlightRef.current = false;
      const pendingBudgetIds = new Set(basketDraftRef.current
        .filter((item) => item.choice === 'need' && item.budgetFallback === true)
        .map((item) => item.productId));
      if (pendingBudgetIds.size > 0) {
        const restoredDraft = basketDraftRef.current.filter((item) => !pendingBudgetIds.has(item.productId));
        basketDraftRef.current = restoredDraft;
        setBasketDraft(restoredDraft);
      }
      setPlanBuild({
        busy: false,
        error: error instanceof Error ? error.message : 'WiseBasket could not build a basket right now.',
      });
      return false;
    }
  };

  // A saved basket can predate the weekly purchase floors. Re-solve it when
  // its screen opens so the visible weights and their prices come from the
  // current planner, while retaining the user's Need/Have/Skip choices.
  useEffect(() => {
    if (screen !== 'plan-basket' || !planCatalogFoods || !planResult
      || !quantityPolicyRefreshPendingRef.current || quantityPolicyRefreshInFlightRef.current) return;
    quantityPolicyRefreshInFlightRef.current = true;
    const savedDraft = planDraft;
    void postPlanForSelection(getNeedItems(basketDraftRef.current).map((item) => item.productId), savedDraft)
      .finally(() => { quantityPolicyRefreshInFlightRef.current = false; });
  }, [screen, planCatalogFoods, planResult, planDraft]);

  // 2026-09-14 user rule: "Confirm & check prices" must re-solve quantities
  // from the FINAL basket list and only ever show exactly those foods. Cancel
  // any pending debounced re-plan, force a fresh POST with the need set, wait
  // for it, and ONLY navigate when the whole basket is actually affordable:
  // if even the minimum purchase of every week-plan food exceeds the budget
  // (status INFEASIBLE, total_cost_rm > budget - e.g. a RM600 basket on a
  // RM200 budget), stay here and tell the user to remove foods instead of
  // presenting an over-budget basket.
  // 2026-09-14 user rule: this check fires ONLY on "Confirm & check prices",
  // never as a proactive banner right after the usual-buys selection.
  const handleConfirmCheckPrices = async (
    items: readonly BasketDraftItem[],
  ): Promise<void> => {
    if (planBuild.busy) return; // a re-solve is already in flight
    setPlanBuild({ busy: true, error: null });
    if (replanTimerRef.current) {
      clearTimeout(replanTimerRef.current);
      replanTimerRef.current = null;
    }
    const needIds = items.map((item) => item.productId);
    const prev = selectedFoodIdsRef.current;
    const same = prev.length === needIds.length
      && prev.every((id) => needIds.includes(id));
    if (!same || quantityPolicyRefreshPendingRef.current) {
      const ok = await postPlanForSelection(needIds);
      if (!ok) return; // stay on the basket screen; the error banner explains
    }
    const fresh = planResultRef.current;
    if (fresh) {
      // 2026-09-14 user rule: the ONLY hard gate at confirm time is genuine
      // unaffordability - the displayed basket's own minimum purchase cost
      // (total_cost_rm) exceeding the budget (e.g. a RM 308 basket of meat
      // floors on a RM 200 budget). An INFEASIBLE result whose basket is
      // WITHIN budget must NOT be blocked: that failure is an energy/
      // nutrition shortfall (days_coverable < days), the basket is the
      // solver's honest best effort, and the user picked these foods on
      // purpose - they may still check prices, same spirit as TIGHT plans.
      const budget = planDraft.weeklyBudget ?? 0;
      const basketCost = fresh.total_cost_rm ?? 0;
      if (basketCost > budget) {
        // W4 (2026-09-16): prefer the backend's three-state copy (names the
        // automatically demoted picks + the real still-over amount, or the
        // plain minimum-cost vs budget figures); only a stale backend that
        // omits the field falls back to the local copy. Zero visual change -
        // same centered dialog, same Skip-then-confirm-again guidance.
        const message = fresh.budget_block_message
          ?? `These foods cost at least ~RM ${basketCost.toFixed(2)} at minimum purchase - more than your RM ${budget.toFixed(2)} budget. Use Skip on some week-plan foods, then confirm again.`;
        // 2026-09-15 user rule: surface this as a centered DIALOG on the
        // basket-confirmed page, not a one-line banner on the week plan -
        // the banner was invisible in real-device testing.
        setBudgetBlockMessage(message);
        setPlanBuild({ busy: false, error: null });
        return;
      }
    }
    // Preserve the displayed quantities when nearby-store pricing exceeds
    // the budget. Any reduction must follow an explicit user decision.
    const budget = planDraft.weeklyBudget ?? 0;
    const storesNow = fresh?.store_comparison ?? [];
    const storeTotals = storesNow
      .map((s) => s.estimated_total_rm ?? s.total_cost_rm)
      .filter((t): t is number => typeof t === 'number' && Number.isFinite(t) && t > 0);
    const cheapestStore = storeTotals.length > 0 ? Math.min(...storeTotals) : null;
    if (budget > 0 && cheapestStore !== null && cheapestStore > budget) {
      const overage = cheapestStore - budget;
      setBudgetBlockMessage(
        `The cheapest nearby-store total is RM ${cheapestStore.toFixed(2)}, which is RM ${overage.toFixed(2)} over your RM ${budget.toFixed(2)} budget. Your planned quantities have not been changed. Edit the basket or change your weekly budget, then check prices again.`,
      );
      setPlanBuild({ busy: false, error: null });
      return;
    }
    const finalItems = getNeedItems(basketDraftRef.current);
    let freshStoreComparison: PlanResponse['store_comparison'] = [];
    try {
      const pricingLocation = await resolveConfirmedLocation();
      if (pricingLocation) {
        freshStoreComparison = await fetchBasketPrices(
          finalItems,
          fresh?.items ?? [],
          planCatalogFoods ?? [],
          pricingLocation,
        );
      }
    } catch {
      setPlanBuild({
        busy: false,
        error: 'Couldn’t check prices right now. Please try again.',
      });
      return;
    }
    const overBudgetQuote = overBudgetStoreQuote(freshStoreComparison, budget);
    if (overBudgetQuote) {
      const missingCount = Math.max(0, finalItems.length - overBudgetQuote.pricedItemCount);
      const quotedScope = missingCount > 0
        ? `for ${overBudgetQuote.pricedItemCount} of ${finalItems.length} basket items`
        : 'for your basket';
      setBudgetBlockMessage(
        `The lowest nearby-store quoted subtotal ${quotedScope} is RM ${overBudgetQuote.quotedSubtotalRm.toFixed(2)}, `
        + `which is RM ${(overBudgetQuote.quotedSubtotalRm - budget).toFixed(2)} over your RM ${budget.toFixed(2)} budget.`
        + (missingCount > 0 ? ` ${missingCount} items are not included in that subtotal.` : '')
        + ' Edit your basket or weekly budget, then check prices again.',
      );
      setPlanBuild({ busy: false, error: null });
      return;
    }
    setBasketStoreComparison(freshStoreComparison);
    setCheckPriceItems(finalItems);
    setPlanBuild({ busy: false, error: null });
    setScreen('check-prices');
  };

  if (screen === 'intro') {
    return <IntroScreen initialPage={introReturnPage} onComplete={handleIntroComplete} />;
  }

  if (
    screen === 'price-check-confirmation'
    && selectedProduct
    && variantConfirmation
  ) {
    return (
      <PriceCheckItemVariantConfirmationScreen
        onBack={() => setScreen('location-price-check')}
        onCheckPrices={(option) => void handleCheckVariantPrices(option)}
        selectedItem={selectedProduct}
        variantConfirmation={variantConfirmation}
      />
    );
  }

  if (screen === 'price-check-results' && resultsData) {
    return (
      <PriceCheckResultsScreen
        data={resultsData}
        onBack={() => setScreen('location-price-check')}
        onEditSelection={() => setScreen(
          selectedProduct?.requiresVariantConfirmation && variantConfirmation
            ? 'price-check-confirmation'
            : 'location-price-check',
        )}
        onOpenPriceInfo={() => undefined}
        onSelectPremise={handleSelectPremise}
      />
    );
  }

  if (screen === 'price-check-store-details' && storeDetailsData) {
    return (
      <PriceCheckStoreDetailsScreen
        data={storeDetailsData}
        onBack={() => setScreen('price-check-results')}
        onNext={handleCheckAnotherItem}
      />
    );
  }

  if (screen === 'price-check-next-step') {
    return (
      <PriceCheckNextStepScreen
        onCheckAnotherItem={handleCheckAnotherItem}
        onFinishForNow={handlePriceCheckFinish}
        onPlanNextWeek={handlePriceCheckPlanNextWeek}
      />
    );
  }

  if (screen === 'plan-confirmation') {
    const selectedFoodIds = new Set(planDraft.usualProductIds);
    const usualFoodNames = (planCatalogFoods ?? [])
      .filter((food) => selectedFoodIds.has(food.food_id as PlanDraft['usualProductIds'][number]))
      .map((food) => food.name);

    return (
      <PlanConfirmationScreen
        onEditSection={handlePlanSectionEdit}
        onBack={handlePlanConfirmationBack}
        onConfirm={handlePlanConfirmationConfirm}
        planDraft={planDraft}
        usualFoodNames={usualFoodNames}
      />
    );
  }

  if (screen === 'plan-building') {
    return (
      <PlanBuildingScreen
        buildBusy={planBuild.busy}
        buildError={planBuild.error}
        onBack={() => {
          setPlanBuild({ busy: false, error: null });
          setScreen('plan-confirmation');
        }}
        onRetry={() => void handleBuildBasket(planDraft)}
      />
    );
  }

  if (screen === 'plan-question-1') {
    return (
      <PlanQuestionOneScreen
        isEditingSection={planSectionEdit === 'household'}
        initialAdults={planDraft.adults}
        initialChildren={planDraft.children}
        initialCustomMealCount={planDraft.customMealCount}
        initialSelectedMealId={planDraft.selectedMealId}
        stepCount={3}
        onBack={handlePlanQuestionOneBack}
        onContinue={() => {
          if (planSectionEdit === 'household') {
            void handlePlanSectionEditSave();
            return;
          }
          setScreen('plan-question-2');
        }}
        onStateChange={handlePlanQuestionOneStateChange}
      />
    );
  }

  if (screen === 'plan-question-2') {
    return (
      <PlanQuestionTwoScreen
        isEditingSection={planSectionEdit === 'budget'}
        initialCustomRestriction={planDraft.customRestriction}
        initialSelectedRestrictions={planDraft.selectedRestrictions}
        initialWeeklyBudget={planDraft.weeklyBudget}
        stepCount={3}
        onBack={() => {
          if (planSectionEdit === 'budget') {
            handlePlanQuestionOneBack();
            return;
          }
          setScreen('plan-question-1');
        }}
        onContinue={() => {
          if (planSectionEdit === 'budget') {
            void handlePlanSectionEditSave();
            return;
          }
          setScreen('plan-question-3');
        }}
        onStateChange={handlePlanQuestionTwoStateChange}
      />
    );
  }

  if (screen === 'plan-question-3') {
    return (
      <PlanQuestionThreeScreen
        isEditingSection={planSectionEdit === 'foods'}
        isEditingPersonalization={personalizationMode === 'edit'}
        initialSelectedProductIds={planDraft.usualProductIds}
        catalogStatus={planCatalogStatus}
        catalogMessage={planCatalogMessage}
        buildBusy={planBuild.busy}
        buildError={planBuild.error}
        onBack={() => {
          if (planSectionEdit === 'foods') {
            handlePlanQuestionOneBack();
            return;
          }
          setScreen('plan-question-2');
        }}
        onBuildBasket={() => {
          if (planSectionEdit === 'foods') {
            void handlePlanSectionEditSave();
            return;
          }
          void handlePlanPersonalizationComplete();
        }}
        onCatalogRetry={() => void loadPlanCatalog()}
        onSelectionChange={handlePlanQuestionThreeSelectionChange}
      />
    );
  }

  if (screen === 'plan-basket') {
    return (
      <PlanBasketScreen
        basketDraft={basketDraft}
        basketProposal={basketProposal}
        onBack={handlePlanBasketBack}
        onBasketDraftChange={handleBasketDraftChange}
        onCheckPrices={(items) => void handleConfirmCheckPrices(items)}
        buildError={planBuild.busy ? null : planBuild.error}
        checkPriceBusy={planBuild.busy}
        budgetBlockMessage={budgetBlockMessage}
        onBudgetBlockDismiss={() => setBudgetBlockMessage(null)}
        planDraft={planDraft}
      />
    );
  }

  if (screen === 'check-prices') {
    return (
      <CheckPricesScreen
        basketItems={checkPriceItems}
        onAddAllToShoppingList={() => {
          setScreen('my-basket-main');
        }}
        onBack={() => {
          setScreen('plan-basket');
        }}
        onSelectedStoreIdChange={setSelectedStoreId}
        planDraft={planDraft}
        prototype={buildPriceGuideFromStoreComparison(checkPriceItems, basketStoreComparison)}
        selectedStoreId={selectedStoreId}
      />
    );
  }

  if (screen === 'my-basket-main') {
    return (
      <MyBasketMainScreen
        onHomePress={() => setScreen('home-dashboard')}
        onPlanNextWeek={() => void openPlanQuestionOne('my-basket-plan-next-week')}
        onPriceCheckPress={() => void openPriceCheckFromMainArea('my-basket-main')}
        onProfilePress={() => openProfile('my-basket-main')}
        onReceiptTakePhotoPress={() => void openReceiptCamera()}
        onReceiptUploadImagePress={() => void openReceiptLibrary()}
        onPurchasedShoppingItemsChange={handlePurchasedShoppingItemsChange}
        onSeeAllMealIdeas={() => void openMealIdeas()}
        basketItems={basketDraft}
        pantryItems={pantryDisplayItems}
        editablePantryFoodIds={isAuthenticated ? pantryItems.filter((item) => item.status === 'AVAILABLE').map((item) => item.food.canonical_food_id) : []}
        onPantryQuantitySave={handlePantryQuantitySave}
        onPantryItemRemove={handlePantryItemRemove}
        planDraft={basketSummaryDraft}
        pricePrototype={buildPriceGuideFromStoreComparison(getNeedItems(basketDraft), basketStoreComparison)}
        recipeHaveItems={recipeHaveItems}
        recipeShoppingListItems={recipeShoppingListItems}
        receiptHaveItems={receiptHaveItems}
        recipeSuggestions={mealIdeas}
        onRecipePress={(recipe) => void handleMealIdeaPress(recipe)}
        persistedPurchasedShoppingItems={purchasedShoppingItems}
        selectedStoreId={selectedStoreId}
      />
    );
  }

  if (screen === 'receipt-capture') {
    return (
      <ReceiptCaptureScreen
        hideIntroBanner={receiptCaptureHideIntroBanner}
        onBack={() => setScreen('my-basket-main')}
        onImageSelected={handleReceiptImageSelected}
      />
    );
  }

  if (screen === 'receipt-processing') {
    return (
      <ReceiptProcessingScreen
        imageUri={receiptImageUri}
        onBack={handleReceiptProcessingBack}
      />
    );
  }

  if (screen === 'receipt-review') {
    return (
      <ReceiptReviewScreen
        receiptId={receipt?.receipt_id}
        catalogItems={pantryCatalogItems.length > 0 ? pantryCatalogItems : catalogItems}
        catalogMessage={catalogMessage}
        catalogStatus={catalogStatus}
        initialLines={receiptReviewLines}
        onBack={() => setScreen('receipt-processing')}
        onConfirm={(items, confirmation) => void handleReceiptConfirm(items, confirmation)}
      />
    );
  }

  if (screen === 'meal-ideas') {
    return (
      <MealIdeasScreen
        onBack={() => setScreen('my-basket-main')}
        onRecipePress={(recipe) => void handleMealIdeaPress(recipe)}
        recipes={mealIdeas}
      />
    );
  }

  if (screen === 'recipe-detail' && selectedMealIdea && selectedRecipeDetail) {
    return (
      <RecipeDetailScreen
        key={selectedRecipeDetail.recipe_id}
        initialIngredientState={recipeIngredientState ?? undefined}
        recipe={selectedRecipeDetail}
        recipeImageSource={selectedMealIdea.imageSource}
        onBack={() => setScreen('meal-ideas')}
        onHaveItemsAdded={handleRecipeHaveItemsAdded}
        onIngredientStateChange={setRecipeIngredientState}
        onNeedItemsAdded={handleRecipeNeedItemsAdded}
      />
    );
  }

  if (screen === 'home-dashboard') {
    return (
      <HomeDashboardScreen
        onBasketPress={() => void openMyBasket()}
        onCreatePlanPress={() => void openPlanQuestionOne('home-create-plan')}
        onLocationPress={openHomeLocationEditor}
        onPlanPress={() => void openPlanQuestionOne('home-plan-next-week')}
        onPriceCheckPress={() => void openPriceCheckFromMainArea('home-dashboard')}
        onProfilePress={() => openProfile('home-dashboard')}
        confirmedLocation={confirmedLocation}
        displayName={profile.name}
        planDraft={activePlanDraft}
        recentChecks={recentChecks}
      />
    );
  }

  if (screen === 'profile') {
    return (
      <ProfileScreen
        onBack={() => setScreen(profileReturnScreen)}
        onLogout={handleProfileLogout}
        onPersonalizationPress={openPersonalizationEditor}
        onProfileChange={handleProfileChange}
        profile={profile}
        saveError={profileSaveError}
      />
    );
  }

  if (screen === 'login-entry') {
    return (
      <LoginEntryScreen
        onCreateAccount={() => setScreen('create-account')}
        onLogin={handleLogin}
      />
    );
  }

  if (screen === 'create-account') {
    return (
      <CreateAccountEntryScreen
        onCreateAccount={handleCreateAccount}
        onLogin={() => setScreen('login-entry')}
      />
    );
  }

  if (screen === 'auth-entry') {
    return (
      <WelcomeScreen
        onContinue={() => setScreen('auth-entry')}
        onLogin={() => setScreen('login-entry')}
        onRegister={() => setScreen('create-account')}
      />
    );
  }

  if (screen === 'price-check-qa-next' && selectedProduct) {
    return (
      <PriceCheckFlowQaNextDestination
        onBack={() => setScreen('location-price-check')}
        selectedItem={selectedProduct}
        status={qaNextDestinationStatus}
      />
    );
  }

  if (screen === 'location-price-check') {
    return (
      <PriceCheckProductSearchScreen
        catalogItems={catalogItems}
        catalogMessage={catalogMessage}
        catalogStatus={catalogStatus}
        onBack={() => setScreen('home-dashboard')}
        onCatalogRetry={() => void loadPriceCheckCatalog()}
        onCatalogItemPress={(item) => void handleSelectProduct(selectedItemFromCatalogEntry(item))}
        onPopularItemPress={(item) => void handleSelectProduct(selectedItemForPopularItem(item))}
      />
    );
  }

  if (screen === 'location-typein') {
    return (
      <ManualLocationSearchScreen
        locationMessage={locationMessage}
        locationStatus={locationStatus}
        onBack={
          locationPurpose === 'price-check'
            ? handlePriceCheckLocationBack
            : locationPurpose === 'home'
              ? handleHomeLocationBack
              : handlePlanLocationBack
        }
        onClearRecentLocations={() => {
          setRecentLocations([]);
          void clearRecentLocations().catch(() => undefined);
        }}
        onSelectAddress={handleLocationAddressSelection}
        recentLocations={recentLocations}
        onUseCurrentLocation={() => void handleLocationUseForPurpose()}
      />
    );
  }

  if (screen === 'location-get-location') {
    return (
      <LocationGetLocationScreen
        locationMessage={locationMessage}
        locationStatus={locationStatus}
        onBack={
          locationPurpose === 'price-check'
            ? handlePriceCheckLocationBack
            : locationPurpose === 'home'
              ? handleHomeLocationBack
              : locationPurpose === 'plan' && planQuestionOneEntrySource !== 'test-flow'
                ? handlePlanLocationBack
                : undefined
        }
        onChangeLocation={pendingLocation ? handleChangePendingLocation : undefined}
        onConfirmLocation={pendingLocation ? () => void handleConfirmLocation() : undefined}
        onEnterAddress={() => setScreen('location-typein')}
        pendingLocation={pendingLocation}
        onUseCurrentLocation={() => void handleLocationUseForPurpose()}
      />
    );
  }

  return null;
}

function AccountFlow() {
  const { user } = useAuth();
  const authHandoff = useRef<PriceCheckSelectedItem | null>(null);
  // A fresh component also clears child-screen state, refs, and pending setters.
  return <TestFlow key={user?.user_id ?? 'guest'} authHandoff={authHandoff} />;
}

export default function App() {
  // Web testing / UAT only. Native platforms keep the original app tree below.
  // The embedded preview uses that same tree inside a phone-sized web viewport.
  if (Platform.OS === 'web'
      && new URLSearchParams(window.location.search).get('embedded') !== '1') {
    return <WebTestingShell />;
  }
  return (
    <SafeAreaProvider>
      <AuthProvider>
        <SafeAreaView edges={['top', 'bottom']} style={styles.app}>
          <AccountFlow />
          <StatusBar style="dark" />
        </SafeAreaView>
      </AuthProvider>
    </SafeAreaProvider>
  );
}

const styles = StyleSheet.create({
  app: {
    backgroundColor: '#FEFDFA',
    flex: 1,
  },
});
