"""
Anchor recovery module for HelixGuard.
Implements robust recovery strategies for Cases A through E from CLAUDE.md Milestone 3.
Guarantees source fidelity and deterministic boundary verification.
"""

import re
import difflib
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Set

from middleware.schemas import SourceSpan, AnchorVerification
from middleware.validation import validate_alphabet, DNA_STANDARD, RNA_STANDARD, DNA_IUPAC, RNA_IUPAC
from middleware.critic import ContextCritic


@dataclass
class AnchorRecoveryResult:
    """Outcome of an anchor verification and recovery attempt."""
    success: bool
    status: str  # "verified", "abstained", "rejected"
    sequence: Optional[str] = None
    source_span: Optional[SourceSpan] = None
    offset_mapping: Optional[List[int]] = None
    normalization_ops: List[str] = field(default_factory=list)
    recovery_method: Optional[str] = None
    anchors_verified: bool = False
    anchor_verification: Optional[AnchorVerification] = None
    candidate_located: bool = False
    alphabet_valid: bool = False
    boundaries_verified: bool = False
    completeness_verified: bool = False
    source_fidelity_verified: bool = False
    field_supported: bool = False
    error_code: Optional[str] = None
    message: Optional[str] = None


def find_all_occurrences(text: str, sub: str) -> List[int]:
    """Returns all starting indices of sub in text."""
    if not text or not sub:
        return []
    indices: List[int] = []
    start = 0
    while True:
        idx = text.find(sub, start)
        if idx == -1:
            break
        indices.append(idx)
        start = idx + 1
    return indices


def fuzzy_find_anchor(
    document_text: str,
    anchor: str,
    min_similarity: float = 0.8
) -> List[Tuple[int, int, float]]:
    """
    Performs bounded fuzzy matching for an anchor string.
    ONLY used for anchor localization, NEVER for nucleotide sequence characters.
    Returns list of (start_idx, end_idx, similarity_ratio).
    """
    if not document_text or not anchor or len(anchor) < 4:
        return []

    anchor_len = len(anchor)
    matches: List[Tuple[int, int, float]] = []
    step = 1

    for i in range(0, len(document_text) - anchor_len + 1, step):
        candidate_window = document_text[i:i + anchor_len]
        matcher = difflib.SequenceMatcher(None, anchor.lower(), candidate_window.lower())
        ratio = matcher.ratio()
        if ratio >= min_similarity:
            matches.append((i, i + anchor_len, ratio))

    matches.sort(key=lambda x: x[2], reverse=True)
    return matches


def parse_sequence_block(
    document_text: str,
    start_offset: int,
    end_offset: int,
    alphabet: str = "DNA",
    allow_iupac: bool = False
) -> Tuple[Optional[str], Optional[List[int]], List[str], List[str]]:
    """
    Parses a raw text slice into a clean nucleotide sequence while tracking:
    - offset_mapping: maps each extracted sequence base index to its exact index in document_text
    - normalization_ops: list of applied operations (e.g. whitespace, line numbers)
    - invalid_chars: any characters not belonging to the alphabet
    """
    raw_slice = document_text[start_offset:end_offset]
    extracted_chars: List[str] = []
    offset_mapping: List[int] = []
    normalization_ops: List[str] = []
    invalid_chars: List[str] = []

    alphabet_upper = alphabet.upper()
    if alphabet_upper == "DNA":
        valid_set = DNA_IUPAC if allow_iupac else DNA_STANDARD
    else:
        valid_set = RNA_IUPAC if allow_iupac else RNA_STANDARD

    lines = raw_slice.splitlines(keepends=True)
    cur_global_offset = start_offset

    had_whitespace = False
    had_line_numbers = False
    had_uppercase_conversion = False

    for line in lines:
        line_start = cur_global_offset
        cur_global_offset += len(line)

        # Check for leading line number (e.g. "10  ATCG" or "1  ATCG")
        m_num = re.match(r"^(\s*\d+\s+)", line)
        line_content_start = 0
        if m_num:
            had_line_numbers = True
            line_content_start = len(m_num.group(1))

        # Check for trailing line numbers or coordinates (e.g. "ATCG  50\n")
        m_trail = re.search(r"(\s+\d+\s*[\r\n]*)$", line)
        line_content_end = len(line)
        if m_trail and m_trail.start() >= line_content_start:
            had_line_numbers = True
            line_content_end = m_trail.start()

        for idx in range(line_content_start, line_content_end):
            ch = line[idx]
            global_idx = line_start + idx

            if ch.isspace():
                had_whitespace = True
                continue

            if ch.upper() in valid_set:
                if ch.islower():
                    had_uppercase_conversion = True
                extracted_chars.append(ch.upper())
                offset_mapping.append(global_idx)
            else:
                invalid_chars.append(ch)

    if had_whitespace:
        normalization_ops.append("strip_whitespace")
    if had_line_numbers:
        normalization_ops.append("remove_line_numbers")
    if had_uppercase_conversion:
        normalization_ops.append("uppercase_conversion")

    seq = "".join(extracted_chars) if extracted_chars else None
    return seq, offset_mapping if seq else None, normalization_ops, invalid_chars


def check_boundary_integrity(
    document_text: str,
    start_offset: int,
    end_offset: int,
    alphabet: str = "DNA",
    allow_iupac: bool = False
) -> Tuple[bool, Optional[str]]:
    """
    Verifies that the sequence span [start_offset, end_offset) has unambiguous,
    delimited boundaries and is not an arbitrary substring of a longer sequence.
    """
    alphabet_upper = alphabet.upper()
    valid_set = (DNA_IUPAC if allow_iupac else DNA_STANDARD) if alphabet_upper == "DNA" else (RNA_IUPAC if allow_iupac else RNA_STANDARD)

    # Preceding character check
    if start_offset > 0:
        prev_char = document_text[start_offset - 1]
        if prev_char.upper() in valid_set:
            return False, "SUBSTRING_OF_LONGER_SEQUENCE: Sequence preceded by adjacent nucleotide base."

    # Following character check
    if end_offset < len(document_text):
        next_char = document_text[end_offset]
        if next_char.upper() in valid_set:
            return False, "SUBSTRING_OF_LONGER_SEQUENCE: Sequence followed by adjacent nucleotide base."

    return True, None


def recover_with_anchors(
    document_text: str,
    candidate_quote: Optional[str],
    anchor_before: Optional[str],
    anchor_after: Optional[str],
    field_type: str = "observed_sequence",
    alphabet: str = "DNA",
    allow_iupac: bool = False
) -> AnchorRecoveryResult:
    """
    Comprehensive anchor verification and recovery engine.
    Orchestrates Normal Verification and Cases A through E.
    """
    critic = ContextCritic()

    # Rule 14: Empty document
    if not document_text or not document_text.strip():
        return AnchorRecoveryResult(
            success=False,
            status="abstained",
            error_code="EMPTY_DOCUMENT",
            message="Document text is empty or whitespace only."
        )

    # Rule 15: Empty candidate quote provided
    if candidate_quote is not None and not candidate_quote.strip():
        return AnchorRecoveryResult(
            success=False,
            status="abstained",
            error_code="EMPTY_CANDIDATE_QUOTE",
            message="Candidate quote provided was empty."
        )

    cand = candidate_quote.strip() if candidate_quote is not None else None
    anc_b = anchor_before.strip() if anchor_before is not None else None
    anc_a = anchor_after.strip() if anchor_after is not None else None

    # Rule 11: Truncation check
    if cand and ("..." in cand or "…" in cand or cand.endswith("-")):
        return AnchorRecoveryResult(
            success=False,
            status="abstained",
            candidate_located=False,
            boundaries_verified=False,
            completeness_verified=False,
            error_code="TRUNCATED_SEQUENCE",
            message="Candidate quote is explicitly truncated."
        )

    verification = AnchorVerification()

    b_indices = find_all_occurrences(document_text, anc_b) if anc_b else []
    a_indices = find_all_occurrences(document_text, anc_a) if anc_a else []
    q_indices = find_all_occurrences(document_text, cand) if cand else []

    verification.anchor_before_found = len(b_indices) > 0
    verification.anchor_after_found = len(a_indices) > 0
    verification.candidate_quote_found = len(q_indices) > 0

    # -------------------------------------------------------------
    # CASE D: Candidate quote provided but not found in source text
    # -------------------------------------------------------------
    if cand and not q_indices:
        # Integrity Rule: The model's proposed sequence is NEVER source truth!
        # Check if anchors uniquely delimit a valid sequence in the source text
        if anc_b and anc_a and len(b_indices) == 1 and len(a_indices) == 1:
            idx_b = b_indices[0]
            idx_a = a_indices[0]
            span_start = idx_b + len(anc_b)
            if span_start < idx_a:
                seq, offset_map, norm_ops, invalids = parse_sequence_block(
                    document_text, span_start, idx_a, alphabet, allow_iupac
                )
                if seq and not invalids and offset_map:
                    b_ok, b_err = check_boundary_integrity(document_text, offset_map[0], offset_map[-1] + 1, alphabet, allow_iupac)
                    field_ok, field_reason = critic.evaluate_deterministic(document_text, offset_map[0], offset_map[-1] + 1, field_type)
                    if b_ok and field_ok:
                        return AnchorRecoveryResult(
                            success=True,
                            status="verified",
                            sequence=seq,
                            source_span=SourceSpan(start=offset_map[0], end=offset_map[-1] + 1),
                            offset_mapping=offset_map,
                            normalization_ops=norm_ops,
                            recovery_method="anchor_delimited_recovery",
                            anchors_verified=True,
                            anchor_verification=verification,
                            candidate_located=True,
                            alphabet_valid=True,
                            boundaries_verified=True,
                            completeness_verified=True,
                            source_fidelity_verified=True,
                            field_supported=True,
                            message="Candidate quote was corrupted; authentic sequence recovered directly from source text delimited by anchors."
                        )

        return AnchorRecoveryResult(
            success=False,
            status="rejected",
            anchors_verified=False,
            anchor_verification=verification,
            candidate_located=False,
            source_fidelity_verified=False,
            error_code="CANDIDATE_NOT_FOUND",
            message=f"Candidate quote '{cand[:30]}...' was not found in the source text and could not be recovered."
        )

    # -------------------------------------------------------------
    # Evaluate anchor pairings with candidate quote occurrences
    # -------------------------------------------------------------
    if cand and q_indices:
        # Find ordered combinations
        # Valid pairs with anchor_before
        pairs_b = [(ib, iq) for ib in b_indices for iq in q_indices if ib + len(anc_b or "") <= iq] if anc_b else []
        # Valid pairs with anchor_after
        pairs_a = [(iq, ia) for iq in q_indices for ia in a_indices if iq + len(cand) <= ia] if anc_a else []

        # Check for complete triples when both anchors were provided
        if anc_b and anc_a:
            valid_triples = [(ib, iq, ia) for (ib, iq) in pairs_b for (iq2, ia) in pairs_a if iq == iq2]
            if len(valid_triples) == 1:
                # NORMAL VERIFICATION
                ib, iq, ia = valid_triples[0]
                verification.ordering_valid = True
                verification.anchor_before_span = SourceSpan(start=ib, end=ib + len(anc_b))
                verification.candidate_quote_span = SourceSpan(start=iq, end=iq + len(cand))
                verification.anchor_after_span = SourceSpan(start=ia, end=ia + len(anc_a))

                seq, offset_map, norm_ops, invalids = parse_sequence_block(
                    document_text, iq, iq + len(cand), alphabet, allow_iupac
                )

                if invalids:
                    return AnchorRecoveryResult(
                        success=False,
                        status="rejected",
                        anchors_verified=True,
                        anchor_verification=verification,
                        candidate_located=True,
                        alphabet_valid=False,
                        error_code="INVALID_NUCLEOTIDE_CHARACTERS",
                        message=f"Invalid characters found for alphabet {alphabet}: {','.join(set(invalids))}"
                    )

                if not seq or not offset_map:
                    return AnchorRecoveryResult(
                        success=False,
                        status="abstained",
                        error_code="EMPTY_SEQUENCE",
                        message="Candidate quote contains no nucleotide sequence."
                    )

                b_ok, b_err = check_boundary_integrity(document_text, offset_map[0], offset_map[-1] + 1, alphabet, allow_iupac)
                if not b_ok:
                    err_code = "SUBSTRING_OF_LONGER_SEQUENCE" if "SUBSTRING" in (b_err or "") else "AMBIGUOUS_SEQUENCE_BOUNDARIES"
                    return AnchorRecoveryResult(
                        success=False,
                        status="abstained",
                        candidate_located=True,
                        boundaries_verified=False,
                        error_code=err_code,
                        message=b_err
                    )

                field_ok, field_msg = critic.evaluate_deterministic(document_text, offset_map[0], offset_map[-1] + 1, field_type)
                if not field_ok:
                    return AnchorRecoveryResult(
                        success=False,
                        status="abstained",
                        candidate_located=True,
                        field_supported=False,
                        error_code="CONTEXT_FIELD_MISMATCH",
                        message=field_msg
                    )

                return AnchorRecoveryResult(
                    success=True,
                    status="verified",
                    sequence=seq,
                    source_span=SourceSpan(start=offset_map[0], end=offset_map[-1] + 1),
                    offset_mapping=offset_map,
                    normalization_ops=norm_ops,
                    recovery_method="exact_quote",
                    anchors_verified=True,
                    anchor_verification=verification,
                    candidate_located=True,
                    alphabet_valid=True,
                    boundaries_verified=True,
                    completeness_verified=True,
                    source_fidelity_verified=True,
                    field_supported=True,
                    message="Exact candidate quote and anchors verified."
                )

            elif len(valid_triples) > 1:
                return AnchorRecoveryResult(
                    success=False,
                    status="abstained",
                    anchors_verified=False,
                    error_code="AMBIGUOUS_SOURCE_LOCATION",
                    message="Multiple occurrences of anchor-delimited candidate found; ambiguous location."
                )

        # If not verified via normal triple, determine recovery case:
        # Determine target candidate offset iq:
        target_iq: Optional[int] = None
        recovery_method: Optional[str] = None

        if anc_b and anc_a:
            # Both anchors were provided, but valid_triples == 0
            if pairs_b and not pairs_a:
                # Case B: anchor_before valid, anchor_after wrong
                if len(pairs_b) == 1:
                    target_iq = pairs_b[0][1]
                    recovery_method = "anchor_after_recovery"
            elif pairs_a and not pairs_b:
                # Case A: anchor_before wrong, anchor_after valid
                if len(pairs_a) == 1:
                    target_iq = pairs_a[0][0]
                    # Check if anchor_before had fuzzy match
                    fuzzy = fuzzy_find_anchor(document_text, anc_b)
                    recovery_method = "fuzzy_anchor_recovery" if (fuzzy and fuzzy[0][2] >= 0.8) else "anchor_before_recovery"
            elif not pairs_b and not pairs_a:
                # Case C: BOTH anchors wrong
                recovery_method = "exact_quote_search"
                if len(q_indices) == 1:
                    target_iq = q_indices[0]
        elif anc_b and not anc_a:
            # Only anchor_before provided
            if len(pairs_b) == 1:
                target_iq = pairs_b[0][1]
                recovery_method = "anchor_after_recovery"
            elif not pairs_b:
                # anchor_before wrong
                fuzzy = fuzzy_find_anchor(document_text, anc_b)
                recovery_method = "fuzzy_anchor_recovery" if (fuzzy and fuzzy[0][2] >= 0.8) else "anchor_before_recovery"
                if len(q_indices) == 1:
                    target_iq = q_indices[0]
        elif anc_a and not anc_b:
            # Only anchor_after provided
            if len(pairs_a) == 1:
                target_iq = pairs_a[0][0]
                recovery_method = "anchor_before_recovery"
            elif not pairs_a:
                recovery_method = "exact_quote_search"
                if len(q_indices) == 1:
                    target_iq = q_indices[0]
        else:
            # No anchors provided
            recovery_method = "exact_quote_search"
            if len(q_indices) == 1:
                target_iq = q_indices[0]

        # If a single unambiguous candidate location target_iq was resolved:
        if target_iq is not None:
            seq, offset_map, norm_ops, invalids = parse_sequence_block(
                document_text, target_iq, target_iq + len(cand), alphabet, allow_iupac
            )

            if invalids:
                return AnchorRecoveryResult(
                    success=False,
                    status="rejected",
                    candidate_located=True,
                    alphabet_valid=False,
                    error_code="INVALID_NUCLEOTIDE_CHARACTERS",
                    message=f"Invalid characters found: {','.join(set(invalids))}"
                )

            if not seq or not offset_map:
                return AnchorRecoveryResult(
                    success=False,
                    status="abstained",
                    error_code="EMPTY_SEQUENCE",
                    message="No sequence found in candidate quote."
                )

            b_ok, b_err = check_boundary_integrity(document_text, offset_map[0], offset_map[-1] + 1, alphabet, allow_iupac)
            if not b_ok:
                err_code = "SUBSTRING_OF_LONGER_SEQUENCE" if "SUBSTRING" in (b_err or "") else "AMBIGUOUS_SEQUENCE_BOUNDARIES"
                return AnchorRecoveryResult(
                    success=False,
                    status="abstained",
                    boundaries_verified=False,
                    error_code=err_code,
                    message=b_err
                )

            field_ok, field_msg = critic.evaluate_deterministic(document_text, offset_map[0], offset_map[-1] + 1, field_type)
            if not field_ok:
                return AnchorRecoveryResult(
                    success=False,
                    status="abstained",
                    field_supported=False,
                    error_code="CONTEXT_FIELD_MISMATCH",
                    message=field_msg
                )

            return AnchorRecoveryResult(
                success=True,
                status="verified",
                sequence=seq,
                source_span=SourceSpan(start=offset_map[0], end=offset_map[-1] + 1),
                offset_mapping=offset_map,
                normalization_ops=norm_ops,
                recovery_method=recovery_method or "exact_quote_search",
                anchors_verified=False,
                anchor_verification=verification,
                candidate_located=True,
                alphabet_valid=True,
                boundaries_verified=True,
                completeness_verified=True,
                source_fidelity_verified=True,
                field_supported=True,
                message=f"Recovered sequence via {recovery_method}."
            )

        # -------------------------------------------------------------
        # CASE E: Multiple candidate occurrences without unique anchor
        # -------------------------------------------------------------
        if len(q_indices) > 1:
            supported_indices: List[int] = []
            boundary_failed_count = 0
            for iq in q_indices:
                seq, offset_map, _, invalids = parse_sequence_block(
                    document_text, iq, iq + len(cand), alphabet, allow_iupac
                )
                if seq and offset_map and not invalids:
                    b_ok, _ = check_boundary_integrity(document_text, offset_map[0], offset_map[-1] + 1, alphabet, allow_iupac)
                    if not b_ok:
                        boundary_failed_count += 1
                        continue
                    field_ok, _ = critic.evaluate_deterministic(document_text, offset_map[0], offset_map[-1] + 1, field_type)
                    if field_ok:
                        supported_indices.append(iq)

            if len(supported_indices) == 1:
                iq = supported_indices[0]
                seq, offset_map, norm_ops, _ = parse_sequence_block(
                    document_text, iq, iq + len(cand), alphabet, allow_iupac
                )
                assert offset_map is not None
                return AnchorRecoveryResult(
                    success=True,
                    status="verified",
                    sequence=seq,
                    source_span=SourceSpan(start=offset_map[0], end=offset_map[-1] + 1),
                    offset_mapping=offset_map,
                    normalization_ops=norm_ops,
                    recovery_method="field_context_search",
                    anchors_verified=False,
                    candidate_located=True,
                    alphabet_valid=True,
                    boundaries_verified=True,
                    completeness_verified=True,
                    source_fidelity_verified=True,
                    field_supported=True,
                    message="Resolved multiple candidates through unique semantic field context match."
                )
            elif boundary_failed_count == len(q_indices):
                return AnchorRecoveryResult(
                    success=False,
                    status="abstained",
                    candidate_located=True,
                    boundaries_verified=False,
                    error_code="SUBSTRING_OF_LONGER_SEQUENCE",
                    message="All candidate occurrences are substrings of longer sequences or have ambiguous boundaries."
                )
            else:
                return AnchorRecoveryResult(
                    success=False,
                    status="abstained",
                    candidate_located=True,
                    error_code="AMBIGUOUS_SOURCE_LOCATION",
                    message="Multiple candidate locations remain plausible."
                )

    return AnchorRecoveryResult(
        success=False,
        status="abstained",
        error_code="NO_CANDIDATE_PROVIDED",
        message="Neither candidate quote nor valid anchors allowed unambiguous extraction."
    )
