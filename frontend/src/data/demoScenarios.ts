import type { DemoScenario, TestCase } from '../types/helixguard';
import { smithWaterman, DEFAULT_SCORING } from '../utils/smithWaterman';

// ─── Shared document text ─────────────────────────────────────────────────────

const SAMPLE_REPORT = `PATIENT REPORT — SYNTHETIC DEMO

Gene Analysis

Reference DNA sequence: ATCGATCG

Observed sequence: ATCGTTCG

Additional notes: This synthetic report is provided only to demonstrate text extraction and sequence alignment.

No real patient data is included.`;

// ─── Scenario A: Both anchors valid — verified ────────────────────────────────

const scenarioA: DemoScenario = {
  id: 'scenario-a',
  name: 'Scenario A — Both anchors valid',
  description:
    'The source document contains a uniquely identifiable observed sequence. Both anchors match exactly. Sequence is verified and alignment is run.',
  expectedOutcome: 'Verified — alignment permitted.',
  documentText: SAMPLE_REPORT,
  referenceSequence: 'ATCGATCG',
  targetField: 'Observed sequence',
  alphabet: 'DNA',
  extractionResult: {
    extractedSequence: 'ATCGTTCG',
    extractionStatus: 'verified',
    sourceFidelityStatus: 'verified',
    boundaryVerificationStatus: 'verified',
    completenessStatus: 'complete',
    recoveryMethod: 'none',
    anchorVerification: {
      anchorBefore: 'Observed sequence:',
      anchorAfter: 'Additional notes:',
      candidateQuote: 'ATCGTTCG',
      anchorBeforeMatched: 'matched',
      anchorAfterMatched: 'matched',
      candidateOccurrences: 1,
      recoveryStrategy: 'none',
      recoverySucceeded: true,
      finalDecision: 'verified',
      finalReason:
        'Both anchors matched. Candidate quote found exactly once between anchors. Source boundaries and completeness verified.',
    },
    provenance: {
      sourceOffsetStart: 89,
      sourceOffsetEnd: 97,
      sourceField: 'Observed sequence',
      normalizationOps: [],
    },
    validationErrors: [],
  },
  alignmentResult: smithWaterman('ATCGATCG', 'ATCGTTCG', DEFAULT_SCORING),
  pipelineState: {
    currentStage: 'complete',
    stages: {
      input: 'success',
      localization: 'success',
      verification: 'success',
      alignment: 'success',
    },
  },
};

// ─── Scenario B: Anchors wrong, recovery succeeds ─────────────────────────────

const scenarioB: DemoScenario = {
  id: 'scenario-b',
  name: 'Scenario B — Anchors incorrect, recovery succeeds',
  description:
    'The mock LLM proposes incorrect anchors. However, the candidate quote "GCTAGCTA" occurs exactly once in the intended field, so exact-quote recovery independently locates and verifies the sequence.',
  expectedOutcome: 'Accepted via exact-quote recovery. Alignment permitted.',
  documentText: `GENE PANEL REPORT — SYNTHETIC DEMO

Panel: BRCA1/2 Screening

Observed variant: GCTAGCTA

Result summary: Variant identified in coding region. For demonstration only.

Notes: No clinical conclusions should be drawn from this synthetic data.`,
  referenceSequence: 'GCTAGCTA',
  targetField: 'Observed sequence',
  alphabet: 'DNA',
  extractionResult: {
    extractedSequence: 'GCTAGCTA',
    extractionStatus: 'candidate',
    sourceFidelityStatus: 'verified',
    boundaryVerificationStatus: 'verified',
    completenessStatus: 'complete',
    recoveryMethod: 'exact_quote_search',
    anchorVerification: {
      anchorBefore: 'Observed sequence:',
      anchorAfter: 'Result notes:',
      candidateQuote: 'GCTAGCTA',
      anchorBeforeMatched: 'failed',
      anchorAfterMatched: 'failed',
      candidateOccurrences: 1,
      recoveryStrategy: 'exact_quote_search',
      recoverySucceeded: true,
      finalDecision: 'candidate',
      finalReason:
        'Both anchors failed. Exact-quote recovery attempted. "GCTAGCTA" found exactly once in the document. Boundaries and completeness independently verified. Sequence accepted under recovery; confidence is lower than full anchor verification.',
    },
    provenance: {
      sourceOffsetStart: 48,
      sourceOffsetEnd: 56,
      sourceField: 'Observed variant',
      normalizationOps: [],
    },
    validationErrors: [],
  },
  alignmentResult: smithWaterman('GCTAGCTA', 'GCTAGCTA', DEFAULT_SCORING),
  pipelineState: {
    currentStage: 'complete',
    stages: {
      input: 'success',
      localization: 'warning',
      verification: 'warning',
      alignment: 'success',
    },
  },
};

// ─── Scenario C: Both anchors wrong, recovery fails — abstained ───────────────

const scenarioC: DemoScenario = {
  id: 'scenario-c',
  name: 'Scenario C — Anchors incorrect, recovery fails (abstained)',
  description:
    'The document contains two plausible occurrences of the same sequence in different fields. Anchors are both wrong. Exact-quote search finds multiple locations; intended field cannot be established. System abstains.',
  expectedOutcome: 'Abstained — alignment not run.',
  documentText: `COMPARATIVE GENOMICS REPORT — SYNTHETIC DEMO

Reference sequence: TTAGCCAT

Observed sequence: TTAGCCAT

Analyst notes: Both the reference and observed sequences happen to share the same value in this synthetic example, illustrating the ambiguous-location failure mode.

No real genomic data is included.`,
  referenceSequence: 'TTAGCCAT',
  targetField: 'Observed sequence',
  alphabet: 'DNA',
  extractionResult: {
    extractedSequence: 'TTAGCCAT',
    extractionStatus: 'abstained',
    sourceFidelityStatus: 'failed',
    boundaryVerificationStatus: 'failed',
    completenessStatus: 'unknown',
    recoveryMethod: 'exact_quote_search',
    anchorVerification: {
      anchorBefore: 'Patient ID:',
      anchorAfter: 'Lab notes:',
      candidateQuote: 'TTAGCCAT',
      anchorBeforeMatched: 'failed',
      anchorAfterMatched: 'failed',
      candidateOccurrences: 2,
      recoveryStrategy: 'exact_quote_search',
      recoverySucceeded: false,
      finalDecision: 'abstained',
      finalReason:
        'Both anchors failed. Exact-quote search found 2 occurrences of "TTAGCCAT" in the document (in "Reference sequence" and "Observed sequence" fields). Intended field cannot be established without additional evidence. System abstains; alignment is not run.',
    },
    provenance: {
      sourceOffsetStart: null,
      sourceOffsetEnd: null,
      sourceField: null,
      normalizationOps: [],
    },
    validationErrors: [
      'Candidate quote "TTAGCCAT" appears 2 times in source document.',
      'Intended field cannot be determined. System abstains.',
    ],
  },
  alignmentResult: {
    referenceSequence: 'TTAGCCAT',
    querySequence: 'TTAGCCAT',
    alignedReference: '',
    alignedQuery: '',
    alignmentScore: 0,
    maxScoringCell: { row: 0, col: 0, value: 0 },
    dpMatrix: [],
    scoringParams: DEFAULT_SCORING,
    skipped: true,
    skipReason:
      'Alignment not run because source verification did not pass. Status: Abstained.',
  },
  pipelineState: {
    currentStage: 'complete',
    stages: {
      input: 'success',
      localization: 'error',
      verification: 'error',
      alignment: 'skipped',
    },
  },
};

// ─── Additional scenarios for test cases ─────────────────────────────────────

const scenarioValidExtraction: DemoScenario = {
  ...scenarioA,
  id: 'tc-valid-extraction',
  name: 'TC-1 Valid extraction',
  description: 'Standard extraction where both anchors match and the sequence is uniquely located.',
  expectedOutcome: 'Extracted sequence verified. Alignment score computed.',
};

const scenarioIncorrectPrecedingAnchor: DemoScenario = {
  id: 'tc-incorrect-preceding-anchor',
  name: 'TC-2 Incorrect preceding anchor',
  description: 'The preceding anchor does not match the source text. Recovery attempted.',
  expectedOutcome: 'Preceding anchor failed. Recovery via exact quote search.',
  documentText: scenarioB.documentText,
  referenceSequence: 'GCTAGCTA',
  targetField: 'Observed sequence',
  alphabet: 'DNA',
  extractionResult: {
    ...scenarioB.extractionResult,
    anchorVerification: {
      ...scenarioB.extractionResult.anchorVerification,
      anchorBeforeMatched: 'failed',
      anchorAfterMatched: 'matched',
      finalReason:
        'Preceding anchor failed; following anchor matched. Exact-quote recovery confirmed single occurrence. Sequence accepted.',
    },
  },
  alignmentResult: smithWaterman('GCTAGCTA', 'GCTAGCTA', DEFAULT_SCORING),
  pipelineState: scenarioB.pipelineState,
};

const scenarioIncorrectFollowingAnchor: DemoScenario = {
  id: 'tc-incorrect-following-anchor',
  name: 'TC-3 Incorrect following anchor',
  description: 'The following anchor does not match. Recovery attempted.',
  expectedOutcome: 'Following anchor failed. Recovery via exact quote search.',
  documentText: scenarioB.documentText,
  referenceSequence: 'GCTAGCTA',
  targetField: 'Observed sequence',
  alphabet: 'DNA',
  extractionResult: {
    ...scenarioB.extractionResult,
    anchorVerification: {
      ...scenarioB.extractionResult.anchorVerification,
      anchorBeforeMatched: 'matched',
      anchorAfterMatched: 'failed',
      finalReason:
        'Following anchor failed; preceding anchor matched. Exact-quote recovery confirmed single occurrence. Sequence accepted.',
    },
  },
  alignmentResult: smithWaterman('GCTAGCTA', 'GCTAGCTA', DEFAULT_SCORING),
  pipelineState: scenarioB.pipelineState,
};

const scenarioBothWrongRecoverable: DemoScenario = {
  ...scenarioB,
  id: 'tc-both-wrong-recoverable',
  name: 'TC-4 Both anchors incorrect, recoverable',
};

const scenarioBothWrongAmbiguous: DemoScenario = {
  ...scenarioC,
  id: 'tc-both-wrong-ambiguous',
  name: 'TC-5 Both anchors incorrect, ambiguous',
};

const scenarioCandidateAbsent: DemoScenario = {
  id: 'tc-candidate-absent',
  name: 'TC-6 Candidate sequence absent from source',
  description: 'The LLM-proposed candidate quote does not appear anywhere in the source document.',
  expectedOutcome: 'Rejected. Candidate not found in source. Alignment not run.',
  documentText: `GENE PANEL REPORT — SYNTHETIC DEMO\n\nObserved variant: AACCTTGG\n\nNotes: Demo only.`,
  referenceSequence: 'AACCTTGG',
  targetField: 'Observed sequence',
  alphabet: 'DNA',
  extractionResult: {
    extractedSequence: 'GGTTCCAA',
    extractionStatus: 'rejected',
    sourceFidelityStatus: 'failed',
    boundaryVerificationStatus: 'failed',
    completenessStatus: 'unknown',
    recoveryMethod: 'exact_quote_search',
    anchorVerification: {
      anchorBefore: 'Observed sequence:',
      anchorAfter: 'Result notes:',
      candidateQuote: 'GGTTCCAA',
      anchorBeforeMatched: 'failed',
      anchorAfterMatched: 'failed',
      candidateOccurrences: 0,
      recoveryStrategy: 'exact_quote_search',
      recoverySucceeded: false,
      finalDecision: 'rejected',
      finalReason:
        'Candidate quote "GGTTCCAA" not found anywhere in the source document. Sequence rejected.',
    },
    provenance: {
      sourceOffsetStart: null,
      sourceOffsetEnd: null,
      sourceField: null,
      normalizationOps: [],
    },
    validationErrors: ['Candidate quote not found in source document.'],
  },
  alignmentResult: {
    referenceSequence: 'AACCTTGG',
    querySequence: 'GGTTCCAA',
    alignedReference: '',
    alignedQuery: '',
    alignmentScore: 0,
    maxScoringCell: { row: 0, col: 0, value: 0 },
    dpMatrix: [],
    scoringParams: DEFAULT_SCORING,
    skipped: true,
    skipReason: 'Alignment not run because source verification did not pass. Status: Rejected.',
  },
  pipelineState: {
    currentStage: 'complete',
    stages: {
      input: 'success',
      localization: 'error',
      verification: 'error',
      alignment: 'skipped',
    },
  },
};

const scenarioTruncated: DemoScenario = {
  id: 'tc-truncated',
  name: 'TC-7 Truncated sequence',
  description:
    'The extracted candidate is shorter than expected, indicating a possible truncation.',
  expectedOutcome: 'Candidate located but completeness check failed. Abstained.',
  documentText: `SEQUENCING REPORT — SYNTHETIC DEMO\n\nObserved sequence: ATCG\n\nNotes: Sequence appears cut off. Demo only.`,
  referenceSequence: 'ATCGATCG',
  targetField: 'Observed sequence',
  alphabet: 'DNA',
  extractionResult: {
    extractedSequence: 'ATCG',
    extractionStatus: 'abstained',
    sourceFidelityStatus: 'unverified',
    boundaryVerificationStatus: 'failed',
    completenessStatus: 'truncated',
    recoveryMethod: 'none',
    anchorVerification: {
      anchorBefore: 'Observed sequence:',
      anchorAfter: 'Notes:',
      candidateQuote: 'ATCG',
      anchorBeforeMatched: 'matched',
      anchorAfterMatched: 'matched',
      candidateOccurrences: 1,
      recoveryStrategy: 'none',
      recoverySucceeded: false,
      finalDecision: 'abstained',
      finalReason:
        'Anchors matched and candidate located. However, completeness check failed: extracted length (4) is less than reference length (8). System abstains.',
    },
    provenance: {
      sourceOffsetStart: 54,
      sourceOffsetEnd: 58,
      sourceField: 'Observed sequence',
      normalizationOps: [],
    },
    validationErrors: ['Completeness check failed: extracted sequence may be truncated.'],
  },
  alignmentResult: {
    referenceSequence: 'ATCGATCG',
    querySequence: 'ATCG',
    alignedReference: '',
    alignedQuery: '',
    alignmentScore: 0,
    maxScoringCell: { row: 0, col: 0, value: 0 },
    dpMatrix: [],
    scoringParams: DEFAULT_SCORING,
    skipped: true,
    skipReason:
      'Alignment not run because source verification did not pass. Status: Abstained.',
  },
  pipelineState: {
    currentStage: 'complete',
    stages: {
      input: 'success',
      localization: 'warning',
      verification: 'error',
      alignment: 'skipped',
    },
  },
};

const scenarioDuplicateQuote: DemoScenario = {
  ...scenarioC,
  id: 'tc-duplicate-quote',
  name: 'TC-8 Duplicate candidate quote',
};

const scenarioInvalidChars: DemoScenario = {
  id: 'tc-invalid-chars',
  name: 'TC-9 Invalid nucleotide characters',
  description:
    'The extracted sequence contains characters outside the expected DNA alphabet.',
  expectedOutcome: 'Rejected — invalid nucleotide characters detected.',
  documentText: `SEQUENCING REPORT — SYNTHETIC DEMO\n\nObserved sequence: ATCGXXCG\n\nNotes: Demo only.`,
  referenceSequence: 'ATCGATCG',
  targetField: 'Observed sequence',
  alphabet: 'DNA',
  extractionResult: {
    extractedSequence: 'ATCGXXCG',
    extractionStatus: 'rejected',
    sourceFidelityStatus: 'failed',
    boundaryVerificationStatus: 'verified',
    completenessStatus: 'complete',
    recoveryMethod: 'none',
    anchorVerification: {
      anchorBefore: 'Observed sequence:',
      anchorAfter: 'Notes:',
      candidateQuote: 'ATCGXXCG',
      anchorBeforeMatched: 'matched',
      anchorAfterMatched: 'matched',
      candidateOccurrences: 1,
      recoveryStrategy: 'none',
      recoverySucceeded: true,
      finalDecision: 'rejected',
      finalReason:
        'Sequence located in source. However, alphabet validation failed: characters "X" are not valid DNA nucleotides. Sequence rejected because it cannot be aligned.',
    },
    provenance: {
      sourceOffsetStart: 54,
      sourceOffsetEnd: 62,
      sourceField: 'Observed sequence',
      normalizationOps: [],
    },
    validationErrors: ['Invalid DNA nucleotide characters detected: X (positions 5, 6).'],
  },
  alignmentResult: {
    referenceSequence: 'ATCGATCG',
    querySequence: 'ATCGXXCG',
    alignedReference: '',
    alignedQuery: '',
    alignmentScore: 0,
    maxScoringCell: { row: 0, col: 0, value: 0 },
    dpMatrix: [],
    scoringParams: DEFAULT_SCORING,
    skipped: true,
    skipReason: 'Alignment not run because sequence contains invalid nucleotide characters.',
  },
  pipelineState: {
    currentStage: 'complete',
    stages: {
      input: 'success',
      localization: 'success',
      verification: 'error',
      alignment: 'skipped',
    },
  },
};

const scenarioWithMismatches: DemoScenario = {
  id: 'tc-alignment-mismatches',
  name: 'TC-10 Alignment with mismatches',
  description:
    'Sequence verified from source. Alignment reveals mismatches against the reference.',
  expectedOutcome: 'Verified. Alignment shows mismatches at positions 5 and 6.',
  documentText: SAMPLE_REPORT,
  referenceSequence: 'ATCGATCG',
  targetField: 'Observed sequence',
  alphabet: 'DNA',
  extractionResult: scenarioA.extractionResult,
  alignmentResult: smithWaterman('ATCGATCG', 'ATCGTTCG', DEFAULT_SCORING),
  pipelineState: scenarioA.pipelineState,
};

// ─── TC-11: Viral Genome Identification (RefSeq Database Search) ───────────────

const scenarioViralIdentification: DemoScenario = {
  id: 'tc-viral-identification',
  name: 'TC-11 Viral Genome Identification (RefSeq Search)',
  description:
    'Pan-viral clinical screening: Query sequence is extracted and verified from the report, then screened across 19,625 RefSeq viral genomes via k-mer inverted index and Smith–Waterman alignment.',
  expectedOutcome: 'Verified from source. Screened 19,625 RefSeq viral genomes; matched Hyposoter fugitivus ichnovirus (NC_008987.1).',
  documentText: `CLINICAL VIROLOGY REPORT — SYNTHETIC DEMO

Patient ID: V-40912
Specimen: Unknown Viral Isolate
Target Field: Observed sequence

Observed sequence: TTACCTGCACAGCTCTGCATAGTCCTACACTGATACGGATGAAAGAAATGAAACTAAACATATTAAACACAACCATTTAT

Laboratory Notes: Extracted fragment submitted for pan-viral RefSeq database search and clinical attribution.`,
  referenceSequence: 'DATABASE',
  targetField: 'Observed sequence',
  alphabet: 'DNA',
  extractionResult: {
    extractedSequence: 'TTACCTGCACAGCTCTGCATAGTCCTACACTGATACGGATGAAAGAAATGAAACTAAACATATTAAACACAACCATTTAT',
    extractionStatus: 'verified',
    sourceFidelityStatus: 'verified',
    boundaryVerificationStatus: 'verified',
    completenessStatus: 'complete',
    recoveryMethod: 'none',
    anchorVerification: {
      anchorBefore: 'Observed sequence:',
      anchorAfter: 'Laboratory Notes:',
      candidateQuote: 'TTACCTGCACAGCTCTGCATAGTCCTACACTGATACGGATGAAAGAAATGAAACTAAACATATTAAACACAACCATTTAT',
      anchorBeforeMatched: 'matched',
      anchorAfterMatched: 'matched',
      candidateOccurrences: 1,
      recoveryStrategy: 'none',
      recoverySucceeded: true,
      finalDecision: 'verified',
      finalReason: 'Extracted sequence verified from field context against source document.',
    },
    provenance: {
      sourceOffsetStart: 104,
      sourceOffsetEnd: 184,
      sourceField: 'Observed sequence',
      normalizationOps: [],
    },
    validationErrors: [],
  },
  alignmentResult: smithWaterman(
    'TTACCTGCACAGCTCTGCATAGTCCTACACTGATACGGATGAAAGAAATGAAACTAAACATATTAAACACAACCATTTAT',
    'TTACCTGCACAGCTCTGCATAGTCCTACACTGATACGGATGAAAGAAATGAAACTAAACATATTAAACACAACCATTTAT',
    DEFAULT_SCORING
  ),
  pipelineState: {
    currentStage: 'complete',
    stages: {
      input: 'success',
      localization: 'success',
      verification: 'success',
      alignment: 'success',
    },
  },
  genomeIdentification: {
    status: 'success',
    querySequence: 'TTACCTGCACAGCTCTGCATAGTCCTACACTGATACGGATGAAAGAAATGAAACTAAACATATTAAACACAACCATTTAT',
    queryLength: 80,
    totalCandidatesEvaluated: 19625,
    topCandidates: [
      {
        rank: 1,
        accession: 'NC_008987.1',
        organism: 'Hyposoter fugitivus ichnovirus DNA, segment D2, complete sequence',
        alignmentScore: 160,
        matchedLength: 80,
        targetStart: 0,
        targetEnd: 280,
        sharedKmers: 3,
        lowComplexity: false,
        hasPolyATail: false,
      },
      {
        rank: 2,
        accession: 'NC_038814.1',
        organism: 'Cardamom bushy dwarf virus clone Fr-S22 segment DNA-U1, complete sequence',
        alignmentScore: 83,
        matchedLength: 80,
        targetStart: 0,
        targetEnd: 1080,
        sharedKmers: 1,
        lowComplexity: false,
        hasPolyATail: false,
      },
      {
        rank: 3,
        accession: 'NC_047736.1',
        organism: 'Bacillus phage B5S, complete genome',
        alignmentScore: 82,
        matchedLength: 80,
        targetStart: 39968,
        targetEnd: 40448,
        sharedKmers: 1,
        lowComplexity: false,
        hasPolyATail: false,
      },
    ],
    closestMatch: {
      rank: 1,
      accession: 'NC_008987.1',
      organism: 'Hyposoter fugitivus ichnovirus DNA, segment D2, complete sequence',
      alignmentScore: 160,
      matchedLength: 80,
      targetStart: 0,
      targetEnd: 280,
      sharedKmers: 3,
      lowComplexity: false,
      hasPolyATail: false,
    },
    abstain: false,
    abstainReason: null,
    searchTimeMs: 183.0,
  },
};

// ─── TC-12: Viral Database Low-Complexity Poly-A Abstain ───────────────────────

const scenarioViralPolyAAbstain: DemoScenario = {
  id: 'tc-viral-poly-a-abstain',
  name: 'TC-12 Viral Database Low-Complexity Poly-A Abstain',
  description:
    'Homopolymer run safety gating: Query is a terminal poly-A sequence. Gating flags potential score inflation against picornavirus poly-A tail and safely abstains on organism attribution.',
  expectedOutcome: 'Abstained on database match: LOW_COMPLEXITY_POLY_A_MATCH to prevent false-positive attribution.',
  documentText: `CLINICAL VIROLOGY REPORT — SYNTHETIC DEMO

Patient ID: V-88219
Specimen: Unknown Viral Isolate
Target Field: Observed sequence

Observed sequence: AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA

Laboratory Notes: Polyadenylated 3' terminal isolate fragment.`,
  referenceSequence: 'DATABASE',
  targetField: 'Observed sequence',
  alphabet: 'DNA',
  extractionResult: {
    extractedSequence: 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA',
    extractionStatus: 'verified',
    sourceFidelityStatus: 'verified',
    boundaryVerificationStatus: 'verified',
    completenessStatus: 'complete',
    recoveryMethod: 'none',
    anchorVerification: {
      anchorBefore: 'Observed sequence:',
      anchorAfter: 'Laboratory Notes:',
      candidateQuote: 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA',
      anchorBeforeMatched: 'matched',
      anchorAfterMatched: 'matched',
      candidateOccurrences: 1,
      recoveryStrategy: 'none',
      recoverySucceeded: true,
      finalDecision: 'verified',
      finalReason: 'Extracted sequence verified from field context against source document.',
    },
    provenance: {
      sourceOffsetStart: 104,
      sourceOffsetEnd: 154,
      sourceField: 'Observed sequence',
      normalizationOps: [],
    },
    validationErrors: [],
  },
  alignmentResult: smithWaterman(
    'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA',
    'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA',
    DEFAULT_SCORING
  ),
  pipelineState: {
    currentStage: 'complete',
    stages: {
      input: 'success',
      localization: 'success',
      verification: 'success',
      alignment: 'warning',
    },
  },
  genomeIdentification: {
    status: 'abstained',
    querySequence: 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA',
    queryLength: 50,
    totalCandidatesEvaluated: 19625,
    topCandidates: [
      {
        rank: 1,
        accession: 'NC_023162.1',
        organism: 'Carp picornavirus 1 isolate F37/06, complete genome',
        alignmentScore: 100,
        matchedLength: 50,
        targetStart: 7432,
        targetEnd: 7697,
        sharedKmers: 38,
        lowComplexity: true,
        hasPolyATail: true,
      },
      {
        rank: 2,
        accession: 'NC_043103.1',
        organism: 'Bat astrovirus Tm/Guangxi/LD38/2007 non-structural polyprotein 1AB gene',
        alignmentScore: 100,
        matchedLength: 50,
        targetStart: 3989,
        targetEnd: 4241,
        sharedKmers: 38,
        lowComplexity: true,
        hasPolyATail: true,
      },
    ],
    closestMatch: {
      rank: 1,
      accession: 'NC_023162.1',
      organism: 'Carp picornavirus 1 isolate F37/06, complete genome',
      alignmentScore: 100,
      matchedLength: 50,
      targetStart: 7432,
      targetEnd: 7697,
      sharedKmers: 38,
      lowComplexity: true,
      hasPolyATail: true,
    },
    abstain: true,
    abstainReason: 'LOW_COMPLEXITY_POLY_A_MATCH: Match is dominated by repetitive sequence (e.g. poly-A tail).',
    searchTimeMs: 144.3,
  },
};

// ─── Exported collections ─────────────────────────────────────────────────────

export const ANCHOR_SCENARIOS: DemoScenario[] = [scenarioA, scenarioB, scenarioC];

export const ALL_SCENARIOS: Record<string, DemoScenario> = {
  'scenario-a': scenarioA,
  'scenario-b': scenarioB,
  'scenario-c': scenarioC,
  'tc-valid-extraction': scenarioValidExtraction,
  'tc-incorrect-preceding-anchor': scenarioIncorrectPrecedingAnchor,
  'tc-incorrect-following-anchor': scenarioIncorrectFollowingAnchor,
  'tc-both-wrong-recoverable': scenarioBothWrongRecoverable,
  'tc-both-wrong-ambiguous': scenarioBothWrongAmbiguous,
  'tc-candidate-absent': scenarioCandidateAbsent,
  'tc-truncated': scenarioTruncated,
  'tc-duplicate-quote': scenarioDuplicateQuote,
  'tc-invalid-chars': scenarioInvalidChars,
  'tc-alignment-mismatches': scenarioWithMismatches,
  'tc-viral-identification': scenarioViralIdentification,
  'tc-viral-poly-a-abstain': scenarioViralPolyAAbstain,
};

export const TEST_CASES: TestCase[] = [
  {
    id: 'tc-1',
    name: 'TC-1 Valid extraction',
    description: 'Both anchors match; sequence uniquely located and verified.',
    expectedOutcome: 'Extracted sequence verified. Alignment score computed.',
    scenarioId: 'tc-valid-extraction',
  },
  {
    id: 'tc-2',
    name: 'TC-2 Incorrect preceding anchor',
    description: 'Preceding anchor fails; following anchor matches. Recovery attempted.',
    expectedOutcome: 'Preceding anchor failed. Recovery succeeds via exact quote.',
    scenarioId: 'tc-incorrect-preceding-anchor',
  },
  {
    id: 'tc-3',
    name: 'TC-3 Incorrect following anchor',
    description: 'Following anchor fails; preceding anchor matches. Recovery attempted.',
    expectedOutcome: 'Following anchor failed. Recovery succeeds via exact quote.',
    scenarioId: 'tc-incorrect-following-anchor',
  },
  {
    id: 'tc-4',
    name: 'TC-4 Both anchors incorrect, recoverable',
    description:
      'Both anchors fail. Candidate quote found exactly once; recovery succeeds.',
    expectedOutcome: 'Accepted via exact-quote recovery. Alignment permitted.',
    scenarioId: 'tc-both-wrong-recoverable',
  },
  {
    id: 'tc-5',
    name: 'TC-5 Both anchors incorrect, ambiguous',
    description: 'Both anchors fail. Candidate quote found in multiple locations.',
    expectedOutcome: 'Abstained. Alignment not run.',
    scenarioId: 'tc-both-wrong-ambiguous',
  },
  {
    id: 'tc-6',
    name: 'TC-6 Candidate sequence absent from source',
    description:
      'The proposed candidate quote does not appear anywhere in the document.',
    expectedOutcome: 'Rejected. Alignment not run.',
    scenarioId: 'tc-candidate-absent',
  },
  {
    id: 'tc-7',
    name: 'TC-7 Truncated sequence',
    description:
      'Candidate located but completeness check indicates sequence is shorter than reference.',
    expectedOutcome: 'Abstained due to truncation. Alignment not run.',
    scenarioId: 'tc-truncated',
  },
  {
    id: 'tc-8',
    name: 'TC-8 Duplicate candidate quote',
    description: 'Candidate quote found in multiple fields; ambiguous location.',
    expectedOutcome: 'Abstained. System cannot determine intended field.',
    scenarioId: 'tc-duplicate-quote',
  },
  {
    id: 'tc-9',
    name: 'TC-9 Invalid nucleotide characters',
    description: 'Extracted sequence contains characters outside the DNA alphabet.',
    expectedOutcome: 'Rejected — invalid characters. Alignment not run.',
    scenarioId: 'tc-invalid-chars',
  },
  {
    id: 'tc-10',
    name: 'TC-10 Alignment with mismatches',
    description:
      'Verified sequence is aligned against reference; mismatches are visible in the DP matrix.',
    expectedOutcome: 'Verified. Alignment matrix shows mismatch columns.',
    scenarioId: 'tc-alignment-mismatches',
  },
  {
    id: 'tc-11',
    name: 'TC-11 Viral Genome Identification (RefSeq Search)',
    description:
      'Screens verified query against 19,625 RefSeq viral genomes, matching Hyposoter fugitivus ichnovirus (NC_008987.1).',
    expectedOutcome: 'Verified from source. Screened 19,625 RefSeq viral genomes; matched NC_008987.1.',
    scenarioId: 'tc-viral-identification',
  },
  {
    id: 'tc-12',
    name: 'TC-12 Viral Low-Complexity Poly-A Abstain',
    description:
      'Safety gating flags homopolymer run matching Carp picornavirus poly-A tail and safely abstains.',
    expectedOutcome: 'Abstained on database match: LOW_COMPLEXITY_POLY_A_MATCH.',
    scenarioId: 'tc-viral-poly-a-abstain',
  },
];

export const SAMPLE_REPORT_TEXT = SAMPLE_REPORT;
