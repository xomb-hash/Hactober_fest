"""
Unit tests for genomic sequence and reference validation.
Tests strict alphabet constraints, non-conversion of U <-> T, IUPAC extensions, and bounds.
"""

import pytest
from middleware.validation import (
    validate_alphabet,
    validate_sequence_input,
    validate_reference_sequence,
)


def test_dna_alphabet_valid():
    """Valid DNA sequences with standard bases should pass."""
    valid, invalids = validate_alphabet("ATCGATCG", alphabet="DNA")
    assert valid is True
    assert invalids == []

    # Lowercase should be recognized as valid standard bases
    valid_lower, invalids_lower = validate_alphabet("atcg", alphabet="DNA")
    assert valid_lower is True
    assert invalids_lower == []


def test_dna_alphabet_with_uracil_fails():
    """DNA containing Uracil (U) MUST FAIL. NEVER silently convert U <-> T."""
    valid, invalids = validate_alphabet("AUCGATCG", alphabet="DNA")
    assert valid is False
    assert "U" in invalids or "u" in invalids


def test_rna_alphabet_valid():
    """Valid RNA sequences with Uracil should pass."""
    valid, invalids = validate_alphabet("AUCGAUCG", alphabet="RNA")
    assert valid is True
    assert invalids == []


def test_rna_alphabet_with_thymine_fails():
    """RNA containing Thymine (T) MUST FAIL. NEVER silently convert U <-> T."""
    valid, invalids = validate_alphabet("ATCG", alphabet="RNA")
    assert valid is False
    assert "T" in invalids or "t" in invalids


def test_invalid_characters_detected():
    """Characters outside standard alphabet must be captured deterministically."""
    valid, invalids = validate_alphabet("ATCGXYZ123", alphabet="DNA")
    assert valid is False
    for ch in ["X", "Y", "Z", "1", "2", "3"]:
        assert ch in invalids


def test_iupac_ambiguity_codes():
    """IUPAC ambiguity codes should be rejected by default and accepted when configured."""
    # Default (allow_iupac=False): 'N', 'R', 'Y' are rejected
    valid_def, invalids_def = validate_alphabet("ATCGNRY", alphabet="DNA", allow_iupac=False)
    assert valid_def is False
    assert "N" in invalids_def
    assert "R" in invalids_def
    assert "Y" in invalids_def

    # Configured (allow_iupac=True): 'N', 'R', 'Y' are accepted
    valid_iupac, invalids_iupac = validate_alphabet("ATCGNRY", alphabet="DNA", allow_iupac=True)
    assert valid_iupac is True
    assert invalids_iupac == []


def test_empty_sequence_input():
    """Empty or whitespace-only sequence input must be rejected."""
    valid_none, err_none = validate_sequence_input(None)
    assert valid_none is False
    assert err_none == "EMPTY_SEQUENCE"

    valid_empty, err_empty = validate_sequence_input("")
    assert valid_empty is False
    assert err_empty == "EMPTY_SEQUENCE"

    valid_ws, err_ws = validate_sequence_input("   \n\t  ")
    assert valid_ws is False
    assert err_ws == "EMPTY_SEQUENCE"


def test_sequence_length_limit():
    """Excessively long sequences should exceed max length."""
    short_seq = "A" * 10
    valid_short, _ = validate_sequence_input(short_seq, max_length=20)
    assert valid_short is True

    long_seq = "A" * 50
    valid_long, err_long = validate_sequence_input(long_seq, max_length=20)
    assert valid_long is False
    assert "SEQUENCE_EXCEEDS_MAX_LENGTH" in err_long


def test_reference_sequence_validation():
    """User-supplied reference sequences must undergo rigorous validation."""
    # Valid DNA reference
    ok, err = validate_reference_sequence("ATCGATCG", alphabet="DNA")
    assert ok is True
    assert err is None

    # Valid RNA reference
    ok_rna, err_rna = validate_reference_sequence("AUCGAUCG", alphabet="RNA")
    assert ok_rna is True
    assert err_rna is None

    # Invalid characters in reference
    bad_dna, bad_err = validate_reference_sequence("ATCGZZZ", alphabet="DNA")
    assert bad_dna is False
    assert "INVALID_ALPHABET_CHARS" in bad_err

    # Empty reference
    empty_ref, empty_err = validate_reference_sequence("", alphabet="DNA")
    assert empty_ref is False
    assert empty_err == "EMPTY_SEQUENCE"
