"""
FASTQ format adapter for HelixGuard.
Handles 4-line sequencing read blocks (@header, sequence, +, quality),
tracking exact zero-based source offsets for every extracted base.
"""

import re
from typing import List
from middleware.adapters.base import BaseFormatAdapter, AdapterCandidate


class FastqAdapter(BaseFormatAdapter):
    """Adapter for FASTQ sequencing reads."""

    @property
    def format_name(self) -> str:
        return "fastq"

    def can_handle(self, text: str) -> bool:
        """FASTQ files start with '@' on the first line and have a '+' separator line."""
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        if len(lines) >= 4 and lines[0].startswith("@") and lines[2].startswith("+"):
            return True
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

        # Find 4-line blocks
        # Line 1: @ID
        # Line 2: Sequence
        # Line 3: +
        # Line 4: Quality
        pattern = re.compile(
            r"(^|\n)@([^\n\r]+)\r?\n([^\n\r]+)\r?\n\+[^\n\r]*\r?\n([^\n\r]+)",
            re.MULTILINE
        )

        for match in pattern.finditer(text):
            read_id = match.group(2).strip()
            seq_line = match.group(3)
            seq_abs_start = match.start(3)

            extracted_chars: List[str] = []
            offset_map: List[int] = []

            for i, c in enumerate(seq_line):
                if c in valid_chars:
                    extracted_chars.append(c.upper())
                    offset_map.append(seq_abs_start + i)

            if extracted_chars and offset_map:
                candidates.append(AdapterCandidate(
                    start=offset_map[0],
                    end=offset_map[-1] + 1,
                    sequence="".join(extracted_chars),
                    offset_map=offset_map,
                    header_or_id=read_id,
                    format_name="fastq",
                    metadata={"read_id": read_id, "length": len(extracted_chars)}
                ))

        return candidates
