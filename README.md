# HelixGuard

A **verification-first** genomic sequence extraction and alignment application.

This repository contains the **Phase 1 frontend** — a fully interactive React + TypeScript dashboard running with predefined mock scenarios. The C++ Smith–Waterman engine, Python middleware, and LLM agents are not yet connected.

---

## Quick start

```bash
cd frontend
npm install
npm run dev
```

Then open **http://localhost:5173** in your browser.

---

## Technology stack

| Tool | Purpose |
|------|---------|
| React 18 + TypeScript | UI framework |
| Vite | Build tool & dev server |
| Tailwind CSS v3 | Utility-first styling |
| Lucide React | Icon library |

---

## Project structure

```
frontend/
├── src/
│   ├── components/
│   │   ├── Sidebar.tsx              Sidebar navigation
│   │   ├── Header.tsx               Page header with DEMO MODE badge
│   │   ├── PipelineStepper.tsx      4-stage pipeline status indicator
│   │   ├── DocumentInput.tsx        Document paste + run controls
│   │   ├── ExtractionEvidence.tsx   Verification evidence display
│   │   ├── AnchorRecoveryInspector.tsx  3 interactive anchor scenarios
│   │   ├── AlignmentMatrix.tsx      DP matrix heatmap + table view
│   │   └── StatusBadge.tsx          Status badge component
│   ├── pages/
│   │   ├── Dashboard.tsx            Pipeline overview + quick start
│   │   ├── SequenceExtraction.tsx   Main extraction workflow
│   │   ├── Alignment.tsx            Alignment results
│   │   ├── TestCases.tsx            10 predefined test cases
│   │   └── About.tsx                Design decisions & limitations
│   ├── services/
│   │   ├── helixguardApi.ts         Abstract API interface
│   │   └── mockHelixguardApi.ts     Mock implementation
│   ├── types/
│   │   └── helixguard.ts            TypeScript interfaces
│   ├── data/
│   │   └── demoScenarios.ts         All mock scenarios + test cases
│   ├── hooks/
│   │   └── useHelixGuard.ts         State management hook
│   └── utils/
│       └── smithWaterman.ts         Deterministic SW algorithm
├── .env                             VITE_USE_MOCK_API=true
└── vite.config.ts
```

---

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `VITE_USE_MOCK_API` | `true` | Use mock scenarios (set to `false` when backend is available) |

---

## TypeScript check

```bash
cd frontend
npx tsc --noEmit
```

---

## Anchor recovery scenarios

| Scenario | Anchors | Recovery | Outcome |
|----------|---------|----------|---------|
| A | Both valid | — | Verified |
| B | Both failed | Exact quote (unique) | Candidate accepted |
| C | Both failed | Exact quote (ambiguous) | Abstained |

---

## Test cases

10 predefined test cases are accessible from the **Test Cases** page:

1. Valid extraction
2. Incorrect preceding anchor
3. Incorrect following anchor
4. Both anchors incorrect, recoverable
5. Both anchors incorrect, ambiguous
6. Candidate sequence absent from source
7. Truncated sequence
8. Duplicate candidate quote
9. Invalid nucleotide characters
10. Alignment with mismatches

---

## Disclaimer

HelixGuard is a research prototype. All results use **synthetic data only**.  
This application does **not** provide clinical diagnoses, medical advice, or treatment recommendations.
