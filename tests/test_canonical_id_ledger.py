"""Canonical food-ID ledger, allocation guard, and identity-repair regression
tests.

Locks the three mechanically-proven repair identities (SF022/SF024/SF025),
proves the ledger validator's fail-closed behaviour on realistic collision/
reuse cases (using representative synthetic examples, not all 24 real
collisions -- the mechanism is what's being proven, not an exhaustive replay
of the audit), and proves the corrective migration itself fails closed on an
unrecognised third identity.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import select, text

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import check_canonical_id  # noqa: E402
import validate_canonical_id_ledger as ledger_mod  # noqa: E402

from services.api.app.db import AsyncSessionLocal, CanonicalFood  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS_DIR = REPO_ROOT / "migrations" / "versions"
CORRECTION_MIGRATION = MIGRATIONS_DIR / "e7a2c9f04b18_correct_sf022_sf024_sf025_bootstrap_identity.py"


def _load_correction_module():
    import importlib.util

    spec = importlib.util.spec_from_file_location("_correction_migration", CORRECTION_MIGRATION)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Section 14: identity regression -- lock the corrected identities
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sf022_sf024_sf025_authoritative_identity_locked():
    """Fails if someone later changes SF024 mackerel -> pork (or similar)
    without an explicit governed ledger change.

    Post-rebuild (2026-09) these IDs carry the Data-team 201-namespace
    identities; the pre-rebuild stale/correct pair (apple/white bread,
    pork loin/indian mackerel) was retired by the namespace rebuild and
    lives in the ledger as RETIRED rows + the e7a2c9f04b18 history.
    """
    expected = {
        "SF022": ("white prawn", "udang putih"),
        "SF023": ("red snapper", "ikan jenahak / ikan merah"),
        "SF024": ("spanish mackerel", "ikan tenggiri"),
        "SF025": ("indian mackerel", "ikan kembung"),
    }
    async with AsyncSessionLocal() as db:
        rows = (
            await db.execute(
                select(CanonicalFood).where(CanonicalFood.canonical_food_id.in_(expected))
            )
        ).scalars().all()
    by_id = {r.canonical_food_id: r for r in rows}
    assert set(by_id) == set(expected)
    for fid, (name, name_ms) in expected.items():
        assert by_id[fid].canonical_name == name, f"{fid} name drifted"
        assert by_id[fid].canonical_name_ms == name_ms, f"{fid} Malay name drifted"


@pytest.mark.asyncio
async def test_full_active_ledger_matches_live_database():
    """Every ACTIVE ledger row's identity must match the live database
    exactly (name), and every ACTIVE canonical_food row in the live
    database must appear in the ledger."""
    ledger = ledger_mod.load_ledger()
    active_ledger = {fid: e for fid, e in ledger.items() if e["status"] == "ACTIVE"}

    async with AsyncSessionLocal() as db:
        rows = (await db.execute(select(CanonicalFood).where(CanonicalFood.status == "ACTIVE"))).scalars().all()

    # Restrict to real "SFxxx" ids -- the test suite's own SEED0xx/PRVTEST/etc.
    # fixtures are not part of the canonical-ID authority this ledger governs.
    sf_id_pattern = ledger_mod.SF_ID_PATTERN
    rows = [r for r in rows if sf_id_pattern.match(r.canonical_food_id)]
    db_ids = {r.canonical_food_id for r in rows}
    ledger_ids = set(active_ledger)

    # every migration-created ACTIVE food must be represented in the ledger
    missing_from_ledger = db_ids - ledger_ids
    assert not missing_from_ledger, f"ACTIVE in DB but absent from ledger: {missing_from_ledger}"

    for row in rows:
        entry = active_ledger.get(row.canonical_food_id)
        if entry is None:
            continue
        assert entry["name"].lower().split(" (")[0] == row.canonical_name.lower().split(" (")[0], (
            f"{row.canonical_food_id}: ledger says {entry['name']!r}, DB says {row.canonical_name!r}"
        )


# ---------------------------------------------------------------------------
# Section 15/16: collision + retired/reserved reuse rejection (mechanism-level,
# using representative synthetic ledgers rather than replaying all 24 real
# collisions -- the audit already proved the real ones exist).
# ---------------------------------------------------------------------------

def _write_ledger(tmp_path: Path, rows: list[dict]) -> Path:
    import csv

    path = tmp_path / "ledger.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["canonical_food_id", "canonical_name", "canonical_name_ms", "status", "note"])
        w.writeheader()
        for r in rows:
            w.writerow({"canonical_name_ms": "", "note": "", **r})
    return path


def _write_migration(tmp_path: Path, filename: str, body: str) -> Path:
    path = tmp_path / filename
    path.write_text(body, encoding="utf-8")
    return path


def test_develop_style_collision_is_rejected():
    """Representative collision case: a real ACTIVE id (matching this
    project's own current SF039 = wheat flour) is proposed by a hypothetical
    migration under a materially different identity (develop's real
    SF039 = 'wet yellow noodles') -- must be rejected."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        migrations_dir = tmp / "migrations"
        migrations_dir.mkdir()
        ledger_path = _write_ledger(tmp, [
            {"canonical_food_id": "SF039", "canonical_name": "wheat flour", "status": "ACTIVE"},
        ])
        _write_migration(migrations_dir, "conflicting.py", (
            'op.bulk_insert(t, [{"canonical_food_id": "SF039", '
            '"canonical_name": "wet yellow noodles", "canonical_name_ms": "mi kuning basah", '
            '"category": "carbohydrate", "status": "ACTIVE"}])\n'
        ))
        violations = ledger_mod.validate(ledger_path=ledger_path, migrations_dir=migrations_dir)
    assert any("ACTIVE_ID_IDENTITY_MISMATCH" in v and "SF039" in v for v in violations)


def test_retired_id_reuse_is_rejected():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        migrations_dir = tmp / "migrations"
        migrations_dir.mkdir()
        ledger_path = _write_ledger(tmp, [
            {"canonical_food_id": "SF054", "canonical_name": "", "status": "RETIRED",
             "note": "retired, must not be reused"},
        ])
        _write_migration(migrations_dir, "reuse.py", (
            'op.bulk_insert(t, [{"canonical_food_id": "SF054", '
            '"canonical_name": "cucumber", "canonical_name_ms": "timun", '
            '"category": "vegetables", "status": "ACTIVE"}])\n'
        ))
        violations = ledger_mod.validate(ledger_path=ledger_path, migrations_dir=migrations_dir)
    assert any("RETIRED_OR_RESERVED_ID_REUSED" in v and "SF054" in v for v in violations)


def test_reserved_id_reuse_is_rejected():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        migrations_dir = tmp / "migrations"
        migrations_dir.mkdir()
        ledger_path = _write_ledger(tmp, [
            {"canonical_food_id": "SF055", "canonical_name": "", "status": "RESERVED",
             "note": "claimed by develop for lime"},
        ])
        _write_migration(migrations_dir, "reuse.py", (
            'op.bulk_insert(t, [{"canonical_food_id": "SF055", '
            '"canonical_name": "broccoli", "canonical_name_ms": "brokoli", '
            '"category": "vegetables", "status": "ACTIVE"}])\n'
        ))
        violations = ledger_mod.validate(ledger_path=ledger_path, migrations_dir=migrations_dir)
    assert any("RETIRED_OR_RESERVED_ID_REUSED" in v and "SF055" in v for v in violations)


def test_check_canonical_id_reports_each_status(tmp_path, monkeypatch):
    ledger_path = _write_ledger(tmp_path, [
        {"canonical_food_id": "SF039", "canonical_name": "wheat flour", "status": "ACTIVE"},
        {"canonical_food_id": "SF054", "canonical_name": "", "status": "RETIRED"},
        {"canonical_food_id": "SF055", "canonical_name": "", "status": "RESERVED"},
    ])
    ledger = ledger_mod.load_ledger(ledger_path)
    assert check_canonical_id.check("SF073", ledger) == "AVAILABLE"
    assert check_canonical_id.check("SF039", ledger) == "ACTIVE"
    assert check_canonical_id.check("SF054", ledger) == "RETIRED"
    assert check_canonical_id.check("SF055", ledger) == "RESERVED"


def test_real_ledger_has_no_structural_violations():
    """The actual, real committed ledger must itself be well-formed."""
    ledger = ledger_mod.load_ledger()  # raises LedgerError on structural problems
    assert len(ledger) > 0
    statuses = {e["status"] for e in ledger.values()}
    assert statuses <= {"ACTIVE", "RETIRED", "RESERVED"}


def test_real_ledger_matches_real_migrations():
    """The actual committed ledger, checked against the actual committed
    migrations -- this is the exact CI gate (Section 21)."""
    violations = ledger_mod.validate()
    assert violations == [], f"Unexpected ledger/migration violations: {violations}"


# ---------------------------------------------------------------------------
# Section 19: adversarial migration test -- unexpected third identity must
# fail closed, not be silently overwritten.
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_correction_fails_closed_on_unexpected_identity():
    mod = _load_correction_module()
    async with AsyncSessionLocal() as db:
        # Mutate SF022 to a third, unrecognised identity that is neither the
        # known-stale ('apple') nor known-correct ('white bread') value.
        await db.execute(
            text("update canonical_food set canonical_name = 'SOMETHING ELSE ENTIRELY' "
                 "where canonical_food_id = 'SF022'")
        )
        await db.commit()

        raw_conn = await db.connection()

        with pytest.raises(RuntimeError, match="UNEXPECTED_IDENTITY"):
            await raw_conn.run_sync(lambda sync_conn: mod.apply_corrections(sync_conn))

        # Roll back our own test mutation regardless of outcome.
        await db.rollback()
        await db.execute(
            text("update canonical_food set canonical_name = 'apple', "
                 "canonical_name_ms = 'epal' where canonical_food_id = 'SF022' "
                 "and canonical_name = 'SOMETHING ELSE ENTIRELY'")
        )
        # Restore to the real, post-rebuild value for the rest of the suite.
        await db.execute(
            text("update canonical_food set canonical_name = 'white prawn', "
                 "canonical_name_ms = 'udang putih' where canonical_food_id = 'SF022'")
        )
        await db.commit()


@pytest.mark.asyncio
async def test_correction_is_idempotent_noop_on_already_correct_row():
    """Applying the correction again to an already-correct database must be
    a safe no-op -- proves the 'already-correct deployed database' path."""
    mod = _load_correction_module()
    async with AsyncSessionLocal() as db:
        raw_conn = await db.connection()
        # SF022/024/025 carry the post-rebuild 201-namespace identities on
        # this database -- applying the pre-rebuild correction again must be
        # a governed no-op (no raise, no rename).
        await raw_conn.run_sync(lambda sync_conn: mod.apply_corrections(sync_conn))
        row = (
            await db.execute(
                text("select canonical_name from canonical_food where canonical_food_id = 'SF024'")
            )
        ).fetchone()
    assert row[0] == "spanish mackerel"
