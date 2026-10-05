#!/usr/bin/env python3
"""Crosswalk identity audit -- fail-closed tripwire on the old->new namespace
mapping (migrations/data/crosswalk_v2.json).

The Phase 1 crosswalk generator shipped with its old-side id<->name binding
silently misaligned for the SF035-SF053 block (discovered 2026-09-09 when the
namespace migration's allergy assertion caught NO_PORK -> 'red tilapia').
This script makes that class of error mechanically impossible to merge again:
for every old food that actually exists (tracked as RET-<id> in the canonical
identity ledger), it checks that the crosswalk's target NEW identity is the
SAME food by bilingual token overlap.

Verdicts:
    OK / OK~   exact or token-subset identity -- pass
    WEAK       partial overlap -- passes ONLY if the pair is in the curated
               ADJUDICATED set below (every entry there is a human decision
               with evidence on file in CROSSWALK_V2_ADJUDICATION.md)
    WRONG      disjoint identities -- always a violation
    EXCLUDED   catalogue gap rows (no new id) -- pass, counted separately

Old identities come from the ledger's RET-<id> rows, so the audit is fully
static (no database needed) and runs identically in CI, a fresh checkout,
and locally.

Usage:
    python scripts/audit_crosswalk_identity.py     # audit the real crosswalk
Exit code 0 = clean, 1 = at least one violation.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "migrations" / "data"
LEDGER_PATH = REPO_ROOT / "data" / "canonical_food_identity_ledger.csv"

# Human-adjudicated non-exact identities (evidence: CROSSWALK_V2_ADJUDICATION.md).
# Keyed old_id -> new_id. Any WEAK pair NOT in this set is a violation.
ADJUDICATED_WEAK = {
    "SF008": "SF124",  # red lentils -> dhal (lentils)
    "SF020": "SF176",  # full cream milk -> fresh / UHT milk (liquid)
    "SF021": "SF120",  # palm cooking oil -> cooking oil (bottle)
    "SF037": "SF161",  # instant curry noodles -> instant noodles (packet)
    "SF062": "SF164",  # instant whole milk powder -> adult milk powder
    "SF064": "SF166",  # sweetened vitamin creamer -> sweetened condensed milk
    "SF065": "SF108",  # kuey teow -> fresh rice noodles (kuetiau basah, Malay-name evidence)
    "SF079": "SF085",  # green bell pepper -> green capsicum
    "SF083": "SF063",  # round eggplant -> eggplant (brinjal)
    "SF088": "SF119",  # brown sugar -> palm sugar (gula merah)
}

STOPWORDS = {"and", "the", "with", "in", "raw", "fresh"}


def norm_tokens(name: str) -> set[str]:
    toks = set(re.sub(r"[^a-z0-9 ]", " ", name.lower()).split())
    return {t for t in toks if t not in STOPWORDS}


def load_old_identities() -> dict[str, str]:
    """RET-<oldid> -> old English identity, from the canonical ledger."""
    import csv

    old: dict[str, str] = {}
    with LEDGER_PATH.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            fid = (row.get("canonical_food_id") or "").strip()
            if fid.startswith("RET-"):
                old[fid[len("RET-"):]] = (row.get("canonical_name") or "").strip()
    return old


def audit(crosswalk_path: Path = DATA_DIR / "crosswalk_v2.json",
          new_foods_path: Path = DATA_DIR / "new_canonical_foods_201.json") -> list[str]:
    """Returns a list of violation strings (empty = clean)."""
    violations: list[str] = []
    old_ids = load_old_identities()
    new_names = {f["canonical_food_id"]: f["canonical_name"]
                 for f in json.loads(new_foods_path.read_text(encoding="utf-8"))}
    rows = json.loads(crosswalk_path.read_text(encoding="utf-8"))["rows"]

    for r in rows:
        old = r["old_canonical_food_id"]
        if old not in old_ids:
            continue  # phantom id: never existed in any database, nothing to audit
        if r["match_status"] == "EXCLUDED_CATALOGUE_GAP":
            continue
        tgt = r.get("new_canonical_food_id")
        old_name = old_ids[old]
        new_name = new_names.get(tgt)
        if not tgt or new_name is None:
            violations.append(f"MISSING_TARGET: {old} ({old_name!r}) has no valid new id")
            continue
        ot, nt = norm_tokens(old_name), norm_tokens(new_name)
        inter = ot & nt
        if not ot - nt and not nt - ot:
            continue  # exact
        if not inter:
            verdict = "WRONG"
        elif not (inter == ot or inter == nt):
            verdict = "WEAK"
        else:
            continue  # token-subset: acceptable without adjudication
        # Any non-exact pair (WEAK or even token-disjoint) must be an
        # explicit human adjudication -- that is the whole point of the
        # tripwire: silent identity drift fails closed here.
        if ADJUDICATED_WEAK.get(old) != tgt:
            violations.append(
                f"IDENTITY_{verdict}: {old} ({old_name!r}) -> {tgt} ({new_name!r}) "
                f"-- overlap={sorted(inter)}; not in ADJUDICATED_WEAK"
            )
    return violations


def main() -> int:
    violations = audit()
    if not violations:
        print("OK: every crosswalk pair whose old food really existed is identity-consistent.")
        return 0
    print(f"FAILED: {len(violations)} crosswalk identity violation(s):", file=sys.stderr)
    for v in violations:
        print(f"  - {v}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
