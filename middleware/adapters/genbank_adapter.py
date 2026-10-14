"""
GenBank format adapter for HelixGuard.
Handles GenBank records with ORIGIN blocks (numbered lines, 10-base spaced groupings),
tracking exact zero-based source offsets for every extracted base.
"""

import re
from typing import List, Set
from middleware.adapters.base import BaseFormatAdapter, AdapterCandidate


class GenBankAdapter(BaseFormatAdapter):
    """Adapter for GenBank flatfile records and ORIGIN sequence blocks."""

    @property
    def format_name(self) -> str:
        return "genbank"

    def can_handle(self, text: str) -> bool:
        """GenBank files typically start with 'LOCUS' or contain an 'ORIGIN' block."""
        upper = text[:2000].upper()
        return "LOCUS" in upper or "ORIGIN" in upper

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

        # Find locus / accession identifier if present
        locus_match = re.search(r"(?i)^LOCUS\s+([A-Za-z0-9_.-]+)", text, re.MULTILINE)
        locus_id = locus_match.group(1) if locus_match else None

        # Locate ORIGIN section
        origin_re = re.compile(r"(?i)\bORIGIN\s*\n([\s\S]*?)(?=(?:\n//|\Z))")
        for match in origin_re.finditer(text):
            seq_block_start = match.start(1)
            seq_block = match.group(1)

            extracted_chars: List[str] = []
            offset_map: List[int] = []

            # Line-by-line parsing: skip leading line numbers (e.g. "        1 ", "       61 ")
            lines = seq_block.splitlines(keepends=True)
            current_rel_idx = 0

            for line in lines:
                line_abs_start = seq_block_start + current_rel_idx
                # Match line number prefix
                num_match = re.match(r"^\s*(\d+)\s*", line)
                start_in_line = num_match.end() if num_match else 0

                for i in range(start_in_line, len(line)):
                    c = line[i]
                    if c in (" ", "\t", "\r", "\n"):
                        continue
                    if c in valid_chars:
                        extracted_chars.append(c.upper())
                        offset_map.append(line_abs_start + i)

                current_rel_idx += len(line)

            if extracted_chars and offset_map:
                candidates.append(AdapterCandidate(
                    start=offset_map[0],
                    end=offset_map[-1] + 1,
                    sequence="".join(extracted_chars),
                    offset_map=offset_map,
                    header_or_id=locus_id or "ORIGIN",
                    format_name="genbank",
                    metadata={"locus": locus_id, "length": len(extracted_chars)}
                ))

        return candidates
