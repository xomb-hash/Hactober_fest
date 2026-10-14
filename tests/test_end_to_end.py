"""
End-to-end integration test suite for HelixGuard.
Validates the entire pipeline from document text through deterministic verification,
safety gating, and C++ Smith-Waterman alignment.

Tests all 8 End-to-End Scenarios specified in CLAUDE.md:
1. Correct sequence -> verified extraction -> alignment
2. Incorrect anchor -> deterministic recovery -> verified extraction
3. Both anchors wrong -> unique, contextually supported candidate recovered
4. Both anchors wrong -> ambiguous candidate -> abstain
5. Corrupted candidate -> verification fails, authentic source sequence preserved
6. No sequence found -> no alignment
7. Ambiguous field -> abstain
8. Alignment service unavailable -> clear structured backend error
"""

import pytest
from unittest.mock import patch
import httpx
from fastapi.testclient import TestClient

from middleware.main import app
from middleware.schemas import ExtractAndAlignRequest, ExtractAndAlignResponse


@pytest.fixture
def client():
    return TestClient(app)


def test_e2e_1_correct_sequence_verified_extraction_alignment(client):
    """
    Scenario 1: Clearly labeled, complete DNA sequence with valid anchors.
    Expects verified extraction and successful alignment.
    """
    payload = {
        "document_text": "PATIENT REPORT\nObserved sequence: ATCGATCG\nAdditional notes: None",
        "reference_sequence": "ATCGATCG",
        "field_type": "observed_sequence",
        "sequence_alphabet": "DNA",
        "candidate_quote": "ATCGATCG",
        "anchor_before": "Observed sequence: ",
        "anchor_after": "\nAdditional notes:"
    }

    resp = client.post("/extract-and-align", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["status"] == "success"
    assert data["extraction"]["validation_status"] == "verified"
    assert data["extraction"]["sequence"] == "ATCGATCG"
    assert data["extraction"]["source_match"] is True
    assert data["extraction"]["boundaries_verified"] is True
    assert data["extraction"]["completeness_verified"] is True
    assert data["extraction"]["anchors_verified"] is True

    # Alignment must have run and produced valid score
    assert data["alignment"] is not None
    assert data["alignment"]["status"] == "success"
    assert data["alignment"]["alignment_score"] == 16
    assert data["alignment"]["max_cell"]["row"] == 8
    assert data["alignment"]["max_cell"]["column"] == 8


def test_e2e_2_incorrect_anchor_deterministic_recovery(client):
    """
    Scenario 2: Valid, uniquely identifiable sequence with one wrong anchor.
    Expects anchor failure recorded, deterministic recovery, verified extraction and alignment.
    """
    payload = {
        "document_text": "PATIENT REPORT\nObserved sequence: GCTAGCTA\nAdditional notes: End",
        "reference_sequence": "GCTAGCTA",
        "field_type": "observed_sequence",
        "sequence_alphabet": "DNA",
        "candidate_quote": "GCTAGCTA",
        "anchor_before": "Tumor DNA Sequence: ",  # Wrong anchor
        "anchor_after": "\nAdditional notes:"
    }

    resp = client.post("/extract-and-align", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["status"] == "success"
    assert data["extraction"]["validation_status"] == "verified"
    assert data["extraction"]["sequence"] == "GCTAGCTA"
    assert data["extraction"]["anchors_verified"] is False
    assert data["extraction"]["recovery_method"] in ["anchor_before_recovery", "exact_quote_search"]

    # Alignment executed
    assert data["alignment"] is not None
    assert data["alignment"]["alignment_score"] == 16


def test_e2e_3_both_anchors_wrong_unique_candidate_recovered(client):
    """
    Scenario 3: Both anchors wrong, but quote is unique and contextually supported.
    Expects recovery via exact quote search, verified extraction, alignment permitted.
    """
    payload = {
        "document_text": "Sample run:\nObserved sequence: TTGCATGC\nConclusion: End of report",
        "reference_sequence": "TTGCATGC",
        "field_type": "observed_sequence",
        "sequence_alphabet": "DNA",
        "candidate_quote": "TTGCATGC",
        "anchor_before": "Nonexistent Label:",
        "anchor_after": "Nonexistent Footer"
    }

    resp = client.post("/extract-and-align", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["status"] == "success"
    assert data["extraction"]["validation_status"] == "verified"
    assert data["extraction"]["sequence"] == "TTGCATGC"
    assert data["extraction"]["recovery_method"] in ["both_anchors_recovery", "exact_quote_search"]
    assert data["alignment"] is not None


def test_e2e_4_both_anchors_wrong_ambiguous_candidate_abstains(client):
    """
    Scenario 4: Both anchors wrong and quote appears in conflicting semantic fields.
    Must abstain with explicit error code; gating prevents engine call.
    """
    payload = {
        "document_text": (
            "Sample 1: ATCGATCG\n"
            "Sample 2: ATCGATCG"
        ),
        "reference_sequence": "ATCGATCG",
        "field_type": "observed_sequence",
        "sequence_alphabet": "DNA",
        "candidate_quote": "ATCGATCG",
        "anchor_before": "Wrong Before",
        "anchor_after": "Wrong After"
    }

    resp = client.post("/extract-and-align", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    # Must abstain because candidate appears under multiple fields with no valid anchors
    assert data["status"] == "abstained"
    assert data["extraction"]["sequence"] is None
    assert data["extraction"]["validation_status"] == "abstained"
    assert data["extraction"]["error_code"] == "AMBIGUOUS_SOURCE_LOCATION"
    # GATING: Alignment must be strictly null
    assert data["alignment"] is None


def test_e2e_5_corrupted_candidate_never_accepted_as_truth(client):
    """
    Scenario 5: Model proposes hallucinated/corrupted bases (e.g. ATCGACTG instead of ATCGATCG).
    System must NEVER accept model bases as source truth.
    Authentic source bases ATCGATCG must be extracted or system must abstain.
    """
    payload = {
        "document_text": "PATIENT REPORT\nObserved sequence: ATCGATCG\nEnd",
        "reference_sequence": "ATCGATCG",
        "field_type": "observed_sequence",
        "sequence_alphabet": "DNA",
        "candidate_quote": "ATCGACTG",  # Corrupted model hallucination!
        "anchor_before": "Observed sequence: ",
        "anchor_after": "\nEnd"
    }

    resp = client.post("/extract-and-align", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    # Integrity verification: model bases "ATCGACTG" were NEVER accepted
    assert data["extraction"]["sequence"] != "ATCGACTG"
    # Either successfully delimited authentic source sequence "ATCGATCG" or abstained
    if data["status"] == "success":
        assert data["extraction"]["sequence"] == "ATCGATCG"
        assert data["alignment"]["alignment_score"] == 16
    else:
        assert data["status"] in ["abstained", "rejected"]
        assert data["alignment"] is None


def test_e2e_6_no_sequence_found_no_alignment(client):
    """
    Scenario 6: Document contains no valid nucleotide sequence for the requested field.
    Expects abstention, no fabricated sequence, and zero engine calls.
    """
    payload = {
        "document_text": "PATIENT REPORT\nAll tests were inconclusive. No genomic reads were captured.\nDoctor: Dr. Smith",
        "reference_sequence": "ATCGATCG",
        "field_type": "observed_sequence",
        "sequence_alphabet": "DNA"
    }

    resp = client.post("/extract-and-align", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["status"] == "abstained"
    assert data["extraction"]["sequence"] is None
    assert data["extraction"]["source_match"] is False
    assert data["alignment"] is None


def test_e2e_7_ambiguous_field_abstains(client):
    """
    Scenario 7: Document has conflicting fields and cannot unambiguously resolve requested field.
    Expects explicit abstention.
    """
    payload = {
        "document_text": "Reference sequence: GCTAGCTA\nNormal control: GCTAGCTA",
        "reference_sequence": "GCTAGCTA",
        "field_type": "observed_sequence",  # Neither field matches requested observed_sequence
        "sequence_alphabet": "DNA"
    }

    resp = client.post("/extract-and-align", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["status"] == "abstained"
    assert data["extraction"]["sequence"] is None
    assert data["alignment"] is None


def test_e2e_8_alignment_service_unavailable_clear_backend_error(client):
    """
    Scenario 8: C++ alignment engine is unreachable.
    Expects verified extraction recorded in provenance, but alignment returned as None
    with status 'error' and descriptive message (no fabricated alignment).
    """
    payload = {
        "document_text": "Observed sequence: ATCGATCG\nFooter",
        "reference_sequence": "ATCGATCG",
        "field_type": "observed_sequence",
        "sequence_alphabet": "DNA",
        "candidate_quote": "ATCGATCG",
        "anchor_before": "Observed sequence: ",
        "anchor_after": "\nFooter"
    }

    # Simulate C++ engine connection failure
    with patch("httpx.AsyncClient.post", side_effect=httpx.ConnectError("Connection refused")):
        resp = client.post("/extract-and-align", json=payload)
        assert resp.status_code == 200
        data = resp.json()

        assert data["status"] == "error"
        # Extraction itself succeeded and was verified
        assert data["extraction"]["validation_status"] == "verified"
        assert data["extraction"]["sequence"] == "ATCGATCG"
        # Alignment is None due to network failure (never fabricated)
        assert data["alignment"] is None
