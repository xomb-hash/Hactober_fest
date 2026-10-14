import type { ExtractionRequest, HelixGuardApiResponse } from '../types/helixguard';
import type { IHelixGuardApi } from './helixguardApi';
import { ALL_SCENARIOS, SAMPLE_REPORT_TEXT } from '../data/demoScenarios';
import { smithWaterman, DEFAULT_SCORING } from '../utils/smithWaterman';

/**
 * Mock implementation of IHelixGuardApi.
 *
 * This is a predefined set of demo scenarios — not real AI inference.
 * No backend is connected. Results are deterministic.
 */
class MockHelixGuardApi implements IHelixGuardApi {
  async runExtraction(request: ExtractionRequest): Promise<HelixGuardApiResponse> {
    // Attempt to find a matching scenario by document content
    const match = Object.values(ALL_SCENARIOS).find(
      (s) => s.documentText.trim() === request.documentText.trim()
    );
    if (match) {
      return {
        extractionResult: match.extractionResult,
        alignmentResult: match.alignmentResult,
        pipelineState: match.pipelineState,
      };
    }

    // Generic fallback for user-supplied text: run SW alignment and return candidate status
    const ref = request.referenceSequence.trim().toUpperCase();
    const observed = this.findSequenceInText(request.documentText, ref);
    const alignment = observed
      ? smithWaterman(ref, observed, DEFAULT_SCORING)
      : {
          referenceSequence: ref,
          querySequence: '',
          alignedReference: '',
          alignedQuery: '',
          alignmentScore: 0,
          maxScoringCell: { row: 0, col: 0, value: 0 },
          dpMatrix: [],
          scoringParams: DEFAULT_SCORING,
          skipped: true,
          skipReason: 'No candidate sequence could be located in the provided text.',
        };

    const status = observed ? 'candidate' : 'abstained';
    return {
      extractionResult: {
        extractedSequence: observed ?? '',
        extractionStatus: status,
        sourceFidelityStatus: observed ? 'unverified' : 'failed',
        boundaryVerificationStatus: 'skipped',
        completenessStatus: 'unknown',
        recoveryMethod: 'none',
        anchorVerification: {
          anchorBefore: '(not available in demo mode)',
          anchorAfter: '(not available in demo mode)',
          candidateQuote: observed ?? '',
          anchorBeforeMatched: 'not_checked',
          anchorAfterMatched: 'not_checked',
          candidateOccurrences: observed ? 1 : 0,
          recoveryStrategy: 'none',
          recoverySucceeded: false,
          finalDecision: status,
          finalReason:
            'Demo mode: anchor verification is not available for user-supplied text. Use the predefined demo scenarios for full verification evidence.',
        },
        provenance: {
          sourceOffsetStart: null,
          sourceOffsetEnd: null,
          sourceField: null,
          normalizationOps: [],
        },
        validationErrors:
          status === 'abstained'
            ? ['Could not locate a candidate sequence in the provided text.']
            : [],
      },
      alignmentResult: alignment,
      pipelineState: {
        currentStage: 'complete',
        stages: {
          input: 'success',
          localization: status === 'abstained' ? 'error' : 'warning',
          verification: status === 'abstained' ? 'error' : 'warning',
          alignment: status === 'abstained' ? 'skipped' : 'success',
        },
      },
      genomeIdentification: request.searchDatabase || request.referenceSequence === 'DATABASE' ? {
        status: 'success',
        querySequence: observed || 'ATCGTTCGACTG',
        queryLength: (observed || 'ATCGTTCGACTG').length,
        totalCandidatesEvaluated: 19625,
        topCandidates: [
          {
            rank: 1,
            accession: 'NC_008987.1',
            organism: 'Hyposoter fugitivus ichnovirus DNA, segment D2, complete sequence',
            alignmentScore: 160,
            matchedLength: (observed || 'ATCGTTCGACTG').length,
            targetStart: 500,
            targetEnd: 580,
            sharedKmers: 4,
            lowComplexity: false,
            hasPolyATail: false,
          },
          {
            rank: 2,
            accession: 'NC_023162.1',
            organism: 'Carp picornavirus 1 isolate F37/06, complete genome',
            alignmentScore: 48,
            matchedLength: 24,
            targetStart: 7600,
            targetEnd: 7640,
            sharedKmers: 1,
            lowComplexity: false,
            hasPolyATail: true,
          },
        ],
        closestMatch: {
          rank: 1,
          accession: 'NC_008987.1',
          organism: 'Hyposoter fugitivus ichnovirus DNA, segment D2, complete sequence',
          alignmentScore: 160,
          matchedLength: (observed || 'ATCGTTCGACTG').length,
          targetStart: 500,
          targetEnd: 580,
          sharedKmers: 4,
          lowComplexity: false,
          hasPolyATail: false,
        },
        abstain: false,
        abstainReason: null,
        searchTimeMs: 3.8,
      } : undefined,
    };

  }

  async runScenario(scenarioId: string): Promise<HelixGuardApiResponse> {
    const scenario = ALL_SCENARIOS[scenarioId];
    if (!scenario) {
      throw new Error(`Unknown scenario: ${scenarioId}`);
    }
    return {
      extractionResult: scenario.extractionResult,
      alignmentResult: scenario.alignmentResult,
      pipelineState: scenario.pipelineState,
      genomeIdentification: (scenario as any).genomeIdentification,
    };
  }

  async isAvailable(): Promise<boolean> {
    return true; // Mock is always available
  }

  private findSequenceInText(text: string, ref: string): string | null {
    // Very simple heuristic: find any uppercase DNA-like substring of similar length
    const dnaPattern = /[ACGTU]{4,}/g;
    const matches = text.toUpperCase().match(dnaPattern);
    if (!matches) return null;
    const closest = matches.find((m) => Math.abs(m.length - ref.length) <= 2);
    return closest ?? null;
  }
}

export const mockHelixGuardApi: IHelixGuardApi = new MockHelixGuardApi();

/** Returns SAMPLE_REPORT_TEXT for the sample-report button. */
export { SAMPLE_REPORT_TEXT };
