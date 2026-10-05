from dataclasses import dataclass

@dataclass(frozen=True)
class CanonicalFood:
    food_id: str
    canonical_name: str
    standard_unit: str
    edible_grams_per_unit: float | None = None
