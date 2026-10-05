"""Evidence-backed food tags persisted from governed nutrition records.

``sync_food_tags`` derives the top two qualifying tags from the current
nutrition evidence and stores both the presentation metadata and the exact
nutrition record/value that justified each assignment. ``compute_tags`` is
the backwards-compatible catalogue read API; it now reads those governed
assignments instead of silently recomputing presentation text per request.

Two tag categories, never blurred together:

  NUTRIENT_CONTENT -- a food's food_nutrition row (per 100g) is mechanically
    compared against Malaysia's own regulatory nutrient-content-claim
    thresholds: Food Regulations 1985, Fifth A Schedule, Table II (percent-
    of-Nutrient-Reference-Value rule for vitamins/minerals; flat g/100g rule
    for fibre), as reproduced in the Ministry of Health's "Malaysia Guide to
    Nutrition Labelling and Claims" (Food Safety and Quality Division,
    2010). Two tiers per nutrient: SOURCE ("a source of X") and HIGH
    ("high in X"), exactly the two tiers the regulation itself defines.

  HEALTH_BENEFIT -- only assigned when a food ALREADY qualifies for a
    NUTRIENT_CONTENT tag (at least SOURCE tier) for that nutrient, AND an
    authoritative nutrient-function claim exists tying that nutrient to a
    stated bodily function. The function claims used below are the ones the
    research confirmed as genuinely Malaysia/Codex-sourced (Fifth A
    Schedule Table III; Codex CAC/GL 23-1997 section 7.1.3) -- e.g. calcium
    to bone development, iron to red blood cell formation, protein to
    tissue repair, vitamin C to iron absorption. Claims that only exist
    under the EU's Regulation (EC) 1924/2006 (e.g. "vitamin C supports
    immune function", "protein supports muscle maintenance") are
    deliberately NOT implemented here -- they are not Malaysia/Codex
    claims, and substituting them would misattribute the evidence.

Every tag carries its own evidence_source citation. A nutrient with no
food_nutrition row, or a value below the SOURCE threshold, gets no tag at
all -- there is no "fill the UI" fallback tag.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from services.api.app.db import (
    CanonicalFood,
    CanonicalFoodTag,
    FoodNutrition,
    FoodTagDefinition,
)

NUTRIENT_CONTENT = "NUTRIENT_CONTENT"
HEALTH_BENEFIT = "HEALTH_BENEFIT"

_MOH_CITATION = (
    "Malaysia Food Regulations 1985, Fifth A Schedule (Reg. 18C), Table II "
    "(per Ministry of Health Food Safety and Quality Division, "
    "'Malaysia Guide to Nutrition Labelling and Claims', 2010)"
)
_FUNCTION_CLAIM_CITATION = (
    "Malaysia Food Regulations 1985, Fifth A Schedule, Table III "
    "(nutrient function claims); also Codex Alimentarius CAC/GL 23-1997 sec. 7.1.3"
)

MAX_TAGS_PER_FOOD = 2


@dataclass(frozen=True)
class NutrientRule:
    key: str  # food_nutrition column name
    nutrient_label: str  # used inside tag text
    source_threshold: float
    high_threshold: float
    unit: str
    source_tag: str
    high_tag: str
    function_claim_tag: Optional[str] = None
    function_claim_text: Optional[str] = None  # verbatim regulatory wording, for the report/citation only


# Thresholds are per 100g, solids -- Fifth A Schedule Table II. Protein/
# vitamin C/iron/calcium are the %NRV rule applied to Malaysia's own NRV
# table (protein 50g, vitamin C 60mg, iron 14mg, calcium 800mg): SOURCE =
# 10% NRV (protein) or 15% NRV (vitamins/minerals) per 100g; HIGH = 2x
# SOURCE. Fibre has a flat g/100g rule with no %NRV involved.
NUTRIENT_RULES: list[NutrientRule] = [
    NutrientRule(
        key="fibre_g", nutrient_label="fibre", source_threshold=3.0, high_threshold=6.0, unit="g",
        source_tag="Fibre source", high_tag="High in fibre",
    ),
    NutrientRule(
        key="protein_g", nutrient_label="protein", source_threshold=5.0, high_threshold=10.0, unit="g",
        source_tag="Protein source", high_tag="High in protein",
        function_claim_tag="Builds body tissue",
        function_claim_text="Protein helps build and repair body tissues",
    ),
    NutrientRule(
        key="vitamin_c_mg", nutrient_label="vitamin C", source_threshold=9.0, high_threshold=18.0, unit="mg",
        source_tag="Vitamin C source", high_tag="Vitamin C rich",
        function_claim_tag="Aids iron absorption",
        function_claim_text="Vitamin C contributes to the absorption of iron from food",
    ),
    NutrientRule(
        key="iron_mg", nutrient_label="iron", source_threshold=2.1, high_threshold=4.2, unit="mg",
        source_tag="Iron source", high_tag="High in iron",
        function_claim_tag="Aids blood formation",
        function_claim_text="Iron is a factor in red blood cell formation",
    ),
    NutrientRule(
        key="calcium_mg", nutrient_label="calcium", source_threshold=120.0, high_threshold=240.0, unit="mg",
        source_tag="Calcium source", high_tag="High in calcium",
        function_claim_tag="Builds strong bones",
        function_claim_text="Calcium aids in the development of strong bones and teeth",
    ),
]

TAG_DEFINITIONS = (
    ("FIBRE_SOURCE", "Fibre source", NUTRIENT_CONTENT, "leaf", "GREEN", _MOH_CITATION, 40),
    ("HIGH_FIBRE", "High in fibre", NUTRIENT_CONTENT, "leaf", "GREEN", _MOH_CITATION, 30),
    (
        "BUILDS_BODY_TISSUE", "Builds body tissue", HEALTH_BENEFIT, "fitness", "BLUE",
        _FUNCTION_CLAIM_CITATION + " -- Protein helps build and repair body tissues; "
        "nutrient-content qualification per " + _MOH_CITATION, 10,
    ),
    (
        "AIDS_IRON_ABSORPTION", "Aids iron absorption", HEALTH_BENEFIT, "shield-checkmark", "BLUE",
        _FUNCTION_CLAIM_CITATION + " -- Vitamin C contributes to the absorption of iron from food; "
        "nutrient-content qualification per " + _MOH_CITATION, 20,
    ),
    (
        "AIDS_BLOOD_FORMATION", "Aids blood formation", HEALTH_BENEFIT, "heart", "RED",
        _FUNCTION_CLAIM_CITATION + " -- Iron is a factor in red blood cell formation; "
        "nutrient-content qualification per " + _MOH_CITATION, 20,
    ),
    (
        "BUILDS_STRONG_BONES", "Builds strong bones", HEALTH_BENEFIT, "shield-checkmark", "BLUE",
        _FUNCTION_CLAIM_CITATION + " -- Calcium aids in the development of strong bones and teeth; "
        "nutrient-content qualification per " + _MOH_CITATION, 20,
    ),
)

_TAG_KEY_BY_TEXT = {definition[1]: definition[0] for definition in TAG_DEFINITIONS}


@dataclass(frozen=True)
class FoodTag:
    text: str
    category: str  # NUTRIENT_CONTENT / HEALTH_BENEFIT
    nutrient: str
    value: float
    threshold: float
    unit: str
    evidence_source: str

    def word_count(self) -> int:
        return len(self.text.split())


def _candidate_for_rule(rule: NutrientRule, value: Optional[float]) -> Optional[FoodTag]:
    if value is None:
        return None
    value = float(value)
    if value >= rule.high_threshold:
        tier_tag, threshold = rule.high_tag, rule.high_threshold
    elif value >= rule.source_threshold:
        tier_tag, threshold = rule.source_tag, rule.source_threshold
    else:
        return None

    if rule.function_claim_tag is not None:
        return FoodTag(
            text=rule.function_claim_tag,
            category=HEALTH_BENEFIT,
            nutrient=rule.nutrient_label,
            value=value,
            threshold=rule.source_threshold,
            unit=rule.unit,
            evidence_source=f"{_FUNCTION_CLAIM_CITATION} -- \"{rule.function_claim_text}\"; "
                             f"nutrient-content qualification per {_MOH_CITATION}",
        )
    return FoodTag(
        text=tier_tag,
        category=NUTRIENT_CONTENT,
        nutrient=rule.nutrient_label,
        value=value,
        threshold=threshold,
        unit=rule.unit,
        evidence_source=_MOH_CITATION,
    )


def compute_tags_from_nutrition(nutrition: dict) -> list[FoodTag]:
    """Pure function: nutrition dict (column name -> value/None) -> ranked,
    capped tag list. Kept separate from the DB fetch so it is directly
    unit-testable without a database."""
    candidates: list[tuple[float, FoodTag]] = []
    for rule in NUTRIENT_RULES:
        tag = _candidate_for_rule(rule, nutrition.get(rule.key))
        if tag is not None:
            ratio = tag.value / rule.source_threshold
            candidates.append((ratio, tag))

    candidates.sort(key=lambda pair: pair[0], reverse=True)
    return [tag for _ratio, tag in candidates[:MAX_TAGS_PER_FOOD]]


async def compute_tags(db: AsyncSession, canonical_food_id: str) -> list[FoodTag]:
    rows = (
        await db.execute(
            select(CanonicalFoodTag, FoodTagDefinition)
            .join(
                FoodTagDefinition,
                FoodTagDefinition.tag_key == CanonicalFoodTag.tag_key,
            )
            .where(
                CanonicalFoodTag.canonical_food_id == canonical_food_id,
                FoodTagDefinition.is_active.is_(True),
            )
            .order_by(
                CanonicalFoodTag.display_priority,
                FoodTagDefinition.display_priority,
                FoodTagDefinition.tag_key,
            )
        )
    ).all()
    return [
        FoodTag(
            text=definition.display_label,
            category=definition.category,
            nutrient=assignment.nutrient_key or "",
            value=float(assignment.nutrient_value or 0),
            threshold=float(assignment.qualifying_threshold or 0),
            unit=assignment.nutrient_unit or "",
            evidence_source=definition.evidence_source,
        )
        for assignment, definition in rows
    ]


async def sync_food_tags(
    db: AsyncSession,
    canonical_food_ids: list[str] | None = None,
) -> int:
    """Refresh persisted tags from current PASS/WARN nutrition evidence.

    Values are normalized to 100 g before applying Malaysia's claim
    thresholds. The function is idempotent and may refresh the whole
    catalogue or only explicitly changed foods.
    """
    definition_rows = [
        {
            "tag_key": key,
            "display_label": label,
            "category": category,
            "icon_key": icon,
            "colour_variant": colour,
            "evidence_source": evidence,
            "display_priority": priority,
            "is_active": True,
        }
        for key, label, category, icon, colour, evidence, priority in TAG_DEFINITIONS
    ]
    statement = insert(FoodTagDefinition).values(definition_rows)
    await db.execute(
        statement.on_conflict_do_update(
            index_elements=[FoodTagDefinition.tag_key],
            set_={
                "display_label": statement.excluded.display_label,
                "category": statement.excluded.category,
                "icon_key": statement.excluded.icon_key,
                "colour_variant": statement.excluded.colour_variant,
                "evidence_source": statement.excluded.evidence_source,
                "display_priority": statement.excluded.display_priority,
                "is_active": statement.excluded.is_active,
            },
        )
    )

    if canonical_food_ids is None:
        canonical_food_ids = list(
            (
                await db.execute(select(CanonicalFood.canonical_food_id))
            ).scalars().all()
        )
    else:
        canonical_food_ids = list(dict.fromkeys(canonical_food_ids))
    if not canonical_food_ids:
        return 0

    await db.execute(
        delete(CanonicalFoodTag).where(
            CanonicalFoodTag.canonical_food_id.in_(canonical_food_ids)
        )
    )
    nutrition_rows = (
        await db.execute(
            select(FoodNutrition)
            .where(
                FoodNutrition.canonical_food_id.in_(canonical_food_ids),
                FoodNutrition.is_current.is_(True),
                FoodNutrition.quality_status.in_(("PASS", "WARN")),
            )
            .distinct(FoodNutrition.canonical_food_id)
            .order_by(
                FoodNutrition.canonical_food_id,
                FoodNutrition.created_at.desc(),
                FoodNutrition.nutrition_id.desc(),
            )
        )
    ).scalars().all()

    assignment_count = 0
    rule_by_nutrient = {rule.nutrient_label: rule for rule in NUTRIENT_RULES}
    for row in nutrition_rows:
        scale = 100.0 / float(row.basis_g)
        nutrition = {
            rule.key: (
                float(getattr(row, rule.key)) * scale
                if getattr(row, rule.key) is not None
                else None
            )
            for rule in NUTRIENT_RULES
        }
        for priority, tag in enumerate(
            compute_tags_from_nutrition(nutrition),
            start=1,
        ):
            rule = rule_by_nutrient[tag.nutrient]
            db.add(
                CanonicalFoodTag(
                    canonical_food_id=row.canonical_food_id,
                    tag_key=_TAG_KEY_BY_TEXT[tag.text],
                    source_nutrition_id=row.nutrition_id,
                    nutrient_key=rule.key,
                    nutrient_value=tag.value,
                    qualifying_threshold=tag.threshold,
                    nutrient_unit=tag.unit,
                    display_priority=priority,
                )
            )
            assignment_count += 1
    await db.flush()
    return assignment_count
