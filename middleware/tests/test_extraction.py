"""
Comprehensive extraction test suite covering all 15 mandatory test cases from CLAUDE.md,
adversarial scenarios, provenance tracking, and FastAPI endpoints.
"""

import pytest
from fastapi.testclient import TestClient

from middleware.main import app
from middleware.extraction import extract_sequence
from middleware.schemas import ExtractionRequest, ExtractAndAlignRequest


@pytest.fixture
def client():
    return TestClient(app)


# -------------------------------------------------------------
# Tests 1-15: Mandatory Test Suite from CLAUDE.md
# -------------------------------------------------------------

def test_1_exact_candidate_both_anchors_correct():
    """1. Exact candidate, both anchors correct."""
    doc = "Header\nObserved sequence: ATCGATCG\nFooter"
    resp = extract_sequence(
        document_text=doc,
        field_type="observed_sequence",
        alphabet="DNA",
        candidate_quote="ATCGATCG",
        anchor_before="Observed sequence: ",
        anchor_after="\nFooter"
    )
    assert resp.validation_status == "verified"
    assert resp.source_match is True
    assert resp.sequence == "ATCGATCG"
    assert resp.boundaries_verified is True
    assert resp.completeness_verified is True
    assert resp.anchors_verified is True
    assert resp.recovery_method == "exact_quote"
    assert resp.source_span is not None
    assert doc[resp.source_span.start:resp.source_span.end] == "ATCGATCG"


def test_2_incorrect_anchor_before():
    """2. Incorrect anchor_before."""
    doc = "Header\nObserved sequence: ATCGATCG\nFooter"
    resp = extract_sequence(
        document_text=doc,
        field_type="observed_sequence",
        alphabet="DNA",
        candidate_quote="ATCGATCG",
        anchor_before="Wrong Label Before:",
        anchor_after="\nFooter"
    )
    assert resp.validation_status == "verified"
    assert resp.source_match is True
    assert resp.sequence == "ATCGATCG"
    assert resp.anchors_verified is False
    assert resp.recovery_method in ["anchor_before_recovery", "exact_quote_search"]


def test_3_incorrect_anchor_after():
    """3. Incorrect anchor_after."""
    doc = "Header\nObserved sequence: ATCGATCG\nFooter"
    resp = extract_sequence(
        document_text=doc,
        field_type="observed_sequence",
        alphabet="DNA",
        candidate_quote="ATCGATCG",
        anchor_before="Observed sequence: ",
        anchor_after="Nonexistent Footer"
    )
    assert resp.validation_status == "verified"
    assert resp.source_match is True
    assert resp.sequence == "ATCGATCG"
    assert resp.anchors_verified is False
    assert resp.recovery_method == "anchor_after_recovery"


def test_4_both_anchors_incorrect():
    """4. Both anchors incorrect (unique candidate in document)."""
    doc = "Header\nObserved sequence: ATCGATCG\nFooter"
    resp = extract_sequence(
        document_text=doc,
        field_type="observed_sequence",
        alphabet="DNA",
        candidate_quote="ATCGATCG",
        anchor_before="Wrong Before:",
        anchor_after="Wrong After:"
    )
    assert resp.validation_status == "verified"
    assert resp.source_match is True
    assert resp.sequence == "ATCGATCG"
    assert resp.anchors_verified is False
    assert resp.recovery_method == "exact_quote_search"


def test_5_candidate_quote_absent_from_source():
    """5. Candidate quote absent from source."""
    doc = "Header\nObserved sequence: ATCGATCG\nFooter"
    resp = extract_sequence(
        document_text=doc,
        field_type="observed_sequence",
        alphabet="DNA",
        candidate_quote="GGGGGGGG",  # Absent sequence
        anchor_before="Wrong Before",
        anchor_after="Wrong After"
    )
    assert resp.validation_status in ["rejected", "abstained"]
    assert resp.source_match is False
    assert resp.sequence is None
    assert resp.error_code == "CANDIDATE_NOT_FOUND"


def test_6_candidate_quote_appears_multiple_times():
    """6. Candidate quote appears multiple times without disambiguating anchors."""
    doc = "Experiment 1: ATCGATCG\nExperiment 2: ATCGATCG"
    resp = extract_sequence(
        document_text=doc,
        field_type="observed_sequence",
        alphabet="DNA",
        candidate_quote="ATCGATCG",
        anchor_before=None,
        anchor_after=None
    )
    assert resp.validation_status == "abstained"
    assert resp.source_match is False
    assert resp.sequence is None
    assert resp.error_code == "AMBIGUOUS_SOURCE_LOCATION"


def test_7_multiple_sequence_fields_in_one_document():
    """7. Multiple sequence fields in one document (Reference vs Observed)."""
    doc = "Reference sequence: AAAAAAAA\nObserved sequence: GCTAGCTA"
    resp = extract_sequence(
        document_text=doc,
        field_type="observed_sequence",
        alphabet="DNA",
        candidate_quote=None
    )
    assert resp.validation_status == "verified"
    assert resp.source_match is True
    assert resp.sequence == "GCTAGCTA"
    assert resp.sequence != "AAAAAAAA"


def test_8_valid_sequence_split_across_lines():
    """8. Valid sequence split across lines."""
    doc = "Observed sequence:\nATCG\nGCTA\nTAGC"
    resp = extract_sequence(
        document_text=doc,
        field_type="observed_sequence",
        alphabet="DNA",
        candidate_quote="ATCG\nGCTA\nTAGC",
        anchor_before="Observed sequence:\n",
        anchor_after=None
    )
    assert resp.validation_status == "verified"
    assert resp.source_match is True
    assert resp.sequence == "ATCGGCTATAGC"
    assert "strip_whitespace" in resp.provenance.normalization_ops
    # Check that each base accurately maps to original text
    for i, base in enumerate(resp.sequence):
        orig_idx = resp.provenance.offset_mapping[i]
        assert doc[orig_idx].upper() == base


def test_9_recognized_line_numbering_and_whitespace():
    """9. Recognized line numbering and whitespace."""
    doc = "Observed sequence:\n1 ATCG ATCG\n2 GCTA GCTA\nEnd of record"
    resp = extract_sequence(
        document_text=doc,
        field_type="observed_sequence",
        alphabet="DNA",
        candidate_quote="1 ATCG ATCG\n2 GCTA GCTA",
        anchor_before="Observed sequence:\n",
        anchor_after="\nEnd of record"
    )
    assert resp.validation_status == "verified"
    assert resp.source_match is True
    assert resp.sequence == "ATCGATCGGCTAGCTA"
    assert "remove_line_numbers" in resp.provenance.normalization_ops
    assert "strip_whitespace" in resp.provenance.normalization_ops
    for i, base in enumerate(resp.sequence):
        orig_idx = resp.provenance.offset_mapping[i]
        assert doc[orig_idx].upper() == base


def test_10_invalid_nucleotide_characters():
    """10. Invalid nucleotide characters."""
    doc = "Observed sequence: ATCGXZGCTA\nEnd"
    resp = extract_sequence(
        document_text=doc,
        field_type="observed_sequence",
        alphabet="DNA",
        candidate_quote="ATCGXZGCTA",
        anchor_before="Observed sequence: ",
        anchor_after="\nEnd"
    )
    assert resp.validation_status == "rejected"
    assert resp.source_match is False
    assert resp.sequence is None
    assert resp.error_code == "INVALID_NUCLEOTIDE_CHARACTERS"


def test_11_truncated_sequence():
    """11. Truncated sequence (marked with ellipsis)."""
    doc = "Observed sequence: ATCGATCG...\nEnd"
    resp = extract_sequence(
        document_text=doc,
        field_type="observed_sequence",
        alphabet="DNA",
        candidate_quote="ATCGATCG...",
        anchor_before="Observed sequence: ",
        anchor_after="\nEnd"
    )
    assert resp.validation_status == "abstained"
    assert resp.completeness_verified is False
    assert resp.sequence is None
    assert resp.error_code == "TRUNCATED_SEQUENCE"


def test_12_ambiguous_sequence_boundaries():
    """12. Ambiguous sequence boundaries."""
    doc = "Observed sequence: ATCGATCG"
    # Candidate quote is bounded improperly or merges
    resp = extract_sequence(
        document_text=doc,
        field_type="observed_sequence",
        alphabet="DNA",
        candidate_quote="ATCG",  # Middle of sequence, leaving ATCG without delimiter
        anchor_before="Observed sequence: ",
        anchor_after=None
    )
    assert resp.validation_status == "abstained"
    assert resp.boundaries_verified is False
    assert resp.sequence is None
    assert resp.error_code in ["SUBSTRING_OF_LONGER_SEQUENCE", "AMBIGUOUS_SEQUENCE_BOUNDARIES"]


def test_13_candidate_is_substring_of_longer_sequence():
    """13. Candidate is a substring of a longer sequence."""
    doc = "Observed sequence: ATCGATCGAAAA"
    resp = extract_sequence(
        document_text=doc,
        field_type="observed_sequence",
        alphabet="DNA",
        candidate_quote="ATCGATCG",  # Next characters 'AAAA' immediately follow
        anchor_before="Observed sequence: ",
        anchor_after=None
    )
    assert resp.validation_status == "abstained"
    assert resp.boundaries_verified is False
    assert resp.sequence is None
    assert resp.error_code == "SUBSTRING_OF_LONGER_SEQUENCE"


def test_14_empty_document():
    """14. Empty document."""
    resp = extract_sequence(
        document_text="",
        field_type="observed_sequence",
        alphabet="DNA"
    )
    assert resp.validation_status == "abstained"
    assert resp.source_match is False
    assert resp.sequence is None
    assert resp.error_code == "EMPTY_DOCUMENT"


def test_15_empty_candidate_quote():
    """15. Empty candidate quote."""
    doc = "Observed sequence: ATCGATCG"
    resp = extract_sequence(
        document_text=doc,
        field_type="observed_sequence",
        alphabet="DNA",
        candidate_quote="",
        anchor_before="Observed sequence: ",
        anchor_after=None
    )
    assert resp.validation_status == "abstained"
    assert resp.sequence is None
    assert resp.error_code == "EMPTY_CANDIDATE_QUOTE"


# -------------------------------------------------------------
# Additional Integrity & Pipeline Tests
# -------------------------------------------------------------

def test_integrity_corrupted_model_proposal_never_accepted():
    """
    Integrity test: source ATCGATCG vs corrupted proposal ATCGACTG.
    Verify: model-proposed bases are NEVER accepted as source truth.
    """
    doc = "Observed sequence: ATCGATCG\nAdditional notes: None"
    resp = extract_sequence(
        document_text=doc,
        field_type="observed_sequence",
        alphabet="DNA",
        candidate_quote="ATCGACTG",  # Corrupted model proposal
        anchor_before="Observed sequence: ",
        anchor_after="\nAdditional notes:"
    )
    # The system must recover the TRUE source sequence, NEVER the corrupted proposal
    assert resp.validation_status == "verified"
    assert resp.sequence == "ATCGATCG"
    assert resp.sequence != "ATCGACTG"
    assert resp.recovery_method == "anchor_delimited_recovery"


def test_rna_extraction_and_uracil_integrity():
    """RNA alphabet extracts U and rejects T."""
    doc = "Observed RNA: AUCGAUCG\nNotes: None"
    resp = extract_sequence(
        document_text=doc,
        field_type="observed_sequence",
        alphabet="RNA",
        candidate_quote="AUCGAUCG",
        anchor_before="Observed RNA: ",
        anchor_after="\nNotes:"
    )
    assert resp.validation_status == "verified"
    assert resp.sequence == "AUCGAUCG"

    # If RNA contains Thymine (T), it must reject
    bad_doc = "Observed RNA: AUCGATCG\nNotes: None"
    bad_resp = extract_sequence(
        document_text=bad_doc,
        field_type="observed_sequence",
        alphabet="RNA",
        candidate_quote="AUCGATCG",
        anchor_before="Observed RNA: ",
        anchor_after="\nNotes:"
    )
    assert bad_resp.validation_status == "rejected"
    assert bad_resp.error_code == "INVALID_NUCLEOTIDE_CHARACTERS"


def test_fastapi_extract_endpoint(client):
    """Test POST /extract HTTP endpoint."""
    payload = {
        "document_text": "Observed sequence: ATCGATCG\nEnd",
        "field_type": "observed_sequence",
        "sequence_alphabet": "DNA",
        "candidate_quote": "ATCGATCG",
        "anchor_before": "Observed sequence: ",
        "anchor_after": "\nEnd"
    }
    res = client.post("/extract", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["validation_status"] == "verified"
    assert data["sequence"] == "ATCGATCG"
    assert data["source_match"] is True


def test_fastapi_extract_and_align_gating(client):
    """
    Test POST /extract-and-align CRITICAL GATING:
    If sequence is unverified or ambiguous, C++ engine is NEVER called,
    and response returns abstained status with alignment=None.
    """
    payload = {
        "document_text": "No sequence here, only text.",
        "reference_sequence": "ATCGATCG",
        "field_type": "observed_sequence",
        "sequence_alphabet": "DNA"
    }
    res = client.post("/extract-and-align", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "abstained"
    assert data["extraction"]["sequence"] is None
    assert data["alignment"] is None


def test_fastapi_health_endpoint(client):
    """Test GET /health endpoint."""
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert "engine_reachable" in data


def test_21_source_offsets_after_normalization():
    """21. Source offsets after normalization (whitespace & coordinates)."""
    doc = "Header\nObserved sequence:\n10 ATCG 14\n15 GCTA 19\nFooter"
    resp = extract_sequence(
        document_text=doc,
        field_type="observed_sequence",
        alphabet="DNA",
        candidate_quote="10 ATCG 14\n15 GCTA 19",
        anchor_before="Observed sequence:\n",
        anchor_after="\nFooter"
    )
    assert resp.validation_status == "verified"
    assert resp.sequence == "ATCGGCTA"
    assert resp.provenance is not None
    assert resp.provenance.offset_mapping is not None
    assert len(resp.provenance.offset_mapping) == len(resp.sequence)
    for idx, base in enumerate(resp.sequence):
        orig_char = doc[resp.provenance.offset_mapping[idx]]
        assert orig_char.upper() == base


def test_22_repeated_sequences_in_different_semantic_fields():
    """22. Repeated sequences in different semantic fields (Reference vs Observed)."""
    doc = "Reference sequence: ATCGATCG\nObserved sequence: ATCGATCG"
    resp = extract_sequence(
        document_text=doc,
        field_type="observed_sequence",
        alphabet="DNA",
        candidate_quote=None
    )
    assert resp.validation_status == "verified"
    assert resp.sequence == "ATCGATCG"
    # Must point to the second occurrence (under Observed sequence)
    assert resp.source_span.start == doc.rfind("ATCGATCG")


def test_24_iupac_ambiguity_codes():
    """24. IUPAC ambiguity codes supported when explicitly enabled."""
    doc = "Observed sequence: ATCGNRYK\nFooter"
    # When allow_iupac is False -> rejected
    resp_no_iupac = extract_sequence(
        document_text=doc,
        field_type="observed_sequence",
        alphabet="DNA",
        candidate_quote="ATCGNRYK",
        anchor_before="Observed sequence: ",
        anchor_after="\nFooter",
        allow_iupac=False
    )
    assert resp_no_iupac.validation_status == "rejected"

    # When allow_iupac is True -> verified
    resp_iupac = extract_sequence(
        document_text=doc,
        field_type="observed_sequence",
        alphabet="DNA",
        candidate_quote="ATCGNRYK",
        anchor_before="Observed sequence: ",
        anchor_after="\nFooter",
        allow_iupac=True
    )
    assert resp_iupac.validation_status == "verified"
    assert resp_iupac.sequence == "ATCGNRYK"


def test_fastapi_extract_and_align_invalid_reference(client):
    """Test extract-and-align with invalid reference sequence."""
    payload = {
        "document_text": "Observed sequence: ATCGATCG\nEnd",
        "reference_sequence": "ATCGZZZ",  # Invalid characters
        "field_type": "observed_sequence",
        "sequence_alphabet": "DNA"
    }
    res = client.post("/extract-and-align", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "rejected"
    assert data["alignment"] is None
    assert "Reference sequence validation failed" in data["extraction"]["message"]


def test_fastapi_extract_and_align_engine_success(client, monkeypatch):
    """Test extract-and-align pipeline with mocked C++ engine response."""
    import httpx

    async def mock_post(self, url, **kwargs):
        class MockResponse:
            status_code = 200
            def json(self):
                return {
                    "status": "success",
                    "alignment_score": 16,
                    "max_cell": {"row": 8, "column": 8},
                    "matrix": [[0] * 9 for _ in range(9)],
                    "matrix_dimensions": {"rows": 9, "columns": 9},
                    "scoring": {"match": 2, "mismatch": -1, "gap": -1}
                }
        return MockResponse()

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    payload = {
        "document_text": "Observed sequence: ATCGATCG\nEnd",
        "reference_sequence": "ATCGATCG",
        "field_type": "observed_sequence",
        "sequence_alphabet": "DNA",
        "candidate_quote": "ATCGATCG",
        "anchor_before": "Observed sequence: ",
        "anchor_after": "\nEnd"
    }
    res = client.post("/extract-and-align", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["extraction"]["sequence"] == "ATCGATCG"
    assert data["alignment"] is not None
    assert data["alignment"]["alignment_score"] == 16

