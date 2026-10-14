# CLAUDE.md — Project HelixGuard

Verification-first genomic sequence extraction and alignment system for a high-stakes hackathon.
Priorities: correctness, traceability, deterministic verification, robust failure handling, working end-to-end demo. Do not add complexity that doesn't serve these.

## Role

Act as Principal Systems Architect, Senior C++ Engineer, Python Backend Engineer, and AI Reliability Engineer. Build a functioning application, run its tests, fix failures, and document limitations. Do not just generate files.

## Working Agreement

- **Current milestone: Complete (Milestones 1–7 implemented and verified)**
- Implement ONLY the current milestone. Do not skip ahead or stub later components.
- At the start: inspect the repo and environment (compilers, Python version, Node, Ollama, Docker). Do not assume dependencies, model weights, or services exist.
- Before moving on, for each milestone:
  1. Run the relevant tests and fix failures.
  2. Explain what was implemented.
  3. Show the exact commands to run it.
  4. List remaining limitations.
- Never claim tests pass without running them. Never claim a feature exists if it is stubbed. Never invent test results.
- Show a full implementation plan before writing code for a milestone.

## Core Principle

The LLM may propose WHERE a sequence is. Only deterministic code operating on the source text may extract and verify the nucleotides.

- Never use an LLM to reconstruct, complete, repair, guess-normalize, or modify a nucleotide sequence.
- If the intended sequence and its boundaries can't be established with sufficient evidence, **abstain**.
- Do not claim zero hallucinations, guaranteed clinical safety, or diagnostic accuracy.
- Example failure to prevent: `ATCGATCG` → `ATCGACTG`. Both are valid DNA, but different sequences.

## Integrity Rules (apply everywhere)

1. **Source text is authoritative** for extracted characters. The LLM is not.
2. **Never accept a model-generated sequence as extracted data.** The LLM may quote a candidate excerpt; deterministic code must independently verify it against the original input.
3. **Syntax validation ≠ source verification.** `^[ACGT]+$` does not mean correct. Track separately:
   - Candidate located
   - Alphabet valid
   - Boundaries established
   - Complete sequence verified
   - Intended field supported by context
   - Source fidelity verified
   - Eligible for alignment
   Do not collapse these into one regex. Alignment requires all checks for the configured task to pass.
4. **Never repair sequence content with an LLM.**
5. **No silent acceptance.** Every rejection, abstention, recovery attempt, normalization op, and verification has an explicit status or traceable record.
6. **No clinical diagnosis.** Smith–Waterman doesn't establish pathogenicity, diagnose, or recommend treatment. No clinical recommendation cards.

## Architecture

```
HelixGuard/
├── engine/            # C++17 Smith–Waterman service (port 8080)
│   ├── main.cpp
│   ├── alignment.hpp / alignment.cpp
│   ├── CMakeLists.txt
│   └── tests/
├── middleware/        # Python 3.12 FastAPI
│   ├── main.py  schemas.py  extraction.py  anchor_recovery.py
│   ├── validation.py  provenance.py  critic.py
│   ├── requirements.txt  .env.example
│   └── tests/
├── frontend/          # React + TypeScript + Vite + Tailwind
│   ├── src/  package.json  vite.config.ts
├── tests/test_end_to_end.py
├── docker-compose.yml  .gitignore  README.md
```

Adapt if needed, but keep clear separation between extraction, verification, alignment, AI-assisted localization, and presentation.

### Stack

- **Engine:** C++17, cpp-httplib, nlohmann/json, CMake, port 8080. RAII / safe memory.
- **Middleware:** Python 3.12, FastAPI, Pydantic, HTTPX (or equivalent), pytest. Type hints throughout.
- **AI localization:** Optional Ollama, configurable local model (e.g. qwen2.5:7b, llama3.2). **Deterministic pipeline must work without Ollama.**
- **Frontend:** React, TypeScript, Vite, Tailwind.
- **Deploy:** Docker Compose where practical; must also run locally without Docker.
- Must run on Apple Silicon MacBook. No paid APIs. No unnecessary cloud dependencies.
- Document that local Ollama ≠ air-gapped; true isolation needs network restrictions plus locally available dependencies and weights.

## Milestones

1. **C++ engine** — Smith–Waterman, input validation, tests, HTTP server.
2. **Deterministic Python extraction** — exact source matching, spans, boundary checks, validation, provenance; normal + adversarial tests.
3. **Anchor recovery** — wrong before/after anchors, both wrong, duplicate quotes, ambiguous fields; abstention paths; bounded fuzzy matching only if time permits.
4. **Backend integration** — connect verified extraction to engine; `/extract-and-align`; structured errors and timeouts; full backend tests.
5. **Frontend** — input form, real pipeline results, provenance/recovery details, DP matrix, three demos.
6. **Optional LLM** — Ollama, Scout, optional Critic, controlled retries; deterministic-only mode still works.
7. **Final testing + docs** — all tests, fix integration failures, document setup/architecture/limitations/demo, record known failures honestly.

If time is short, prioritize: deterministic extraction/verification → C++ engine → frontend. Add LLM localization only after safety-critical behavior works.

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
- First row and column initialized to 0.
- Track max-scoring cell; support traceback if feasible.

Response (illustrative; all values computed from real input, never hardcoded):
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

Validate: missing fields, empty sequences, unsupported characters, excessively large inputs, invalid scoring params, malformed JSON. Implement CORS for the local frontend.

Tests: known scores, mismatches, empty input, edge cases. Verify expected values independently (e.g. hand calculation or an independent reference implementation).

The engine must NOT claim its input was extracted correctly — that is the middleware's job.

## Milestone 2 — Deterministic Extraction

**Endpoint:** `POST /extract`
```json
{
  "document_text": "Observed sequence: ATCGATCG",
  "field_type": "observed_sequence",
  "sequence_alphabet": "DNA"
}
```
Schema may add options for ambiguity codes, normalization rules, and recovery config.

Responsibilities: identify candidate spans; preserve original text; record exact offsets; establish boundaries; apply only explicitly defined normalization; validate alphabet; establish fidelity and completeness; return structured results + provenance; abstain when intent can't be established.

Alphabets: DNA (A,C,G,T), RNA (A,C,G,U). IUPAC ambiguity codes as a configurable extension. **Never silently convert U↔T.** Whitespace, line numbers, and punctuation handled by explicit, tested rules — never strip every non-letter character from a whole paragraph.

## Milestone 3 — Anchor Recovery (`anchor_recovery.py`, mandatory)

Anchors are localization hints, not trusted boundaries. Never depend entirely on them.

**Normal verification:** exact-match `anchor_before`, `candidate_quote`, `anchor_after` against the original; confirm strings exist, ordering is consistent, quote belongs to the intended field, boundaries exclude unrelated text, sequence is complete. Handle repeated anchors explicitly — never pick the first of multiple remaining combinations.

**Case A — `anchor_before` wrong** (e.g. doc `Observed sequence: GCTAGCTA`, proposed anchor `Tumor DNA sequence:`): try exact anchors → record failure → search exact quote → check occurrence count → inspect context → independently establish boundaries and field identity → accept only if all rules pass, else abstain. A bad anchor doesn't invalidate an independently verifiable candidate.

**Case B — `anchor_after` wrong:** verify preceding anchor and exact quote, check ordering, establish boundaries by deterministic parsing and context. Accept only if identity and completeness are established. Never invent a replacement boundary.

**Case C — both wrong:** record both failures → search exact quote → none = reject; multiple = evaluate each independently against field and context; one = still verify boundaries, completeness, field identity. A unique quote is not automatically a verified sequence (e.g. the same sequence may appear in a reference section and an observed-sample section — identify the correct field). Ambiguous/truncated/unsupported → abstain.

**Case D — candidate quote itself wrong:** never modify it to match; never accept a similar sequence; search alternatives only under a defined recovery strategy with deterministic verification; abstain if uncertain.

**Case E — multiple candidates:** enumerate with source locations, evaluate contextual support, never default to the first, require an unambiguous field match or return an ambiguity status. May ask the user to choose.

**Bounded fuzzy matching** (optional, localization only): e.g. source `Observed snequce:` vs anchor `Observed sequence:`. Must never modify nucleotide characters or rewrite the source; documented similarity threshold; bounded search region; detect competing matches; record proposed match + similarity; require exact source verification of the final sequence; abstain if ambiguous. A fuzzy anchor match is not proof of sequence fidelity.

## Milestone 6 — AI Localization and Retries

Only integrate after deterministic tests pass.

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
`candidate_quote` may be an excerpt containing a sequence; deterministic code extracts the sequence from it.

**Agent B — Context Critic (`critic.py`):** evaluates whether the location is consistent with the requested field. Must not rewrite the sequence, declare an unverified sequence correct, override deterministic validation, diagnose, or infer clinical significance. A successful Critic response cannot compensate for failed source-fidelity verification.

**Retries:** configurable max 3 attempts; bounded, purposeful, observable.
1. Locate the requested field and quote surrounding context.
2. On anchor/candidate failure: ask for a *different exact excerpt* from the source, including the previous failure reason. Never ask the model to correct or reconstruct the sequence.
3. If ambiguity remains: distinguish between explicitly identified candidates or propose a better-supported location.

Rules: every proposal goes through the same deterministic recovery + validation; no retry after verified success; no retry on deterministic input errors the model can't fix; no retries to force a candidate to pass; never exceed the limit; keep an audit record per attempt; bounded timeouts; handle model unavailable and malformed responses; deterministic-only mode when Ollama is unavailable. The retry budget is a limit, not a requirement. After the final failure, return explicit abstention/rejection with a useful error code.

## Provenance (`provenance.py`)

For each accepted extraction record: request/document ID; input text hash; exact source offsets; exact source excerpt; extracted sequence; alphabet; normalization operations; candidate quote; per-anchor verification; recovery method; number of LLM attempts; boundary, completeness, source-fidelity, and context/field validation results; final status and reason.

- **Offset convention:** zero-based, half-open, `start <= pos < end`, referring to the **original** input string, not a normalized copy.
- If normalization removes spaces or line numbers, keep a mapping tracing each extracted character to its original position.
- Don't claim extracted-PDF-text offsets equal original-PDF offsets; for PDF support record page + bounding box where available.
- Keep sensitive data out of logs by default. Use synthetic/fictional data only.
- PDF parsing/OCR are extensions — don't represent them as implemented until they work. MVP is pasted text.

## Milestone 4 — Backend Orchestration

**Endpoint:** `POST /extract-and-align`
```json
{
  "document_text": "Observed sequence: ATCGATCG",
  "reference_sequence": "ATCGATCG",
  "field_type": "observed_sequence",
  "sequence_alphabet": "DNA"
}
```

Flow: validate request → identify candidate span → (optional) LLM localization → verify anchors and exact quote → deterministic recovery if needed → boundaries + completeness → alphabet + source fidelity → verified? No → abstain; Yes → record provenance → call C++ engine → return alignment. Prefer the deterministic route when it can resolve the task alone; the candidate may be located before any LLM call.

**Critical gating rule:** the C++ engine must never receive an unverified extracted query sequence. The user-supplied reference sequence must also pass input validation. Valid sequences ≠ biological relevance.

Success response (illustrative; offsets/scores computed from real input):
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
Use suitable HTTP status codes and consistent error schemas. Never return fabricated alignment after failed extraction.

## Milestone 5 — Frontend Dashboard

Clean, technical React dashboard.

- **A. Document input:** large textarea (synthetic text), reference-sequence input, field selector, DNA/RNA selector, Extract & Align button, Load Demo buttons.
- **B. Pipeline status:** request validation, candidate localization, anchor verification, recovery (if required), sequence validation, provenance verification, alignment. **Show real backend state only — no simulated stages or fake progress percentages.**
- **C. Extraction evidence:** accepted sequence, source excerpt, offsets, verified/failed anchors, recovery method, normalization ops, completeness and source-fidelity statuses.
- **D. Alignment visualization:** score, DP matrix heatmap, row/column labels, max cell, legend, scrollable for large matrices.
- **E. Failure/abstention panel:** human-readable reason, error code, whether retry or manual disambiguation is possible, explicit note that no alignment was run when extraction was unverified.

No clinical diagnosis, treatment suggestion, or unsupported mutation interpretation.

## Testing (core feature, not cosmetic)

Use deterministic synthetic fixtures with known expected results. Mock Ollama in unit tests — they must not need a running LLM.

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

**Integrity tests:** source `ATCGATCG` vs corrupted proposal `ATCGACTG`. Verify: model-proposed bases are never accepted as source truth; extraction happens only through deterministic source matching + boundary validation; abstain if recovery can't establish the intended sequence; no alignment after failed source-fidelity verification. Also test the reverse: a syntactically valid model sequence that doesn't occur in the source.

**Alignment tests:** known score and matrix; exact matches; mismatches; indels where supported; empty inputs; invalid alphabet; large inputs and size limits; malformed API requests.

**End-to-end tests:**
1. Correct sequence → verified extraction → alignment
2. Incorrect anchor → deterministic recovery → verified extraction (if evidence suffices)
3. Both anchors wrong → unique, contextually supported candidate recovered
4. Both anchors wrong → ambiguous candidate → abstain
5. Corrupted candidate → verification fails, or independently verified source sequence replaces it
6. No sequence found → no alignment
7. Ambiguous field → abstain or explicit user disambiguation
8. Alignment service unavailable → clear backend error

## Demo Cases

- **Demo A — Success:** clearly labeled, complete DNA sequence → deterministic extraction, verified span, successful alignment, visible provenance + matrix.
- **Demo B — Incorrect anchors:** valid, uniquely identifiable sequence with one or both wrong LLM anchors → anchor failure recorded; recovery via exact source matching; accepted only if field identity, boundaries, completeness, and fidelity are independently established, else abstain.
- **Demo C — Ambiguous/missing:** no supported sequence, or multiple undisambiguable candidates → explicit abstention, useful message, no fabricated sequence, no engine call.
- **Extra:** a case where the LLM proposes an altered sequence, demonstrating the system never silently accepts it.

## Engineering Requirements

- Modular, maintainable code; avoid unnecessary abstractions.
- Pydantic models + type hints in Python; RAII in C++.
- Validate all external inputs.
- No hardcoded absolute paths; configuration via environment variables; `.env.example` with no real secrets.
- Useful logging that excludes document contents by default.
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
8. Unverified sequences cannot reach the engine.
9. Frontend shows actual extraction and alignment results.
10. All three demos work.
11. Automated tests cover the major adversarial cases.
12. Setup and known limitations are documented.

The application must be honest about what it has verified and what it cannot establish.

> The innovation is not the number of AI agents. It is AI-assisted localization combined with deterministic source verification, robust recovery, traceable provenance, and explicit abstention.
>
> **When the system cannot prove it has recovered the intended sequence from the supplied source, it must not pretend that it has.**
