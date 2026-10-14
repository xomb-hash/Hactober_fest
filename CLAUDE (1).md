# CLAUDE.md — Project HelixGuard (Final)

Verification-first genomic sequence extraction, alignment, and reference identification system for a high-stakes hackathon.
Priorities: correctness, traceability, deterministic verification, robust failure handling, privacy, working end-to-end demo. Do not add complexity that doesn't serve these.

**Document history:** merges (1) the original spec (Milestones 1–7), (2) the Round 2 judge-feedback plan, and (3) the extensions implemented after the original spec. Where they conflict, this file wins.

## What HelixGuard Is For (positioning — keep this honest)

- **Intended user:** a lab technician, bioinformatician, or student who has a sequence buried in a messy report, paper excerpt, scan, or notes and wants to know **what it is** (closest reference genome) **with proof the sequence was not altered on the way in**.
- **Primary use case:** identifying an unknown pathogen/organism sequence found in a document by screening it against a reference database (NCBI RefSeq viral).
- **NOT for:** personal human DNA reports, health interpretation, or clinical decisions. A person's own DNA will not match a viral database; do not pitch it that way.
- **What we do not do:** we do not compete with BLAST on alignment. Smith–Waterman is textbook. We guard the step *before* alignment: "which sequence in this messy document, and is it exactly what the source says?"
- **Pitch:** AI-assisted localization + deterministic source verification + traceable provenance + explicit abstention. It can sit in front of any aligner.

| Alternative | What it does well | Gap we fill |
|---|---|---|
| BLAST, EMBOSS Water, Biopython, Parasail | Excellent alignment | Assume a clean sequence is already in hand |
| Biopython SeqIO / regex parsers | Structured formats | Fail silently or grab the wrong field on messy text |
| ChatGPT / generic LLM extraction | Flexible | Can change bases (`ATCGATCG` → `ATCGACTG`), no verification, privacy risk |
| OCR / document AI | Text recovery | No guarantee characters match the source |

## Role

Act as Principal Systems Architect, Senior C++ Engineer, Python Backend Engineer, and AI Reliability Engineer. Build a functioning application, run its tests, fix failures, and document limitations. Do not just generate files.

## Working Agreement

- **Current phase: Round 2 hardening.** Milestones 1–7 and Extensions E1–E6 are reported implemented (see Status). Update this line as work completes.
- The Round 2 plan was written from this spec only; the repo was **not** inspected. **At the start of every session, inspect the repo and environment** (compilers, Python version, Node, Docker, Ollama or cloud key) and verify what actually exists. Do not assume features, dependencies, model weights, services, or the numbers in this file are real until checked.
- Implement ONLY the current task. Do not skip ahead or stub later components.
- For each task before moving on:
  1. Run the relevant tests and fix failures.
  2. Explain what was implemented.
  3. Show the exact commands to run it.
  4. List remaining limitations.
- Never claim tests pass without running them. Never claim a feature exists if it is stubbed. Never invent test results or benchmark numbers.
- Show a full implementation plan before writing code.
- Terminal instructions: give all commands together in one block.

## Core Principle

The LLM may propose WHERE a sequence is. Only deterministic code operating on the source text may extract and verify the nucleotides.

- Never use an LLM to reconstruct, complete, repair, guess-normalize, or modify a nucleotide sequence.
- If the intended sequence and its boundaries can't be established with sufficient evidence, **abstain**.
- Do not claim zero hallucinations, guaranteed clinical safety, or diagnostic accuracy.
- Example failure to prevent: `ATCGATCG` → `ATCGACTG`. Both are valid DNA, but different sequences.

## Integrity Rules (apply everywhere)

1. **Source text is authoritative** for extracted characters. The LLM is not.
2. **Never accept a model-generated sequence as extracted data.** The LLM may point to a candidate; deterministic code must independently verify it against the original input.
3. **Syntax validation ≠ source verification.** `^[ACGT]+$` does not mean correct. Track separately:
   - Candidate located
   - Alphabet valid
   - Boundaries established
   - Complete sequence verified
   - Intended field supported by context
   - Source fidelity verified
   - Eligible for alignment / database search
   Do not collapse these into one regex. Alignment and identification require all checks for the configured task to pass.
4. **Never repair sequence content with an LLM.**
5. **No silent acceptance.** Every rejection, abstention, recovery attempt, normalization op, and verification has an explicit status or traceable record.
6. **No clinical diagnosis.** Smith–Waterman and database matching do not establish pathogenicity, diagnose, or recommend treatment. No clinical recommendation cards. "Closest reference match" is not a diagnosis.
7. **Unverified sequences never reach the C++ engine or the genome database search.**
8. **Identification must abstain when evidence is weak:** tied or near-tied top scores, low-complexity/homopolymer matches, and tiny coverage all produce an explicit abstention or flag, never a confident organism name.
9. **OCR and PDF text are not the original.** Source fidelity for a document-derived sequence is relative to the *extracted text*, not the image or PDF. OCR can confuse characters; mark OCR-derived sequences as lower-confidence and never present them as image-verified.
10. **Never silently convert U↔T.** The one allowed exception is the reference database loader's documented, logged RNA U→T normalization (RefSeq stores RNA viruses as DNA-encoded FASTA); it applies only to database records, never to user-extracted sequences.

## Status (verify against the repo before relying on it)

| Area | Status |
|---|---|
| M1 C++ engine, M2 extraction, M3 anchor recovery, M4 orchestration, M5 frontend, M6 Scout/Critic/retries, M7 docs/tests | Reported implemented |
| E1 Pan-viral reference identification | Reported implemented |
| E2 Multi-format ingestion (PDF, DOCX, MD, TXT, FASTA) | Reported implemented |
| E3 Local OCR for images/scans | Reported implemented |
| E4 Ollama Cloud + API key pooling | Reported implemented |
| E5 Frontend identification UI + 12 test cases | Reported implemented |
| E6 Production containerization (Nginx, cache volume) | Reported implemented |
| R2 Round 2 hardening (Security, Feasibility, Unseen data) | **Planned — not yet implemented** |

## Architecture

```
HelixGuard/
├── engine/            # C++17 Smith–Waterman service (port 8080)
│   ├── main.cpp  alignment.hpp / alignment.cpp  CMakeLists.txt  tests/
├── middleware/        # Python 3.12 FastAPI
│   ├── main.py  schemas.py  extraction.py  anchor_recovery.py
│   ├── validation.py  provenance.py  critic.py
│   ├── database.py          # streaming multi-FASTA loader, k-mer index, cache   (E1)
│   ├── document_parser.py   # PDF / DOCX / MD / TXT / FASTA / image OCR          (E2, E3)
│   ├── llm_client.py        # Ollama local/cloud client, key pooling             (E4)
│   ├── masking.py           # nucleotide + identifier tokenization               (R2, planned)
│   ├── adapters/            # FASTA / GenBank / FASTQ format adapters            (R2, planned)
│   ├── requirements.txt  .env.example  tests/
├── frontend/          # React + TypeScript + Vite + Tailwind
│   ├── src/ (DocumentInput.tsx, GenomeIdentificationCard, ...)  nginx.conf  package.json  vite.config.ts
├── tests/test_end_to_end.py
├── docker-compose.yml  Dockerfile(s)  .gitignore  README.md
```

Adapt if needed, but keep clear separation between extraction, verification, alignment, database identification, AI-assisted localization, and presentation.

### Stack

- **Engine:** C++17, cpp-httplib, nlohmann/json, CMake, port 8080. RAII / safe memory. Needs `#include <cstdint>` / `std::uint8_t` for Linux/GCC (Alpine).
- **Middleware:** Python 3.12, FastAPI, Pydantic, HTTPX, pytest, pypdf, python-docx, RapidOCR (ONNX Runtime). Type hints throughout.
- **AI localization:** Optional. Local Ollama (e.g. qwen2.5:7b, llama3.2) **or** Ollama Cloud (default model gemma4:31b, alt deepseek-v3.1:671b). **Deterministic pipeline must work with no LLM at all.**
- **Frontend:** React, TypeScript, Vite, Tailwind; production build served by Nginx.
- **Deploy:** Docker Compose; must also run locally without Docker. Must run on Apple Silicon MacBook. No paid APIs required.
- Local Ollama ≠ air-gapped; true isolation needs network restrictions plus locally available dependencies and weights. **Ollama Cloud sends text off-machine** — see Security.

## Milestone 1 — C++ Alignment Engine

**Endpoint:** `POST /align` on port 8080.

Request:
```json
{ "reference_sequence": "ATCGATCG", "query_sequence": "ATCGTTCG" }
```

Algorithm (local alignment, DP):
```
H[i][j] = max(0,
              H[i-1][j-1] + substitution_score,
              H[i-1][j]   + gap_score,
              H[i][j-1]   + gap_score)
```
- Defaults: match +2, mismatch −1, gap −1. Allow safe configuration if practical.
- First row and column initialized to 0. Track max-scoring cell; traceback if feasible.

Response (all values computed from real input, never hardcoded):
```json
{
  "status": "success",
  "alignment_score": 11,
  "max_cell": { "row": 7, "column": 8 },
  "matrix": [],
  "matrix_dimensions": { "rows": 9, "columns": 9 },
  "scoring": { "match": 2, "mismatch": -1, "gap": -1 }
}
```

Validate: missing fields, empty sequences, unsupported characters, excessively large inputs (`INPUT_TOO_LARGE` above 10k bp), invalid scoring params, malformed JSON. CORS for the local frontend (strict origins, no wildcard when shared).

Tests: known scores, mismatches, empty input, edge cases. Verify expected values independently (hand calculation or independent reference implementation). The engine must NOT claim its input was extracted correctly — that is the middleware's job. DP matrix is O(m×n): provide a score-only or banded mode for long sequences and state size limits.

## Milestone 2 — Deterministic Extraction

**Endpoint:** `POST /extract`
```json
{ "document_text": "Observed sequence: ATCGATCG", "field_type": "observed_sequence", "sequence_alphabet": "DNA" }
```
Schema may add options for ambiguity codes, normalization rules, and recovery config.

Responsibilities: identify candidate spans; preserve original text; record exact offsets; establish boundaries; apply only explicitly defined normalization; validate alphabet; establish fidelity and completeness; return structured results + provenance; abstain when intent can't be established.

Alphabets: DNA (A,C,G,T), RNA (A,C,G,U). IUPAC ambiguity codes as a configurable extension. Whitespace, line numbers, and punctuation handled by explicit, tested rules — never strip every non-letter character from a whole paragraph.

## Milestone 3 — Anchor Recovery (`anchor_recovery.py`, mandatory)

Anchors are localization hints, not trusted boundaries. Never depend entirely on them.

**Normal verification:** exact-match `anchor_before`, `candidate_quote`, `anchor_after` against the original; confirm strings exist, ordering is consistent, quote belongs to the intended field, boundaries exclude unrelated text, sequence is complete. Handle repeated anchors explicitly — never pick the first of multiple remaining combinations.

**Case A — `anchor_before` wrong** (e.g. doc `Observed sequence: GCTAGCTA`, proposed anchor `Tumor DNA sequence:`): try exact anchors → record failure → search exact quote → check occurrence count → inspect context → independently establish boundaries and field identity → accept only if all rules pass, else abstain. A bad anchor doesn't invalidate an independently verifiable candidate.

**Case B — `anchor_after` wrong:** verify preceding anchor and exact quote, check ordering, establish boundaries by deterministic parsing and context. Accept only if identity and completeness are established. Never invent a replacement boundary.

**Case C — both wrong:** record both failures → search exact quote → none = reject; multiple = evaluate each independently against field and context; one = still verify boundaries, completeness, field identity. A unique quote is not automatically a verified sequence (the same sequence may appear in a reference section and an observed-sample section — identify the correct field). Ambiguous/truncated/unsupported → abstain.

**Case D — candidate quote itself wrong:** never modify it to match; never accept a similar sequence; search alternatives only under a defined recovery strategy with deterministic verification; abstain if uncertain.

**Case E — multiple candidates:** enumerate with source locations, evaluate contextual support, never default to the first, require an unambiguous field match or return an ambiguity status. May ask the user to choose.

**Bounded fuzzy matching** (optional, localization only): e.g. source `Observed snequce:` vs anchor `Observed sequence:`. Must never modify nucleotide characters or rewrite the source; documented similarity threshold; bounded search region; detect competing matches; record proposed match + similarity; require exact source verification of the final sequence; abstain if ambiguous. A fuzzy anchor match is not proof of sequence fidelity.

## Milestone 4 — Backend Orchestration

**Endpoints:**
- `POST /extract-and-align` (original)
- `POST /identify-genome`, `POST /extract-and-identify`, `GET /genome-database/status` (E1)
- `POST /parse-document` (E2/E3)

Flow: validate request → parse document if a file → identify candidate span → (optional) LLM localization → verify anchors and exact quote → deterministic recovery if needed → boundaries + completeness → alphabet + source fidelity → verified? No → abstain; Yes → record provenance → call C++ engine (and/or database search) → return result. Prefer the deterministic route when it can resolve the task alone.

**Critical gating rule:** the C++ engine and genome database search must never receive an unverified extracted query sequence. The user-supplied reference sequence must also pass input validation. Valid sequences ≠ biological relevance.

Success response (offsets/scores computed from real input):
```json
{
  "status": "success",
  "extraction": {
    "sequence": "ATCGATCG",
    "validation_status": "verified",
    "source_match": true,
    "boundaries_verified": true,
    "completeness_verified": true,
    "recovery_method": "exact_quote",
    "anchors_verified": true,
    "source_span": { "start": 19, "end": 27 }
  },
  "alignment": { "status": "success", "alignment_score": 16, "matrix": [] }
}
```
Abstention response:
```json
{
  "status": "abstained",
  "extraction": {
    "sequence": null,
    "validation_status": "unverified",
    "source_match": false,
    "error_code": "AMBIGUOUS_SOURCE_LOCATION",
    "recovery_method": "exact_quote_search",
    "message": "Multiple candidate locations remain plausible."
  },
  "alignment": null
}
```
Use suitable HTTP status codes and consistent error schemas. Never return fabricated alignment or identification after failed extraction. Structured errors and timeouts; clear error when the engine is unavailable.

## Milestone 5 — Frontend Dashboard

Clean, technical React dashboard.

- **A. Document input:** large textarea (synthetic text), drag-and-drop file upload (E2), reference mode toggle ("Viral Database" vs "Custom Sequence"), field selector, DNA/RNA selector, AI Scout toggle, Extract & Align button, Load Demo buttons, Live/Mock mode indicator.
- **B. Pipeline status:** request validation, candidate localization, anchor verification, recovery (if required), sequence validation, provenance verification, alignment/identification. **Show real backend state only — no simulated stages or fake progress percentages.**
- **C. Extraction evidence:** accepted sequence, source excerpt, offsets, verified/failed anchors, recovery method, normalization ops, completeness and source-fidelity statuses.
- **D. Alignment visualization:** score, DP matrix heatmap, row/column labels, max cell, legend, scrollable for large matrices.
- **E. Genome identification card (E1):** closest organism, RefSeq accession with NCBI link, score pills, target-genome coordinate bar with coverage %, ranked candidate table, and any abstention/flag (tie, low-complexity).
- **F. Failure/abstention panel:** human-readable reason, error code, whether retry or manual disambiguation is possible, explicit note that no alignment/identification was run when extraction was unverified.

No clinical diagnosis, treatment suggestion, or unsupported mutation interpretation.

## Milestone 6 — AI Localization and Retries

Only deterministic tests gate integration. Deterministic-only mode must always work.

**Agent A — Scout:** proposes a location; never generates a replacement sequence. Must quote source exactly and signal uncertainty explicitly when it can't locate. Output is a *proposal*, not fact:
```json
{
  "field_type": "observed_sequence",
  "candidate_quote": "GCTAGCTA",
  "anchor_before": "Observed sequence:",
  "anchor_after": "Additional notes:",
  "expected_alphabet": "DNA",
  "reason": "The quoted text appears in the observed-sequence field."
}
```
`candidate_quote` may be an excerpt containing a sequence; deterministic code extracts the sequence from it. (Round 2 adds a token-masked mode where the Scout never sees nucleotides — see R2-1.)

**Agent B — Context Critic (`critic.py`):** evaluates whether the location is consistent with the requested field. Must not rewrite the sequence, declare an unverified sequence correct, override deterministic validation, diagnose, or infer clinical significance. A successful Critic response cannot compensate for failed source-fidelity verification.

**Retries:** configurable max 3 attempts; bounded, purposeful, observable.
1. Locate the requested field and quote surrounding context.
2. On anchor/candidate failure: ask for a *different exact excerpt* from the source, including the previous failure reason. Never ask the model to correct or reconstruct the sequence.
3. If ambiguity remains: distinguish between explicitly identified candidates or propose a better-supported location.

Rules: every proposal goes through the same deterministic recovery + validation; no retry after verified success; no retry on deterministic input errors the model can't fix; no retries to force a candidate to pass; never exceed the limit; audit record per attempt; bounded timeouts; handle model unavailable and malformed responses. After the final failure, return explicit abstention/rejection with a useful error code.

## Milestone 7 — Final Testing + Docs

All tests, fix integration failures, document setup/architecture/limitations/demo, record known failures honestly. Re-run after every extension.

## Provenance (`provenance.py`)

For each accepted extraction record: request/document ID; input text hash; exact source offsets; exact source excerpt; extracted sequence; alphabet; normalization operations; candidate quote; per-anchor verification; recovery method; number of LLM attempts; boundary, completeness, source-fidelity, and context/field validation results; final status and reason. For identification results also record: database name/release, accession, score, margin to runner-up, coverage, and any safety-gate flag.

- **Offset convention:** zero-based, half-open, `start <= pos < end`, referring to the **original** input string, not a normalized copy.
- If normalization removes spaces or line numbers, keep a mapping tracing each extracted character to its original position.
- For PDF/DOCX/OCR input, offsets refer to the *extracted text*, not the original file. Don't claim they equal original-file offsets; record page + bounding box where available.
- Keep sensitive data out of logs by default. Use synthetic/fictional data only.
- **Round 2:** replace the plain input hash with a salted HMAC so a hash cannot confirm someone's sequence.

## Extensions Implemented After the Original Spec

Numbers below come from the implementation change log. **Re-measure and re-verify them before showing judges.**

### E1 — Pan-Viral Reference Identification

Replaces "1 query vs 1 user reference" with an optional "query vs reference database" mode. Framing is pathogen/organism identification, **not clinical**.

- **Database:** NCBI RefSeq viral, one multi-FASTA `.fna` file (`viral.1.1.genomic.fna`). Reported: 19,625 genomes, 583.7M bp. Record the download date and source URL in the README.
- **`database.py`:** streaming multi-FASTA parser; header `>accession organism name`; joins 80-column wrapped lines; RNA U→T normalization for database records only (Integrity Rule 10); handles `N`/IUPAC characters by an explicit, configurable rule.
- **K-mer prefilter:** inverted index, k=13, step=32, reported ~13.7M unique k-mers, shortlist in ~1 ms. Persistent binary cache (`viral.1.1.genomic.fna.cache`) in Docker volume `viral_cache_data` cuts cold load from ~60 s to ~3 s.
- **Window extraction:** ±200 bp around k-mer hits, so the engine never receives sequences over its size limit.
- **Safety gating (both mandatory):**
  1. **Low-complexity / poly-A penalty:** homopolymer runs (e.g. Carp picornavirus 1, NC_023162.1, ends in a long poly-A tail) must not inflate scores → `LOW_COMPLEXITY_POLY_A_MATCH`.
  2. **Ambiguity gating:** abstain when top scores are tied or indistinguishable (Δ ≤ 1 or relative margin < 0.03) → `AMBIGUOUS_GENOMIC_MATCH`.
- Output is a ranked list with accession, organism, score, coverage, target coordinates. Never output a single confident organism when the gates fire.
- Limits to document: only viral genomes in one release file; not bacteria; k-mer prefilter can miss highly divergent matches; closest match ≠ clinical meaning.

### E2 — Multi-Format Document Ingestion (`document_parser.py`)

`.pdf` (pypdf), `.docx` (python-docx), `.md`, `.txt`, `.fasta`, `.fna`; drag-and-drop in `DocumentInput.tsx` with client-side reading fallback and backend `POST /parse-document`. Parsing produces text; **all extraction and verification then run on that text** with the same rules. Record the parser used and any text-layer limitations in provenance.

### E3 — Local OCR (RapidOCR / ONNX)

`.png .jpg .jpeg .tiff .bmp .webp`, runs locally in the Python container (Debian packages `libgl1`, `libglib2.0-0`). Layout-aware reconstruction removes spurious OCR line wraps while keeping field boundaries. Per Integrity Rule 9, OCR-derived sequences are flagged lower-confidence; OCR must never "fix" characters.

### E4 — Ollama Cloud + Key Pooling (`llm_client.py`)

- Supports local Ollama and Ollama Cloud; if `OLLAMA_API_KEY` is set it routes to cloud, otherwise to the local host port. Default model `gemma4:31b`.
- Comma-separated key pool with round-robin rotation on HTTP 429 or failure.
- **Constraints:** cloud mode sends document text off-machine, so it must follow the Security section (token-masked Scout, identifier masking, visible "cloud mode" indicator, opt-in for sensitive use). Use only keys the operator legitimately owns and check provider terms before pooling keys to get around rate limits. Never log keys.

### E5 — Frontend Extensions + 12 Test Cases

Genome identification card, identification results shown across Extraction, Alignment, and Test Cases pages. Runnable cases:
- **TC-1 – TC-10:** anchor recovery, duplicate quotes, truncation, invalid characters, mismatches, etc.
- **TC-11:** pan-viral screening identifying Hyposoter fugitivus ichnovirus (NC_008987.1).
- **TC-12:** homopolymer run triggering `LOW_COMPLEXITY_POLY_A_MATCH` against Carp picornavirus 1 (NC_023162.1).

### E6 — Production Containerization

Multi-stage frontend build served by Nginx reverse proxy (`nginx.conf`); named volume `viral_cache_data`; Linux/GCC fix in `alignment.hpp`. Must still run locally without Docker.

## Round 2 Hardening Plan (judge feedback — NOT yet implemented)

Judges raised four concerns: (1) security of DNA data, (2) user feasibility, (3) differentiation from public alternatives, (4) handling of new/unseen datasets. Differentiation is covered in the positioning section above.

### R2-1 Security: DNA is sensitive and cannot be anonymized

**Main change: the LLM never sees nucleotides.**
- Deterministic code finds every nucleotide-like run and replaces it with a token, e.g. `Observed sequence: <SEQ_2, 48 nt>`.
- The Scout picks which token matches the requested field using only surrounding text.
- The model cannot leak or alter bases it never received. Final sequence is still verified against the source.
- Keep the quote-based Scout as an opt-in fallback, **disabled by default in cloud mode**.

| Area | Control |
|---|---|
| Retention | Zero retention: no database, no disk writes of user content, request-scoped memory only. Python cannot guarantee memory wiping — do not claim it. |
| Deployment | Local-first. Bind to `127.0.0.1`. Engine and (local) Ollama on a Docker network with `internal: true` (no egress). Do not publish the engine port to the host. Add a test proving no outbound connections. Cloud LLM mode is the explicit exception and must be clearly labeled. |
| Shared use | Token auth, TLS, strict CORS instead of wildcard. |
| Provenance | Salted HMAC instead of plain hash. "Redacted export" containing offsets, statuses, and hash only. |
| Frontend | No localStorage, no telemetry, no CDN assets, CSP header, "Clear all" button, idle auto-clear. |
| Patient identifiers | Names and MRNs in a report are often a bigger risk than the sequence. Mask before any LLM call; state plainly that regex masking is imperfect. |
| Claims | Do **not** claim HIPAA/GDPR compliance. Say the system supports a privacy-preserving deployment. |

### R2-2 User feasibility

Named user: lab technician or bioinformatician pulling sequences out of lab reports.
- **Setup:** one command (`docker compose up` or `make demo`), no GPU, works with no LLM.
- **Input:** paste, drag-and-drop `.txt`, FASTA, GenBank (already extended to PDF/DOCX/OCR).
- **Plain-language verdict:** "Verified" or "Not sure — here's why and what to do." No jargon.
- **Human-in-the-loop:** when ambiguous, show the source document with candidate spans highlighted and let the user click the right one, turning abstention into a workflow.
- **Output:** downloadable report (JSON plus readable HTML/PDF) and a FASTA export whose header carries provenance.
- **Scale:** score-only or banded mode for long sequences; state size limits.

### R2-3 New or unseen datasets

We cannot promise to parse every format. We promise **fail-safe behavior**: unknown input leads to abstention, never a wrong sequence.
- **Format adapters (`adapters/`):** each adapter detects its format and returns candidate spans with original offsets. Start with plain text, FASTA, GenBank `ORIGIN` blocks (line numbers and 10-base groups), FASTQ. Unrecognized formats fall through to the generic path, which abstains when unsure.
- **Declared normalization:** every rule named, tested, logged. Unknown characters mean reject, not strip.
- **Alphabet profiles:** DNA, RNA, IUPAC, soft-masked lowercase and `N` runs as explicit options. Protein needs BLOSUM62 in the engine — list as future work.
- **Field aliases in config:** new labels ("Tumor DNA", "Query", "Specimen seq") added without code changes. Unmatched label means ask the user or abstain.
- **Coverage check:** unrecognized structure returns `UNSUPPORTED_FORMAT`, not a guess.

**Evidence for judges:**
- Property-based fuzzing (Hypothesis) with one invariant: output is either an exact source substring after declared normalization, or an abstention.
- Mutation benchmark reporting accepted-altered-sequences = 0, plus acceptance and abstention rates.
- Public non-sensitive test data (NCBI FASTA/GenBank records, e.g. phiX174) formatted in many layouts.

### Round 2 priority order if time is short

1. Token-masked Scout (security + differentiation at once).
2. Click-to-disambiguate source viewer (usability).
3. Fuzz and mutation benchmark (unseen data).
4. FASTA/GenBank adapters, `internal: true` Compose network, HMAC hash.

## Testing (core feature, not cosmetic)

Use deterministic synthetic fixtures with known expected results. Mock Ollama in unit tests — they must not need a running LLM or a network.

**Extraction tests:**
1. Exact candidate, both anchors correct
2. Incorrect `anchor_before`
3. Incorrect `anchor_after`
4. Both anchors incorrect
5. Candidate quote absent from source
6. Candidate quote appears multiple times
7. Multiple sequence fields in one document
8. Valid sequence split across lines
9. Recognized line numbering and whitespace
10. Invalid nucleotide characters
11. Truncated sequence
12. Ambiguous sequence boundaries
13. Candidate is a substring of a longer sequence
14. Empty document
15. Empty candidate quote
16. Malformed LLM response
17. Ollama unavailable
18. Retry exhaustion
19. Fuzzy anchor match, one plausible location
20. Fuzzy anchor match, competing locations
21. Source offsets after normalization
22. Repeated sequences in different semantic fields
23. DNA/RNA alphabet configuration
24. Optional IUPAC ambiguity codes

**Integrity tests:** source `ATCGATCG` vs corrupted proposal `ATCGACTG`. Verify: model-proposed bases are never accepted as source truth; extraction happens only through deterministic source matching + boundary validation; abstain if recovery can't establish the intended sequence; no alignment or identification after failed source-fidelity verification. Also test the reverse: a syntactically valid model sequence that doesn't occur in the source. In token-masked mode, assert no nucleotide run appears in any outbound LLM payload.

**Alignment tests:** known score and matrix; exact matches; mismatches; indels where supported; empty inputs; invalid alphabet; large inputs and size limits; malformed API requests.

**Identification tests:** known viral fragment ranks the correct accession first; tied scores → `AMBIGUOUS_GENOMIC_MATCH`; poly-A/homopolymer query → `LOW_COMPLEXITY_POLY_A_MATCH`; unverified extraction never triggers a database search; database loader handles wrapping, `N`/IUPAC, and RNA U→T for database records only; cache rebuild and corrupted-cache fallback.

**Ingestion tests:** each supported file type yields text; unsupported or corrupt files return a structured error; OCR output is flagged lower-confidence; offsets refer to extracted text.

**End-to-end tests:**
1. Correct sequence → verified extraction → alignment
2. Incorrect anchor → deterministic recovery → verified extraction (if evidence suffices)
3. Both anchors wrong → unique, contextually supported candidate recovered
4. Both anchors wrong → ambiguous candidate → abstain
5. Corrupted candidate → verification fails, or independently verified source sequence replaces it
6. No sequence found → no alignment
7. Ambiguous field → abstain or explicit user disambiguation
8. Alignment service unavailable → clear backend error
9. Verified extraction → database identification → ranked organisms (TC-11)
10. Low-complexity query → flagged, no confident organism (TC-12)

**Round 2 tests:** property-based fuzzing; mutation benchmark; no-egress test for `internal: true` network; redacted export contains no sequence.

## Demo Cases

- **Demo A — Success:** complete DNA sequence → deterministic extraction, verified span, alignment, visible provenance + matrix.
- **Demo B — Incorrect anchors:** valid, uniquely identifiable sequence with one or both wrong anchors → failure recorded; recovery via exact source matching; accepted only if field identity, boundaries, completeness, and fidelity are independently established, else abstain.
- **Demo C — Ambiguous/missing:** no supported sequence, or multiple undisambiguable candidates → explicit abstention, useful message, no fabricated sequence, no engine call.
- **Demo D — Identification:** extract a sequence from a document, screen against the viral database, show closest organism with accession, coverage, and ranked candidates (TC-11).
- **Demo E — Safety gates:** poly-A query abstains/flags (TC-12); near-tied scores abstain.
- **Extra:** a case where the LLM proposes an altered sequence, demonstrating the system never silently accepts it.

## Engineering Requirements

- Modular, maintainable code; avoid unnecessary abstractions.
- Pydantic models + type hints in Python; RAII in C++.
- Validate all external inputs, including uploaded files (size and type limits).
- No hardcoded absolute paths; configuration via environment variables; `.env.example` with no real secrets.
- Useful logging that excludes document contents and API keys by default.
- Handle service failures and malformed responses; never silently swallow exceptions.
- Reproducible setup instructions; useful error messages for missing dependencies.

## Definition of Done

1. C++ engine runs and passes unit tests.
2. Python backend extracts sequences deterministically.
3. Backend detects incorrect/missing anchors.
4. Backend recovers only with sufficient independent evidence.
5. Ambiguous or incomplete cases abstain.
6. LLM-generated nucleotides are never accepted as authoritative.
7. Provenance has usable offsets and normalization history.
8. Unverified sequences cannot reach the engine or the genome database.
9. Frontend shows actual extraction, alignment, and identification results.
10. All demos work; all 12 test cases run.
11. Automated tests cover the major adversarial cases.
12. Identification safety gates (tie, low-complexity) verified by tests.
13. Round 2: token-masked Scout, redacted export, and no-egress deployment verified, or documented as not done.
14. Setup, data sources, and known limitations are documented.

## Claims Policy

Say: verified source extraction, deterministic checks, explicit abstention, privacy-preserving deployment option, closest reference match.
Do not say: zero hallucinations, HIPAA/GDPR compliant, clinically safe, diagnostic, novel alignment algorithm, air-gapped (unless network isolation is actually enforced), memory securely wiped.

The application must be honest about what it has verified and what it cannot establish.

> The innovation is not the number of AI agents. It is AI-assisted localization combined with deterministic source verification, robust recovery, traceable provenance, and explicit abstention.
>
> **When the system cannot prove it has recovered the intended sequence from the supplied source, it must not pretend that it has.**
