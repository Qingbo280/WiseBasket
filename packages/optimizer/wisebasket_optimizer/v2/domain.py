# Reviewed recipe and substitution contracts for the recipe-first planner.
# This module is independent of persistence and optimization. It decides
# whether catalogue records are safe to pass to the solver.
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum


class IngredientRole(str, Enum):
    MAIN_PROTEIN = "MAIN_PROTEIN"
    STAPLE = "STAPLE"
    MAIN_VEGETABLE = "MAIN_VEGETABLE"
    SUPPORTING_VEGETABLE = "SUPPORTING_VEGETABLE"
    COOKING_ESSENTIAL = "COOKING_ESSENTIAL"
    SEASONING = "SEASONING"
    OPTIONAL = "OPTIONAL"


class MealType(str, Enum):
    COMPLETE_MEAL = "COMPLETE_MEAL"
    MAIN_DISH = "MAIN_DISH"
    SIDE = "SIDE"


class QuantityBasis(str, Enum):
    RAW_EDIBLE_KG = "RAW_EDIBLE_KG"
    PURCHASE_KG = "PURCHASE_KG"


class ReviewStatus(str, Enum):
    DRAFT = "DRAFT"
    APPROVED = "APPROVED"
    PILOT = "PILOT"


def require_identifier(value: str, label: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a nonempty string")


def require_positive_decimal(value: Decimal, label: str) -> None:
    if not isinstance(value, Decimal) or not value.is_finite() or value <= 0:
        raise ValueError(f"{label} must be a positive finite Decimal")


def require_positive_integer(value: int, label: str) -> None:
    if type(value) is not int or value <= 0:
        raise ValueError(f"{label} must be a positive integer")


@dataclass(frozen=True)
class RecipeIngredient:
    food_id: str
    quantity_kg: Decimal
    role: IngredientRole
    required: bool = True

    def __post_init__(self) -> None:
        require_identifier(self.food_id, "Food id")
        require_positive_decimal(self.quantity_kg, "Ingredient quantity")
        if not isinstance(self.role, IngredientRole):
            raise ValueError("Ingredient role must be an IngredientRole")
        if type(self.required) is not bool:
            raise ValueError("Required must be boolean")


@dataclass(frozen=True)
class CookingStep:
    step_number: int
    instruction: str
    food_ids: frozenset[str]

    def __post_init__(self) -> None:
        require_positive_integer(self.step_number, "Step number")
        require_identifier(self.instruction, "Instruction")
        if not isinstance(self.food_ids, frozenset):
            raise ValueError("Step food ids must be a frozenset")
        for food_id in self.food_ids:
            require_identifier(food_id, "Step food id")


@dataclass(frozen=True)
class ReviewedRecipe:
    recipe_id: str
    name: str
    meal_type: MealType
    base_servings: Decimal
    version: int
    review_status: ReviewStatus
    optimizer_eligible: bool
    quantity_basis: QuantityBasis
    ingredients: tuple[RecipeIngredient, ...]
    steps: tuple[CookingStep, ...]
    max_weekly_occurrences: int

    def __post_init__(self) -> None:
        require_identifier(self.recipe_id, "Recipe id")
        require_identifier(self.name, "Recipe name")
        if not isinstance(self.meal_type, MealType):
            raise ValueError("Meal type must be a MealType")
        require_positive_decimal(self.base_servings, "Base servings")
        require_positive_integer(self.version, "Recipe version")
        if not isinstance(self.review_status, ReviewStatus):
            raise ValueError("Review status must be a ReviewStatus")
        if type(self.optimizer_eligible) is not bool:
            raise ValueError("Optimizer eligibility must be boolean")
        if not isinstance(self.quantity_basis, QuantityBasis):
            raise ValueError("Quantity basis must be a QuantityBasis")
        if not self.ingredients:
            raise ValueError("Recipe must have ingredients")
        if len({ingredient.food_id for ingredient in self.ingredients}) != len(self.ingredients):
            raise ValueError("Recipe cannot contain duplicate foods")
        if not self.steps:
            raise ValueError("Recipe must have cooking steps")
        if len({step.step_number for step in self.steps}) != len(self.steps):
            raise ValueError("Recipe cannot contain duplicate step numbers")
        require_positive_integer(self.max_weekly_occurrences, "Maximum weekly occurrences")


@dataclass(frozen=True)
class RecipeAssessment:
    optimizer_eligible: bool
    counts_as_meal: bool
    reasons: tuple[str, ...]
    unused_required_food_ids: tuple[str, ...]
    excluded_food_ids: tuple[str, ...]


def assess_recipe(
    recipe: ReviewedRecipe,
    excluded_food_ids: set[str] | frozenset[str] = frozenset(),
    *,
    allow_pilot: bool = False,
) -> RecipeAssessment:
    # Fail closed unless a recipe is reviewed, complete, and measurable.
    reasons: list[str] = []
    if recipe.review_status is not ReviewStatus.APPROVED and not (
        allow_pilot and recipe.review_status is ReviewStatus.PILOT
    ):
        reasons.append("NOT_APPROVED")
    if not recipe.optimizer_eligible:
        reasons.append("OPTIMIZER_DISABLED")
    if recipe.meal_type is not MealType.COMPLETE_MEAL:
        reasons.append("NOT_COMPLETE_MEAL")
    if recipe.quantity_basis is not QuantityBasis.RAW_EDIBLE_KG:
        reasons.append("UNSUPPORTED_QUANTITY_BASIS")

    required_roles = {ingredient.role for ingredient in recipe.ingredients if ingredient.required}
    for role, reason in (
        (IngredientRole.MAIN_PROTEIN, "MISSING_MAIN_PROTEIN"),
        (IngredientRole.STAPLE, "MISSING_STAPLE"),
        (IngredientRole.MAIN_VEGETABLE, "MISSING_MAIN_VEGETABLE"),
    ):
        if role not in required_roles:
            reasons.append(reason)
    if any(
        ingredient.role is IngredientRole.COOKING_ESSENTIAL and not ingredient.required
        for ingredient in recipe.ingredients
    ):
        reasons.append("OPTIONAL_COOKING_ESSENTIAL")

    step_numbers = sorted(step.step_number for step in recipe.steps)
    if step_numbers != list(range(1, len(recipe.steps) + 1)):
        reasons.append("NONCONTIGUOUS_STEPS")

    ingredient_ids = {ingredient.food_id for ingredient in recipe.ingredients}
    referenced_ids = set().union(*(step.food_ids for step in recipe.steps))
    if referenced_ids - ingredient_ids:
        reasons.append("STEP_REFERENCES_UNKNOWN_FOOD")
    required_ids = {ingredient.food_id for ingredient in recipe.ingredients if ingredient.required}
    unused_required = tuple(sorted(required_ids - referenced_ids))
    if unused_required:
        reasons.append("REQUIRED_INGREDIENT_NOT_IN_STEPS")

    excluded = tuple(sorted(ingredient_ids & set(excluded_food_ids)))
    if excluded:
        reasons.append("CONTAINS_EXCLUDED_FOOD")

    eligible = not reasons
    return RecipeAssessment(eligible, eligible, tuple(reasons), unused_required, excluded)


@dataclass(frozen=True)
class SubstitutionRule:
    rule_id: str
    original_food_id: str
    substitute_food_id: str
    quantity_ratio: Decimal
    role: IngredientRole
    recipe_ids: frozenset[str] = frozenset()
    review_status: ReviewStatus = ReviewStatus.DRAFT
    version: int = 1

    def __post_init__(self) -> None:
        require_identifier(self.rule_id, "Rule id")
        require_identifier(self.original_food_id, "Original food id")
        require_identifier(self.substitute_food_id, "Substitute food id")
        if self.original_food_id == self.substitute_food_id:
            raise ValueError("Substitution must change the food")
        require_positive_decimal(self.quantity_ratio, "Substitution quantity ratio")
        if not isinstance(self.role, IngredientRole):
            raise ValueError("Substitution role must be an IngredientRole")
        if not isinstance(self.recipe_ids, frozenset):
            raise ValueError("Recipe ids must be a frozenset")
        for recipe_id in self.recipe_ids:
            require_identifier(recipe_id, "Recipe id")
        if not isinstance(self.review_status, ReviewStatus):
            raise ValueError("Review status must be a ReviewStatus")
        require_positive_integer(self.version, "Substitution version")


@dataclass(frozen=True)
class SubstitutionAssessment:
    rule: SubstitutionRule
    allowed: bool
    reasons: tuple[str, ...]

    def substitute_quantity(self, original_quantity: Decimal) -> Decimal:
        require_positive_decimal(original_quantity, "Original quantity")
        if not self.allowed:
            raise ValueError("Cannot calculate quantity for a rejected substitution")
        return original_quantity * self.rule.quantity_ratio


def assess_substitution(
    rule: SubstitutionRule,
    recipe: ReviewedRecipe,
    excluded_food_ids: set[str] | frozenset[str] = frozenset(),
) -> SubstitutionAssessment:
    # Validate one directional substitution against one recipe version.
    reasons: list[str] = []
    if rule.review_status is not ReviewStatus.APPROVED:
        reasons.append("RULE_NOT_APPROVED")
    if rule.recipe_ids and recipe.recipe_id not in rule.recipe_ids:
        reasons.append("RULE_NOT_FOR_RECIPE")

    original = next(
        (ingredient for ingredient in recipe.ingredients if ingredient.food_id == rule.original_food_id),
        None,
    )
    if original is None:
        reasons.append("ORIGINAL_NOT_IN_RECIPE")
    elif not original.required:
        reasons.append("ORIGINAL_NOT_REQUIRED")
    elif original.role is not rule.role:
        reasons.append("ROLE_MISMATCH")

    if any(
        ingredient.food_id == rule.substitute_food_id
        for ingredient in recipe.ingredients
    ):
        reasons.append("SUBSTITUTE_ALREADY_IN_RECIPE")
    if rule.substitute_food_id in excluded_food_ids:
        reasons.append("SUBSTITUTE_EXCLUDED")
    return SubstitutionAssessment(rule, not reasons, tuple(reasons))
