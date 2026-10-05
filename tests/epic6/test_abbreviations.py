# Epic 6 deterministic abbreviation-dictionary tests (no DB, no inference).
from __future__ import annotations

import csv

import pytest

from packages.receipt_matching import expand_receipt_label
from packages.receipt_matching import match_text_candidates
from packages.receipt_matching.abbreviations import DATA_PATH, _dictionary


def test_dictionary_csv_has_no_identity_or_shadow_rows():
    """Every row must add real signal: expansion must differ beyond case."""
    with DATA_PATH.open(encoding="utf-8", newline="") as handle:
        for row in csv.reader(handle):
            if not row or row[0].strip().startswith("#"):
                continue
            token, expansion = row[0].strip(), row[1].strip()
            assert token.lower() != expansion.lower(), (
                f"identity row wastes lookups: {token!r} -> {expansion!r} "
                "(case-insensitive matching already covers this)"
            )


def test_dictionary_is_loaded_from_package_data():
    table = _dictionary()
    assert table["ch"] == "Chilled"
    assert table["sayur"] == ""  # drop-token


def test_expands_retailer_abbreviation_line():
    assert expand_receipt_label("AUS CH OY BL GF") == "Australian Chilled Oyster Blade GF"


def test_unknown_tokens_are_kept_verbatim():
    """Fail-closed: GF is not in the dictionary and must survive unchanged."""
    out = expand_receipt_label("CH GF")
    assert out == "Chilled GF"


def test_category_prefix_dropped_when_other_tokens_remain():
    assert expand_receipt_label("SAYUR KANGKUNG") == "KANGKUNG"
    assert expand_receipt_label("BUAH NAGA") == "NAGA"


@pytest.mark.parametrize("lone", ["SAYUR", "BUAH", "sayur buah"])
def test_drop_tokens_never_expand_into_nothing(lone):
    assert expand_receipt_label(lone) is None


def test_glued_letter_digit_tokens_are_split_before_dictionary_lookup():
    """Glued tokens split first; numbers and glued units drop so the staple
    name that survives reaches an exact catalogue alias (BERAS -> beras)."""
    assert expand_receipt_label("BERAS5KG") == "BERAS"
    assert expand_receipt_label("BERAS 10 KG") == "BERAS"
    assert expand_receipt_label("CH5KG") == "Chilled"


def test_numeric_size_tokens_dropped_but_never_into_nothing():
    """Numbers glued in the name line are packaging noise (qty/unit are
    separate receipt fields); the never-expand-into-nothing guard still
    holds when digits are the only surviving content."""
    assert expand_receipt_label("TELURA10BIJI") == "TELURA BIJI"
    assert expand_receipt_label("NAGA5") == "NAGA"
    assert expand_receipt_label("5") is None
    assert expand_receipt_label("5KG") is None
    assert expand_receipt_label("5 KG") is None


def test_variant_spellings_map_to_catalogue_vocabulary():
    assert expand_receipt_label("TELOR") == "Telur"
    assert expand_receipt_label("KANGKONG") == "Kangkung"
    assert expand_receipt_label("TEMPEH") == "Tempe"


def test_no_expansion_returns_none():
    """Nothing changed -> None so callers leave expanded_name unset."""
    assert expand_receipt_label("KANGKUNG") is None  # full word, not a variant
    assert expand_receipt_label("CH CHICKEN") == "Chilled CHICKEN"
    assert expand_receipt_label("") is None
    assert expand_receipt_label("   ") is None


def test_expansion_improves_fuzzy_ranking_against_catalogue_aliases():
    """The 0.88 auto-gate with the 0.85 subset cap rarely auto-confirms, so the
    dictionary's win is ranking: the right food becomes top-1 with a higher
    score, i.e. one tap in the confirmation UI instead of a deep list."""
    aliases = [
        ("SF-BEEF", "oyster blade beef"),
        ("SF-PORK", "pork belly"),
    ]
    _, _, before_cands = match_text_candidates(["AUS CH OY BL"], aliases)
    _, _, after_cands = match_text_candidates(
        ["AUS CH OY BL", expand_receipt_label("AUS CH OY BL")], aliases
    )
    assert after_cands[0][0] == "SF-BEEF"
    assert after_cands[0][1] > before_cands[0][1]


def test_expansion_does_not_break_existing_exact_match():
    aliases = [("SF-KANGKUNG", "kangkung")]
    food_id, score, _ = match_text_candidates(
        ["SAYUR KANGKUNG", expand_receipt_label("SAYUR KANGKUNG")], aliases
    )
    assert food_id == "SF-KANGKUNG"
    assert score == 1.0


def test_size_token_expansion_reaches_auto_match_gate_on_rice():
    """End-to-end for the MYDIN staple line: BERAS5KG expands to BERAS, which
    exact-matches the catalogue Malay alias 'beras' at 1.0 - above the 0.88
    auto-gate, so the line auto-confirms instead of waiting for a manual pick.
    """
    aliases = [("SF110", "rice"), ("SF110-MS", "beras"), ("SF065", "kuey teow")]
    expanded = expand_receipt_label("BERAS5KG")
    assert expanded == "BERAS"
    food_id, score, cands = match_text_candidates(["BERAS5KG", expanded], aliases)
    assert food_id == "SF110-MS"
    assert score == 1.0
    assert cands[0][1] == 1.0
