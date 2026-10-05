#!/usr/bin/env python3
"""Canonical food-ID ledger validator (fail-closed).

Reads data/canonical_food_identity_ledger.csv -- the ONE authoritative record
of which SF IDs are ACTIVE, RETIRED, or RESERVED -- and:

1. Validates the ledger's own internal structure (duplicates, malformed IDs,
   unsupported status values, missing identity on ACTIVE rows).
2. Cross-checks it against every canonical_food_id any migration in this
   repository ever creates: a migration must never create an ID the ledger
   marks RETIRED or RESERVED, and an ID a migration creates ACTIVE must match
   the ledger's own name for it exactly (this is the PR #81 collision this
   tool exists to prevent, made mechanical rather than tribal knowledge).

This is intentionally a static check -- it reads migration source files as
text, it does not run them. It is deliberately independent of any live/local
database, so it runs the same way in CI, in a fresh checkout, and locally.

Exit code 0 = clean. Non-zero = at least one violation (printed to stderr).

Usage:
    python scripts/validate_canonical_id_ledger.py
    python scripts/check_canonical_id.py SF073   # single-ID lookup (see that script)
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
LEDGER_PATH = REPO_ROOT / "data" / "canonical_food_identity_ledger.csv"
MIGRATIONS_DIR = REPO_ROOT / "migrations" / "versions"

VALID_STATUSES = {"ACTIVE", "RETIRED", "RESERVED"}
# Plain SF ids plus RET-SF ids: the namespace rebuild (foundation migration
# 9b1c2d3e4f50) retires every pre-rebuild identity under a RET- prefix so
# the number can never be silently mistaken for its post-rebuild meaning.
SF_ID_PATTERN = re.compile(r"^(?:RET-)?SF\d{3,}$")

# Matches both the dict-literal bulk_insert shape ("canonical_food_id": "SF054",
# "canonical_name": "cucumber", ...) and the positional-tuple raw-SQL shape
# ('SF022', 'apple', 'epal', 'carbohydrate', 'ACTIVE').
_DICT_ROW = re.compile(
    r'"canonical_food_id"\s*:\s*"(SF\d+)"\s*,\s*"canonical_name"\s*:\s*"([^"]*)"'
)
_TUPLE_ROW = re.compile(
    r"\(\s*'(SF\d+)'\s*,\s*'([^']*)'\s*,\s*'[^']*'\s*,\s*'[^']*'\s*,\s*'ACTIVE'\s*\)"
)

# Matches this repository's established shape for a fail-closed corrective
# migration's module-level CORRECTIONS list -- see
# migrations/versions/e7a2c9f04b18_correct_sf022_sf024_sf025_bootstrap_identity.py
# for the canonical example. A migration using this exact convention is
# understood to make `correct_name` (the 4th element) the FINAL authoritative
# English identity for that ID, overriding whatever any earlier seeding
# migration wrote -- deliberately independent of file/revision order, since a
# correction always wins over the value it corrects by definition.
_CORRECTION_ROW = re.compile(
    r'\(\s*"(SF\d+)"\s*,\s*"[^"]*"\s*,\s*"[^"]*"\s*,\s*"([^"]*)"\s*,\s*"[^"]*"\s*\)'
)

# A migration that performs a namespace rebuild declares its final
# authoritative identities in bundled JSON data (see LEDGER_SOURCE_JSON in
# migrations/versions/9b1c2d3e4f50_iteration_1_backend_foundation.py). These
# override everything earlier, exactly like CORRECTIONS do.
_LEDGER_SOURCE_JSON_ROW = re.compile(
    r"^LEDGER_SOURCE_JSON\s*=\s*\(([^)]*)\)", re.MULTILINE
)


class LedgerError(Exception):
    pass


def load_ledger(path: Path = LEDGER_PATH) -> dict[str, dict[str, str]]:
    """Returns {canonical_food_id: {name, name_ms, status, note}}.

    Raises LedgerError on any structural violation (A, B, E, F, G below).
    """
    if not path.exists():
        raise LedgerError(f"MISSING_LEDGER: {path} does not exist")

    ledger: dict[str, dict[str, str]] = {}
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        required_cols = {"canonical_food_id", "canonical_name", "status"}
        missing_cols = required_cols - set(reader.fieldnames or [])
        if missing_cols:
            raise LedgerError(f"MALFORMED_LEDGER: missing required column(s) {missing_cols}")

        for lineno, row in enumerate(reader, start=2):
            fid = (row.get("canonical_food_id") or "").strip()
            name = (row.get("canonical_name") or "").strip()
            name_ms = (row.get("canonical_name_ms") or "").strip()
            status = (row.get("status") or "").strip()
            note = (row.get("note") or "").strip()

            if not SF_ID_PATTERN.match(fid):
                raise LedgerError(f"MALFORMED_SF_ID: line {lineno}: {fid!r} is not a valid SF ID")

            # A. duplicate canonical_food_id entries
            if fid in ledger:
                # B. an ACTIVE ID with multiple different authoritative identities
                # (covers the general duplicate case too -- any duplicate is a failure,
                # whether or not the two rows happen to agree)
                raise LedgerError(
                    f"DUPLICATE_ID: {fid} appears more than once in the ledger "
                    f"(line {lineno}) -- existing entry: {ledger[fid]!r}"
                )

            # G. unsupported status
            if status not in VALID_STATUSES:
                raise LedgerError(
                    f"UNSUPPORTED_STATUS: {fid} (line {lineno}) has status {status!r}, "
                    f"expected one of {sorted(VALID_STATUSES)}"
                )

            # F. missing required identity for ACTIVE records
            if status == "ACTIVE" and not name:
                raise LedgerError(
                    f"MISSING_IDENTITY: {fid} (line {lineno}) is ACTIVE but has no "
                    f"canonical_name"
                )

            ledger[fid] = {"name": name, "name_ms": name_ms, "status": status, "note": note}

    return ledger


def extract_migration_seeded_ids(migrations_dir: Path = MIGRATIONS_DIR) -> dict[str, str]:
    """Best-effort static extraction of every canonical_food_id a migration
    file creates, and the English name it assigns. Not a full Python parser --
    matches the literal shapes actually used in this repository's migrations:
    dict-literal bulk inserts, positional-tuple raw SQL, CORRECTIONS lists,
    and LEDGER_SOURCE_JSON cutover data files (applied last -- a cutover is
    the final word on identity by definition)."""
    import json

    seeded: dict[str, str] = {}
    corrections: dict[str, str] = {}
    cutover: dict[str, str] = {}
    for path in sorted(migrations_dir.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        for fid, name in _DICT_ROW.findall(text):
            seeded[fid] = name
        for fid, name in _TUPLE_ROW.findall(text):
            seeded[fid] = name
        if "CORRECTIONS" in text:
            for fid, correct_name in _CORRECTION_ROW.findall(text):
                corrections[fid] = correct_name
        m = _LEDGER_SOURCE_JSON_ROW.search(text)
        if m:
            data_dir = path.parent.parent / "data"
            for raw_name in m.group(1).split(","):
                json_name = raw_name.strip().strip('"').strip("'").rstrip(",")
                if not json_name:
                    continue
                payload = json.loads((data_dir / json_name).read_text(encoding="utf-8"))
                for food in payload:
                    cutover[food["canonical_food_id"]] = food["canonical_name"]

    # Corrections always win over the value they correct, independent of file
    # order -- see the _CORRECTION_ROW docstring above. A namespace cutover
    # wins over everything: it is the last migration by definition.
    seeded.update(corrections)
    seeded.update(cutover)
    return seeded


def validate(ledger_path: Path = LEDGER_PATH, migrations_dir: Path = MIGRATIONS_DIR) -> list[str]:
    """Returns a list of violation strings (empty = clean)."""
    violations: list[str] = []

    try:
        ledger = load_ledger(ledger_path)
    except LedgerError as exc:
        return [str(exc)]

    try:
        seeded = extract_migration_seeded_ids(migrations_dir)
    except OSError as exc:
        return [f"CANNOT_READ_MIGRATIONS: {exc}"]

    for fid, seeded_name in seeded.items():
        entry = ledger.get(fid)
        if entry is None:
            violations.append(
                f"UNLEDGERED_ID: migration(s) create {fid} ({seeded_name!r}) but it does not "
                f"appear in the ledger at all -- every canonical_food_id a migration creates "
                f"must have a ledger entry (Section 9 invariant)"
            )
            continue

        # C/D. reuse of RETIRED or RESERVED IDs
        if entry["status"] in ("RETIRED", "RESERVED"):
            violations.append(
                f"RETIRED_OR_RESERVED_ID_REUSED: migration(s) create {fid} ({seeded_name!r}) "
                f"but the ledger marks it {entry['status']} -- {entry['note'] or 'no note on record'}"
            )
            continue

        # H. accidental reassignment of an existing active ID
        if entry["name"] != seeded_name:
            violations.append(
                f"ACTIVE_ID_IDENTITY_MISMATCH: migration(s) create {fid} as {seeded_name!r}, "
                f"but the ledger's authoritative identity for {fid} is {entry['name']!r}"
            )

    return violations


def main() -> int:
    violations = validate()
    if not violations:
        print(f"OK: ledger at {LEDGER_PATH} is internally consistent and matches every "
              f"migration-seeded canonical_food_id.")
        return 0
    print(f"FAILED: {len(violations)} canonical-ID ledger violation(s):", file=sys.stderr)
    for v in violations:
        print(f"  - {v}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
