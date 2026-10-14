"""
Clinical / Lab Report Text format adapter for HelixGuard.
Handles semi-structured reports with field labels (Observed sequence, Variant, Query, etc.),
tracking exact zero-based source offsets for every extracted base.
"""

import re
from typing import List, Set
from middleware.adapters.base import BaseFormatAdapter, AdapterCandidate


class TextReportAdapter(BaseFormatAdapter):
    """Adapter for unstructured and semi-structured laboratory and clinical reports."""

    @property
    def format_name(self) -> str:
        return "clinical_report"

    def can_handle(self, text: str) -> bool:
        # Default fallback adapter for any text report
        return True

    def parse_candidates(
        self,
        text: str,
        alphabet: str = "DNA",
        allow_iupac: bool = False
    ) -> List[AdapterCandidate]:
        candidates: List[AdapterCandidate] = []
        valid_chars = set("ACGTacgt") if alphabet.upper() == "DNA" else set("ACGUacgu")
        if allow_iupac:
            valid_chars.update(set("RYSWKMBDHVNryswkmbdhvn"))

        # Field patterns common in reports: "Observed sequence:", "Variant:", "Query:", "Sample:"
        field_re = re.compile(
            r"(?i)\b(?P<label>(?:observed(?:\s+sequence)?|variant(?:\s+sequence)?|sample|tumor(?:\s+dna)?|query|specimen(?:\s+seq)?))\s*[:=]\s*(?P<content>[^\n\r]+(?:\n[ \t]+[^\n\r]+)*)"
        )

        for match in field_re.finditer(text):
            label = match.group("label").strip()
            content = match.group("content")
            content_start = match.start("content")

            extracted_chars: List[str] = []
            offset_map: List[int] = []

            for i, c in enumerate(content):
                if c.isspace() or c.isdigit() or c in ("-", "_", ":"):
                    continue
                if c in valid_chars:
                    extracted_chars.append(c.upper())
                    offset_map.append(content_start + i)

            if len(extracted_chars) >= 4 and offset_map:
                candidates.append(AdapterCandidate(
                    start=offset_map[0],
                    end=offset_map[-1] + 1,
                    sequence="".join(extracted_chars),
                    offset_map=offset_map,
                    header_or_id=label,
                    format_name="clinical_report",
                    metadata={"field_label": label, "length": len(extracted_chars)}
                ))

        # Fallback: scan for any contiguous nucleotide run of length >= 6
        if not candidates:
            for match in re.finditer(r"\b([A-Za-z]{6,})\b", text):
                word = match.group(1)
                clean_bases = [c.upper() for c in word if c in valid_chars]
                if len(clean_bases) == len(word):
                    offset_map = list(range(match.start(), match.end()))
                    candidates.append(AdapterCandidate(
                        start=match.start(),
                        end=match.end(),
                        sequence="".join(clean_bases),
                        offset_map=offset_map,
                        header_or_id=None,
                        format_name="clinical_report",
                        metadata={"type": "raw_run", "length": len(clean_bases)}
                    ))

        return candidates
