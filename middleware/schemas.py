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
    input_hmac: Optional[str] = Field(None, description="Salted HMAC-SHA256 for privacy-preserving verification")
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
    ai_scout_used: bool = False
    scout_model: Optional[str] = None
    scout_proposal: Optional[dict] = None
    critic_evaluation: Optional[str] = None

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

    def to_redacted_dict(self) -> dict:
        """Returns a privacy-safe provenance dictionary stripped of raw sequences and excerpts."""
        return {
            "request_id": self.request_id,
            "input_hmac": self.input_hmac or self.input_hash,
            "source_span": self.source_span.model_dump() if self.source_span else None,
            "alphabet": self.alphabet,
            "normalization_ops": self.normalization_ops,
            "recovery_method": self.recovery_method,
            "ai_scout_used": self.ai_scout_used,
            "candidate_located": self.candidate_located,
            "alphabet_valid": self.alphabet_valid,
            "boundaries_verified": self.boundaries_verified,
            "completeness_verified": self.completeness_verified,
            "source_fidelity_verified": self.source_fidelity_verified,
            "field_supported": self.field_supported,
            "eligible_for_alignment": self.eligible_for_alignment,
            "validation_status": self.validation_status,
            "final_status": self.final_status,
            "reason": self.reason,
            "timestamp": self.timestamp,
        }


class ExtractionRequest(BaseModel):
    """Request payload for deterministic sequence extraction."""
    document_text: str = Field(..., description="Original raw document text containing genomic data")
    field_type: str = Field("observed_sequence", description="Target semantic field (e.g. observed_sequence)")
    sequence_alphabet: Literal["DNA", "RNA"] = Field("DNA", description="Target sequence alphabet")
    candidate_quote: Optional[str] = Field(None, description="Optional LLM-proposed excerpt quote")
    anchor_before: Optional[str] = Field(None, description="Optional text immediately preceding candidate")
    anchor_after: Optional[str] = Field(None, description="Optional text immediately following candidate")
    allow_iupac: bool = Field(False, description="Whether IUPAC ambiguity codes are accepted")
    use_ai: bool = Field(True, description="Whether to query Ollama Cloud Scout for AI-assisted localization")
    use_token_mask: Optional[bool] = Field(None, description="Enforce token masking so no nucleotides reach LLM")
    selected_span: Optional[SourceSpan] = Field(None, description="User-selected span for interactive disambiguation")


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
    redacted_provenance: Optional[dict] = Field(None, description="Privacy-safe provenance stripped of raw sequences")
    scout_proposal: Optional[dict] = Field(None, description="Proposal returned by AI Scout agent")
    critic_evaluation: Optional[str] = Field(None, description="Evaluation returned by Context Critic agent")
    candidate_spans: Optional[List[dict]] = Field(None, description="Discovered candidate spans for human-in-the-loop disambiguation")
    format_detected: Optional[str] = Field(None, description="Detected format of document (e.g. fasta, genbank, clinical_report)")
    plain_language_verdict: Optional[str] = Field(None, description="User-facing plain-language verdict ('Verified' vs 'Not sure')")


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
    use_ai: bool = True
    use_token_mask: Optional[bool] = None
    selected_span: Optional[SourceSpan] = None
    scoring: Optional[ScoringConfig] = None


class ExtractAndAlignResponse(BaseModel):
    """Full pipeline response."""
    status: Literal["success", "abstained", "rejected", "error"]
    extraction: ExtractionResponse
    alignment: Optional[AlignmentResponse] = None


class DocumentUploadResponse(BaseModel):
    """Response returned upon uploading an arbitrary document file."""
    filename: str
    file_type: str
    text: str
    character_count: int
    message: str = "Document parsed successfully."


class GenomeMatchCandidate(BaseModel):
    """A ranked genome candidate from the viral reference database."""
    rank: int
    accession: str
    organism: str
    alignment_score: int
    matched_length: int
    target_start: int
    target_end: int
    shared_kmers: int
    low_complexity: bool = False
    has_poly_a_tail: bool = False


class GenomeIdentificationRequest(BaseModel):
    """Request to identify closest genome in the reference database."""
    query_sequence: str
    sequence_alphabet: Literal["DNA", "RNA"] = "DNA"
    top_k: int = 5
    score_margin_threshold: float = 0.03
    allow_iupac: bool = False


class GenomeIdentificationResponse(BaseModel):
    """Response identifying the closest genome(s) from multi-FASTA database."""
    status: Literal["success", "abstained", "no_match", "error"]
    query_sequence: str
    query_length: int
    total_candidates_evaluated: int
    top_candidates: List[GenomeMatchCandidate] = Field(default_factory=list)
    closest_match: Optional[GenomeMatchCandidate] = None
    abstain: bool = False
    abstain_reason: Optional[str] = None
    search_time_ms: float = 0.0


class ExtractAndIdentifyRequest(BaseModel):
    """Extracts sequence from document and identifies closest genome in database."""
    document_text: str
    field_type: str = "observed_sequence"
    sequence_alphabet: Literal["DNA", "RNA"] = "DNA"
    candidate_quote: Optional[str] = None
    anchor_before: Optional[str] = None
    anchor_after: Optional[str] = None
    allow_iupac: bool = False
    use_ai: bool = True
    use_token_mask: Optional[bool] = None
    selected_span: Optional[SourceSpan] = None
    top_k: int = 5


class ExtractAndIdentifyResponse(BaseModel):
    """Combined response: document extraction + viral genome identification."""
    status: Literal["success", "abstained", "rejected", "no_match", "error"]
    extraction: ExtractionResponse
    identification: Optional[GenomeIdentificationResponse] = None
    closest_organism: Optional[str] = None
    closest_accession: Optional[str] = None

