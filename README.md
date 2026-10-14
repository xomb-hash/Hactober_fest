# HelixGuard

A **verification-first** genomic sequence extraction and alignment system for high-stakes verification.

> **Core Principle:** An LLM may propose *where* a sequence is located. Only deterministic code operating directly on the authoritative source text may extract and verify the nucleotides.

---

## Architecture Overview

```
HelixGuard/
├── engine/            # C++17 Smith–Waterman alignment engine (port 8080)
│   ├── alignment.hpp / alignment.cpp
│   ├── main.cpp       (HTTP server with cpp-httplib & nlohmann/json)
│   ├── CMakeLists.txt
│   ├── Dockerfile
│   └── tests/
├── middleware/        # Python 3.12 FastAPI service (port 8000)
│   ├── main.py        (FastAPI routes: /extract, /extract-and-align, /health)
│   ├── schemas.py     (Pydantic v2 data models)
│   ├── extraction.py  (Deterministic parsing, boundaries, offset mapping)
│   ├── anchor_recovery.py (Cases A-E recovery, fuzzy anchors)
│   ├── validation.py  (DNA/RNA alphabets, strict no U↔T conversion)
│   ├── provenance.py  (SHA-256 hash, zero-based half-open offsets)
│   ├── critic.py      (Deterministic & Ollama field consistency critic)
│   ├── scout.py       (Localization Scout with bounded retries)
│   ├── Dockerfile
│   └── tests/
├── frontend/          # React 18 + TypeScript + Vite + Tailwind (port 5173)
│   ├── src/           (Components, Pages, Live & Mock API services)
│   ├── Dockerfile
│   └── vite.config.ts
├── tests/
│   └── test_end_to_end.py (8 end-to-end integration tests)
├── docker-compose.yml
└── CLAUDE.md          (Specification & verification contract)
```

---

## Quick Start

### Option A: Local Development (Native)

#### 1. C++ Alignment Engine (Port 8080)
```powershell
# Using MSVC (Developer PowerShell for VS 2026 / 2022)
cd engine
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --config Release
.\build\Release\server.exe
```

#### 2. Python Middleware (Port 8000)
```powershell
# Using uv or virtual environment with Python 3.12
cd middleware
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
uvicorn middleware.main:app --host 0.0.0.0 --port 8000
```

#### 3. React Frontend (Port 5173)
```powershell
cd frontend
npm install
npm run dev
```
Open **http://localhost:5173** in your browser. The top bar will display:
`🟢 LIVE BACKEND (Engine + Middleware)` when both services are running. You can also toggle to **Demo Mock Mode** anytime to run offline test scenarios.

---

### Option B: Docker Compose

To launch all 3 services together in isolated containers:
```bash
docker compose up --build
```
- Frontend: `http://localhost:5173`
- Middleware: `http://localhost:8000`
- Engine: `http://localhost:8080`

---

## Running the Automated Test Suites

### 1. Python Unit & End-to-End Tests (51 Tests)
```powershell
# Run the complete test suite (all 51 tests)
middleware\.venv\Scripts\python.exe -m pytest -v
```

Tests include:
- **Anchor Recovery (Cases A–E)**: Handling wrong `anchor_before`, wrong `anchor_after`, both wrong, fuzzy matching, and multiple candidates.
- **System Integrity**: Source `ATCGATCG` vs corrupted model quote `ATCGACTG` (verifies model hallucinated bases are strictly rejected and never accepted as truth).
- **Alphabet & Biology Validation**: Strict DNA (`ACGT`), RNA (`ACGU`), no silent `U↔T` conversion, and IUPAC ambiguity codes.
- **FastAPI Endpoint Gating**: Unverified sequences strictly blocked from reaching the C++ engine.
- **End-to-End Integration**: All 8 CLAUDE.md integration scenarios with live C++ engine traceback and matrix validation.

### 2. C++ Unit Tests (9 Tests)
```powershell
cd engine\build
ctest --output-on-failure -C Release
# Or directly run the binary:
.\Release\test_alignment.exe
```

---

## Integrity Guarantees

1. **Source text is authoritative**: Extracted sequence characters originate strictly from deterministic offsets in the user's document.
2. **Never accept model bases**: LLM quotes are location hints. Deterministic code matches and extracts nucleotides from the source document.
3. **Critical Safety Gating**: Unverified, ambiguous, truncated, or syntactically invalid sequences are prevented from ever reaching the alignment engine.
4. **Traceable Provenance**: Every extraction records SHA-256 document hash, zero-based half-open offsets `[start, end)`, character-level offset mappings, and validation checklist flags.
5. **No clinical diagnosis**: Smith–Waterman computes mathematical local alignment scores only. It does not provide pathogenicity classification or clinical recommendations.

---

## System Limitations

1. **Input Format**: Operates on plain text genomic reports and excerpts. PDF/OCR parsing is an extension not implemented in MVP.
2. **Local Alignment Scope**: Uses standard Smith–Waterman local dynamic programming with linear gap penalties.
3. **Synthetic Data**: Developed and tested against synthetic genomics reports. Not validated for clinical diagnostic use.
