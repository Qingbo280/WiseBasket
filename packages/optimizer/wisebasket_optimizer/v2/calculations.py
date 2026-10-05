# Exact recipe -> edible demand -> pantry -> purchase weight -> cost.
# Quantities are Decimal kilograms of raw edible food, except purchase_kg,
# which is bought weight. These calculations evaluate selections; they do not
# choose recipes, certify dietary adequacy, or declare sides complete meals.
from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP
from typing import Iterable, Mapping

from .oil_equivalence import OIL_FOOD_IDS, oil_group

D = Decimal
ZERO = D("0")
CENT = D("0.01")


def require_positive_decimal(value: Decimal, label: str) -> None:
    if not isinstance(value, Decimal) or not value.is_finite() or value <= 0:
        raise ValueError(f"{label} must be a positive finite Decimal")


def require_identifier(value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Identifiers must be nonempty strings")


@dataclass(frozen=True)
class Household:
    adults: int
    children: int
    child_portion_factor: Decimal = D("0.5")

    def __post_init__(self):
        if any(type(n) is not int or n < 0 for n in (self.adults, self.children)) or self.adults + self.children == 0:
            raise ValueError("Household needs nonnegative integer counts and at least one member")
        require_positive_decimal(self.child_portion_factor, "Child portion factor")
        if self.child_portion_factor > 1:
            raise ValueError("Child portion factor cannot exceed 1")

    @property
    def servings(self) -> Decimal:
        return D(self.adults) + D(self.children) * self.child_portion_factor


@dataclass(frozen=True)
class Ingredient:
    food_id: str
    quantity_kg: Decimal
    required: bool = True

    def __post_init__(self):
        require_identifier(self.food_id)
        require_positive_decimal(self.quantity_kg, "Ingredient quantity")
        if type(self.required) is not bool:
            raise ValueError("Required must be boolean")


@dataclass(frozen=True)
class Recipe:
    recipe_id: str
    base_servings: Decimal
    ingredients: tuple[Ingredient, ...]

    def __post_init__(self):
        require_identifier(self.recipe_id)
        require_positive_decimal(self.base_servings, "Base servings")
        if not self.ingredients or not any(i.required for i in self.ingredients):
            raise ValueError("Recipe needs required ingredients")
        if len({i.food_id for i in self.ingredients}) != len(self.ingredients):
            raise ValueError("Duplicate ingredients in recipe")


@dataclass(frozen=True)
class RecipeSelection:
    recipe: Recipe
    occurrences: int
    optional_food_ids: frozenset[str] = frozenset()

    def __post_init__(self):
        if type(self.occurrences) is not int or self.occurrences <= 0:
            raise ValueError("Occurrences must be a positive integer")
        allowed = {i.food_id for i in self.recipe.ingredients if not i.required}
        if not self.optional_food_ids <= allowed:
            raise ValueError("Selected optional ingredients must belong to the recipe")


@dataclass(frozen=True)
class PantryStock:
    food_id: str
    quantity_kg: Decimal | None
    status: str = "CONFIRMED"

    def __post_init__(self):
        require_identifier(self.food_id)
        if self.status not in {"CONFIRMED", "ESTIMATED", "UNKNOWN"}:
            raise ValueError("Invalid pantry status")
        if self.quantity_kg is not None:
            require_positive_decimal(self.quantity_kg, "Pantry quantity")
        if self.status == "CONFIRMED" and self.quantity_kg is None:
            raise ValueError("Confirmed stock needs a quantity")


@dataclass(frozen=True)
class PurchaseOption:
    food_id: str
    unit_kg: Decimal
    price_rm_per_kg: Decimal
    edible_yield: Decimal = D("1")
    price_is_estimated: bool = False

    def __post_init__(self):
        require_identifier(self.food_id)
        require_positive_decimal(self.unit_kg, "Purchase unit")
        require_positive_decimal(self.price_rm_per_kg, "Trusted purchase price")
        require_positive_decimal(self.edible_yield, "Edible yield")
        if self.edible_yield > 1:
            raise ValueError("Edible yield cannot exceed 1")
        if type(self.price_is_estimated) is not bool:
            raise ValueError("Estimated-price flag must be boolean")


@dataclass(frozen=True)
class Allocation:
    recipe_id: str
    food_id: str
    demand_kg: Decimal
    pantry_used_kg: Decimal
    purchase_allocated_kg: Decimal
    pantry_source_food_ids: tuple[str, ...] = ()
    purchase_source_food_id: str | None = None


@dataclass(frozen=True)
class ShoppingItem:
    food_id: str
    demand_kg: Decimal
    pantry_used_kg: Decimal
    shortage_kg: Decimal
    purchase_units: int
    purchase_kg: Decimal
    edible_surplus_kg: Decimal
    exact_cost_rm: Decimal


@dataclass(frozen=True)
class CalculationResult:
    meal_count: int
    items: dict[str, ShoppingItem]
    allocations: tuple[Allocation, ...]
    exact_cost_rm: Decimal
    budget_rm: Decimal

    @property
    def total_cost_rm(self) -> Decimal:
        return self.exact_cost_rm.quantize(CENT, rounding=ROUND_HALF_UP)

    @property
    def within_budget(self) -> bool:
        return self.exact_cost_rm <= self.budget_rm

    @property
    def extra_budget_rm(self) -> Decimal:
        return max(ZERO, self.exact_cost_rm - self.budget_rm).quantize(CENT, rounding=ROUND_CEILING)


def calculate_plan(household: Household, selections: Iterable[RecipeSelection],
                   pantry: Iterable[PantryStock], options: Iterable[PurchaseOption],
                   budget_rm: Decimal,
                   minimum_purchase_kg: Mapping[str, Decimal] | None = None,
                   purchase_units_by_food_id: dict[str, int] | None = None) -> CalculationResult:
    # Evaluate finite selections and allocate confirmed stock in input order.
    # Pantry entries are additive lots, not repeated copies of the same record.
    # Only one purchase option per food is accepted in this first milestone.
    # Over-budget results remain explicitly over-budget; no portions are trimmed.
    require_positive_decimal(budget_rm, "Budget")
    minimum_purchase_kg = dict(minimum_purchase_kg or {})
    for food_id, quantity_kg in minimum_purchase_kg.items():
        require_identifier(food_id)
        require_positive_decimal(quantity_kg, "Minimum purchase quantity")
    selections = tuple(selections)
    pantry = tuple(pantry)
    options = tuple(options)
    if purchase_units_by_food_id is not None:
        return _calculate_with_solver_units(
            household, selections, pantry, options, budget_rm, purchase_units_by_food_id,
            minimum_purchase_kg,
        )
    stock: dict[str, Decimal] = {}
    for entry in pantry:
        if entry.status == "CONFIRMED":
            stock[entry.food_id] = stock.get(entry.food_id, ZERO) + entry.quantity_kg
    purchase_options = {}
    for option in options:
        if option.food_id in purchase_options:
            raise ValueError(f"Duplicate purchase option for {option.food_id}")
        purchase_options[option.food_id] = option
    demands: dict[str, Decimal] = {}
    used: dict[str, Decimal] = {}
    allocations = []
    for selection in selections:
        scale = household.servings / selection.recipe.base_servings * selection.occurrences
        for ingredient in selection.recipe.ingredients:
            if not ingredient.required and ingredient.food_id not in selection.optional_food_ids:
                continue
            fid = ingredient.food_id
            demand = ingredient.quantity_kg * scale
            allocated = min(demand, stock.get(fid, ZERO))
            stock[fid] = stock.get(fid, ZERO) - allocated
            demands[fid] = demands.get(fid, ZERO) + demand
            used[fid] = used.get(fid, ZERO) + allocated
            allocations.append(Allocation(selection.recipe.recipe_id, fid, demand, allocated, demand - allocated))
    for food_id in minimum_purchase_kg:
        demands.setdefault(food_id, ZERO)
        used.setdefault(food_id, ZERO)
    items = {}
    for fid in sorted(demands):
        shortage = demands[fid] - used[fid]
        units, bought, surplus, cost = 0, ZERO, ZERO, ZERO
        minimum = minimum_purchase_kg.get(fid, ZERO)
        if shortage > 0 or minimum > 0:
            option = purchase_options.get(fid)
            if option is None:
                raise ValueError(f"Missing trusted purchase option for {fid}")
            shortage_units = int((shortage / (option.unit_kg * option.edible_yield)).to_integral_value(rounding=ROUND_CEILING))
            minimum_units = int((minimum / option.unit_kg).to_integral_value(rounding=ROUND_CEILING))
            units = max(shortage_units, minimum_units)
            bought = units * option.unit_kg
            surplus = bought * option.edible_yield - shortage
            cost = bought * option.price_rm_per_kg
        items[fid] = ShoppingItem(fid, demands[fid], used[fid], shortage, units, bought, surplus, cost)
    exact_cost = sum((i.exact_cost_rm for i in items.values()), ZERO)
    return CalculationResult(sum(s.occurrences for s in selections), items, tuple(allocations), exact_cost, budget_rm)


def _calculate_with_solver_units(
    household: Household,
    selections: tuple[RecipeSelection, ...],
    pantry: tuple[PantryStock, ...],
    options: tuple[PurchaseOption, ...],
    budget_rm: Decimal,
    units_by_food: dict[str, int],
    minimum_purchase_kg: Mapping[str, Decimal],
) -> CalculationResult:
    """Replay the solver's exact purchase decision, never independently ceil."""
    option_by_food = {option.food_id: option for option in options}
    if len(option_by_food) != len(options):
        raise ValueError("Duplicate purchase option")
    if any(type(units) is not int or units < 0 for units in units_by_food.values()):
        raise ValueError("Purchase units must be nonnegative integers")
    if any(food_id not in option_by_food for food_id in units_by_food):
        raise ValueError("Purchase units reference an unknown option")
    for food_id, minimum in minimum_purchase_kg.items():
        option = option_by_food.get(food_id)
        if option is None or option.unit_kg * units_by_food.get(food_id, 0) < minimum:
            raise ValueError("Solver purchase does not meet accepted minimum")
    purchased_remaining = {
        food_id: option_by_food[food_id].unit_kg * option_by_food[food_id].edible_yield * units
        for food_id, units in units_by_food.items()
    }
    purchased_used = {food_id: ZERO for food_id in purchased_remaining}
    stock_remaining: dict[str, Decimal] = {}
    for item in pantry:
        if item.status == "CONFIRMED":
            stock_remaining[item.food_id] = stock_remaining.get(item.food_id, ZERO) + item.quantity_kg
    demands: dict[str, Decimal] = {}
    pantry_used: dict[str, Decimal] = {}
    allocations: list[Allocation] = []
    for selection in selections:
        scale = household.servings / selection.recipe.base_servings * selection.occurrences
        for ingredient in selection.recipe.ingredients:
            if not ingredient.required and ingredient.food_id not in selection.optional_food_ids:
                continue
            food_id = ingredient.food_id
            demand = ingredient.quantity_kg * scale
            demands[food_id] = demands.get(food_id, ZERO) + demand
            need = demand
            used_stock = ZERO
            # Same-ID confirmed stock first, then other equivalent oils in a
            # fixed order. Every lot is decremented exactly once.
            stock_ids = [food_id]
            used_stock_ids: list[str] = []
            if food_id in OIL_FOOD_IDS:
                stock_ids += sorted(OIL_FOOD_IDS - {food_id})
            for stock_id in stock_ids:
                take = min(need, stock_remaining.get(stock_id, ZERO))
                stock_remaining[stock_id] = stock_remaining.get(stock_id, ZERO) - take
                if take > ZERO:
                    used_stock_ids.append(stock_id)
                need -= take
                used_stock += take
            pantry_used[food_id] = pantry_used.get(food_id, ZERO) + used_stock
            purchase_ids = [food_id] if food_id not in OIL_FOOD_IDS else sorted(OIL_FOOD_IDS)
            purchase_source_id = None
            for purchase_id in purchase_ids:
                take = min(need, purchased_remaining.get(purchase_id, ZERO))
                purchased_remaining[purchase_id] = purchased_remaining.get(purchase_id, ZERO) - take
                purchased_used[purchase_id] = purchased_used.get(purchase_id, ZERO) + take
                if take > ZERO:
                    purchase_source_id = purchase_id
                need -= take
            if need > ZERO:
                raise ValueError(f"Solver purchase does not cover {oil_group(food_id)} demand")
            allocations.append(Allocation(
                selection.recipe.recipe_id, food_id, demand, used_stock,
                demand - used_stock, tuple(used_stock_ids), purchase_source_id,
            ))

    items: dict[str, ShoppingItem] = {}
    for food_id in sorted(set(demands) | {fid for fid, units in units_by_food.items() if units > 0}):
        units = units_by_food.get(food_id, 0)
        option = option_by_food.get(food_id)
        bought = option.unit_kg * units if option is not None else ZERO
        edible = bought * option.edible_yield if option is not None else ZERO
        cost = bought * option.price_rm_per_kg if option is not None else ZERO
        used = pantry_used.get(food_id, ZERO)
        items[food_id] = ShoppingItem(
            food_id, demands.get(food_id, ZERO), used,
            demands.get(food_id, ZERO) - used, units, bought,
            edible - purchased_used.get(food_id, ZERO), cost,
        )
    exact_cost = sum((item.exact_cost_rm for item in items.values()), ZERO)
    if exact_cost > budget_rm:
        raise ValueError("Solver purchase exceeds budget")
    if any(remaining < ZERO for remaining in (*stock_remaining.values(), *purchased_remaining.values())):
        raise ValueError("Solver allocation overused stock or purchases")
    return CalculationResult(sum(s.occurrences for s in selections), items, tuple(allocations), exact_cost, budget_rm)


def display_kg(quantity: Decimal) -> str:
    if not isinstance(quantity, Decimal) or not quantity.is_finite() or quantity < 0:
        raise ValueError("Display quantity must be a nonnegative finite Decimal")
    if ZERO < quantity < CENT:
        return "<0.01 kg"
    return f"{quantity.quantize(CENT, rounding=ROUND_HALF_UP):.2f} kg"
