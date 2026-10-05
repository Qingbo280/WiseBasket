"""Test-suite-wide fixtures/environment.

CC8: tests must run fully without a real LLM. A local .env with
DEEPSEEK_API_KEY makes the app construct a live client, which would turn
the API tests into slow, non-deterministic network calls - disable the
LLM for the whole suite, before any app module is imported.

The serving paths read foods live from PostgreSQL, so the suite seeds a
standard trusted candidate set (tests/db_seed.py) once per session. The
monorepo suite therefore requires a migrated PostgreSQL (CI provides the
postgres service; locally, run PostgreSQL and `alembic -c config/alembic.ini
upgrade head` with DATABASE_URL pointed at it).
"""
import os

os.environ["APP_ENV"] = "test"
os.environ["LLM_ENABLED"] = "false"

import pytest

# Test-safety guard (SF009 deployment-readiness review, Section 10): this suite's
# fixtures are destructive by design (tests/db_seed.py deletes and re-inserts
# SEED0xx rows every session; individual test files do the same for their own
# prefixes). That is exactly the shape of the CB-DEF-005 incident on record
# (docs/data_food_integrity/P0_INTEGRITY_AUDIT.md): a pytest run once resolved
# DATABASE_URL to the shared Railway instance and silently polluted production
# with SEED001-009 rows. This check runs at conftest import time -- before any
# fixture or test in the suite -- and aborts the entire run immediately if the
# resolved database (env var OR .env file, i.e. whatever the app itself would
# actually connect to) looks like a non-local/production host. It is
# deliberately a denylist of known-dangerous host patterns, not an allowlist of
# "safe" ones, so it cannot be satisfied by simply renaming a still-remote host.
_DANGEROUS_HOST_PATTERNS = ("railway", "rlwy.net", "amazonaws.com", "rds.", ".render.com", "supabase.co")


def _refuse_if_database_url_looks_remote() -> None:
    try:
        from services.api.app.config import get_settings
        resolved_url = get_settings().database_url
    except Exception:
        resolved_url = os.environ.get("DATABASE_URL", "")
    lowered = resolved_url.lower()
    matched = [p for p in _DANGEROUS_HOST_PATTERNS if p in lowered]
    if matched:
        pytest.exit(
            f"REFUSING TO RUN: resolved DATABASE_URL matches known remote/production "
            f"host pattern(s) {matched} -- this test suite runs destructive fixtures "
            f"and must only ever target a local/CI database. See CB-DEF-005 in "
            f"docs/data_food_integrity/P0_INTEGRITY_AUDIT.md for why this guard exists. "
            f"Point DATABASE_URL at a local Postgres instance instead.",
            returncode=1,
        )


_refuse_if_database_url_looks_remote()


@pytest.fixture(scope="session", autouse=True)
def _seed_standard_candidates():
    from tests.db_seed import (
        cleanup_standard_candidates,
        run_db,
        seed_standard_candidates,
    )

    run_db(seed_standard_candidates())
    yield
    # Leave the database clean: the local docker PostgreSQL doubles as the
    # manual web-testing database, and leftover SEED rows surface as fake
    # "Seed premise" stores / seed foods in the served API.
    run_db(cleanup_standard_candidates())


@pytest.fixture(scope="session", autouse=True)
def _neutralize_week_floors_in_fixture_worlds(request):
    """2026-09-16 per-food weekly floors (week_floors.csv) are curated for
    the REAL 202-food catalogue. The solver unit-test worlds (pilot
    load_foods() CSV and make_food synthetics) reuse SF-prefixed ids with
    completely different identities (pilot SF002 = chicken egg vs real
    SF002 = beef), so the curated rows would apply arbitrary floors to
    those fixture worlds and couple every future CSV edit to dozens of
    unrelated mechanic tests. Neutralize the per-food lookup suite-wide
    (session scope, so module-scoped plan fixtures set up before any
    function-scoped monkeypatch are covered too); fixture worlds keep the
    household-size table floor they were calibrated under.
    tests/test_week_floors.py re-enables the real lookup for itself - it
    tests the real table."""
    import packages.optimizer.wisebasket_optimizer.portions as portions

    original = portions.solo_week_floor_g
    portions.solo_week_floor_g = lambda food_id: None
    yield
    portions.solo_week_floor_g = original


# ---------------------------------------------------------------------------
# Epic 5 curated recipe fixture (shared by tests/epic5, test_recipe_sets and
# any other module that needs a deterministic recipe catalogue).
#
# Migration o7p8q9r0s1t2 removed the three original seed recipes from the
# catalogue, and the local ns_rebuild database additionally carries the
# collected 35-recipe W8 dataset (environment asset). Tests that pin recipe
# suggestions / seed semantics were written for an empty catalogue plus
# additive fixtures and are polluted by that real data. `curated_recipes`
# therefore snapshots all three recipe tables, wipes them, installs the three
# curated fixture recipes, and restores the snapshot on teardown - so the
# tests are deterministic on both an empty (CI-fresh) and a populated local
# database. canonical_food_id values are the current 201-namespace IDs (the
# old 72-space IDs collide with different foods and must never be used).
# ---------------------------------------------------------------------------

_CURATED_RECIPE_ROWS = (
    {"recipe_id": "chicken-kangkung-stir-fry", "name": "Chicken & Kangkung Stir-fry", "description": "A quick stir-fry that makes practical use of chicken, kangkung and rice.", "active": True, "base_servings": 2},
    {"recipe_id": "egg-fried-rice", "name": "Egg Fried Rice", "description": "A simple fried-rice meal using eggs and rice.", "active": True, "base_servings": 2},
    {"recipe_id": "tofu-kangkung-stir-fry", "name": "Tofu & Kangkung Stir-fry", "description": "A simple vegetable-forward tofu stir-fry.", "active": True, "base_servings": 2},
)

_CURATED_INGREDIENT_ROWS = (
    {"recipe_id": "chicken-kangkung-stir-fry", "canonical_food_id": "SF006", "required": True, "base_quantity_g": 300, "display_order": 1},
    {"recipe_id": "chicken-kangkung-stir-fry", "canonical_food_id": "SF074", "required": True, "base_quantity_g": 200, "display_order": 2},
    {"recipe_id": "chicken-kangkung-stir-fry", "canonical_food_id": "SF110", "required": True, "base_quantity_g": 160, "display_order": 3},
    {"recipe_id": "chicken-kangkung-stir-fry", "canonical_food_id": "SF056", "required": False, "base_quantity_g": None, "display_order": 4},
    {"recipe_id": "chicken-kangkung-stir-fry", "canonical_food_id": "SF069", "required": False, "base_quantity_g": None, "display_order": 5},
    {"recipe_id": "egg-fried-rice", "canonical_food_id": "SF018", "required": True, "base_quantity_g": 100, "display_order": 1},
    {"recipe_id": "egg-fried-rice", "canonical_food_id": "SF110", "required": True, "base_quantity_g": 160, "display_order": 2},
    {"recipe_id": "egg-fried-rice", "canonical_food_id": "SF056", "required": False, "base_quantity_g": None, "display_order": 3},
    {"recipe_id": "egg-fried-rice", "canonical_food_id": "SF077", "required": False, "base_quantity_g": None, "display_order": 4},
    {"recipe_id": "tofu-kangkung-stir-fry", "canonical_food_id": "SF107", "required": True, "base_quantity_g": 300, "display_order": 1},
    {"recipe_id": "tofu-kangkung-stir-fry", "canonical_food_id": "SF074", "required": True, "base_quantity_g": 200, "display_order": 2},
    {"recipe_id": "tofu-kangkung-stir-fry", "canonical_food_id": "SF056", "required": False, "base_quantity_g": None, "display_order": 3},
    {"recipe_id": "tofu-kangkung-stir-fry", "canonical_food_id": "SF069", "required": False, "base_quantity_g": None, "display_order": 4},
)

_CURATED_STEP_ROWS = (
    {"recipe_id": "chicken-kangkung-stir-fry", "step_number": 1, "instruction": "Wash the chicken and kangkung."},
    {"recipe_id": "chicken-kangkung-stir-fry", "step_number": 2, "instruction": "Stir-fry chicken until it is cooked through."},
    {"recipe_id": "chicken-kangkung-stir-fry", "step_number": 3, "instruction": "Add kangkung and any preferred seasoning, then stir-fry for 2 to 3 minutes."},
    {"recipe_id": "chicken-kangkung-stir-fry", "step_number": 4, "instruction": "Serve with rice."},
    {"recipe_id": "egg-fried-rice", "step_number": 1, "instruction": "Scramble the eggs in a hot pan."},
    {"recipe_id": "egg-fried-rice", "step_number": 2, "instruction": "Add rice and stir-fry until heated through."},
    {"recipe_id": "egg-fried-rice", "step_number": 3, "instruction": "Add any preferred vegetables or seasoning, then serve."},
    {"recipe_id": "tofu-kangkung-stir-fry", "step_number": 1, "instruction": "Pan-fry tofu until lightly golden."},
    {"recipe_id": "tofu-kangkung-stir-fry", "step_number": 2, "instruction": "Add kangkung, then stir-fry until tender."},
    {"recipe_id": "tofu-kangkung-stir-fry", "step_number": 3, "instruction": "Add any preferred vegetables or seasoning and serve."},
)


@pytest.fixture(scope="module")
def curated_recipes_world():
    """Deterministic Epic 5 recipe world for any database state.

    Snapshot the three recipe tables, wipe them, install the three curated
    fixture recipes, and restore the snapshot afterwards (module scope, so
    sequential/concurrent file runs each get their own setup/teardown).

    Named uniquely (NOT `curated_recipes`): tests/epic5/conftest.py defines
    a same-named install-only fixture for the epic5 package, and a pytest 8.4
    non-package collection quirk can put BOTH defs in one node's fixture
    chain with the nearer (install-only) one winning - the deterministic
    wipe fixture was silently bypassed and the real 35-recipe collection
    leaked into boost counts (2026-09-17, caught by the full suite after the
    develop merge). Unique name = no shadowing, whatever the chain does.
    """
    from services.api.app.db import (
        AsyncSessionLocal,
        RecipeCatalog,
        RecipeCatalogIngredient,
        RecipeCookingStep,
    )
    from tests.w9_recipe_fixtures import (
        delete_all_recipes,
        restore_recipes,
        run_db,
        snapshot_all_recipes,
    )

    async def setup():
        async with AsyncSessionLocal() as db:
            snapshot = await snapshot_all_recipes(db)
            await delete_all_recipes(db)
            db.add_all(RecipeCatalog(**row) for row in _CURATED_RECIPE_ROWS)
            db.add_all(RecipeCatalogIngredient(**row) for row in _CURATED_INGREDIENT_ROWS)
            db.add_all(RecipeCookingStep(**row) for row in _CURATED_STEP_ROWS)
            await db.commit()
            return snapshot

    async def teardown(snapshot):
        async with AsyncSessionLocal() as db:
            await delete_all_recipes(db)
            await restore_recipes(db, snapshot)

    snapshot = run_db(setup())
    yield
    run_db(teardown(snapshot))

