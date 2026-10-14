"""
FASTA format adapter for HelixGuard.
Handles single and multi-FASTA records (>header followed by wrapped sequence lines),
tracking exact zero-based source offsets for every extracted base.
"""

import re
from typing import List, Set
from middleware.adapters.base import BaseFormatAdapter, AdapterCandidate


class FastaAdapter(BaseFormatAdapter):
    """Adapter for FASTA formatted files and text excerpts."""

    @property
    def format_name(self) -> str:
        return "fasta"

    def can_handle(self, text: str) -> bool:
        """FASTA files start with '>' on the first non-empty line."""
        for line in text.splitlines():
            s = line.strip()
            if not s:
                continue
            return s.startswith(">")
        return False

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

        # Regex matching >header line and following sequence content until next > or EOF
        record_re = re.compile(r"(?:^|\n)>\s*([^\n\r]+)\r?\n([\s\S]*?)(?=(?:\n>|\Z))")

        for match in record_re.finditer(text):
            header = match.group(1).strip()
            seq_block_start = match.start(2)
            seq_block = match.group(2)

            # Trace individual bases and their exact character positions
            extracted_chars: List[str] = []
            offset_map: List[int] = []

            for rel_idx, char in enumerate(seq_block):
                if char.isspace() or char in ("\n", "\r", "\t"):
                    continue
                abs_idx = seq_block_start + rel_idx
                if char in valid_chars:
                    extracted_chars.append(char.upper())
                    offset_map.append(abs_idx)
                elif char == ";":  # FASTA comment line within sequence
                    continue
                else:
                    # Invalid base encountered in strict FASTA mode
                    pass

            if extracted_chars and offset_map:
                candidates.append(AdapterCandidate(
                    start=offset_map[0],
                    end=offset_map[-1] + 1,
                    sequence="".join(extracted_chars),
                    offset_map=offset_map,
                    header_or_id=header,
                    format_name="fasta",
                    metadata={"header": header, "length": len(extracted_chars)}
                ))

        return candidates
