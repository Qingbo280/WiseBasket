/**
 * Planner API types for the WiseBasket mobile app and backend planner API.
 * The Backend* aliases keep the pre-existing mobile code compiling; new code
 * should use the canonical names.
 */

export type PlanStatus = 'FEASIBLE' | 'TIGHT' | 'INFEASIBLE';

export type ExplanationSource = 'template' | 'deepseek' | null;

export type MealSlot = 'breakfast' | 'lunch' | 'dinner';

export type MealsAtHome =
  | 'most_days_multiple'
  | 'once_daily'
  | 'few_times_week'
  | 'weekends_only'
  | null;

export type ShoppingRhythm = 'one_big_shop' | 'top_up_through_week' | null;

/** W10 (I2 Phase 2 A2): one confirmed Epic 6 pantry stock entry, normalised
 *  by the client to known grams. Unconfirmed or NULL/unknown-quantity items
 *  are never sent (fail-closed: when in doubt the plan buys). */
export interface PantryStockItem {
  food_id: string;
  grams: number;
  /** Age of the entry's confirmed snapshot in days (optional pass-through;
   *  the response reports stock_max_age_days for a future UI). */
  confirmed_days_ago?: number;
}

export interface PlanRequest {
  budget_rm: number;
  target_meals?: number;
  days: number;
  adults: number;
  children: number;
  allergies: string[];
  dislikes: string[];
  excludes: string[];
  locks: { food_id: string; grams: number }[];
  dietary_patterns: string[];
  iron_bioavailability: '10pct';
  preference_scores: Record<string, number>;
  /** Q3 ticks as the habit-pick retry's authoritative pick list (2026-09-14). */
  habit_picks: string[];
  /** FINAL food set the shopping list is solved within (2026-09-14 user
   *  decision): non-empty restricts the solver to exactly these ids (quantities
   *  only); empty keeps the legacy whole-catalogue solve. Round 1 carries the
   *  Q3 ticks; accepting a worth-considering recommendation appends its id and
   *  re-posts. */
  selected_food_ids: string[];
  /** Purchase-weight floors from the currently accepted Need basket. A
   * re-plan may increase these amounts but must never reduce them. */
  minimum_purchase_quantities?: { food_id: string; purchase_kg: number }[];
  /** Exact purchases while accepting a budget food idea. */
  fixed_purchase_quantities?: { food_id: string; purchase_kg: number }[];
  /** 2026-09-17 (A1): picks the app already showed in the week plan - in a
   * curated solve these keep their presence guarantee (only new adds are
   * curatable). Absent = current behaviour. */
  pinned_food_ids?: string[] | null;
  habit_adjustments: Record<string, number>;
  store_id: string | null;
  location_state: string | null;
  location_district: string | null;
  location_lat: number | null;
  location_lon: number | null;
  meals_at_home: MealsAtHome;
  shopping_rhythm: ShoppingRhythm;
  /** W10 (I2 Phase 2 A2): confirmed pantry stock as zero-cost grams. Absent /
   *  empty = plan from scratch (backend regression-locked: identical to the
   *  pre-stock behaviour). */
  pantry_stock?: PantryStockItem[];
}

export interface SubstituteOption {
  food_id: string;
  name: string;
  name_ms: string;
  price_rm_per_100g: number;
  price_is_estimated: boolean;
  pack_grams: number | null;
  pack_label: string;
  est_cost_rm: number;
  cost_delta_rm: number;
}

export interface WorthItem {
  food_id: string;
  name: string;
  name_ms: string;
  category: string;
  angle: 'recipe_pairing' | 'nutrient_gap' | 'health_upgrade' | 'budget_fit';
  /** Curated bilingual display tags (never free-text LLM output). */
  reason_en: string;
  reason_ms: string;
  /** Cost of one purchase unit (a pack; by-weight = 250 g). */
  est_cost_rm: number;
  /** Purchase-unit display info (2026-09-14): real units for the
   *  recommendation row ("10 biji", "250 g") instead of the generic "item".
   *  Optional: older backends omit these, catalogue pack_label is the
   *  fallback. */
  pack_label?: string;
  by_weight?: boolean;
}

export interface PlanItem {
  food_id: string;
  name: string;
  name_ms: string;
  category: string;
  grams: number;
  cost_rm: number;
  price_rm_per_100g: number;
  price_is_estimated: boolean;
  packs: number;
  pack_label: string;
  display_quantity: string;
  /** By-weight fresh items (meat/seafood) are priced per gram at the counter;
   *  display them as plain grams ("600 g"), never pack arithmetic. */
  by_weight: boolean;
  /** Estimated household consumption (grams) for the planning period,
   *  distinct from purchase grams. */
  estimated_consumption_g: number | null;
  substitutes: SubstituteOption[];
  /** W10 (I2 Phase 2 A2): already-owned stock grams vs newly purchased grams
   *  (grams == purchase_g). Optional: older backends omit both. */
  stock_g?: number;
  purchase_g?: number;
}

/** W9 (I2 B3, 2026-09-16): one required ingredient the plan does not fully
 *  cover yet. required_g is the household-scaled shortfall in grams; null
 *  means the catalogue row has no reviewed grams (presence-only verdict). */
export interface CookableRecipeMissingItem {
  food_id: string;
  name: string;
  required_g: number | null;
}

/** W9 (I2 B3, 2026-09-16): one active catalogue recipe vs the plan's
 *  buy+stock coverage. cookable = every REQUIRED ingredient covered for this
 *  household; optional garnishes never affect the verdict. */
export interface CookableRecipe {
  recipe_id: string;
  slug: string;
  name: string;
  name_ms: string | null;
  cookable: boolean;
  missing: CookableRecipeMissingItem[];
}

export interface MealPlanItem {
  food_id: string;
  name: string;
  name_ms: string;
  grams: number;
}

export interface MealPlanEntry {
  day: number;
  meal: MealSlot;
  items: MealPlanItem[];
}

export interface AuthUser {
  user_id: string;
  email: string;
  role: string;
  status: string;
  email_verified: boolean;
}

export interface SupportedLocation {
  state: string;
  districts: string[];
}

export interface LocationSearchSuggestion {
  id: string;
  label: string;
  latitude: number;
  longitude: number;
  source: 'osm';
}

export interface FoodPriceUnit {
  unit: string;
  unit_label: string;
  target_unit: string;
  /** Grams represented by one source unit. Optional during backend rollout. */
  factor?: number;
}

export interface NearbyFoodPriceStore {
  rank: number;
  store_id: string;
  store_name: string;
  premise_type: string | null;
  state: string | null;
  district: string | null;
  address: string | null;
  distance_km: number | null;
  price_rm: number;
  original_unit: string | null;
  price_rm_per_100g_purchase: number;
  requested_quantity: number | null;
  requested_unit: string | null;
  requested_quantity_g: number;
  estimated_total_rm: number;
  last_updated: string;
  price_source: string;
  source_dataset_version: string;
  price_provenance: string;
  availability_status: 'OBSERVED_PRICE';
  price_observation_id: number;
}

export interface NearbyFoodPriceResponse {
  canonical_food_id: string;
  food_name: string;
  food_name_ms: string;
  requested_quantity: number | null;
  requested_unit: string | null;
  requested_quantity_g: number;
  available_units: FoodPriceUnit[];
  search_mode: 'GPS_RADIUS' | 'MANUAL_AREA';
  state: string | null;
  district: string | null;
  area_label: string | null;
  radius_km: number | null;
  radius_expanded: boolean;
  distance_note: string | null;
  max_age_days: number | null;
  sort: 'LOWEST_TOTAL_FIRST';
  unit_comparison_basis: 'price_rm_per_100g_purchase';
  result_status: 'FOUND' | 'NO_PRICE_IN_RADIUS' | 'NO_PRICE_IN_AREA';
  disclaimer: string;
  stores: NearbyFoodPriceStore[];
}

export interface AuthTokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in_seconds: number;
  user: AuthUser;
}

export interface FoodInfo {
  food_id: string;
  name: string;
  name_ms: string;
  category: string;
  allergen_tags: string[];
  exclusion_codes: string[];
  price_rm_per_100g: number | null;
  price_rm_per_100g_purchase?: number | null;
  min_price_rm_per_100g_purchase?: number | null;
  sold_by_weight?: boolean;
  price_unit: string;
  price_available: boolean;
  price_is_estimated: boolean;
  price_source: string;
  price_updated: string;
  nutrients: Record<string, number | null>;
  nutrients_unit: string;
  nutrition_available: boolean;
  nutrition_source: string;
  nutrition_updated: string;
  pack_grams: number | null;
  pack_label: string;
  // Curated solo-adult weekly purchase floor in g/ml (backend serves it
  // from week_floors.csv, code-side; additive + optional, 2026-09-16).
  // Multiply by effective persons (adults + 0.6 * children); absent/empty
  // -> fall back to the household-size table floor.
  week_floor_g_per_person?: number | null;
  // Catalogue-completeness fields (additive API change, Catalogue Expansion
  // V2). Optional here so existing screens that ignore them keep compiling
  // unchanged; a food missing these should be treated as fully-detailed for
  // backward compatibility, matching the backend's own default values.
  detail_level?: "FULL_DETAIL" | "PARTIAL_DETAIL" | "NO_DETAIL";
  missing_detail_fields?: string[];
  optimizer_eligible?: boolean;
  // Evidence-backed food tags (food_tag_service), e.g. "Protein source",
  // "Builds strong bones". Additive; optional for the same backward-
  // compatibility reason as the detail_level fields above -- absent/empty
  // means no qualifying evidence was found, never a loading placeholder.
  tags?: string[];
}

export interface CategorySubtotal {
  category: string;
  cost_rm: number;
  grams: number;
}

export interface NutritionCoverage {
  nutrient: string;
  coverage: number;
  intake: number;
  target: number;
  unit: string;
}

export interface NutritionGap {
  nutrient: string;
  shortfall: number;
  unit: string;
  cheapest_fix_food_id: string;
  cheapest_fix_food_name: string;
  extra_cost_rm: number;
}

export interface PriceContext {
  scope: 'national' | 'store';
  store_id: string | null;
  store_name: string | null;
  district: string | null;
  pricing_version: string;
  is_fictional: true;
}

export interface StoreFillAlternative {
  store_id: string;
  store_name: string;
  price_rm_per_100g: number;
  observed_date: string | null;
}

export interface MissingItemOptions {
  food_id: string;
  label: string;
  alternatives: StoreFillAlternative[];
}

export interface StoreQuoteItem {
  food_id: string;
  available: boolean;
  cost_rm: number | null;
  price_rm_per_100g: number | null;
}

export interface StoreComparison {
  store_id: string;
  store_name: string;
  total_cost_rm: number;
  is_cheapest: boolean;
  items_available: number;
  items_missing: number;
  price_coverage_ratio: number;
  observed_date: string | null;
  /** Straight-line user->store distance; only set when GPS was used. */
  distance_km: number | null;
  missing_item_options: MissingItemOptions[];
  /** Per-item prices at this store (list total matches the quote). */
  items: StoreQuoteItem[];
  /** A2.5 (2026-09-17): basket lines this store does NOT price, backfilled
   *  with the plan's own estimate (same source as the price guide) so the
   *  card total is comparable across stores. 0 on old backends / full
   *  coverage. */
  estimated_items_count?: number;
  /** Quote total + the estimate backfill (= total_cost_rm + sum of the
   *  backfilled line estimates). Absent on old backends. */
  estimated_total_rm?: number;
}

export interface RecommendedStore {
  store_id: string;
  store_name: string;
  total_cost_rm: number;
  saving_vs_most_expensive_rm: number;
  note: string;
}

/** Area price spread for the plan's basket (I1 savings banner). Derived
 *  from the displayed same-coverage store quotes only; always an estimate. */
export interface SavingsEstimate {
  basket_min_rm: number;
  basket_max_rm: number;
  save_up_to_rm: number;
  cheapest_store_name: string;
  quotes_count: number;
  is_estimate: boolean;
}

export interface StoreSplitPart {
  store_id: string;
  store_name: string;
  food_ids: string[];
  item_count: number;
  subtotal_rm: number;
}

/** Cheapest two-store shopping plan; only set when no single store prices
 *  the whole basket. Each item goes to the cheaper store of the pair. */
export interface MultiStorePlan {
  stores: StoreSplitPart[];
  total_rm: number;
  covers_all: boolean;
  uncovered_food_ids: string[];
}

export type SuggestionType = 'swap' | 'addition' | 'gap-fix';

export interface PlanSuggestion {
  suggestion_id: string;
  type: SuggestionType;
  title: string;
  body: string;
  cost_delta_rm: number;
  related_food_ids: string[];
}

export interface HabitDimension {
  key: string;
  label: string;
  level: number;
  summary: string;
  context: string;
  target_categories: string[];
  target_food_ids: string[];
}

export interface HabitProfile {
  dimensions: HabitDimension[];
  inferred_from: string[];
}

export interface PlanResponse {
  planner_version?: 'recipe-first-v2';
  recipes?: {
    recipe_id: string;
    name: string;
    occurrences: number;
    household_servings: number;
  }[];
  recipe_allocations?: {
    recipe_id: string;
    food_id: string;
    demand_kg: number;
    pantry_used_kg: number;
    purchase_allocated_kg: number;
  }[];
  recipe_opportunities?: {
    recipe_id: string;
    recipe_name: string;
    additional_meals: number;
    estimated_cost_rm: number;
    missing_ingredients: {
      food_id: string;
      quantity_kg: number;
      purchase_units: number;
      purchase_kg: number;
      estimated_cost_rm: number;
      recipe_reuse_count: number;
      price_is_estimated: boolean;
      purchase_priority?: number;
    }[];
  }[];
  food_fallback_suggestions?: {
    food_id: string;
    group: 'protein' | 'vegetables' | 'carbohydrate';
    purchase_units: number;
    purchase_kg: number;
    estimated_cost_rm: number;
    requires_swap?: boolean;
  }[];
  requested_meals?: number;
  supported_meals?: number;
  deferred_meals?: number;
  planner_error_codes?: string[];
  missing_price_food_ids?: string[];
  status: PlanStatus;
  budget_rm: number;
  adults: number;
  children: number;
  days: number;
  explanation: string | null;
  explanation_source: ExplanationSource;
  items: PlanItem[];
  meal_plan: MealPlanEntry[];
  meal_plan_source: 'llm' | 'template' | null;
  meal_plan_text: string | null;
  meal_plan_text_source: ExplanationSource;
  category_subtotals: CategorySubtotal[];
  total_cost_rm: number;
  exact_total_cost_rm?: number;
  buffer_rm: number;
  nutrition_coverage: NutritionCoverage[];
  overall_coverage_pct: number;
  gaps: NutritionGap[];
  estimated_price_items: number;
  total_items: number;
  infeasibility_reason: string | null;
  /** W4 (2026-09-16): ready-made over-budget dialog copy for the confirm
   *  gate (three-state, real amounts; null unless INFEASIBLE over budget).
   *  Optional - old backends omit it and the client falls back to its local
   *  copy. */
  budget_block_message?: string | null;
  min_budget_for_energy_rm: number | null;
  additional_budget_needed_rm: number | null;
  days_coverable: number | null;
  applied_excludes: string[];
  dropped_locks: string[];
  data_version: string;
  solve_time_ms: number;
  price_context: PriceContext | null;
  store_comparison: StoreComparison[];
  recommended_store: RecommendedStore | null;
  /** How store_comparison was scoped: 'nearby' = GPS radius, 'area' =
   *  district/state level (no GPS, or the radius held no store). */
  store_comparison_scope: 'nearby' | 'area' | null;
  /** Why store_comparison is empty (null when it has quotes). */
  store_comparison_reason: 'no_prices_for_basket' | 'no_stores_in_area' | null;
  /** Area the plan was actually priced/compared against. source 'gps' means
   *  the backend resolved the GPS fix to the nearest area with store data. */
  resolved_location: ResolvedLocation | null;
  savings_estimate: SavingsEstimate | null;
  multi_store_plan: MultiStorePlan | null;
  suggestions: PlanSuggestion[];
  /** Worth-considering recommendations from the backend (2026-09-14):
   *  LLM-picked with deterministic hard constraints + rule fallback. Opt-in:
   *  the client appends an accepted food_id to selected_food_ids and re-posts.
   *  Empty array/absent on legacy anonymous solves and when absent from the
   *  backend payload (older deployments) - clients fall back to local ranking. */
  worth_considering?: WorthItem[];
  /** W3 (2026-09-15): protein picks demoted out of the solve domain by the
   *  price-tier rule (surfaced as budget_fit worth items). Optional. */
  budget_demoted_picks?: string[] | null;
  /** V6-1 (2026-09-17 PM): true when the plan came from the last-resort
   *  caps-relaxed fallback (the selected-journey carb/spice/oil caps were
   *  widened 3x at the full budget after the strict model proved
   *  INFEASIBLE) - the client may disclose "bought a little above the
   *  usual caps". Optional; False/absent = strict caps throughout. */
  caps_relaxed?: boolean;
  /** Step 1 (2026-09-16 curated selection): true when the solver curated the
   *  user's ticks (tight world) - the client must NOT re-apply the week-plan
   *  caps; the solver's item set is already the final curation. Optional. */
  curated_selection?: boolean;
  /** Step 1: ticks the curation left out (sorted food_ids); already rendered
   *  as budget_fit worth items by the backend. Optional. */
  unselected_picks?: string[] | null;
  unpriced_food_ids?: string[];
  /** Step 2 (2026-09-16): bilingual advantage-tag reason for EVERY selected
   *  tick (recommend_tags.csv), letting the client retire its hardcoded
   *  overflow copy. Optional - older backends omit it. */
  pick_reasons?: Record<string, { en: string; ms: string }> | null;
  /** W9 (I2 B3, 2026-09-16): what this plan can cook this week - active
   *  recipe_catalog recipes vs (purchase grams + any declared pantry stock).
   *  Optional/absent on older backends and when the catalogue is empty; no
   *  UI renders it yet. */
  cookable_recipes?: CookableRecipe[] | null;
  habit_profile: HabitProfile | null;
  /** Stable identifier for this plan generation; used to guard against
   *  confirming a plan that has been replaced by a background re-plan. */
  plan_generation_id: string;
}

export interface ResolvedLocation {
  state: string | null;
  district: string | null;
  source: 'gps' | 'request';
}

// ---------------------------------------------------------------------------
// Backwards-compatible aliases for the pre-existing mobile code.
// New code should import the canonical names above.
// ---------------------------------------------------------------------------

export type BackendUser = AuthUser;
export type BackendTokenResponse = AuthTokenResponse;
export type BackendPlanRequest = PlanRequest;
export type BackendGeneratedFoodItem = PlanItem;
export type BackendRecommendedStore = RecommendedStore;
export type BackendPlanResponse = PlanResponse;
