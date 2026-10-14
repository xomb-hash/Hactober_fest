"""
Unit tests for anchor verification and recovery engine.
Covers Cases A through E and integrity checks against corrupted model proposals.
"""

import pytest
from middleware.anchor_recovery import recover_with_anchors


def test_normal_verification_success():
    """All anchors and candidate quote match accurately in proper order."""
    doc = "Patient Report\nObserved sequence: ATCGATCG\nAdditional notes: None"
    res = recover_with_anchors(
        document_text=doc,
        candidate_quote="ATCGATCG",
        anchor_before="Observed sequence: ",
        anchor_after="\nAdditional notes:",
        field_type="observed_sequence",
        alphabet="DNA"
    )
    assert res.success is True
    assert res.status == "verified"
    assert res.sequence == "ATCGATCG"
    assert res.recovery_method == "exact_quote"
    assert res.anchors_verified is True
    assert res.boundaries_verified is True
    assert res.completeness_verified is True
    assert res.source_span.start == doc.find("ATCGATCG")
    assert res.source_span.end == doc.find("ATCGATCG") + 8


def test_case_a_anchor_before_wrong():
    """Case A: anchor_before is incorrect, candidate quote is exact and unique."""
    doc = "Patient Report\nObserved sequence: GCTAGCTA\nAdditional notes: Normal"
    res = recover_with_anchors(
        document_text=doc,
        candidate_quote="GCTAGCTA",
        anchor_before="Tumor DNA sequence:",  # Incorrect anchor
        anchor_after="Additional notes:",
        field_type="observed_sequence",
        alphabet="DNA"
    )
    assert res.success is True
    assert res.status == "verified"
    assert res.sequence == "GCTAGCTA"
    assert res.anchors_verified is False
    assert res.recovery_method in ["anchor_before_recovery", "exact_quote_search"]


def test_case_b_anchor_after_wrong():
    """Case B: anchor_after is incorrect, anchor_before and quote match."""
    doc = "Patient Report\nObserved sequence: GCTAGCTA\nAdditional notes: Normal"
    res = recover_with_anchors(
        document_text=doc,
        candidate_quote="GCTAGCTA",
        anchor_before="Observed sequence: ",
        anchor_after="Nonexistent Section Header",  # Incorrect anchor
        field_type="observed_sequence",
        alphabet="DNA"
    )
    assert res.success is True
    assert res.status == "verified"
    assert res.sequence == "GCTAGCTA"
    assert res.recovery_method == "anchor_after_recovery"
    assert res.anchors_verified is False


def test_case_c_both_anchors_wrong_unique_candidate():
    """Case C: Both anchors wrong, candidate quote appears once and context is compatible."""
    doc = "Report Header\nSample isolate sequence: GCTAGCTA\nFooter"
    res = recover_with_anchors(
        document_text=doc,
        candidate_quote="GCTAGCTA",
        anchor_before="Wrong Before:",
        anchor_after="Wrong After:",
        field_type="observed_sequence",
        alphabet="DNA"
    )
    assert res.success is True
    assert res.status == "verified"
    assert res.sequence == "GCTAGCTA"
    assert res.recovery_method == "exact_quote_search"
    assert res.anchors_verified is False


def test_case_c_both_anchors_wrong_conflicting_context():
    """Case C: Both anchors wrong, unique quote found but in a conflicting field (reference)."""
    doc = "Report Header\nReference sequence: GCTAGCTA\nEnd of file"
    res = recover_with_anchors(
        document_text=doc,
        candidate_quote="GCTAGCTA",
        anchor_before="Wrong Before:",
        anchor_after="Wrong After:",
        field_type="observed_sequence",  # Requesting observed, but text is reference
        alphabet="DNA"
    )
    assert res.success is False
    assert res.status == "abstained"
    assert res.error_code == "CONTEXT_FIELD_MISMATCH"


def test_case_d_candidate_quote_wrong_anchor_delimited_recovery():
    """
    Case D & Integrity Test:
    Source text has: 'Observed sequence: ATCGATCG\nAdditional notes:'
    Model proposed corrupted quote: 'ATCGACTG' (swapped bases).
    
    SYSTEM INTEGRITY RULES:
    1. NEVER accept model's 'ATCGACTG' as extracted data!
    2. Since anchors uniquely delimit the region, recovery extracts authentic 'ATCGATCG' from source.
    """
    doc = "Observed sequence: ATCGATCG\nAdditional notes: None"
    res = recover_with_anchors(
        document_text=doc,
        candidate_quote="ATCGACTG",  # Model corrupted base sequence!
        anchor_before="Observed sequence: ",
        anchor_after="\nAdditional notes:",
        field_type="observed_sequence",
        alphabet="DNA"
    )
    assert res.success is True
    assert res.status == "verified"
    # Authenticated sequence MUST be the source sequence, NOT the model proposal
    assert res.sequence == "ATCGATCG"
    assert res.sequence != "ATCGACTG"
    assert res.recovery_method == "anchor_delimited_recovery"
    assert res.source_fidelity_verified is True


def test_case_d_candidate_quote_wrong_no_valid_anchors_abstains():
    """Case D: Corrupted candidate quote with no valid anchors to delimit source -> rejects."""
    doc = "Observed sequence: ATCGATCG\nAdditional notes: None"
    res = recover_with_anchors(
        document_text=doc,
        candidate_quote="ATCGACTG",  # Not in source
        anchor_before="Bogus Before",
        anchor_after="Bogus After",
        field_type="observed_sequence",
        alphabet="DNA"
    )
    assert res.success is False
    assert res.sequence is None
    assert res.status == "rejected"
    assert res.error_code == "CANDIDATE_NOT_FOUND"


def test_case_e_multiple_candidates_ambiguous_abstains():
    """Case E: Candidate appears multiple times with identical/ambiguous context -> must abstain."""
    doc = "Sample 1: ATCGATCG\nSample 2: ATCGATCG"
    res = recover_with_anchors(
        document_text=doc,
        candidate_quote="ATCGATCG",
        anchor_before=None,
        anchor_after=None,
        field_type="observed_sequence",
        alphabet="DNA"
    )
    assert res.success is False
    assert res.status == "abstained"
    assert res.error_code == "AMBIGUOUS_SOURCE_LOCATION"
    assert "Multiple candidate locations remain plausible" in (res.message or "")


def test_fuzzy_anchor_recovery():
    """Fuzzy anchor matching handles minor typos in anchor_before without rewriting source."""
    doc = "Observed sequence: ATCGATCG\nNotes: None"
    # Typo in anchor_before: 'Observed snequce:'
    res = recover_with_anchors(
        document_text=doc,
        candidate_quote="ATCGATCG",
        anchor_before="Observed snequce: ",  # Minor typo
        anchor_after="\nNotes:",
        field_type="observed_sequence",
        alphabet="DNA"
    )
    assert res.success is True
    assert res.status == "verified"
    assert res.sequence == "ATCGATCG"
    assert res.recovery_method in ["fuzzy_anchor_recovery", "anchor_before_recovery"]
