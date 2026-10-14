"""
Format Adapters package for HelixGuard (Round 2 Hardening).
Provides automated format detection and offset-tracked candidate sequence extraction
for FASTA, GenBank (ORIGIN), FASTQ, and semi-structured clinical/lab reports.
"""

from typing import List, Tuple
from middleware.adapters.base import BaseFormatAdapter, AdapterCandidate
from middleware.adapters.fasta_adapter import FastaAdapter
from middleware.adapters.genbank_adapter import GenBankAdapter
from middleware.adapters.fastq_adapter import FastqAdapter
from middleware.adapters.text_adapter import TextReportAdapter

# Ordered by specificity (specialized structured formats checked before generic text)
FORMAT_ADAPTERS: List[BaseFormatAdapter] = [
    FastaAdapter(),
    GenBankAdapter(),
    FastqAdapter(),
    TextReportAdapter(),
]


def detect_and_parse_format(
    text: str,
    alphabet: str = "DNA",
    allow_iupac: bool = False
) -> Tuple[str, List[AdapterCandidate]]:
    """
    Auto-detects the format of the document and extracts candidate sequences
    with verified zero-based source offset mappings.

    Returns:
        (format_name, candidates)
    """
    if not text or not text.strip():
        return "empty", []

    for adapter in FORMAT_ADAPTERS:
        if adapter.can_handle(text):
            candidates = adapter.parse_candidates(text, alphabet=alphabet, allow_iupac=allow_iupac)
            if candidates or adapter.format_name in ("fasta", "genbank", "fastq"):
                return adapter.format_name, candidates

    # Default fallback
    fallback = TextReportAdapter()
    return fallback.format_name, fallback.parse_candidates(text, alphabet=alphabet, allow_iupac=allow_iupac)
