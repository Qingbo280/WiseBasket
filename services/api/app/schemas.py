from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .services.pantry_units import normalize_quantity_unit


class AuthRegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=200)
    client_type: Literal["MOBILE"] = "MOBILE"
    device_name: str | None = Field(default=None, max_length=160)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        if "@" not in value or "." not in value.rsplit("@", 1)[-1]:
            raise ValueError("A valid email address is required.")
        return value.strip()


class AuthLoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=200)
    client_type: Literal["MOBILE", "ADMIN_WEB"] = "MOBILE"
    device_name: str | None = Field(default=None, max_length=160)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=20)


class LogoutRequest(BaseModel):
    refresh_token: str = Field(min_length=20)


class UserResponse(BaseModel):
    user_id: UUID
    email: str
    role: str
    status: str
    email_verified: bool


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in_seconds: int
    user: UserResponse


class HouseholdInput(BaseModel):
    household_id: int | None = None
    name: str | None = Field(default=None, max_length=100)
    adults: int = Field(ge=0, le=20)
    children: int = Field(ge=0, le=20)
    household_size: int | None = Field(default=None, ge=1, le=40)

    @model_validator(mode="after")
    def validate_members(self) -> "HouseholdInput":
        if self.adults + self.children <= 0:
            raise ValueError("Household must have at least one member.")
        if self.household_size is not None and self.household_size != self.adults + self.children:
            raise ValueError("household_size must equal adults + children.")
        return self


class PantryQuantityInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    quantity: float | None = Field(default=None, gt=0, le=100_000)
    unit: str | None = Field(default=None, max_length=24)

    @model_validator(mode="after")
    def validate_quantity_pair(self) -> "PantryQuantityInput":
        if (self.quantity is None) != (self.unit is None):
            raise ValueError("quantity and unit must be provided together.")
        if self.quantity is not None:
            quantity, unit = normalize_quantity_unit(Decimal(str(self.quantity)), self.unit)
            self.quantity = float(quantity) if quantity is not None else None
            self.unit = unit
        return self


class PantryItemCreateRequest(PantryQuantityInput):
    canonical_food_id: str = Field(min_length=1, max_length=32)


class PantryItemUpdateRequest(PantryQuantityInput):
    canonical_food_id: str = Field(min_length=1, max_length=32)


class BasketHaveSyncRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    food_ids: list[str] = Field(max_length=202)

    @field_validator("food_ids")
    @classmethod
    def normalize_food_ids(cls, value: list[str]) -> list[str]:
        if any(not food_id or not food_id.strip() or len(food_id) > 32 for food_id in value):
            raise ValueError("Each food ID must be nonempty and at most 32 characters.")
        return sorted(set(value))


class PantryFoodResponse(BaseModel):
    canonical_food_id: str
    name: str
    name_ms: str | None
    category: str


class PantryItemResponse(BaseModel):
    pantry_item_id: int
    household_id: int
    food: PantryFoodResponse
    source: str
    status: str
    basket_have_managed: bool = False
    quantity: float | None
    unit: str | None
    created_at: datetime


class PantryConfirmationResponse(BaseModel):
    household_id: int
    available_item_count: int
    confirmed_at: datetime


# --- Epic 6: receipt capture ---


class ReceiptLineCandidate(BaseModel):
    """One top-k match candidate for a receipt line (may sit below the
    0.55 auto-match threshold - the user decides, not the gate)."""

    canonical_food_id: str
    score: float


class ReceiptLineResponse(BaseModel):
    line_id: UUID
    client_line_id: UUID | None = None
    display_order: int
    name_raw: str
    # OCR model's abbreviation expansion of name_raw (None when unsure).
    expanded_name: str | None = None
    qty: float | None
    unit: str | None
    price_rm: float | None
    proposed_food: PantryFoodResponse | None
    match_score: float | None
    candidates: list[ReceiptLineCandidate] = Field(default_factory=list)
    status: str
    match_basis: str | None = None


class ReceiptResponse(BaseModel):
    receipt_id: UUID
    household_id: int
    status: str
    error: str | None
    created_at: datetime
    processed_at: datetime | None
    lines: list[ReceiptLineResponse] = Field(default_factory=list)
    duplicate_of_receipt_id: UUID | None = None


class ReceiptLineConfirmRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    line_id: UUID
    # Null = user rejected/skipped this line (no pantry item is created).
    canonical_food_id: str | None = Field(default=None, max_length=32)
    # Optional price correction (AC 6.2.3): overrides the OCR-recognised price.
    price_rm: float | None = Field(default=None, ge=0, le=999999)
    # Optional quantity correction. Units are canonicalized before persistence.
    qty: float | None = Field(default=None, gt=0, le=100_000)
    unit: str | None = Field(default=None, max_length=24)

    @model_validator(mode="after")
    def validate_quantity_pair(self) -> "ReceiptLineConfirmRequest":
        if ("qty" in self.model_fields_set) != ("unit" in self.model_fields_set):
            raise ValueError("qty and unit must be updated together.")
        if self.qty is not None:
            quantity, unit = normalize_quantity_unit(Decimal(str(self.qty)), self.unit)
            self.qty = float(quantity) if quantity is not None else None
            self.unit = unit
        return self


class ReceiptAddedLineRequest(BaseModel):
    """A grocery item the user adds manually because OCR missed it (AC 6.2.5).

    The line becomes a normal CONFIRMED receipt line (match_score stays null)
    and its own RECEIPT-source pantry item, exactly like an accepted OCR line.
    """

    model_config = ConfigDict(extra="forbid")

    canonical_food_id: str = Field(max_length=32)
    client_line_id: UUID | None = None
    name_raw: str | None = Field(default=None, max_length=240)
    qty: float | None = Field(default=None, gt=0, le=100_000)
    unit: str | None = Field(default=None, max_length=24)
    price_rm: float | None = Field(default=None, ge=0, le=999999)

    @model_validator(mode="after")
    def validate_quantity_pair(self) -> "ReceiptAddedLineRequest":
        if (self.qty is None) != (self.unit is None):
            raise ValueError("qty and unit must be provided together.")
        if self.qty is not None:
            quantity, unit = normalize_quantity_unit(Decimal(str(self.qty)), self.unit)
            self.qty = float(quantity) if quantity is not None else None
            self.unit = unit
        return self


class ReceiptConfirmRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lines: list[ReceiptLineConfirmRequest] = Field(default_factory=list)
    added_lines: list[ReceiptAddedLineRequest] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_line_identity(self) -> "ReceiptConfirmRequest":
        if not self.lines and not self.added_lines:
            raise ValueError("At least one receipt or manually added line is required.")
        ids = [line.line_id for line in self.lines]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate receipt line IDs are not allowed.")
        client_ids = [line.client_line_id for line in self.added_lines if line.client_line_id]
        if len(client_ids) != len(set(client_ids)):
            raise ValueError("Duplicate manual line IDs are not allowed.")
        return self


class SpendingSummaryResponse(BaseModel):
    """Actual grocery spending vs the current weekly plan (AC 6.3 / 6.4)."""

    household_id: int
    # Latest planning request budget; null when the household has no plan yet.
    weekly_budget_rm: float | None = None
    # Latest generated plan estimated basket cost; null when no plan exists.
    estimated_cost_rm: float | None = None
    # Sum of CONFIRMED receipt line prices = recorded actual grocery spending.
    actual_spend_rm: float
    confirmed_receipt_count: int
    last_confirmed_at: datetime | None = None
    # Calculated from confirmed receipt spending, not the optimizer's planned
    # remaining budget. Null means the household has not created a plan yet.
    remaining_budget_rm: float | None = None
    amount_above_budget_rm: float | None = None
    # Positive means actual confirmed spending exceeded the plan estimate.
    estimated_vs_actual_difference_rm: float | None = None
    budget_status: Literal["NO_BUDGET", "WITHIN_BUDGET", "OVER_BUDGET"]


class RecipeIngredientResponse(BaseModel):
    food: PantryFoodResponse
    required: bool
    # Quantities are null for optional/unreviewed ingredients or when a
    # displayed substitute has no validated conversion from recipe grams.
    base_quantity_kg: float | None = None
    required_quantity_kg: float | None = None
    available_quantity_kg: float | None = None
    quantity_status: str = "NOT_TRACKED"
    is_quantity_sufficient: bool | None = None
    shortfall_quantity_kg: float | None = None
    remaining_quantity_kg: float | None = None


class RecipeSubstitutionResponse(BaseModel):
    rule_id: str
    original_food: PantryFoodResponse
    substitute_food: PantryFoodResponse
    reason: str


class RecipeReadinessIssue(BaseModel):
    # Original recipe slot and display-facing pantry food may have different IDs.
    recipe_food_id: str
    food: PantryFoodResponse
    status: Literal["MISSING", "INSUFFICIENT", "UNKNOWN", "NOT_TRACKED"]
    reason: Literal["NOT_IN_PANTRY", "KNOWN_SHORTFALL", "AMOUNT_UNKNOWN",
                    "RECIPE_AMOUNT_UNREVIEWED", "SUBSTITUTION_CONVERSION_UNAVAILABLE"]
    required_quantity_kg: float | None = None
    available_quantity_kg: float | None = None
    shortfall_quantity_kg: float | None = None
    message_en: str


class RecipeReadinessResponse(BaseModel):
    status: Literal["READY", "MISSING_INGREDIENTS", "INSUFFICIENT_QUANTITY", "CHECK_QUANTITIES"]
    all_required_ingredients_available: bool
    all_required_quantities_sufficient: bool
    # Suggested copy, not a requirement to change the existing UI.
    message_en: str
    issues: list[RecipeReadinessIssue] = Field(default_factory=list)


class QuickWinSuggestion(BaseModel):
    # A single-main-ingredient dish: buying this one food makes it cookable.
    canonical_food_id: str
    name: str
    name_ms: str | None
    category: str
    recipe_id: str
    recipe_name: str
    # Representative purchase price (RM/100g) from the read-only batch
    # representative-price path; None when no price is resolvable.
    estimated_price_rm: float | None = None


class PlannedUnlockSummary(BaseModel):
    # Basics-only pantries with week-plan foods that are main ingredients in
    # eligible recipes: "your plan already unlocks these dishes".
    dishes_count: int
    sample_recipe_names: list[str]  # up to 3, alphabetical
    planned_main_food_ids: list[str]  # sorted, planned foods matching mains


class UnlockSuggestion(BaseModel):
    # One main ingredient whose purchase would unlock new cookable dishes.
    canonical_food_id: str
    name: str
    name_ms: str | None
    category: str
    recipes_unlocked: int
    sample_recipe_names: list[str]  # up to 3, alphabetical
    # Representative purchase price (RM/100g); None when unresolvable.
    estimated_price_rm: float | None = None
    # Best (highest-priority) main role this food holds across recipes.
    ingredient_role: str | None = None


class RecipeSuggestionResponse(BaseModel):
    recipe_id: str
    name: str
    description: str | None
    available_ingredients: list[PantryFoodResponse]
    missing_required_ingredients: list[PantryFoodResponse]
    required_match_count: int
    required_ingredient_count: int
    # All listed ingredients, including optional pantry staples, for card badges.
    ingredient_count: int
    optional_ingredient_count: int = 0
    # Stored recipe ingredient ID -> actual pantry substitute ID. Presence
    # counts one slot; display may use the substitute while the stored recipe
    # ingredient and its original cooking quantities remain unchanged.
    matched_alternatives: dict[str, str] = Field(default_factory=dict)
    # Household-scaled quantity summary. These do not deduct pantry stock.
    base_servings: int | None = None
    household_servings: float | None = None
    quantity_status: str = "NOT_TRACKED"
    is_quantity_sufficient: bool | None = None
    required_quantity_sufficient_count: int = 0
    # Additive presentation contract, shared by suggestions and recipe detail.
    readiness: RecipeReadinessResponse | None = None
    # Epic 6 semantic recall: strongest pantry<->ingredient embedding bridge.
    # None when the request did not ask for semantic scoring.
    semantic_score: float | None = None
    # Main-role statistics (additive). "Main" = required ingredients whose
    # ingredient_role is MAIN_PROTEIN/STAPLE/MAIN_VEGETABLE/
    # SUPPORTING_VEGETABLE (grams heuristic when the role is NULL).
    # COOKING_ESSENTIAL (oil) and SEASONING never count, so an oil-only
    # pantry cannot inflate the match. missing_required_ingredients above
    # intentionally still lists oil/salt for honest shopping-gap display.
    main_ingredient_count: int | None = None
    main_match_count: int | None = None
    # Required main-role ingredients found in the pantry, in curated
    # display_order. Pairs with missing_main_ingredients; the frontend uses
    # the two lists to preview real headline ingredients on meal-idea cards
    # instead of whatever optional seasoning sorted first.
    available_main_ingredients: list[PantryFoodResponse] | None = None
    missing_main_ingredients: list[PantryFoodResponse] | None = None
    # Presence-only readiness: True when every main ingredient is in the
    # pantry (main_match_count == main_ingredient_count). Quantity
    # shortfalls are still expressed by the quantity fields above.
    can_make: bool | None = None
    # Pantry-level signals. The suggestions endpoint returns a bare list, so
    # these are repeated (same value) on every item; older clients simply
    # ignore them. pantry_state is "basics_only" when no suggestion matched
    # any main ingredient (empty pantry or pantry of seasonings/oil only),
    # otherwise "ok". unlock_suggestions is only set for basics_only.
    pantry_state: str | None = None
    unlock_suggestions: list[UnlockSuggestion] | None = None
    # Basics-only empty-state layers. quick_win lists single-main dishes that
    # become cookable with one purchase; planned_unlock_summary counts dishes
    # already unlocked by week-plan (planned, unpurchased) main foods. Like
    # the fields above they are repeated (same value) on every item, and an
    # empty basics_only list currently has no item to carry them.
    quick_win_suggestions: list[QuickWinSuggestion] | None = None
    planned_unlock_summary: PlannedUnlockSummary | None = None


class RecipeDetailResponse(RecipeSuggestionResponse):
    ingredients: list[RecipeIngredientResponse]
    substitution_suggestions: list[RecipeSubstitutionResponse]
    cooking_steps: list[str]


class RecipeSuggestionsAdviceResponse(BaseModel):
    # Opt-in wrapper for GET .../recipe-suggestions?advice=true. The default
    # (no flag) response stays the bare list, byte-identical for older
    # clients. The wrapper carries the pantry-level basics_only advice that
    # an empty bare list cannot: quick-win dishes, unlock suggestions and
    # the week-plan unlock summary. Item-level duplicated fields are kept
    # untouched inside suggestions.
    suggestions: list[RecipeSuggestionResponse]
    pantry_state: str  # "ok" | "basics_only"
    quick_win_suggestions: list[QuickWinSuggestion] | None = None
    unlock_suggestions: list[UnlockSuggestion] | None = None
    planned_unlock_summary: PlannedUnlockSummary | None = None


PlannerV2ErrorCode = Literal[
    "INSUFFICIENT_BUDGET",
    "RECIPE_LIMIT_REACHED",
    "MISSING_PRICE",
    "NO_ELIGIBLE_RECIPE",
    "RESTRICTIONS_TOO_LIMITING",
    "TARGET_STRUCTURALLY_UNREACHABLE",
    "MISSING_SAFETY_METADATA",
]

PlannerV2DietaryPattern = Literal["VEGETARIAN", "VEGAN", "NO_PORK"]
PlannerV2Allergen = Literal[
    "EGG", "MILK", "PEANUT", "TREE_NUT", "SOY", "WHEAT", "FISH", "SHELLFISH",
]


class PlannerV2OutcomeResponse(BaseModel):
    status: Literal["FULL_PLAN", "SHORTFALL"]
    requested_meals: int
    supported_meals: int
    deferred_meals: int
    error_codes: list[PlannerV2ErrorCode] = Field(default_factory=list)
    minimum_additional_budget_rm: float | None = None
    estimated_total_cost_rm: float
    missing_price_food_ids: list[str] = Field(default_factory=list)


class PlannerV2PantryItemInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    food_id: str = Field(min_length=1)
    quantity_kg: Decimal | None = Field(default=None, gt=0)
    status: Literal["CONFIRMED", "ESTIMATED", "UNKNOWN"] = "UNKNOWN"

    @model_validator(mode="after")
    def validate_quantity_status(self) -> "PlannerV2PantryItemInput":
        if self.status == "UNKNOWN" and self.quantity_kg is not None:
            raise ValueError("Unknown pantry items cannot include a quantity.")
        if self.status != "UNKNOWN" and self.quantity_kg is None:
            raise ValueError("Confirmed and estimated pantry items require a quantity.")
        return self


class PlannerV2FoodPreferenceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    food_id: str = Field(min_length=1)
    score: int = Field(ge=-100, le=100)

    @field_validator("score")
    @classmethod
    def validate_nonzero_score(cls, value: int) -> int:
        if value == 0:
            raise ValueError("Preference score cannot be zero.")
        return value


class PlannerV2MinimumPurchaseInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    food_id: str = Field(min_length=1)
    purchase_kg: Decimal = Field(gt=0)


class PlannerV2HouseholdInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    adults: int = Field(ge=0, le=20)
    children: int = Field(ge=0, le=20)

    @model_validator(mode="after")
    def validate_members(self) -> "PlannerV2HouseholdInput":
        if self.adults + self.children <= 0:
            raise ValueError("Household must have at least one member.")
        return self


class PlannerV2PurchasePolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    preferred_oil_food_ids: list[str] = Field(default_factory=list)

    @field_validator("preferred_oil_food_ids")
    @classmethod
    def validate_oils(cls, value: list[str]) -> list[str]:
        from packages.optimizer.wisebasket_optimizer.v2.oil_equivalence import OIL_FOOD_IDS

        if len(value) != len(set(value)) or not set(value) <= OIL_FOOD_IDS:
            raise ValueError("Preferred oil IDs must be unique reviewed cooking oils")
        return value


class PlannerV2CreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    household: PlannerV2HouseholdInput
    budget_rm: Decimal = Field(gt=0, le=10_000)
    target_meals: int = Field(gt=0, le=42)
    pantry: list[PlannerV2PantryItemInput] = Field(default_factory=list)
    preferences: list[PlannerV2FoodPreferenceInput] = Field(default_factory=list)
    minimum_purchase_quantities: list[PlannerV2MinimumPurchaseInput] = Field(default_factory=list)
    fixed_purchase_quantities: list[PlannerV2MinimumPurchaseInput] = Field(default_factory=list)
    selected_food_ids: list[str] = Field(default_factory=list)
    excluded_food_ids: list[str] = Field(default_factory=list)
    dietary_patterns: list[PlannerV2DietaryPattern] = Field(default_factory=list)
    allergens: list[PlannerV2Allergen] = Field(default_factory=list)
    purchase_policy: PlannerV2PurchasePolicy = Field(default_factory=PlannerV2PurchasePolicy)

    @model_validator(mode="after")
    def validate_unique_food_inputs(self) -> "PlannerV2CreateRequest":
        pantry_ids = [item.food_id for item in self.pantry]
        preference_ids = [item.food_id for item in self.preferences]
        minimum_purchase_ids = [item.food_id for item in self.minimum_purchase_quantities]
        fixed_purchase_ids = [item.food_id for item in self.fixed_purchase_quantities]
        if len(set(pantry_ids)) != len(pantry_ids):
            raise ValueError("Pantry foods must be unique.")
        if len(set(preference_ids)) != len(preference_ids):
            raise ValueError("Food preferences must be unique.")
        if len(set(minimum_purchase_ids)) != len(minimum_purchase_ids):
            raise ValueError("Minimum purchase foods must be unique.")
        if len(set(fixed_purchase_ids)) != len(fixed_purchase_ids):
            raise ValueError("Fixed purchase foods must be unique.")
        if not set(minimum_purchase_ids) <= set(self.selected_food_ids):
            raise ValueError("Minimum purchase foods must be selected foods.")
        if not set(fixed_purchase_ids) <= set(minimum_purchase_ids):
            raise ValueError("Fixed purchase foods must have minimum purchase quantities.")
        minimum_by_id = {item.food_id: item.purchase_kg for item in self.minimum_purchase_quantities}
        if any(item.purchase_kg != minimum_by_id[item.food_id] for item in self.fixed_purchase_quantities):
            raise ValueError("Fixed purchases must match their minimum purchase quantities.")
        if len(set(self.selected_food_ids)) != len(self.selected_food_ids):
            raise ValueError("Selected foods must be unique.")
        if len(set(self.excluded_food_ids)) != len(self.excluded_food_ids):
            raise ValueError("Excluded foods must be unique.")
        if len(set(self.dietary_patterns)) != len(self.dietary_patterns):
            raise ValueError("Dietary patterns must be unique.")
        if len(set(self.allergens)) != len(self.allergens):
            raise ValueError("Allergens must be unique.")
        return self


class PlannerV2RecipeResponse(BaseModel):
    recipe_id: str
    name: str
    occurrences: int
    household_servings: float


class PlannerV2ShoppingItemResponse(BaseModel):
    food_id: str
    demand_kg: float
    pantry_used_kg: float
    shortage_kg: float
    purchase_units: int
    purchase_kg: float
    surplus_kg: float
    estimated_cost_rm: float
    price_is_estimated: bool


class PlannerV2AllocationResponse(BaseModel):
    recipe_id: str
    food_id: str
    demand_kg: float
    pantry_used_kg: float
    purchase_allocated_kg: float
    pantry_source_food_ids: list[str] = Field(default_factory=list)
    purchase_source_food_id: str | None = None


class PlannerV2OpportunityIngredientResponse(BaseModel):
    food_id: str
    quantity_kg: float
    purchase_units: int
    purchase_kg: float
    estimated_cost_rm: float
    recipe_reuse_count: int
    price_is_estimated: bool
    purchase_priority: int = Field(ge=0, le=5)


class PlannerV2RecipeOpportunityResponse(BaseModel):
    recipe_id: str
    recipe_name: str
    additional_meals: int
    estimated_cost_rm: float
    missing_ingredients: list[PlannerV2OpportunityIngredientResponse]


class PlannerV2FoodFallbackResponse(BaseModel):
    food_id: str
    group: Literal["protein", "vegetables", "carbohydrate"]
    purchase_units: int = Field(gt=0)
    purchase_kg: float = Field(gt=0)
    estimated_cost_rm: float = Field(gt=0)
    requires_swap: bool = False


class PlannerV2AppliedSubstitutionResponse(BaseModel):
    rule_id: str
    recipe_id: str
    original_food_id: str
    substitute_food_id: str
    occurrences: int
    original_quantity_kg: float
    substitute_quantity_kg: float


class PlannerV2NutritionResponse(BaseModel):
    energy_coverage: float
    protein_coverage: float
    calcium_coverage: float
    missing_food_ids: list[str]


class PlannerV2QualityResponse(BaseModel):
    preference_score: int
    pantry_used_kg: float
    purchase_surplus_kg: float
    purchased_food_count: int
    recipe_variety: int


class PlannerV2PlanResponse(BaseModel):
    planner_version: Literal["recipe-first-v2"]
    unpriced_food_ids: list[str] = Field(default_factory=list)
    baseline_id: str | None = None
    baseline_version: str | None = None
    baseline_status: Literal["PILOT"] | None = None
    portion_policy_version: Literal["adult-1-child-0.5-v1"]
    child_portion_factor: float
    quantity_basis: Literal["RAW_EDIBLE_KG"]
    outcome: PlannerV2OutcomeResponse
    recipes: list[PlannerV2RecipeResponse]
    shopping_items: list[PlannerV2ShoppingItemResponse]
    allocations: list[PlannerV2AllocationResponse]
    recipe_opportunities: list[PlannerV2RecipeOpportunityResponse]
    food_fallback_suggestions: list[PlannerV2FoodFallbackResponse] = Field(default_factory=list)
    substitutions: list[PlannerV2AppliedSubstitutionResponse]
    nutrition: PlannerV2NutritionResponse | None
    quality: PlannerV2QualityResponse
    exact_total_cost_rm: float
    displayed_total_cost_rm: float
    remaining_budget_rm: float
    safety_missing_food_ids: list[str] = Field(default_factory=list)


class SupportedLocationResponse(BaseModel):
    state: str
    districts: list[str]


class FoodPriceUnitResponse(BaseModel):
    unit: str
    unit_label: str
    target_unit: str = "g"
    factor: float


class NearbyFoodPriceStoreResponse(BaseModel):
    rank: int
    store_id: str
    store_name: str
    premise_type: str | None = None
    state: str | None = None
    district: str | None = None
    address: str | None = None
    distance_km: float | None = None
    price_rm: float
    original_unit: str | None = None
    price_rm_per_100g_purchase: float
    requested_quantity: float | None = None
    requested_unit: str | None = None
    requested_quantity_g: float
    estimated_total_rm: float
    purchase_mass_g: float | None = None
    purchase_units: int | None = None
    minimum_purchase_cost_rm: float
    pricing_method: Literal["EXACT_PACK", "MULTIPLE_PACKS", "LARGER_PACK", "BY_WEIGHT"]
    last_updated: str
    price_source: str = "PriceCatcher"
    source_dataset_version: str
    price_provenance: str
    availability_status: Literal["OBSERVED_PRICE"] = "OBSERVED_PRICE"
    price_observation_id: int


class NearbyFoodPriceResponse(BaseModel):
    canonical_food_id: str
    food_name: str
    food_name_ms: str
    requested_quantity: float | None = None
    requested_unit: str | None = None
    requested_quantity_g: float
    available_units: list[FoodPriceUnitResponse] = Field(default_factory=list)
    search_mode: Literal["GPS_RADIUS", "MANUAL_AREA"]
    state: str | None = None
    district: str | None = None
    area_label: str | None = None
    radius_km: float | None = None
    radius_expanded: bool
    distance_note: str | None = None
    max_age_days: int | None
    sort: Literal["LOWEST_TOTAL_FIRST"] = "LOWEST_TOTAL_FIRST"
    unit_comparison_basis: Literal["price_rm_per_100g_purchase"] = "price_rm_per_100g_purchase"
    result_status: Literal["FOUND", "NO_PRICE_IN_RADIUS", "NO_PRICE_IN_AREA"]
    disclaimer: str = (
        "Prices are the latest available observed PriceCatcher records and may be older; "
        "they are not live stock or checkout guarantees."
    )
    stores: list[NearbyFoodPriceStoreResponse] = Field(default_factory=list)


class BasketPriceLocationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: str | None = Field(default=None, max_length=80)
    district: str | None = Field(default=None, max_length=120)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)

    @model_validator(mode="after")
    def validate_search_location(self):
        has_latitude = self.latitude is not None
        has_longitude = self.longitude is not None
        if has_latitude != has_longitude:
            raise ValueError("latitude and longitude must be provided together")
        if not has_latitude and not self.state:
            raise ValueError("Provide latitude/longitude or a manual state")
        return self


class BasketPriceItemRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    food_id: str = Field(min_length=1, max_length=32)
    quantity_kg: float = Field(gt=0, le=200)


class BasketPriceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    location: BasketPriceLocationRequest
    items: list[BasketPriceItemRequest] = Field(min_length=1, max_length=100)


class BasketPriceItemResponse(BaseModel):
    food_id: str
    food_name: str
    quantity_kg: float
    purchase_mode: Literal["FIXED_PACK", "BY_WEIGHT"]
    price_source: Literal["OBSERVED_STORE_PRICE", "CATALOGUE_ESTIMATE", "UNAVAILABLE"]
    matched_store_count: int
    estimated_cost_rm: float | None
    latest_observed_date: str | None
    recommended_pack_label: str | None
    recommended_pack_count: int | None
    pricing_method: Literal["EXACT_PACK", "MULTIPLE_PACKS", "LARGER_PACK", "BY_WEIGHT"] | None


class BasketPriceStoreResponse(BaseModel):
    store_id: str
    store_name: str
    matched_item_count: int
    basket_cost_rm: float
    distance_km: float | None
    latest_observed_date: str | None
    items: list["BasketPriceStoreItemResponse"]


class BasketPriceStoreItemResponse(BaseModel):
    food_id: str
    cost_rm: float


class BasketPriceSummaryResponse(BaseModel):
    total_item_count: int
    matched_item_count: int
    estimated_item_count: int
    unavailable_item_count: int


class BasketPriceResponse(BaseModel):
    currency: Literal["MYR"]
    pricing_scope: Literal["LATEST_AVAILABLE_OBSERVED_PRICES"]
    items: list[BasketPriceItemResponse]
    stores: list[BasketPriceStoreResponse]
    summary: BasketPriceSummaryResponse


class LocationSearchSuggestion(BaseModel):
    id: str
    label: str
    address: str
    latitude: float
    longitude: float
    state: str | None = None
    district: str | None = None


class LocationSearchResponse(BaseModel):
    results: list[LocationSearchSuggestion] = Field(default_factory=list)


class AdminSummaryResponse(BaseModel):
    canonical_foods: int
    active_canonical_foods: int
    optimizer_eligible_foods: int
    optimizer_ineligible_foods: int
    price_observations: int
    locations: int
    active_locations: int
    pending_mappings: int
    block_data_quality_issues: int
    generated_plans: int
    latest_etl_run_at: datetime | None = None
    latest_etl_status: str | None = None
