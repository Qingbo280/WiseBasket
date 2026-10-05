"""Shared response models that are independent of the retired V1 planner."""

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class FoodInfo(BaseModel):
    """Food catalogue entry returned by ``GET /api/v1/foods``.

    Missing price or nutrition evidence remains null and is disclosed as
    unavailable. The catalogue route is shared infrastructure and is not part
    of the retired V1 optimization flow.
    """

    food_id: str
    name: str
    name_ms: str
    category: str
    allergen_tags: List[str] = Field(default_factory=list)
    exclusion_codes: List[str] = Field(default_factory=list)
    price_rm_per_100g: Optional[float] = None
    # Receipt quantities describe purchased mass, not edible mass. Keep the
    # purchase-basis rate separate from the planner's edible-basis rate.
    price_rm_per_100g_purchase: Optional[float] = None
    # Cheapest eligible latest-per-shop purchase price; receipt-only estimate.
    min_price_rm_per_100g_purchase: Optional[float] = None
    sold_by_weight: bool = False
    price_unit: str = "RM/100g"
    price_available: bool = False
    price_is_estimated: bool = False
    price_provenance: str = ""
    price_source: str = ""
    price_updated: str = ""
    nutrients: Dict[str, Optional[float]] = Field(default_factory=dict)
    nutrients_unit: str = "per 100g edible portion"
    nutrition_available: bool = False
    nutrition_source: str = ""
    nutrition_updated: str = ""
    pack_grams: Optional[int] = None
    pack_label: str = ""
    detail_level: str = "FULL_DETAIL"
    missing_detail_fields: List[str] = Field(default_factory=list)
    optimizer_eligible: bool = True
    week_floor_g_per_person: Optional[int] = None
    tags: List[str] = Field(default_factory=list)
