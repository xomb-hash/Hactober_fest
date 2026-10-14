"""
Unit tests for Round 2 Hardening (Security, Adapters, Disambiguation, Mutation Benchmark).
HelixGuard Final Verification.
"""

import pytest
import os
import re
from middleware.masking import mask_document_for_llm, dereference_token
from middleware.adapters import detect_and_parse_format
from middleware.adapters.fasta_adapter import FastaAdapter
from middleware.adapters.genbank_adapter import GenBankAdapter
from middleware.adapters.fastq_adapter import FastqAdapter
from middleware.provenance import ProvenanceTracker
from middleware.extraction import extract_sequence
from middleware.schemas import SourceSpan


# ─── 1. Security: Token Masking Invariant Tests ──────────────────────────────

def test_token_masking_strips_all_nucleotides():
    """
    CRITICAL SECURITY INVARIANT:
    Assert that mask_document_for_llm replaces all nucleotide sequences >= 6 nt,
    leaving ZERO raw nucleotide runs in the masked text.
    """
    raw_doc = (
        "CLINICAL GENOMICS REPORT\n"
        "Patient: Alice Johnson\n"
        "MRN: 987654321\n"
        "Observed sequence: GCAAGAAACAAGTAAGAAAGAGAGTCGTTGTCTTTGTTTCCCAATTTTT\n"
        "Control sequence: ATCGATCGATCGATCG\n"
        "Notes: Normal control run."
    )

    masked_doc = mask_document_for_llm(raw_doc, alphabet="DNA", min_length=6)

    # Assert masked text contains no raw nucleotide runs of 6+ bases
    assert not masked_doc.contains_raw_nucleotides
    assert "GCAAGAAACAAGTAAGAAAGAGAGTCGTTGTCTTTGTTTCCCAATTTTT" not in masked_doc.masked_text
    assert "ATCGATCGATCGATCG" not in masked_doc.masked_text

    # Assert tokens were created
    assert len(masked_doc.tokens) >= 2
    assert "<SEQ_0" in masked_doc.masked_text
    assert "<SEQ_1" in masked_doc.masked_text

    # Assert patient identifiers were redacted
    assert "Alice Johnson" not in masked_doc.masked_text
    assert "<NAME_REDACTED>" in masked_doc.masked_text
    assert "987654321" not in masked_doc.masked_text
    assert "<MRN_REDACTED>" in masked_doc.masked_text


def test_token_dereferencing():
    """Verifies that tokens can be dereferenced back to exact source text."""
    raw_doc = "Variant sequence: TTACCTGCACAGCTCTGCATAGTCCTACACTGATACGGATGAAAGAAATGAAACTAAACATATTAAACACAACCATTTAT"
    masked_doc = mask_document_for_llm(raw_doc, alphabet="DNA", min_length=6)

    assert len(masked_doc.tokens) == 1
    token_label = masked_doc.tokens[0].token

    deref = dereference_token(token_label, masked_doc.token_map)
    assert deref is not None
    assert deref.raw_sequence == "TTACCTGCACAGCTCTGCATAGTCCTACACTGATACGGATGAAAGAAATGAAACTAAACATATTAAACACAACCATTTAT"

    # Also test base tag dereferencing e.g. "<SEQ_0>"
    deref_short = dereference_token("<SEQ_0>", masked_doc.token_map)
    assert deref_short is not None
    assert deref_short.raw_sequence == deref.raw_sequence


# ─── 2. Salted HMAC & Redacted Export Tests ──────────────────────────────────

def test_salted_hmac_and_redacted_export():
    """Verifies salted HMAC calculation and sequence redaction in audit export."""
    text = "Observed sequence: ATCGATCGATCG"
    tracker1 = ProvenanceTracker(text, salt="salt-alpha")
    tracker2 = ProvenanceTracker(text, salt="salt-beta")

    # Plain hash is identical for same text
    assert tracker1.input_hash == tracker2.input_hash
    # Salted HMAC MUST differ across different salts to prevent rainbow tables
    assert tracker1.input_hmac != tracker2.input_hmac

    # Redacted export contains NO raw sequence or excerpts
    tracker1.extracted_sequence = "ATCGATCGATCG"
    tracker1.source_excerpt = "ATCGATCGATCG"
    tracker1.candidate_quote = "ATCGATCGATCG"
    tracker1.candidate_located = True
    tracker1.validation_status = "verified"

    record = tracker1.build_record()
    redacted = record.to_redacted_dict()

    assert "extracted_sequence" not in redacted
    assert "source_excerpt" not in redacted
    assert "candidate_quote" not in redacted
    assert "offset_mapping" not in redacted
    assert redacted["input_hmac"] == tracker1.input_hmac
    assert redacted["validation_status"] == "verified"


# ─── 3. Format Adapter Tests ─────────────────────────────────────────────────

def test_fasta_adapter_multiline():
    """Tests FASTA adapter parsing with multiline wrapped sequence and exact offsets."""
    fasta_doc = (
        ">NC_008987.1 Hyposoter fugitivus segment D2\n"
        "TTACCTGCACAGCTCTGCAT\n"
        "AGTCCTACACTGATACGGAT\n"
        "GAAAGAAATGAAACTAAACA\n"
    )

    fmt, candidates = detect_and_parse_format(fasta_doc, alphabet="DNA")
    assert fmt == "fasta"
    assert len(candidates) == 1
    assert candidates[0].sequence == "TTACCTGCACAGCTCTGCATAGTCCTACACTGATACGGATGAAAGAAATGAAACTAAACA"
    assert candidates[0].header_or_id == "NC_008987.1 Hyposoter fugitivus segment D2"

    # Verify character offsets match raw document
    for char, offset in zip(candidates[0].sequence, candidates[0].offset_map):
        assert fasta_doc[offset] == char


def test_genbank_origin_adapter():
    """Tests GenBank adapter parsing of ORIGIN block with line numbers and 10-base groups."""
    genbank_doc = (
        "LOCUS       NC_001422              5386 bp    DNA     circular VRL 13-AUG-2018\n"
        "DEFINITION  Enterobacteria phage phiX174, complete genome.\n"
        "ORIGIN\n"
        "        1 gagttttatc gcttccatga cgcagaagtt aacactttcg gatatttctg atgagtcgaa\n"
        "       61 aaattatctt gataaagcag gaattactac tgcttgttta cgaattaaat cgaagtggac\n"
        "//\n"
    )

    fmt, candidates = detect_and_parse_format(genbank_doc, alphabet="DNA")
    assert fmt == "genbank"
    assert len(candidates) == 1
    expected_seq = (
        "GAGTTTTATCGCTTCCATGACGCAGAAGTTAACACTTTCGGATATTTCTGATGAGTCGAA"
        "AAATTATCTTGATAAAGCAGGAATTACTACTGCTTGTTTACGAATTAAATCGAAGTGGAC"
    )
    assert candidates[0].sequence == expected_seq

    # Every mapped offset in genbank_doc must match the character
    for char, offset in zip(candidates[0].sequence, candidates[0].offset_map):
        assert genbank_doc[offset].upper() == char


def test_fastq_adapter():
    """Tests FASTQ adapter parsing of 4-line sequencing reads."""
    fastq_doc = (
        "@READ_001 isolate fragment\n"
        "GATTTGGGGTTCAAAGCAGTATCGATCAAATAGTAAATCCATTTGTTCAACTCACAGTTT\n"
        "+\n"
        "!''*((((***+))%%%++)(%%%%).1***-+*''))**55CCF>>>>>>CCCCCCC65\n"
    )

    fmt, candidates = detect_and_parse_format(fastq_doc, alphabet="DNA")
    assert fmt == "fastq"
    assert len(candidates) == 1
    assert candidates[0].sequence == "GATTTGGGGTTCAAAGCAGTATCGATCAAATAGTAAATCCATTTGTTCAACTCACAGTTT"
    assert candidates[0].header_or_id == "READ_001 isolate fragment"


# ─── 4. Human-in-the-Loop Disambiguation Tests ───────────────────────────────

def test_interactive_user_disambiguation():
    """
    Verifies that providing a selected_span resolves ambiguity deterministically,
    turning an abstention into a verified extraction.
    """
    ambiguous_doc = (
        "COMPARATIVE GENOMICS REPORT\n"
        "Observed sequence 1: ATCGATCGATCG\n"
        "Observed sequence 2: ATCGATCGATCG\n"
    )

    # 1. Unambiguated extraction abstains due to duplicate occurrences
    resp_ambiguous = extract_sequence(
        document_text=ambiguous_doc,
        field_type="observed_sequence",
        candidate_quote="ATCGATCGATCG",
        use_ai=False
    )
    assert resp_ambiguous.validation_status == "abstained"

    # 2. Providing selected_span deterministically accepts the exact chosen span
    first_start = ambiguous_doc.find("ATCGATCGATCG")
    first_end = first_start + len("ATCGATCGATCG")

    resp_disambiguated = extract_sequence(
        document_text=ambiguous_doc,
        field_type="observed_sequence",
        selected_span=SourceSpan(start=first_start, end=first_end),
        use_ai=False
    )

    assert resp_disambiguated.validation_status == "verified"
    assert resp_disambiguated.sequence == "ATCGATCGATCG"
    assert resp_disambiguated.recovery_method == "user_disambiguation"
    assert resp_disambiguated.source_span.start == first_start
    assert resp_disambiguated.source_span.end == first_end


# ─── 5. Mutation Benchmark & Property Invariant Tests ────────────────────────

def test_mutation_invariant_accepted_altered_sequences_zero():
    """
    CORE INTEGRITY INVARIANT:
    Accepted-altered-sequences MUST EQUAL ZERO.
    Inject point mutations, insertions, deletions into candidate quotes;
    assert the system NEVER accepts altered bases as truth.
    """
    source_seq = "TTACCTGCACAGCTCTGCATAGTCCTACACTGATACGGATGAAAGAAATGAAACTAAACATATTAAACACAACCATTTAT"
    doc = f"Observed sequence: {source_seq}\nAdditional notes: None."

    mutations = [
        # Point substitution at start
        "ATACCTGCACAGCTCTGCATAGTCCTACACTGATACGGATGAAAGAAATGAAACTAAACATATTAAACACAACCATTTAT",
        # Point substitution in middle
        "TTACCTGCACAGCTCTGCATAGTCCTACACTGATACGGATGACAGAAATGAAACTAAACATATTAAACACAACCATTTAT",
        # Insertion
        "TTACCTGCACAGCTCTGCATAGTCCTACACTGATACGGATGAAAGAAATGAAACTAAACATATTAAACACAACCATTTATT",
        # Deletion
        "TTACCTGCACAGCTCTGCATAGTCCTACACTGATACGGATGAAAGAAATGAAACTAAACATATTAAACACAACCATTTA",
    ]

    accepted_altered_count = 0

    for mutated_quote in mutations:
        resp = extract_sequence(
            document_text=doc,
            field_type="observed_sequence",
            candidate_quote=mutated_quote,
            anchor_before="Observed sequence:",
            anchor_after="Additional notes:",
            use_ai=False
        )

        # If verified, the extracted sequence MUST match the genuine source sequence, NEVER the mutated candidate
        if resp.validation_status == "verified":
            if resp.sequence != source_seq:
                accepted_altered_count += 1
        elif resp.validation_status == "rejected" or resp.validation_status == "abstained":
            # Rejection or abstention is correct fail-safe behavior
            pass

    assert accepted_altered_count == 0, f"Critical failure: {accepted_altered_count} altered sequences were accepted!"
