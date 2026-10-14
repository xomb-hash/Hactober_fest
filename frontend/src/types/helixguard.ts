// ─── Extraction Status ────────────────────────────────────────────────────────

export type ExtractionStatus =
  | 'verified'
  | 'candidate'
  | 'recovery_required'
  | 'ambiguous'
  | 'rejected'
  | 'abstained';

export type AnchorMatchStatus = 'matched' | 'failed' | 'not_checked';

export type RecoveryStrategy =
  | 'none'
  | 'exact_quote_search'
  | 'fuzzy_search'
  | 'field_heuristic'
  | 'failed';

// ─── Anchor Verification ──────────────────────────────────────────────────────

export interface AnchorVerification {
  anchorBefore: string;
  anchorAfter: string;
  candidateQuote: string;
  anchorBeforeMatched: AnchorMatchStatus;
  anchorAfterMatched: AnchorMatchStatus;
  candidateOccurrences: number;
  recoveryStrategy: RecoveryStrategy;
  recoverySucceeded: boolean;
  finalDecision: ExtractionStatus;
  finalReason: string;
}

// ─── Source Provenance ────────────────────────────────────────────────────────

export interface SourceProvenance {
  sourceOffsetStart: number | null;
  sourceOffsetEnd: number | null;
  sourceField: string | null;
  normalizationOps: string[];
}

// ─── Extraction Result ────────────────────────────────────────────────────────

export interface ExtractionResult {
  extractedSequence: string;
  extractionStatus: ExtractionStatus;
  sourceFidelityStatus: 'verified' | 'unverified' | 'failed';
  boundaryVerificationStatus: 'verified' | 'failed' | 'skipped';
  completenessStatus: 'complete' | 'truncated' | 'unknown';
  recoveryMethod: RecoveryStrategy;
  anchorVerification: AnchorVerification;
  provenance: SourceProvenance;
  validationErrors: string[];
}

// ─── Alignment ────────────────────────────────────────────────────────────────

export interface ScoringParams {
  match: number;
  mismatch: number;
  gap: number;
}

export interface AlignmentResult {
  referenceSequence: string;
  querySequence: string;
  alignedReference: string;
  alignedQuery: string;
  alignmentScore: number;
  maxScoringCell: { row: number; col: number; value: number };
  dpMatrix: number[][];
  scoringParams: ScoringParams;
  skipped: boolean;
  skipReason?: string;
}

// ─── Pipeline State ───────────────────────────────────────────────────────────

export type PipelineStage =
  | 'idle'
  | 'input'
  | 'localization'
  | 'verification'
  | 'alignment'
  | 'complete';

export type StageStatus = 'pending' | 'running' | 'success' | 'warning' | 'error' | 'skipped';

export interface PipelineState {
  currentStage: PipelineStage;
  stages: {
    input: StageStatus;
    localization: StageStatus;
    verification: StageStatus;
    alignment: StageStatus;
  };
}

// ─── Demo Scenario ────────────────────────────────────────────────────────────

export interface DemoScenario {
  id: string;
  name: string;
  description: string;
  expectedOutcome: string;
  documentText: string;
  referenceSequence: string;
  targetField: string;
  alphabet: 'DNA' | 'RNA';
  extractionResult: ExtractionResult;
  alignmentResult: AlignmentResult;
  pipelineState: PipelineState;
}

// ─── API Interface ────────────────────────────────────────────────────────────

export interface ExtractionRequest {
  documentText: string;
  referenceSequence: string;
  targetField: string;
  alphabet: 'DNA' | 'RNA';
}

export interface HelixGuardApiResponse {
  extractionResult: ExtractionResult;
  alignmentResult: AlignmentResult;
  pipelineState: PipelineState;
}

export interface StructuredError {
  code: string;
  message: string;
  field?: string;
}

// ─── Test Case ────────────────────────────────────────────────────────────────

export interface TestCase {
  id: string;
  name: string;
  description: string;
  expectedOutcome: string;
  scenarioId: string;
}
