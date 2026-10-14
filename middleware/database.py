"""
Genomic Database module for Project HelixGuard.
Parses multi-FASTA reference databases (.fna), builds k-mer prefilter indices,
detects low-complexity/poly-A regions, and performs Smith-Waterman candidate ranking
to identify which genome an extracted query sequence is closest to.
"""

import os
import io
import re
import time
import math
import pickle
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Any
from pathlib import Path

import httpx

from middleware.schemas import (
    GenomeMatchCandidate,
    GenomeIdentificationResponse,
)

logger = logging.getLogger("helixguard.database")

# Default paths to check for the viral genomic database
DEFAULT_DB_FILENAMES = [
    "viral.1.1.genomic.fna",
    "../viral.1.1.genomic.fna",
    "/app/data/viral.1.1.genomic.fna",
    "data/viral.1.1.genomic.fna",
]


@dataclass
class GenomeRecord:
    """A parsed genome entry from the multi-FASTA reference database."""
    accession: str
    organism: str
    sequence: str
    length: int
    has_poly_a_tail: bool = False
    has_iupac: bool = False


def compute_sequence_complexity(seq: str, threshold: float = 1.2) -> Tuple[bool, float, float]:
    """
    Computes Shannon entropy and homopolymer frequency to detect low-complexity regions
    such as poly-A tails that could artificially inflate Smith-Waterman scores.
    Returns: (is_low_complexity, entropy, max_single_base_fraction)
    """
    if not seq:
        return True, 0.0, 1.0

    counts: Dict[str, int] = {}
    for ch in seq:
        counts[ch] = counts.get(ch, 0) + 1

    n = len(seq)
    entropy = -sum((c / n) * math.log2(c / n) for c in counts.values())
    max_freq = max(counts.values()) / n

    # Check for homopolymer runs of 12+ identical nucleotides (e.g. AAAAAAAAAAAA)
    has_homopolymer = bool(re.search(r"A{12,}|T{12,}|C{12,}|G{12,}", seq))

    is_low = (entropy < threshold) or (max_freq > 0.65) or has_homopolymer
    return is_low, entropy, max_freq


def parse_fna_records(
    filepath: str,
    max_records: Optional[int] = None,
    allow_iupac: bool = True
) -> List[GenomeRecord]:
    """
    Parses a multi-FASTA (.fna) file into normalized GenomeRecords.
    - Header: first token after '>' is accession, remainder is organism description.
    - Wrapped lines: concatenated until next header.
    - Alphabet: normalized to uppercase DNA ('U' converted to 'T').
    - Detects poly-A tails and IUPAC ambiguity codes.
    """
    records: List[GenomeRecord] = []
    if not os.path.exists(filepath):
        logger.warning("FNA file '%s' not found.", filepath)
        return records

    logger.info("Parsing multi-FASTA file: %s (allow_iupac=%s)...", filepath, allow_iupac)
    t0 = time.time()

    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        cur_acc: Optional[str] = None
        cur_org: str = ""
        cur_seq_parts: List[str] = []

        for line in f:
            if line.startswith(">"):
                if cur_acc:
                    full_seq = "".join(cur_seq_parts)
                    records.append(_create_record(cur_acc, cur_org, full_seq, allow_iupac))
                    if max_records and len(records) >= max_records:
                        cur_acc = None
                        break

                header_content = line[1:].strip()
                tokens = header_content.split(" ", 1)
                cur_acc = tokens[0].strip()
                cur_org = tokens[1].strip() if len(tokens) > 1 else cur_acc
                cur_seq_parts = []
            else:
                cur_seq_parts.append(line.strip().upper())

        if cur_acc:
            full_seq = "".join(cur_seq_parts)
            records.append(_create_record(cur_acc, cur_org, full_seq, allow_iupac))

    elapsed = time.time() - t0
    logger.info("Parsed %d genome records in %.2fs from %s", len(records), elapsed, filepath)
    return records


def _create_record(accession: str, organism: str, raw_seq: str, allow_iupac: bool) -> GenomeRecord:
    """Helper to normalize and validate a single genome record."""
    # Convert any RNA Uracil to Thymine for consistent DNA alphabet
    clean_seq = raw_seq.replace("U", "T")

    # Check for poly-A tail at 3' terminus (>= 15 consecutive A's)
    has_poly_a = bool(re.search(r"A{15,}$", clean_seq))

    # Check for non-ACGT IUPAC ambiguity codes
    has_iupac = bool(re.search(r"[RYSWKMBDHVN]", clean_seq))

    if not allow_iupac and has_iupac:
        # If IUPAC not allowed, mask with A or leave as-is with flag
        pass

    return GenomeRecord(
        accession=accession,
        organism=organism,
        sequence=clean_seq,
        length=len(clean_seq),
        has_poly_a_tail=has_poly_a,
        has_iupac=has_iupac,
    )


class GenomeDatabase:
    """
    In-memory reference database with k-mer indexing and C++ Smith-Waterman alignment.
    Enables rapid pathogen identification against thousands of viral genomes.
    """

    def __init__(self, k: int = 13, step: int = 32):
        self.k: int = k
        self.step: int = step
        self.records: List[GenomeRecord] = []
        self.records_by_accession: Dict[str, GenomeRecord] = {}
        # Inverted index: k-mer -> list of record indices (rec_id)
        self.kmer_index: Dict[str, List[int]] = {}
        self.is_loaded: bool = False
        self.source_path: Optional[str] = None
        self.cache_path: Optional[str] = None

    def load(
        self,
        filepath: Optional[str] = None,
        max_records: Optional[int] = None,
        allow_iupac: bool = True,
        use_cache: bool = True,
    ) -> bool:
        """
        Loads the database from the given .fna file (or default locations).
        Uses a disk cache if available for near-instant (<1s) startup.
        """
        target_path = self._resolve_db_path(filepath)
        if not target_path:
            logger.warning("No genomic database FNA file could be located.")
            return False

        self.source_path = target_path
        cache_file = self._get_cache_path(target_path)
        self.cache_path = cache_file

        # Check if cache is fresh
        if use_cache and os.path.exists(cache_file) and not max_records:
            try:
                src_mtime = os.path.getmtime(target_path)
                cache_mtime = os.path.getmtime(cache_file)
                if cache_mtime >= src_mtime:
                    logger.info("Loading cached genome database from %s...", cache_file)
                    t0 = time.time()
                    with open(cache_file, "rb") as f:
                        data = pickle.load(f)
                    self.records = data["records"]
                    self.kmer_index = data["kmer_index"]
                    self.records_by_accession = {r.accession: r for r in self.records}
                    self.is_loaded = True
                    logger.info(
                        "Loaded %d records (%d unique %d-mers) from cache in %.2fs.",
                        len(self.records),
                        len(self.kmer_index),
                        self.k,
                        time.time() - t0,
                    )
                    return True
            except Exception as exc:
                logger.warning("Failed to load cache (%s), rebuilding from source...", exc)

        # Parse from source FNA
        records = parse_fna_records(target_path, max_records=max_records, allow_iupac=allow_iupac)
        if not records:
            return False

        self.records = records
        self.records_by_accession = {r.accession: r for r in self.records}

        # Build k-mer inverted index
        self._build_index()
        self.is_loaded = True

        # Save cache if full database was loaded
        if use_cache and not max_records:
            try:
                os.makedirs(os.path.dirname(os.path.abspath(cache_file)), exist_ok=True)
                with open(cache_file, "wb") as f:
                    pickle.dump(
                        {"records": self.records, "kmer_index": self.kmer_index},
                        f,
                        protocol=pickle.HIGHEST_PROTOCOL,
                    )
                logger.info("Saved genome database cache to %s", cache_file)
            except Exception as exc:
                logger.warning("Could not write cache file: %s", exc)

        return True

    def _resolve_db_path(self, filepath: Optional[str]) -> Optional[str]:
        """Finds the database file from environment, argument, or defaults."""
        candidates = []
        if filepath:
            candidates.append(filepath)
        env_path = os.getenv("GENOME_DATABASE_PATH")
        if env_path:
            candidates.append(env_path)
        candidates.extend(DEFAULT_DB_FILENAMES)

        for p in candidates:
            if os.path.isfile(p):
                return os.path.abspath(p)
        return None

    def _get_cache_path(self, target_path: str) -> str:
        """Determines the cache filepath corresponding to the database file and parameters."""
        base_name = os.path.basename(target_path)
        dir_name = os.path.dirname(target_path)
        return os.path.join(dir_name, f".{base_name}.k{self.k}_s{self.step}.cache")

    def _build_index(self) -> None:
        """Constructs spaced k-mer inverted index across all loaded records."""
        logger.info(
            "Building spaced k-mer index (k=%d, step=%d) across %d genomes...",
            self.k,
            self.step,
            len(self.records),
        )
        t0 = time.time()
        idx: Dict[str, List[int]] = {}

        k = self.k
        step = self.step

        for rec_id, rec in enumerate(self.records):
            seq = rec.sequence
            n = len(seq)
            for i in range(0, n - k + 1, step):
                km = seq[i : i + k]
                if km in idx:
                    # Avoid duplicate rec_id for closely spaced identical k-mers in same record
                    if idx[km][-1] != rec_id:
                        idx[km].append(rec_id)
                else:
                    idx[km] = [rec_id]

        self.kmer_index = idx
        elapsed = time.time() - t0
        logger.info(
            "Index complete: %d unique %d-mers indexed in %.2fs",
            len(self.kmer_index),
            k,
            elapsed,
        )

    def prefilter(self, query_seq: str, top_n: int = 10) -> List[Tuple[int, int]]:
        """
        Fast k-mer prefilter: ranks database genomes by the number of shared k-mers.
        Returns: List of (rec_id, shared_kmer_count) sorted descending.
        """
        if not self.is_loaded or not query_seq or len(query_seq) < self.k:
            return []

        counts: Dict[int, int] = {}
        k = self.k
        n = len(query_seq)

        for i in range(n - k + 1):
            km = query_seq[i : i + k]
            hit_list = self.kmer_index.get(km)
            if hit_list:
                for rec_id in hit_list:
                    counts[rec_id] = counts.get(rec_id, 0) + 1

        if not counts:
            return []

        sorted_candidates = sorted(counts.items(), key=lambda x: x[1], reverse=True)
        return sorted_candidates[:top_n]

    def identify_closest_genome(
        self,
        query_seq: str,
        top_k: int = 5,
        score_margin_threshold: float = 0.03,
        engine_url: str = "http://engine:8080",
    ) -> GenomeIdentificationResponse:
        """
        Full identification pipeline:
        1. Query complexity check (flags poly-A / homopolymers).
        2. K-mer prefilter to extract top candidate genomes.
        3. Local Smith-Waterman alignment on candidate windows.
        4. Ranking and tie / ambiguity gating (abstains when top scores are too close).
        """
        t0 = time.time()
        q_clean = query_seq.strip().upper().replace("U", "T")

        # 1. Check query complexity
        is_q_low, q_entropy, q_max_freq = compute_sequence_complexity(q_clean)
        if is_q_low:
            logger.warning(
                "Query sequence is low complexity (entropy=%.2f, max_freq=%.2f). Flagging poly-A/repetitive query.",
                q_entropy,
                q_max_freq,
            )

        # 2. Run k-mer prefilter
        candidate_hits = self.prefilter(q_clean, top_n=max(top_k * 2, 10))
        if not candidate_hits:
            elapsed_ms = (time.time() - t0) * 1000
            return GenomeIdentificationResponse(
                status="no_match",
                query_sequence=q_clean,
                query_length=len(q_clean),
                total_candidates_evaluated=0,
                top_candidates=[],
                closest_match=None,
                abstain=True,
                abstain_reason="NO_SIGNIFICANT_MATCH: No database genome shares sufficient sequence similarity.",
                search_time_ms=elapsed_ms,
            )

        # 3. Align top candidate genomes
        candidates: List[GenomeMatchCandidate] = []

        for rec_id, shared_cnt in candidate_hits:
            rec = self.records[rec_id]
            # Find matching window in reference genome
            target_subseq, win_start, win_end = self._extract_alignment_window(rec.sequence, q_clean)

            # Perform Smith-Waterman alignment
            sw_score, align_len = self._align_candidate(q_clean, target_subseq, engine_url)

            # Check if match region is low complexity (e.g. picornavirus poly-A tail)
            is_match_low, _, _ = compute_sequence_complexity(target_subseq)
            match_low_complexity = is_q_low or (is_match_low and rec.has_poly_a_tail)

            candidates.append(
                GenomeMatchCandidate(
                    rank=0,  # assigned after sorting
                    accession=rec.accession,
                    organism=rec.organism,
                    alignment_score=sw_score,
                    matched_length=align_len,
                    target_start=win_start,
                    target_end=win_end,
                    shared_kmers=shared_cnt,
                    low_complexity=match_low_complexity,
                    has_poly_a_tail=rec.has_poly_a_tail,
                )
            )

        # 4. Sort candidates by Smith-Waterman score descending
        candidates.sort(key=lambda c: (c.alignment_score, c.shared_kmers), reverse=True)

        for i, c in enumerate(candidates):
            c.rank = i + 1

        top_candidates = candidates[:top_k]
        elapsed_ms = (time.time() - t0) * 1000

        if not top_candidates or top_candidates[0].alignment_score <= 0:
            return GenomeIdentificationResponse(
                status="no_match",
                query_sequence=q_clean,
                query_length=len(q_clean),
                total_candidates_evaluated=len(candidate_hits),
                top_candidates=[],
                closest_match=None,
                abstain=True,
                abstain_reason="NO_SIGNIFICANT_MATCH: Alignment scores were zero or negative.",
                search_time_ms=elapsed_ms,
            )

        winner = top_candidates[0]

        # 5. Abstain Condition A: Low-complexity match (Poly-A tail inflation)
        if winner.low_complexity:
            return GenomeIdentificationResponse(
                status="abstained",
                query_sequence=q_clean,
                query_length=len(q_clean),
                total_candidates_evaluated=len(candidate_hits),
                top_candidates=top_candidates,
                closest_match=winner,
                abstain=True,
                abstain_reason="LOW_COMPLEXITY_POLY_A_MATCH: Match is dominated by repetitive sequence (e.g. poly-A tail).",
                search_time_ms=elapsed_ms,
            )

        # 6. Abstain Condition B: Ambiguous match (Top candidates too close)
        if len(top_candidates) > 1:
            second = top_candidates[1]
            s1 = winner.alignment_score
            s2 = second.alignment_score
            score_delta = s1 - s2
            relative_delta = score_delta / s1 if s1 > 0 else 0.0

            if score_delta <= 1 or relative_delta < score_margin_threshold:
                return GenomeIdentificationResponse(
                    status="abstained",
                    query_sequence=q_clean,
                    query_length=len(q_clean),
                    total_candidates_evaluated=len(candidate_hits),
                    top_candidates=top_candidates,
                    closest_match=winner,
                    abstain=True,
                    abstain_reason=(
                        f"AMBIGUOUS_GENOMIC_MATCH: Top candidates '{winner.accession}' ({s1}) and "
                        f"'{second.accession}' ({s2}) have indistinguishable scores (delta={score_delta})."
                    ),
                    search_time_ms=elapsed_ms,
                )

        # Definitive high-confidence match
        return GenomeIdentificationResponse(
            status="success",
            query_sequence=q_clean,
            query_length=len(q_clean),
            total_candidates_evaluated=len(candidate_hits),
            top_candidates=top_candidates,
            closest_match=winner,
            abstain=False,
            abstain_reason=None,
            search_time_ms=elapsed_ms,
        )

    def _extract_alignment_window(self, ref_seq: str, query_seq: str) -> Tuple[str, int, int]:
        """
        Locates the best target window around matching k-mers to avoid aligning
        entire 200,000 bp genomes and to respect the C++ engine's 10,000 bp limit.
        """
        k = self.k
        q_len = len(query_seq)
        ref_len = len(ref_seq)

        # If reference is small enough, align the entire genome
        if ref_len <= 4000:
            return ref_seq, 0, ref_len

        # Search for first matching k-mer position in reference
        best_pos = -1
        for i in range(q_len - k + 1):
            km = query_seq[i : i + k]
            pos = ref_seq.find(km)
            if pos != -1:
                best_pos = pos - i
                break

        if best_pos == -1:
            # Fallback to middle or start
            best_pos = 0

        win_start = max(0, best_pos - 200)
        win_end = min(ref_len, best_pos + q_len + 200)
        return ref_seq[win_start:win_end], win_start, win_end

    def _align_candidate(self, query: str, ref_window: str, engine_url: str) -> Tuple[int, int]:
        """
        Executes Smith-Waterman alignment via the C++ engine (or local DP fallback).
        Returns: (alignment_score, matched_length)
        """
        try:
            with httpx.Client(timeout=2.0) as client:
                resp = client.post(
                    f"{engine_url}/align",
                    json={"reference_sequence": ref_window, "query_sequence": query},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    score = data.get("alignment_score", 0)
                    return score, len(query)
        except Exception:
            pass

        # Local fallback dynamic programming alignment
        return self._local_smith_waterman(ref_window, query)

    def _local_smith_waterman(
        self, ref: str, qry: str, match: int = 2, mismatch: int = -1, gap: int = -1
    ) -> Tuple[int, int]:
        """Pure-Python local alignment fallback if C++ engine is offline."""
        n, m = len(ref), len(qry)
        if n == 0 or m == 0:
            return 0, 0

        prev = [0] * (m + 1)
        max_score = 0

        for i in range(1, n + 1):
            curr = [0] * (m + 1)
            r_ch = ref[i - 1]
            for j in range(1, m + 1):
                q_ch = qry[j - 1]
                diag = prev[j - 1] + (match if r_ch == q_ch else mismatch)
                up = prev[j] + gap
                left = curr[j - 1] + gap
                score = max(0, diag, up, left)
                curr[j] = score
                if score > max_score:
                    max_score = score
            prev = curr

        return max_score, m


# Singleton instance
_GLOBAL_GENOME_DATABASE: Optional[GenomeDatabase] = None


def get_genome_database() -> GenomeDatabase:
    """Returns the singleton GenomeDatabase instance, initializing lazily if needed."""
    global _GLOBAL_GENOME_DATABASE
    if _GLOBAL_GENOME_DATABASE is None:
        db = GenomeDatabase(k=13, step=32)
        # Attempt to load from default paths
        db.load(use_cache=True)
        _GLOBAL_GENOME_DATABASE = db
    return _GLOBAL_GENOME_DATABASE
