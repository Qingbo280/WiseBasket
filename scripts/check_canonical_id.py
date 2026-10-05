#!/usr/bin/env python3
"""Check whether a proposed SF ID is safe to allocate to a new canonical food.

This is a LOOKUP only -- it never reserves or allocates anything. Actually
claiming an ID still requires an explicit ledger change (a new row in
data/canonical_food_identity_ledger.csv) in the same PR/commit that adds it,
which scripts/validate_canonical_id_ledger.py then checks.

Usage:
    python scripts/check_canonical_id.py SF073
    python scripts/check_canonical_id.py SF073 SF074 SF039   # multiple at once

Prints one of, per ID:
    AVAILABLE    -- not in the ledger at all; free to propose (still requires
                    adding a ledger entry before it can actually be used)
    ACTIVE       -- already a real, currently-served food; do not reuse
    RETIRED      -- permanently retired; must never be reused
    RESERVED     -- claimed by another workstream (see the ledger note); do
                    not reuse without resolving the conflict first
    CONFLICTED   -- the ledger itself is ambiguous/malformed for this ID; fails
                    closed rather than guessing

Exit code is 0 only if every given ID is AVAILABLE; non-zero otherwise (so
this can be used as a pre-check in scripting without parsing output).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_canonical_id_ledger import LEDGER_PATH, LedgerError, load_ledger  # noqa: E402


def check(food_id: str, ledger: dict[str, dict[str, str]] | None) -> str:
    if ledger is None:
        return "CONFLICTED"
    entry = ledger.get(food_id)
    if entry is None:
        return "AVAILABLE"
    status = entry.get("status")
    if status in ("ACTIVE", "RETIRED", "RESERVED"):
        return status
    return "CONFLICTED"


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2

    try:
        ledger = load_ledger(LEDGER_PATH)
    except LedgerError as exc:
        print(f"CONFLICTED: ledger itself is malformed -- {exc}", file=sys.stderr)
        ledger = None

    all_available = True
    for food_id in argv:
        result = check(food_id, ledger)
        note = ""
        if ledger is not None and food_id in ledger and ledger[food_id].get("note"):
            note = f" -- {ledger[food_id]['note']}"
        elif ledger is not None and food_id in ledger and ledger[food_id].get("name"):
            note = f" -- currently: {ledger[food_id]['name']}"
        print(f"{food_id}: {result}{note}")
        if result != "AVAILABLE":
            all_available = False

    return 0 if all_available else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
