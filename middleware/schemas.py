"""
Pydantic schemas for HelixGuard middleware.
Defines data structures for extraction, alignment, provenance, and verification.
"""

from typing import List, Optional, Literal
from pydantic import BaseModel, Field


class SourceSpan(BaseModel):
    """Zero-based, half-open interval [start, end) referring to original document."""
    start: int = Field(..., description="Zero-based start offset in the original document")
    end: int = Field(..., description="Zero-based half-open end offset in the original document")


class AnchorVerification(BaseModel):
    """Detailed anchor verification metrics."""
    anchor_before_found: bool = False
    anchor_after_found: bool = False
    candidate_quote_found: bool = False
    ordering_valid: bool = False
    anchor_before_span: Optional[SourceSpan] = None
    anchor_after_span: Optional[SourceSpan] = None
    candidate_quote_span: Optional[SourceSpan] = None


class ProvenanceRecord(BaseModel):
    """Comprehensive traceability record for sequence extraction."""
    request_id: Optional[str] = None
    input_hash: str = Field(..., description="SHA-256 hash of the original document_text")
    source_span: Optional[SourceSpan] = None
    source_excerpt: Optional[str] = None
    extracted_sequence: Optional[str] = None
    alphabet: str = "DNA"
    normalization_ops: List[str] = Field(default_factory=list)
    offset_mapping: Optional[List[int]] = Field(
        default=None,
        description="Index-to-index mapping from extracted sequence character to original document offset"
    )
    candidate_quote: Optional[str] = None
    anchor_before: Optional[str] = None
    anchor_after: Optional[str] = None
    anchors_verified: bool = False
    anchor_verification: Optional[AnchorVerification] = None
    recovery_method: Optional[str] = None
    llm_attempts: int = 0

    # Verification checklist flags
    candidate_located: bool = False
    alphabet_valid: bool = False
    boundaries_verified: bool = False
    completeness_verified: bool = False
    source_fidelity_verified: bool = False
    field_supported: bool = False
    eligible_for_alignment: bool = False

    validation_status: str = "unverified"
    final_status: str = "abstained"
    reason: Optional[str] = None
    timestamp: Optional[str] = None


class ExtractionRequest(BaseModel):
    """Request payload for deterministic sequence extraction."""
    document_text: str = Field(..., description="Original raw document text containing genomic data")
    field_type: str = Field("observed_sequence", description="Target semantic field (e.g. observed_sequence)")
    sequence_alphabet: Literal["DNA", "RNA"] = Field("DNA", description="Target sequence alphabet")
    candidate_quote: Optional[str] = Field(None, description="Optional LLM-proposed excerpt quote")
    anchor_before: Optional[str] = Field(None, description="Optional text immediately preceding candidate")
    anchor_after: Optional[str] = Field(None, description="Optional text immediately following candidate")
    allow_iupac: bool = Field(False, description="Whether IUPAC ambiguity codes are accepted")


class ExtractionResponse(BaseModel):
    """Response payload for sequence extraction with full verification details."""
    sequence: Optional[str] = Field(None, description="Verified extracted sequence, or None if abstained")
    validation_status: Literal["verified", "unverified", "abstained", "rejected"] = Field(
        ..., description="Verification status"
    )
    source_match: bool = Field(..., description="Whether sequence was deterministically matched to source")
    boundaries_verified: bool = Field(..., description="Whether sequence boundaries were independently verified")
    completeness_verified: bool = Field(..., description="Whether sequence is complete without truncation")
    recovery_method: Optional[str] = Field(None, description="Method used to recover sequence if anchors failed")
    anchors_verified: Optional[bool] = Field(None, description="Whether anchors were strictly verified")
    source_span: Optional[SourceSpan] = Field(None, description="Span in the original document")
    error_code: Optional[str] = Field(None, description="Error or abstention code")
    message: Optional[str] = Field(None, description="Descriptive human-readable explanation")
    provenance: Optional[ProvenanceRecord] = Field(None, description="Full audit provenance record")


class MaxCell(BaseModel):
    """Matrix cell coordinates with maximum score."""
    row: int
    column: int


class MatrixDimensions(BaseModel):
    """Dimensions of dynamic programming matrix."""
    rows: int
    columns: int


class ScoringConfig(BaseModel):
    """Scoring parameters for local alignment."""
    match: int = 2
    mismatch: int = -1
    gap: int = -1


class AlignmentRequest(BaseModel):
    """Request sent to C++ Smith-Waterman alignment engine."""
    reference_sequence: str
    query_sequence: str
    scoring: Optional[ScoringConfig] = None


class AlignmentResponse(BaseModel):
    """Response returned by C++ Smith-Waterman alignment engine."""
    status: str
    alignment_score: int
    max_cell: Optional[MaxCell] = None
    matrix: List[List[int]] = Field(default_factory=list)
    matrix_dimensions: Optional[MatrixDimensions] = None
    scoring: Optional[ScoringConfig] = None


class ExtractAndAlignRequest(BaseModel):
    """Full pipeline request: extraction from document followed by alignment."""
    document_text: str
    reference_sequence: str
    field_type: str = "observed_sequence"
    sequence_alphabet: Literal["DNA", "RNA"] = "DNA"
    candidate_quote: Optional[str] = None
    anchor_before: Optional[str] = None
    anchor_after: Optional[str] = None
    allow_iupac: bool = False
    scoring: Optional[ScoringConfig] = None


class ExtractAndAlignResponse(BaseModel):
    """Full pipeline response."""
    status: Literal["success", "abstained", "rejected", "error"]
    extraction: ExtractionResponse
    alignment: Optional[AlignmentResponse] = None
