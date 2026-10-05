"""Catalogue Expansion V2 -- post-rebuild no-op guard regression tests.

History: migration f19b6d84c3a7 once seeded 12 genuinely-new foods
(SF073-SF076, SF079, SF080, SF083-SF088) and merged incremental evidence
into 8 existing ids. During the 2026-09 namespace rebuild the Data-team
201-food namespace claimed the SAME id range for entirely different foods
(SF073 = okra, SF088 = guava, ...). The migration was therefore given a
governed skip guard: on any database holding the new namespace (SF201
present) it must no-op, both at upgrade and downgrade time -- seeding the
old identities would silently overwrite the new catalogue.

These tests lock that new-world invariant: every id the old expansion
touched must carry its NEW-namespace identity, and none of the old
expansion/merge evidence may exist. The pre-rebuild behaviour (detail
tiers, merge evidence) was retired together with the old namespace and
lives in git history.
"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from services.api.app.db import AsyncSessionLocal, CanonicalFood

# The 12 "genuinely new" expansion ids and the identity the 201-namespace
# assigns to each (from migrations/data/new_canonical_foods_201.json).
OLD_EXPANSION_NEW_IDENTITY = {
    "SF073": "okra (lady's finger)",
    "SF074": "water spinach",
    "SF075": "red capsicum",
    "SF076": "bean sprouts",
    "SF079": "cauliflower",
    "SF080": "celery",
    "SF083": "calamansi lime",
    "SF084": "long beans",
    "SF085": "green capsicum",
    "SF086": "yellow capsicum",
    "SF087": "cucumber",
    "SF088": "guava",
}

# The 8 retired-draft ids the old expansion never created. The rebuild
# namespace assigns each of them a real food too.
RETIRED_DRAFT_NEW_IDENTITY = {
    "SF077": "carrot",
    "SF078": "kailan",
    "SF081": "mustard greens",
    "SF082": "broccoli",
    "SF089": "watermelon (red)",
    "SF090": "banana",
    "SF091": "lai fruit",
    "SF092": "papaya",
}


@pytest.mark.asyncio
@pytest.mark.parametrize("food_id", sorted(OLD_EXPANSION_NEW_IDENTITY))
async def test_old_expansion_id_carries_new_namespace_identity(food_id):
    """f19b6d84c3a7's skip guard held: the id exists with the identity the
    201-namespace catalogue assigns -- never the old expansion identity."""
    expected = OLD_EXPANSION_NEW_IDENTITY[food_id]
    async with AsyncSessionLocal() as db:
        row = (
            await db.execute(
                select(CanonicalFood.canonical_name).where(
                    CanonicalFood.canonical_food_id == food_id
                )
            )
        ).fetchone()
    assert row is not None, f"{food_id} missing from rebuilt catalogue"
    assert row[0] == expected, (
        f"{food_id} holds {row[0]!r}; the old catalogue-expansion identity "
        f"would have overwritten the 201-namespace identity {expected!r}. "
        "The f19b6d84c3a7 skip guard is broken."
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("food_id", sorted(RETIRED_DRAFT_NEW_IDENTITY))
async def test_retired_draft_id_carries_new_namespace_identity(food_id):
    """The old draft ids were 'never created' pre-rebuild; post-rebuild the
    namespace rightfully owns them -- with its own identities."""
    expected = RETIRED_DRAFT_NEW_IDENTITY[food_id]
    async with AsyncSessionLocal() as db:
        row = (
            await db.execute(
                select(CanonicalFood.canonical_name).where(
                    CanonicalFood.canonical_food_id == food_id
                )
            )
        ).fetchone()
    assert row is not None, f"{food_id} missing from rebuilt catalogue"
    assert row[0] == expected, f"{food_id} holds unexpected identity {row[0]!r}"


@pytest.mark.asyncio
async def test_old_expansion_names_absent_from_canonical_food():
    """No row anywhere may still carry an old expansion identity name --
    guards against a partial/no-guarded f19b6 run corrupting other ids."""
    # Names that exist nowhere in the 201-namespace catalogue; any row
    # carrying one can only be an unguarded f19b6 run (shallot/grated
    # coconut/tamarind are legitimate 201 foods, so not blacklisted).
    old_names = [
        "bell pepper", "eggplant", "kacang bendi", "brown sugar",
    ]
    async with AsyncSessionLocal() as db:
        rows = (
            await db.execute(select(CanonicalFood.canonical_name))
        ).scalars().all()
    remaining = {n for n in rows if n in old_names}
    assert not remaining, f"old expansion identities survive: {remaining}"
