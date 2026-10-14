"""
Privacy & Security Masking module for HelixGuard (Round 2 Hardening).

CRITICAL SECURITY INVARIANT:
The LLM must never receive raw nucleotide sequences in token-masked mode.
This module deterministically tokenizes all nucleotide sequences and common
patient identifiers (names, MRNs) before passing document text to an LLM.

- Nucleotide sequences are replaced with tokens like `<SEQ_0, 48 nt>`.
- Patient names and MRNs are replaced with `<NAME_REDACTED>` and `<MRN_REDACTED>`.
- A bidirectional registry maps tokens back to exact source spans.
- Final sequence verification is ALWAYS performed deterministically on the raw source.
"""

import re
from typing import Dict, List, Optional, Tuple, NamedTuple
from pydantic import BaseModel, Field


class TokenInfo(BaseModel):
    """Metadata tracking a masked sequence token back to original text."""
    token: str
    original_start: int
    original_end: int
    length: int
    raw_sequence: str
    field_hint: Optional[str] = None


class MaskedDocument(BaseModel):
    """A sanitized document safe for LLM consumption with token registry."""
    masked_text: str
    token_map: Dict[str, TokenInfo]
    tokens: List[TokenInfo]
    patient_redactions_count: int = 0
    contains_raw_nucleotides: bool = False


# Matches nucleotide runs of 6 or more characters (DNA and RNA)
NUCLEOTIDE_RUN_REGEX = re.compile(
    r"\b([ACGTUacgtu\s\n]{6,})\b"
)

# Patient identifier patterns (common in clinical / lab reports)
PATIENT_NAME_REGEX = re.compile(
    r"(?i)\b(?:Patient(?:\s+Name)?|Patient\s*ID|Subject)\s*:\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)"
)
PATIENT_MRN_REGEX = re.compile(
    r"(?i)\b(?:MRN|Medical\s*Record\s*(?:Number|#)?|Specimen\s*ID|Case\s*(?:#|No))\s*:\s*([A-Za-z0-9_-]+)"
)


def mask_document_for_llm(
    document_text: str,
    alphabet: str = "DNA",
    min_length: int = 6
) -> MaskedDocument:
    """
    Sanitizes document text so that no nucleotide sequences or direct patient identifiers
    are sent to an external or local LLM.

    Args:
        document_text: The authoritative raw document string.
        alphabet: Target alphabet ('DNA' or 'RNA').
        min_length: Minimum nucleotide run length to tokenize (default: 6).

    Returns:
        MaskedDocument containing the sanitized text and token dereference mapping.
    """
    if not document_text:
        return MaskedDocument(masked_text="", token_map={}, tokens=[])

    # 1. Identify all nucleotide sequence blocks
    # Build candidate matches with their original offsets
    valid_chars = set("ACGTacgt \t\n\r") if alphabet.upper() == "DNA" else set("ACGUacgu \t\n\r")

    # We first scan for candidate sequence sections
    # Look for both explicit field lines (e.g. "Observed sequence: ATCG...") and raw sequence blocks
    candidates: List[Tuple[int, int, str]] = []

    # Find contiguous nucleotide-like runs
    for match in re.finditer(r"\b([A-Za-z\s]{6,})\b", document_text):
        chunk = match.group(1)
        # Check if characters are predominantly nucleotides
        clean_bases = re.sub(r"\s+", "", chunk)
        if len(clean_bases) >= min_length and all(c in "ACGTUacgtu" for c in clean_bases):
            candidates.append((match.start(1), match.end(1), clean_bases.upper()))

    # Merge overlapping/adjacent spans and sort
    sorted_spans = sorted(candidates, key=lambda x: x[0])
    merged_spans: List[Tuple[int, int, str]] = []
    for span in sorted_spans:
        if not merged_spans:
            merged_spans.append(span)
        else:
            prev_start, prev_end, prev_seq = merged_spans[-1]
            if span[0] <= prev_end:
                # Overlap: extend
                new_end = max(prev_end, span[1])
                raw_chunk = document_text[prev_start:new_end]
                clean = re.sub(r"[^A-Za-z]", "", raw_chunk).upper()
                merged_spans[-1] = (prev_start, new_end, clean)
            else:
                merged_spans.append(span)

    # 2. Build token map and construct sanitized text
    token_map: Dict[str, TokenInfo] = {}
    tokens_list: List[TokenInfo] = []

    # We replace from end to beginning to preserve string offsets for patient regex later,
    # or build a reconstructed string
    result_parts: List[str] = []
    last_idx = 0

    for i, (start, end, raw_seq) in enumerate(merged_spans):
        token_label = f"<SEQ_{i}, {len(raw_seq)} nt>"
        token_info = TokenInfo(
            token=token_label,
            original_start=start,
            original_end=end,
            length=len(raw_seq),
            raw_sequence=raw_seq
        )
        token_map[token_label] = token_info
        token_map[f"<SEQ_{i}>"] = token_info  # Allow short reference format
        tokens_list.append(token_info)

        result_parts.append(document_text[last_idx:start])
        result_parts.append(token_label)
        last_idx = end

    result_parts.append(document_text[last_idx:])
    sanitized = "".join(result_parts)

    # 3. Mask patient identifiers in the sanitized text
    redaction_count = 0

    def mask_name(match):
        nonlocal redaction_count
        redaction_count += 1
        prefix = match.group(0).split(":")[0]
        return f"{prefix}: <NAME_REDACTED>"

    def mask_mrn(match):
        nonlocal redaction_count
        redaction_count += 1
        prefix = match.group(0).split(":")[0]
        return f"{prefix}: <MRN_REDACTED>"

    sanitized = PATIENT_NAME_REGEX.sub(mask_name, sanitized)
    sanitized = PATIENT_MRN_REGEX.sub(mask_mrn, sanitized)

    # Verify no raw nucleotide run of 6+ bases remains in the text
    # (Checking uppercase letters that are only ACGT/U)
    has_raw_nucleotides = False
    for word in re.findall(r"\b([A-Z]{6,})\b", sanitized):
        if all(c in "ACGTU" for c in word):
            has_raw_nucleotides = True
            break

    return MaskedDocument(
        masked_text=sanitized,
        token_map=token_map,
        tokens=tokens_list,
        patient_redactions_count=redaction_count,
        contains_raw_nucleotides=has_raw_nucleotides
    )


def dereference_token(
    token_or_text: str,
    token_map: Dict[str, TokenInfo]
) -> Optional[TokenInfo]:
    """
    Dereferences a token string returned by an LLM (e.g. '<SEQ_0>' or '<SEQ_0, 48 nt>')
    back to its TokenInfo and raw source coordinates.
    """
    clean_token = token_or_text.strip()
    if clean_token in token_map:
        return token_map[clean_token]

    # Try extracting <SEQ_\d+> pattern
    match = re.search(r"(<SEQ_\d+(?:,\s*\d+\s*nt)?>)", clean_token)
    if match:
        extracted = match.group(1)
        if extracted in token_map:
            return token_map[extracted]
        # Try base tag e.g. <SEQ_0>
        base_tag = match.group(1).split(",")[0].strip() + (">" if not match.group(1).split(",")[0].endswith(">") else "")
        if base_tag in token_map:
            return token_map[base_tag]

    return None
