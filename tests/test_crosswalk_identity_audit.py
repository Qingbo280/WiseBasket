"""Crosswalk identity-audit regression tests.

Locks the fail-closed tripwire that caught the SF035-SF053 generator
misalignment (NO_PORK -> 'red tilapia') in September 2026: the real crosswalk
must always pass, and synthetic identity drift / un-adjudicated weak pairs /
target tampering must always fail.
"""
from __future__ import annotations

import csv
import json
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import audit_crosswalk_identity as audit_mod  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "migrations" / "data"


def _load() -> tuple[dict, dict, list]:
    cw = json.loads((DATA_DIR / "crosswalk_v2.json").read_text(encoding="utf-8"))
    new = {f["canonical_food_id"]: f for f in json.loads((DATA_DIR / "new_canonical_foods_201.json").read_text(encoding="utf-8"))}
    old = audit_mod.load_old_identities()
    return cw, new, old


def _write_json(tmp_path: Path, name: str, payload) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def test_real_crosswalk_passes_identity_audit():
    assert audit_mod.audit() == []


def test_wrong_pair_fails_closed(tmp_path, monkeypatch):
    """The exact 2026-09-09 failure shape: pork silently mapped to tilapia."""
    cw, new, _old = _load()
    for r in cw["rows"]:
        if r["old_canonical_food_id"] == "SF041":
            r["new_canonical_food_id"] = "SF035"  # red tilapia
            r["match_status"] = "EXACT_IDENTITY_MATCH"
    monkeypatch.setattr(audit_mod, "LEDGER_PATH", REPO_ROOT / "data" / "canonical_food_identity_ledger.csv")
    cw_path = _write_json(tmp_path, "crosswalk_v2.json", cw)
    violations = audit_mod.audit(crosswalk_path=cw_path)
    assert any("SF041" in v and "IDENTITY_WRONG" in v for v in violations)


def test_unadjudicated_weak_pair_fails(tmp_path, monkeypatch):
    cw, new, _old = _load()
    for r in cw["rows"]:
        if r["old_canonical_food_id"] == "SF026":  # onion -- an exact pair today
            r["new_canonical_food_id"] = "SF127"   # peanuts: partial token bait
            r["match_status"] = "EXACT_IDENTITY_MATCH"
    monkeypatch.setattr(audit_mod, "LEDGER_PATH", REPO_ROOT / "data" / "canonical_food_identity_ledger.csv")
    cw_path = _write_json(tmp_path, "crosswalk_v2.json", cw)
    violations = audit_mod.audit(crosswalk_path=cw_path)
    assert violations, "un-adjudicated identity drift must not pass"


def test_adjudicated_pairs_are_explicitly_listed():
    """Every non-exact pair in the real crosswalk must appear in ADJUDICATED_WEAK
    -- if the set is emptied or trimmed, the audit must fail loudly."""
    cw, new, old = _load()
    assert audit_mod.ADJUDICATED_WEAK, "adjudication set must not be empty"
    for r in cw["rows"]:
        old_id = r["old_canonical_food_id"]
        if old_id not in old or r["match_status"] == "EXCLUDED_CATALOGUE_GAP":
            continue
        tgt = r.get("new_canonical_food_id")
        ot = audit_mod.norm_tokens(old[old_id])
        nt = audit_mod.norm_tokens(new[tgt]["canonical_name"])
        exact = (not ot - nt) and (not nt - ot)
        subset = (ot & nt) == ot or (ot & nt) == nt
        if not exact and not subset:
            assert audit_mod.ADJUDICATED_WEAK.get(old_id) == tgt, (
                f"{old_id}->{tgt} is non-exact but missing from ADJUDICATED_WEAK"
            )
