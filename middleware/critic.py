"""
Context Critic agent module for HelixGuard.
Evaluates whether a candidate sequence location is semantically consistent with the requested field.

IMPORTANT RULES:
- Must NOT rewrite sequences.
- Must NOT declare an unverified sequence correct.
- Must NOT override deterministic validation.
- Works deterministically without Ollama.
"""

import os
import re
import logging
from typing import Tuple, Optional, Dict, Any
import httpx

logger = logging.getLogger("helixguard.critic")

# Field keyword heuristics for deterministic context evaluation
FIELD_KEYWORDS = {
    "observed_sequence": {
        "positive": ["observed", "sample", "tumor", "patient", "query", "sequenced", "read", "isolate", "variant"],
        "negative": ["reference", "control", "wildtype", "wild-type", "ref:", "primer", "standard"]
    },
    "reference_sequence": {
        "positive": ["reference", "control", "wildtype", "wild-type", "standard", "ref:", "canonical"],
        "negative": ["observed", "sample", "tumor", "patient", "mutant", "isolate"]
    },
    "tumor_sequence": {
        "positive": ["tumor", "biopsy", "neoplasm", "cancer", "somatic", "observed"],
        "negative": ["germline", "normal", "reference", "control"]
    },
    "control_sequence": {
        "positive": ["control", "negative control", "positive control", "normal", "germline", "reference"],
        "negative": ["tumor", "patient variant", "isolate"]
    }
}


class ContextCritic:
    """
    Evaluates whether a candidate excerpt or location in the text
    matches the requested field semantics (e.g. observed vs reference).
    """

    def __init__(
        self,
        ollama_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout_seconds: float = 2.0
    ) -> None:
        self.ollama_url = ollama_url or os.getenv("OLLAMA_URL", "http://localhost:11434")
        self.model = model or os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
        self.timeout_seconds = timeout_seconds

    def evaluate_deterministic(
        self,
        document_text: str,
        span_start: int,
        span_end: int,
        field_type: str
    ) -> Tuple[bool, str]:
        """
        Purely deterministic context evaluation using proximity heuristics and negative-field detection.
        """
        if not document_text:
            return False, "Document text is empty."

        # Extract context window around sequence (up to 200 chars before, 100 after)
        ctx_start = max(0, span_start - 200)
        ctx_end = min(len(document_text), span_end + 100)
        pre_context = document_text[ctx_start:span_start].lower()
        post_context = document_text[span_end:ctx_end].lower()
        full_context = f"{pre_context} ... {post_context}"

        normalized_field = field_type.lower().replace("-", "_").replace(" ", "_")
        field_rules = FIELD_KEYWORDS.get(normalized_field)

        # If field is generic or not recognized, check if field_type itself appears in context
        field_terms = [t for t in normalized_field.split("_") if len(t) > 2]
        
        if field_rules:
            pos_matches = [w for w in field_rules["positive"] if w in pre_context]
            neg_matches = [w for w in field_rules["negative"] if w in pre_context]

            if neg_matches and not pos_matches:
                return False, f"Context matches conflicting field: '{neg_matches[0]}' rather than '{field_type}'."
            if pos_matches:
                return True, f"Context contains positive field marker: '{pos_matches[0]}'."

        # Fallback heuristic: check if field name tokens appear in preceding context
        for term in field_terms:
            if term in pre_context:
                return True, f"Field term '{term}' found in preceding context."

        # If no explicit conflicting field label is right before the span, accept as default compatible
        # unless there is an explicit conflicting field label immediately preceding
        for conflict_key, rules in FIELD_KEYWORDS.items():
            if conflict_key != normalized_field:
                for neg in rules["positive"]:
                    # If e.g. "Reference sequence:" immediately precedes the candidate
                    pattern = rf"{re.escape(neg)}\s*[:=]\s*$"
                    if re.search(pattern, pre_context.strip()):
                        return False, f"Candidate is preceded by conflicting field label '{neg}:'."

        return True, "No conflicting field labels found in context."

    def evaluate_with_llm(
        self,
        document_text: str,
        span_start: int,
        span_end: int,
        field_type: str
    ) -> Tuple[bool, str]:
        """
        Optionally asks local Ollama model to verify field consistency.
        Fails safely and falls back to deterministic heuristic if Ollama is unreachable.
        """
        # Guard: If Ollama URL is not set or unreachable, use deterministic
        try:
            ctx_start = max(0, span_start - 150)
            ctx_end = min(len(document_text), span_end + 100)
            excerpt = document_text[ctx_start:ctx_end]

            prompt = (
                f"You are a genomic document verification critic.\n"
                f"Document excerpt:\n'''{excerpt}'''\n"
                f"Question: Does the excerpt at this position represent the field '{field_type}'?\n"
                f"Answer exactly 'YES' or 'NO' followed by a short reason."
            )

            with httpx.Client(timeout=self.timeout_seconds) as client:
                resp = client.post(
                    f"{self.ollama_url.rstrip('/')}/api/generate",
                    json={"model": self.model, "prompt": prompt, "stream": False}
                )
                if resp.status_code == 200:
                    text_resp = resp.json().get("response", "").strip()
                    if text_resp.upper().startswith("YES"):
                        return True, f"Ollama confirmed field consistency: {text_resp}"
                    elif text_resp.upper().startswith("NO"):
                        return False, f"Ollama rejected field consistency: {text_resp}"
        except Exception as exc:
            logger.debug("Ollama context evaluation skipped or failed (%s). Using deterministic evaluation.", exc)

        # Fallback to deterministic evaluation
        return self.evaluate_deterministic(document_text, span_start, span_end, field_type)
