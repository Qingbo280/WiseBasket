"""Deterministic retailer-abbreviation expansion for receipt OCR labels.

Malaysian grocery receipts abbreviate heavily (``AUS CH OY BL GF`` =
Australian Chilled Oyster Blade). This module expands known abbreviation
tokens into full catalogue-vocabulary words using a curated CSV
(``data/abbreviations.csv``) so the fuzzy matcher in
``receipt_matching`` can reach exact/near-exact alias scores.

Design rules (fail-closed, no hallucination):
- Only tokens present in the CSV are ever changed; unknown tokens are kept
  verbatim (e.g. ``GF`` stays ``GF``).
- CSV rows with an EMPTY expansion are category prefixes (SAYUR/BUAH) or
  glued units (KG/G/L/ML) that carry no identity; they are dropped ONLY when
  at least one other token survives, so a lone ``SAYUR`` is never expanded
  into nothing.
- Glued OCR tokens (``BERAS5KG``, ``TELURA10BIJI``) are split at
  letter<->digit boundaries before expansion so unit/size tokens match.
- Pure-numeric size/count tokens (``5``, ``10``, ``3``) are dropped like
  units: quantities and units are structurally parsed into separate receipt
  fields, so a number glued into the NAME line is packaging noise. Same
  guard: a label must never expand into nothing.
- When no token changed, ``expand_receipt_label`` returns None: callers
  should leave ``expanded_name`` unset rather than echo the raw label.
"""
from __future__ import annotations

import csv
import re
from functools import lru_cache
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parent / "data" / "abbreviations.csv"

# Split glued tokens: letters next to digits are separate receipt tokens
# ("BERAS5KG" -> "BERAS 5KG"). Compact (space-free) normalisation used by the
# matcher is unaffected, so this can only add token-level signal.
_GLUE_BOUNDARY = re.compile(r"(?<=[A-Za-z])(?=\d)|(?<=\d)(?=[A-Za-z])")
_TOKEN = re.compile(r"[A-Za-z]+|\d+(?:\.\d+)?")
# Pure-numeric size/count token ("5" in "BERAS5KG"): packaging noise, dropped
# under the same never-expand-into-nothing guard as the CSV drop-tokens.
_NUMERIC_SIZE = re.compile(r"\d+(?:\.\d+)?")

_HEADER = ("token", "expansion", "note")


@lru_cache(maxsize=1)
def _dictionary() -> dict[str, str]:
    """token(lower) -> expansion ('' = drop). Comment/blank lines skipped."""
    table: dict[str, str] = {}
    with DATA_PATH.open(encoding="utf-8", newline="") as handle:
        for row in csv.reader(handle):
            if not row or row[0].strip().startswith("#"):
                continue
            token = row[0].strip().lower()
            if not token or token in {h.lower() for h in _HEADER}:
                continue
            expansion = row[1].strip() if len(row) > 1 else ""
            table[token] = expansion
    return table


def expand_receipt_label(name_raw: str) -> str | None:
    """Deterministically expand a receipt label; None when nothing changed.

    >>> expand_receipt_label("AUS CH OY BL GF")
    'Australian Chilled Oyster Blade GF'
    >>> expand_receipt_label("SAYUR KANGKUNG")
    'Kangkung'
    >>> expand_receipt_label("SAYUR") is None
    True
    """
    text = " ".join(str(name_raw or "").split())
    if not text:
        return None
    text = _GLUE_BOUNDARY.sub(" ", text)
    dictionary = _dictionary()
    tokens = _TOKEN.findall(text)
    if not tokens:
        return None

    changed = False
    kept: list[str] = []
    for token in tokens:
        key = token.lower()
        if _NUMERIC_SIZE.fullmatch(token):
            # Size/count glued into the name line: qty/unit are separate
            # receipt fields, so the number carries no identity. Drop it
            # (guard below refuses labels that would expand into nothing).
            changed = True
            continue
        if key in dictionary:
            expansion = dictionary[key]
            if expansion:
                kept.append(expansion)
            # drop-token (empty expansion): skip, guard below restores if lone
            changed = True
        else:
            kept.append(token)
    if not kept:
        # All tokens were drop-tokens: refuse to expand into nothing.
        return None
    if not changed:
        return None
    return " ".join(kept)
