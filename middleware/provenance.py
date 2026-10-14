"""
Provenance tracker for sequence extraction in HelixGuard.
Ensures full auditability, offset tracing back to raw source text, and verification checklist.
"""

import os
import hmac
import hashlib
from datetime import datetime, timezone
from typing import List, Optional
from middleware.schemas import SourceSpan, AnchorVerification, ProvenanceRecord


class ProvenanceTracker:
    """
    Constructs and manages a ProvenanceRecord throughout the extraction lifecycle.
    """

    def __init__(
        self,
        document_text: str,
        alphabet: str = "DNA",
        request_id: Optional[str] = None,
        salt: Optional[str] = None
    ) -> None:
        self.document_text = document_text
        self.input_hash = self.compute_hash(document_text)
        self.input_hmac = self.compute_hmac(document_text, salt=salt)
        self.alphabet = alphabet
        self.request_id = request_id

        self.source_span: Optional[SourceSpan] = None
        self.source_excerpt: Optional[str] = None
        self.extracted_sequence: Optional[str] = None
        self.normalization_ops: List[str] = []
        self.offset_mapping: Optional[List[int]] = None

        self.candidate_quote: Optional[str] = None
        self.anchor_before: Optional[str] = None
        self.anchor_after: Optional[str] = None
        self.anchors_verified: bool = False
        self.anchor_verification: Optional[AnchorVerification] = None
        self.recovery_method: Optional[str] = None
        self.llm_attempts: int = 0
        self.ai_scout_used: bool = False
        self.scout_model: Optional[str] = None
        self.scout_proposal: Optional[dict] = None
        self.critic_evaluation: Optional[str] = None

        # Verification flags
        self.candidate_located: bool = False
        self.alphabet_valid: bool = False
        self.boundaries_verified: bool = False
        self.completeness_verified: bool = False
        self.source_fidelity_verified: bool = False
        self.field_supported: bool = False
        self.eligible_for_alignment: bool = False

        self.validation_status: str = "unverified"
        self.final_status: str = "abstained"
        self.reason: Optional[str] = None

    @staticmethod
    def compute_hash(text: str) -> str:
        """Computes SHA-256 hash of raw input text."""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    @staticmethod
    def compute_hmac(text: str, salt: Optional[str] = None) -> str:
        """Computes salted HMAC-SHA256 of raw input text to prevent hash inversion or oracle attacks."""
        key = (salt or os.getenv("HMAC_SALT", "helixguard-deterministic-salt-2026")).encode("utf-8")
        return hmac.new(key, text.encode("utf-8"), hashlib.sha256).hexdigest()

    def add_normalization_op(self, op: str) -> None:
        """Records an explicit normalization operation applied during extraction."""
        if op not in self.normalization_ops:
            self.normalization_ops.append(op)

    def set_source_location(
        self,
        start: int,
        end: int,
        offset_mapping: Optional[List[int]] = None
    ) -> None:
        """
        Sets zero-based half-open [start, end) offsets in the original document_text
        and the character-level offset mapping.
        """
        self.source_span = SourceSpan(start=start, end=end)
        self.source_excerpt = self.document_text[start:end]
        self.offset_mapping = offset_mapping
        self.candidate_located = True

    def set_anchors(
        self,
        anchor_before: Optional[str],
        anchor_after: Optional[str],
        candidate_quote: Optional[str]
    ) -> None:
        """Records requested anchors and candidate quote."""
        self.anchor_before = anchor_before
        self.anchor_after = anchor_after
        self.candidate_quote = candidate_quote

    def set_anchor_verification(
        self,
        verified: bool,
        verification_details: Optional[AnchorVerification] = None
    ) -> None:
        """Sets anchor verification outcome."""
        self.anchors_verified = verified
        self.anchor_verification = verification_details

    def record_decision(
        self,
        validation_status: str,
        final_status: str,
        reason: Optional[str] = None
    ) -> None:
        """Records final verification decision and reason."""
        self.validation_status = validation_status
        self.final_status = final_status
        self.reason = reason
        self.eligible_for_alignment = (
            self.candidate_located
            and self.alphabet_valid
            and self.boundaries_verified
            and self.completeness_verified
            and self.source_fidelity_verified
            and self.field_supported
            and validation_status == "verified"
        )

    def build_record(self) -> ProvenanceRecord:
        """Builds immutable Pydantic ProvenanceRecord."""
        return ProvenanceRecord(
            request_id=self.request_id,
            input_hash=self.input_hash,
            input_hmac=self.input_hmac,
            source_span=self.source_span,
            source_excerpt=self.source_excerpt,
            extracted_sequence=self.extracted_sequence,
            alphabet=self.alphabet,
            normalization_ops=list(self.normalization_ops),
            offset_mapping=list(self.offset_mapping) if self.offset_mapping else None,
            candidate_quote=self.candidate_quote,
            anchor_before=self.anchor_before,
            anchor_after=self.anchor_after,
            anchors_verified=self.anchors_verified,
            anchor_verification=self.anchor_verification,
            recovery_method=self.recovery_method,
            llm_attempts=self.llm_attempts,
            ai_scout_used=self.ai_scout_used,
            scout_model=self.scout_model,
            scout_proposal=self.scout_proposal,
            critic_evaluation=self.critic_evaluation,
            candidate_located=self.candidate_located,
            alphabet_valid=self.alphabet_valid,
            boundaries_verified=self.boundaries_verified,
            completeness_verified=self.completeness_verified,
            source_fidelity_verified=self.source_fidelity_verified,
            field_supported=self.field_supported,
            eligible_for_alignment=self.eligible_for_alignment,
            validation_status=self.validation_status,
            final_status=self.final_status,
            reason=self.reason,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
