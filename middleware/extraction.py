"""
Deterministic genomic sequence extraction module for HelixGuard.
Orchestrates candidate span finding, boundary verification, normalization,
traceable offset mapping, and provenance generation.
"""

import re
import logging
from typing import List, Optional, Tuple
from pydantic import BaseModel

logger = logging.getLogger("helixguard.extraction")

from middleware.schemas import (
    SourceSpan,
    ExtractionRequest,
    ExtractionResponse,
    ProvenanceRecord,
)
from middleware.validation import (
    validate_alphabet,
    DNA_STANDARD,
    RNA_STANDARD,
    DNA_IUPAC,
    RNA_IUPAC,
)
from middleware.provenance import ProvenanceTracker
from middleware.critic import ContextCritic
from middleware.scout import ScoutAgent
from middleware.anchor_recovery import (
    recover_with_anchors,
    parse_sequence_block,
    check_boundary_integrity,
    find_all_occurrences,
)
from middleware.adapters import detect_and_parse_format


class CandidateSpan(BaseModel):
    """A located sequence candidate span in the document."""
    start: int
    end: int
    raw_text: str
    field_match: bool = False
    field_label: Optional[str] = None


def find_candidate_spans(
    document_text: str,
    field_type: str = "observed_sequence",
    alphabet: str = "DNA",
    allow_iupac: bool = False
) -> List[CandidateSpan]:
    """
    Locates candidate sequence regions in the document using deterministic pattern matching.
    First checks for field-labeled blocks (e.g. 'Observed sequence: ...').
    Then scans for candidate nucleotide runs.
    """
    if not document_text:
        return []

    # Format Adapter check first (for FASTA, GenBank ORIGIN, FASTQ)
    fmt_name, adapter_candidates = detect_and_parse_format(document_text, alphabet=alphabet, allow_iupac=allow_iupac)
    if fmt_name in ("fasta", "genbank", "fastq") and adapter_candidates:
        return [
            CandidateSpan(
                start=c.start,
                end=c.end,
                raw_text=document_text[c.start:c.end],
                field_match=True,
                field_label=c.header_or_id
            )
            for c in adapter_candidates
        ]

    critic = ContextCritic()
    candidates: List[CandidateSpan] = []

    # Pattern 1: Explicit field label followed by sequence block
    # Matches e.g. "Observed sequence: \n1 ATCG..." or "Observed: ATCGATCG"
    field_normalized = field_type.replace("_", r"[\s_-]*")
    field_pattern = re.compile(
        rf"(?P<label>(?:{field_normalized}|observed(?:\s+sequence)?|sample|tumor(?:\s+dna)?))\s*[:=]\s*",
        re.IGNORECASE
    )

    for match in field_pattern.finditer(document_text):
        label_str = match.group("label")
        start_idx = match.end()

        # Extract following block until next empty line or next field label
        # Scan until we hit a distinct label or double newline
        rest_text = document_text[start_idx:]
        end_match = re.search(r"(\n\s*\n|\n(?=[A-Za-z0-9_-]+:)|$)", rest_text)
        block_len = end_match.start() if end_match else len(rest_text)
        end_idx = start_idx + block_len

        # Parse the block to see if it contains valid bases
        seq, offset_map, _, invalids = parse_sequence_block(
            document_text, start_idx, end_idx, alphabet, allow_iupac
        )
        if seq and offset_map and not invalids:
            candidates.append(CandidateSpan(
                start=offset_map[0],
                end=offset_map[-1] + 1,
                raw_text=document_text[offset_map[0]:offset_map[-1] + 1],
                field_match=True,
                field_label=label_str
            ))

    # Pattern 2: Scan for nucleotide blocks in the text if no labeled candidates found
    if not candidates:
        base_chars = "ACGTacgt" if alphabet.upper() == "DNA" else "ACGUacgu"
        if allow_iupac:
            base_chars += "RYSWKMBDHVNryswkmbdhvn"

        # Match contiguous blocks of at least 4 nucleotide characters (allowing spaces and line breaks)
        # Regex captures potential sequence tokens
        token_pattern = re.compile(rf"\b[{base_chars}]{{4,}}\b")
        for m in token_pattern.finditer(document_text):
            span_start = m.start()
            span_end = m.end()

            # Verify boundaries
            b_ok, _ = check_boundary_integrity(document_text, span_start, span_end, alphabet, allow_iupac)
            if b_ok:
                field_ok, _ = critic.evaluate_deterministic(document_text, span_start, span_end, field_type)
                candidates.append(CandidateSpan(
                    start=span_start,
                    end=span_end,
                    raw_text=document_text[span_start:span_end],
                    field_match=field_ok
                ))

    return candidates


def make_plain_verdict(validation_status: str, message: Optional[str] = None, num_candidates: int = 0, format_name: Optional[str] = None) -> str:
    msg = message or ""
    if validation_status == "verified":
        fmt_note = f" via {format_name.upper()} adapter" if format_name and format_name != "text" else ""
        return f"Verified: authentic sequence deterministically extracted and validated against source text{fmt_note}."
    elif validation_status == "abstained":
        if num_candidates > 1:
            return "Not sure — multiple candidate sequence locations were found in the document. Please click a candidate span to disambiguate."
        elif "semantic field" in msg or "CONTEXT_FIELD_MISMATCH" in msg:
            return "Not sure — found sequences do not match the requested semantic field context. Please verify field label or document layout."
        elif "EMPTY_DOCUMENT" in msg:
            return "Not sure — input document is empty."
        else:
            return f"Not sure — {msg or 'insufficient evidence to establish authentic sequence'}. Downstream alignment blocked for safety."
    elif validation_status == "rejected":
        return f"Rejected — {msg or 'invalid nucleotide characters or structural violations detected'}."
    return f"Status: {validation_status} — {msg}."


def extract_sequence(
    document_text: str,
    field_type: str = "observed_sequence",
    alphabet: str = "DNA",
    candidate_quote: Optional[str] = None,
    anchor_before: Optional[str] = None,
    anchor_after: Optional[str] = None,
    allow_iupac: bool = False,
    use_ai: bool = True,
    use_token_mask: Optional[bool] = None,
    selected_span: Optional[SourceSpan] = None,
    request_id: Optional[str] = None
) -> ExtractionResponse:
    """
    Main sequence extraction pipeline combining AI-assisted localization with strict deterministic verification.
    
    Adheres strictly to:
    - Never accept model-generated sequence as truth.
    - Zero-based half-open offsets referencing original document_text.
    - Full provenance tracking with salted HMAC.
    - Strict gating: unverified sequences are rejected or abstained.
    """
    tracker = ProvenanceTracker(document_text, alphabet=alphabet, request_id=request_id)
    tracker.set_anchors(anchor_before, anchor_after, candidate_quote)

    fmt_name, _ = detect_and_parse_format(document_text, alphabet=alphabet, allow_iupac=allow_iupac)

    # 1. Empty document check
    if not document_text or not document_text.strip():
        tracker.record_decision("abstained", "abstained", "EMPTY_DOCUMENT")
        rec = tracker.build_record()
        return ExtractionResponse(
            sequence=None,
            validation_status="abstained",
            source_match=False,
            boundaries_verified=False,
            completeness_verified=False,
            recovery_method=None,
            anchors_verified=False,
            source_span=None,
            error_code="EMPTY_DOCUMENT",
            message="Document text is empty.",
            provenance=rec,
            redacted_provenance=rec.to_redacted_dict(),
            scout_proposal=None,
            critic_evaluation=None,
            candidate_spans=[],
            format_detected=fmt_name,
            plain_language_verdict="Not sure — document text is empty.",
        )

    # 2. Interactive Human-in-the-Loop Disambiguation (if selected_span provided)
    if selected_span is not None:
        start_idx = selected_span.start
        end_idx = selected_span.end
        seq, offset_map, norm_ops, invalids = parse_sequence_block(
            document_text, start_idx, end_idx, alphabet, allow_iupac
        )
        for op in norm_ops:
            tracker.add_normalization_op(op)
        if invalids:
            tracker.record_decision("rejected", "rejected", f"INVALID_NUCLEOTIDE_CHARACTERS: {','.join(set(invalids))}")
            rec = tracker.build_record()
            return ExtractionResponse(
                sequence=None,
                validation_status="rejected",
                source_match=False,
                boundaries_verified=False,
                completeness_verified=False,
                error_code="INVALID_NUCLEOTIDE_CHARACTERS",
                message=f"Invalid nucleotide characters in selected span: {','.join(set(invalids))}",
                provenance=rec,
                redacted_provenance=rec.to_redacted_dict(),
                format_detected="user_disambiguation",
                plain_language_verdict=f"Rejected — invalid nucleotide characters in selected span: {','.join(set(invalids))}.",
            )
        if seq and offset_map:
            span = SourceSpan(start=offset_map[0], end=offset_map[-1] + 1)
            tracker.set_source_location(span.start, span.end, offset_map)
            tracker.extracted_sequence = seq
            tracker.recovery_method = "user_disambiguation"
            tracker.candidate_located = True
            tracker.alphabet_valid = True
            tracker.boundaries_verified = True
            tracker.completeness_verified = True
            tracker.source_fidelity_verified = True
            tracker.field_supported = True
            tracker.record_decision("verified", "success", "Deterministically verified via user-disambiguated selection.")
            rec = tracker.build_record()
            return ExtractionResponse(
                sequence=seq,
                validation_status="verified",
                source_match=True,
                boundaries_verified=True,
                completeness_verified=True,
                recovery_method="user_disambiguation",
                anchors_verified=False,
                source_span=span,
                message="Deterministically verified from user-disambiguated source span.",
                provenance=rec,
                redacted_provenance=rec.to_redacted_dict(),
                format_detected="user_disambiguation",
                plain_language_verdict="Verified: authentic sequence deterministically verified from user-selected candidate span.",
            )

    # 3. AI Scout localization when anchors/quotes are not provided
    if candidate_quote is None and anchor_before is None and anchor_after is None and use_ai:
        try:
            scout = ScoutAgent()
            tracker.llm_attempts += 1
            logger.info("Calling Ollama Scout agent (%s) for field '%s' (token_mask=%s)...", scout.client.model, field_type, use_token_mask)
            proposal = scout.propose_with_llm(document_text, field_type, alphabet, use_token_mask=use_token_mask)
            if proposal and proposal.candidate_quote:
                tracker.ai_scout_used = True
                tracker.scout_model = scout.client.model
                tracker.scout_proposal = proposal.model_dump()
                candidate_quote = proposal.candidate_quote
                anchor_before = proposal.anchor_before
                anchor_after = proposal.anchor_after
                logger.info(
                    "Ollama Scout proposed sequence quote '%s' (before: '%s', after: '%s'). Forwarding to deterministic verifier.",
                    proposal.candidate_quote,
                    proposal.anchor_before,
                    proposal.anchor_after,
                )
        except Exception as exc:
            logger.warning("Ollama Scout proposal encountered error (%s). Proceeding with deterministic fallback.", exc)

    # 4. If candidate quote or anchors are provided, route through anchor recovery
    if candidate_quote is not None or anchor_before is not None or anchor_after is not None:
        recovery_result = recover_with_anchors(
            document_text=document_text,
            candidate_quote=candidate_quote,
            anchor_before=anchor_before,
            anchor_after=anchor_after,
            field_type=field_type,
            alphabet=alphabet,
            allow_iupac=allow_iupac
        )

        for op in recovery_result.normalization_ops:
            tracker.add_normalization_op(op)

        tracker.recovery_method = recovery_result.recovery_method
        tracker.anchors_verified = recovery_result.anchors_verified
        tracker.anchor_verification = recovery_result.anchor_verification
        tracker.candidate_located = recovery_result.candidate_located
        tracker.alphabet_valid = recovery_result.alphabet_valid
        tracker.boundaries_verified = recovery_result.boundaries_verified
        tracker.completeness_verified = recovery_result.completeness_verified
        tracker.source_fidelity_verified = recovery_result.source_fidelity_verified
        tracker.field_supported = recovery_result.field_supported

        if recovery_result.source_span:
            tracker.set_source_location(
                recovery_result.source_span.start,
                recovery_result.source_span.end,
                recovery_result.offset_mapping
            )

        rec = tracker.build_record()
        fallback_candidates = find_candidate_spans(document_text, field_type, alphabet, allow_iupac)
        cand_dicts = [
            {"start": c.start, "end": c.end, "preview": document_text[c.start:min(c.end, c.start+40)], "label": c.field_label}
            for c in fallback_candidates
        ]

        if recovery_result.success and recovery_result.status == "verified":
            tracker.extracted_sequence = recovery_result.sequence
            tracker.record_decision("verified", "success", recovery_result.message)
            rec = tracker.build_record()
            return ExtractionResponse(
                sequence=recovery_result.sequence,
                validation_status="verified",
                source_match=True,
                boundaries_verified=recovery_result.boundaries_verified,
                completeness_verified=recovery_result.completeness_verified,
                recovery_method=recovery_result.recovery_method,
                anchors_verified=recovery_result.anchors_verified,
                source_span=recovery_result.source_span,
                message=recovery_result.message,
                provenance=rec,
                redacted_provenance=rec.to_redacted_dict(),
                scout_proposal=tracker.scout_proposal,
                critic_evaluation=tracker.critic_evaluation,
                format_detected=fmt_name,
                plain_language_verdict=make_plain_verdict("verified", recovery_result.message, format_name=fmt_name),
            )
        else:
            final_status = recovery_result.status
            tracker.record_decision(final_status, "abstained" if final_status == "abstained" else "rejected", recovery_result.message)
            rec = tracker.build_record()
            return ExtractionResponse(
                sequence=None,
                validation_status=final_status,
                source_match=False,
                boundaries_verified=recovery_result.boundaries_verified,
                completeness_verified=recovery_result.completeness_verified,
                recovery_method=recovery_result.recovery_method,
                anchors_verified=recovery_result.anchors_verified,
                source_span=recovery_result.source_span,
                error_code=recovery_result.error_code,
                message=recovery_result.message,
                provenance=rec,
                redacted_provenance=rec.to_redacted_dict(),
                scout_proposal=tracker.scout_proposal,
                critic_evaluation=tracker.critic_evaluation,
                candidate_spans=cand_dicts if len(cand_dicts) > 1 else None,
                format_detected=fmt_name,
                plain_language_verdict=make_plain_verdict(final_status, recovery_result.message, len(cand_dicts), format_name=fmt_name),
            )

    # 5. No candidate quote or anchors provided: deterministic field discovery
    critic = ContextCritic()
    candidates = find_candidate_spans(document_text, field_type, alphabet, allow_iupac)
    cand_dicts = [
        {"start": c.start, "end": c.end, "preview": document_text[c.start:min(c.end, c.start+40)], "label": c.field_label}
        for c in candidates
    ]

    if not candidates:
        tracker.record_decision("abstained", "abstained", "NO_SEQUENCE_FOUND")
        rec = tracker.build_record()
        return ExtractionResponse(
            sequence=None,
            validation_status="abstained",
            source_match=False,
            boundaries_verified=False,
            completeness_verified=False,
            recovery_method=None,
            anchors_verified=False,
            source_span=None,
            error_code="NO_SEQUENCE_FOUND",
            message="No sequence matching field criteria found in document.",
            provenance=rec,
            redacted_provenance=rec.to_redacted_dict(),
            scout_proposal=tracker.scout_proposal,
            critic_evaluation=tracker.critic_evaluation,
            format_detected=fmt_name,
            plain_language_verdict="Not sure — no sequence content found in document matching requested alphabet criteria.",
        )

    # Evaluate candidates by field support (using Ollama Context Critic if use_ai=True)
    supported_candidates: List[CandidateSpan] = []
    for cand in candidates:
        if use_ai:
            field_ok, critic_msg = critic.evaluate_with_llm(document_text, cand.start, cand.end, field_type)
            tracker.critic_evaluation = critic_msg
        else:
            field_ok, critic_msg = critic.evaluate_deterministic(document_text, cand.start, cand.end, field_type)
        if field_ok:
            supported_candidates.append(cand)

    if len(supported_candidates) == 1:
        chosen = supported_candidates[0]
        seq, offset_map, norm_ops, invalids = parse_sequence_block(
            document_text, chosen.start, chosen.end, alphabet, allow_iupac
        )

        for op in norm_ops:
            tracker.add_normalization_op(op)

        if invalids:
            tracker.record_decision("rejected", "rejected", f"INVALID_NUCLEOTIDE_CHARACTERS: {','.join(set(invalids))}")
            rec = tracker.build_record()
            return ExtractionResponse(
                sequence=None,
                validation_status="rejected",
                source_match=False,
                boundaries_verified=False,
                completeness_verified=False,
                error_code="INVALID_NUCLEOTIDE_CHARACTERS",
                message=f"Invalid nucleotide characters: {','.join(set(invalids))}",
                provenance=rec,
                redacted_provenance=rec.to_redacted_dict(),
                scout_proposal=tracker.scout_proposal,
                critic_evaluation=tracker.critic_evaluation,
                format_detected=fmt_name,
                plain_language_verdict=f"Rejected — invalid nucleotide characters detected: {','.join(set(invalids))}.",
            )

        assert offset_map is not None
        span = SourceSpan(start=offset_map[0], end=offset_map[-1] + 1)
        tracker.set_source_location(span.start, span.end, offset_map)
        tracker.extracted_sequence = seq
        tracker.recovery_method = "field_context_search"
        tracker.candidate_located = True
        tracker.alphabet_valid = True
        tracker.boundaries_verified = True
        tracker.completeness_verified = True
        tracker.source_fidelity_verified = True
        tracker.field_supported = True
        tracker.record_decision("verified", "success", "Deterministically extracted from field context.")
        rec = tracker.build_record()

        return ExtractionResponse(
            sequence=seq,
            validation_status="verified",
            source_match=True,
            boundaries_verified=True,
            completeness_verified=True,
            recovery_method="field_context_search",
            anchors_verified=False,
            source_span=span,
            message="Deterministically extracted and verified from field context.",
            provenance=rec,
            redacted_provenance=rec.to_redacted_dict(),
            scout_proposal=tracker.scout_proposal,
            critic_evaluation=tracker.critic_evaluation,
            format_detected=fmt_name,
            plain_language_verdict=make_plain_verdict("verified", "Deterministically extracted from field context.", format_name=fmt_name),
        )

    elif len(supported_candidates) > 1:
        tracker.record_decision("abstained", "abstained", "AMBIGUOUS_SOURCE_LOCATION")
        rec = tracker.build_record()
        return ExtractionResponse(
            sequence=None,
            validation_status="abstained",
            source_match=False,
            boundaries_verified=False,
            completeness_verified=False,
            recovery_method=None,
            anchors_verified=False,
            error_code="AMBIGUOUS_SOURCE_LOCATION",
            message="Multiple candidate sequence locations remain plausible for the requested field.",
            provenance=rec,
            redacted_provenance=rec.to_redacted_dict(),
            scout_proposal=tracker.scout_proposal,
            critic_evaluation=tracker.critic_evaluation,
            candidate_spans=cand_dicts,
            format_detected=fmt_name,
            plain_language_verdict=make_plain_verdict("abstained", "Multiple candidate sequence locations remain plausible.", len(supported_candidates), format_name=fmt_name),
        )
    else:
        tracker.record_decision("abstained", "abstained", "CONTEXT_FIELD_MISMATCH")
        rec = tracker.build_record()
        return ExtractionResponse(
            sequence=None,
            validation_status="abstained",
            source_match=False,
            boundaries_verified=False,
            completeness_verified=False,
            recovery_method=None,
            anchors_verified=False,
            error_code="CONTEXT_FIELD_MISMATCH",
            message="Found sequences do not match the requested semantic field context.",
            provenance=rec,
            redacted_provenance=rec.to_redacted_dict(),
            scout_proposal=tracker.scout_proposal,
            critic_evaluation=tracker.critic_evaluation,
            candidate_spans=cand_dicts if len(cand_dicts) > 1 else None,
            format_detected=fmt_name,
            plain_language_verdict=make_plain_verdict("abstained", "CONTEXT_FIELD_MISMATCH", len(cand_dicts), format_name=fmt_name),
        )
