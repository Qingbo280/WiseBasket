#!/usr/bin/env python3
"""Canonical ID freeze regression check.

Compares a baseline canonical_food export against a CURRENT one and fails
loudly on any MATERIAL_IDENTITY_CHANGE -- a canonical_food_id whose name (and
usually category) has silently changed to a different food between the two
snapshots. This is a real, previously-observed failure mode in a separate,
independently-evolved copy of this codebase (18 IDs were found reassigned in
that incident) -- this script is a general-purpose port of the check used to
catch it there, not a claim that the same 18 IDs, or any material change at
all, exists in THIS repository's own canonical_food data. It has not yet been
run against this repository's actual production/UAT canonical_food export
(this port did not have read access to that data), so treat it as a tool
made available for the team to run and baseline themselves, not as a
pre-verified finding about this repository.

READ-ONLY: this script only reads two CSV files and prints a report. It
never connects to any database and never writes anything. It is not wired
into pytest or CI -- run it manually against a baseline export and a current
export whenever a canonical_food data refresh happens.

Usage:
    python scripts/canonical_identity_regression_check.py \\
        --baseline path/to/baseline_canonical_food.csv \\
        --current path/to/current_canonical_food.csv
    (column names are configurable via --baseline-id-col etc.; see --help)
"""
from __future__ import annotations

import argparse
import csv
import re
import sys


def normalise(name: str) -> str:
    return re.sub(r"[^a-z ]", "", (name or "").lower()).strip()


def load(path: str, id_col: str, name_col: str, category_col: str | None) -> dict[str, dict]:
    out = {}
    with open(path, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            fid = row[id_col]
            out[fid] = {
                "name": row.get(name_col, ""),
                "category": row.get(category_col, "") if category_col else "",
            }
    return out


def check(baseline: dict[str, dict], current: dict[str, dict]) -> tuple[list[dict], list[dict], list[dict]]:
    """Returns (failures, retired, display_only_changes)."""
    failures, retired, display_only = [], [], []
    for fid, base in baseline.items():
        cur = current.get(fid)
        if cur is None:
            retired.append({"canonical_food_id": fid, "baseline_name": base["name"]})
            continue
        base_norm, cur_norm = normalise(base["name"]), normalise(cur["name"])
        if base_norm == cur_norm:
            continue  # SAME_IDENTITY, or a pure case/whitespace difference -- not a failure
        if base["category"] and cur["category"] and base["category"] != cur["category"]:
            failures.append({
                "canonical_food_id": fid, "baseline_name": base["name"], "current_name": cur["name"],
                "baseline_category": base["category"], "current_category": cur["category"],
                "severity": "MATERIAL_IDENTITY_CHANGE (name AND category both differ -- near-certain reassignment)",
            })
        else:
            failures.append({
                "canonical_food_id": fid, "baseline_name": base["name"], "current_name": cur["name"],
                "baseline_category": base["category"], "current_category": cur["category"],
                "severity": "MATERIAL_IDENTITY_CHANGE (name differs)",
            })
    return failures, retired, display_only


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--current", required=True)
    ap.add_argument("--baseline-id-col", default="canonical_food_id")
    ap.add_argument("--baseline-name-col", default="canonical_name")
    ap.add_argument("--baseline-category-col", default="category")
    ap.add_argument("--current-id-col", default="canonical_food_id")
    ap.add_argument("--current-name-col", default="canonical_name")
    ap.add_argument("--current-category-col", default="category")
    args = ap.parse_args()

    baseline = load(args.baseline, args.baseline_id_col, args.baseline_name_col, args.baseline_category_col)
    current = load(args.current, args.current_id_col, args.current_name_col, args.current_category_col)

    failures, retired, _ = check(baseline, current)

    print(f"Baseline IDs checked: {len(baseline)}")
    print(f"MATERIAL_IDENTITY_CHANGE failures: {len(failures)}")
    for f in failures:
        print(f"  FAIL {f['canonical_food_id']}: {f['baseline_name']!r} -> {f['current_name']!r}  [{f['severity']}]")
    print(f"POSSIBLY_RETIRED (in baseline, absent from current): {len(retired)}")
    for r in retired:
        print(f"  RETIRED? {r['canonical_food_id']}: {r['baseline_name']!r}")

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
