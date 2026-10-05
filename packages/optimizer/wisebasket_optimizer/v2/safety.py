# Optional dietary-pattern and allergen filtering for catalogue foods.
from dataclasses import dataclass
from typing import Iterable


SUPPORTED_ALLERGENS = {
    "EGG", "MILK", "PEANUT", "TREE_NUT", "SOY", "WHEAT", "FISH", "SHELLFISH",
}
SUPPORTED_DIETARY_PATTERNS = {"VEGETARIAN", "VEGAN", "NO_PORK"}


@dataclass(frozen=True)
class FoodSafety:
    food_id: str
    vegetarian: bool
    vegan: bool
    contains_pork: bool
    allergens: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        if not isinstance(self.food_id, str) or not self.food_id.strip():
            raise ValueError("Safety food id must be a nonempty string")
        if any(type(value) is not bool for value in (
            self.vegetarian, self.vegan, self.contains_pork,
        )):
            raise ValueError("Dietary safety flags must be boolean")
        if not isinstance(self.allergens, frozenset):
            raise ValueError("Allergens must be a frozenset")
        if not self.allergens <= SUPPORTED_ALLERGENS:
            raise ValueError("Unsupported allergen in food safety record")
        if self.vegan and not self.vegetarian:
            raise ValueError("Vegan-compatible food must also be vegetarian-compatible")
        if self.contains_pork and (self.vegetarian or self.vegan):
            raise ValueError("Pork cannot be vegetarian or vegan")


@dataclass(frozen=True)
class SafetyResolution:
    excluded_food_ids: frozenset[str]
    missing_food_ids: tuple[str, ...]


def resolve_safety_exclusions(
    food_ids: Iterable[str],
    records: Iterable[FoodSafety],
    dietary_patterns: Iterable[str],
    allergens: Iterable[str],
    explicit_exclusions: Iterable[str] = (),
) -> SafetyResolution:
    patterns = frozenset(dietary_patterns)
    selected_allergens = frozenset(allergens)
    if not patterns <= SUPPORTED_DIETARY_PATTERNS:
        raise ValueError("Unsupported dietary pattern")
    if not selected_allergens <= SUPPORTED_ALLERGENS:
        raise ValueError("Unsupported allergen")
    exclusions = set(explicit_exclusions)
    if not patterns and not selected_allergens:
        return SafetyResolution(frozenset(exclusions), ())
    records = tuple(records)
    if len({record.food_id for record in records}) != len(records):
        raise ValueError("Food safety records must be unique per food")
    by_food = {record.food_id: record for record in records}
    missing = set()
    for food_id in set(food_ids):
        record = by_food.get(food_id)
        if record is None:
            exclusions.add(food_id)
            missing.add(food_id)
            continue
        if "VEGETARIAN" in patterns and not record.vegetarian:
            exclusions.add(food_id)
        if "VEGAN" in patterns and not record.vegan:
            exclusions.add(food_id)
        if "NO_PORK" in patterns and record.contains_pork:
            exclusions.add(food_id)
        if record.allergens & selected_allergens:
            exclusions.add(food_id)
    return SafetyResolution(frozenset(exclusions), tuple(sorted(missing)))
