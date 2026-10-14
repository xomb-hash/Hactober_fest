"""
Base interface and data models for genomic document format adapters.
HelixGuard Round 2 Hardening.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class AdapterCandidate(BaseModel):
    """A located genomic sequence candidate extracted by a format adapter."""
    start: int = Field(..., description="Zero-based start offset in the original document text")
    end: int = Field(..., description="Zero-based end offset in the original document text")
    sequence: str = Field(..., description="Normalized uppercase extracted nucleotide sequence")
    offset_map: List[int] = Field(..., description="Character-level mapping to original document indices")
    header_or_id: Optional[str] = Field(None, description="Record identifier, header, or field label")
    format_name: str = Field(..., description="Name of the format adapter (e.g. fasta, genbank, fastq)")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class BaseFormatAdapter(ABC):
    """Abstract base class for format-specific sequence extraction."""

    @property
    @abstractmethod
    def format_name(self) -> str:
        """Name of the format handled by this adapter."""
        pass

    @abstractmethod
    def can_handle(self, text: str) -> bool:
        """Determines if the document text matches this specific format."""
        pass

    @abstractmethod
    def parse_candidates(
        self,
        text: str,
        alphabet: str = "DNA",
        allow_iupac: bool = False
    ) -> List[AdapterCandidate]:
        """
        Extracts candidate sequences from the document, tracking exact character offsets.
        """
        pass
