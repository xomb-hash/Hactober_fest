import type {
  ExtractionRequest,
  HelixGuardApiResponse,
  ExtractionResult,
  AlignmentResult,
  PipelineState,
  RecoveryStrategy,
  ExtractionStatus,
} from '../types/helixguard';
import type { IHelixGuardApi } from './helixguardApi';
import { ALL_SCENARIOS } from '../data/demoScenarios';

const API_BASE_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/+$/, '');

/**
 * Real API client communicating with HelixGuard Python FastAPI middleware (port 8000)
 * and through it, the C++ Smith-Waterman engine (port 8080).
 */
export class RealHelixGuardApi implements IHelixGuardApi {
  private baseUrl: string;

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl;
  }

  async isAvailable(): Promise<boolean> {
    try {
      const resp = await fetch(`${this.baseUrl}/health`, {
        method: 'GET',
        headers: { 'Accept': 'application/json' },
        signal: AbortSignal.timeout(2000),
      });
      if (!resp.ok) return false;
      const data = await resp.json();
      return data.status === 'healthy';
    } catch {
      return false;
    }
  }

  async runExtraction(request: ExtractionRequest): Promise<HelixGuardApiResponse> {
    const isDbMode = request.searchDatabase || request.referenceSequence === 'DATABASE' || !request.referenceSequence.trim();

    if (isDbMode) {
      const payload: any = {
        document_text: request.documentText,
        field_type: request.targetField.toLowerCase().replace(/\s+/g, '_'),
        sequence_alphabet: request.alphabet,
        use_ai: request.useAi !== false,
        use_token_mask: request.useTokenMask,
        selected_span: request.selectedSpan,
        top_k: 5,
      };

      const resp = await fetch(`${this.baseUrl}/extract-and-identify`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
        body: JSON.stringify(payload),
      });

      if (!resp.ok && resp.status !== 400 && resp.status !== 422) {
        throw new Error(`HelixGuard backend returned HTTP ${resp.status}: ${await resp.text()}`);
      }

      const data = await resp.json();
      return this.transformIdentifyBackendResponse(data, request);
    }

    const payload: any = {
      document_text: request.documentText,
      reference_sequence: request.referenceSequence,
      field_type: request.targetField.toLowerCase().replace(/\s+/g, '_'),
      sequence_alphabet: request.alphabet,
      use_ai: request.useAi !== false,
      use_token_mask: request.useTokenMask,
      selected_span: request.selectedSpan,
    };

    const resp = await fetch(`${this.baseUrl}/extract-and-align`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
      body: JSON.stringify(payload),
    });

    if (!resp.ok && resp.status !== 400 && resp.status !== 422) {
      throw new Error(`HelixGuard backend returned HTTP ${resp.status}: ${await resp.text()}`);
    }

    const data = await resp.json();
    return this.transformBackendResponse(data, request);
  }

  private transformIdentifyBackendResponse(
    data: any,
    req: ExtractionRequest
  ): HelixGuardApiResponse {
    const ext = data.extraction || {};
    const ident = data.identification;
    const overallStatus = data.status;

    let extractionStatus: ExtractionStatus = 'unverified' as any;
    if (ext.validation_status === 'verified') extractionStatus = 'verified';
    else if (ext.validation_status === 'abstained' || overallStatus === 'abstained') extractionStatus = 'abstained';
    else if (ext.validation_status === 'rejected' || overallStatus === 'rejected') extractionStatus = 'rejected';
    else if (ext.source_match) extractionStatus = 'candidate';
    else extractionStatus = 'abstained';

    const prov = ext.provenance || {};
    const extractionResult: ExtractionResult = {
      extractedSequence: ext.sequence || '',
      extractionStatus,
      sourceFidelityStatus: ext.source_match ? 'verified' : 'failed',
      boundaryVerificationStatus: ext.boundaries_verified ? 'verified' : 'failed',
      completenessStatus: ext.completeness_verified ? 'complete' : (ext.sequence ? 'truncated' : 'unknown'),
      recoveryMethod: (ext.recovery_method as RecoveryStrategy) || 'none',
      anchorVerification: {
        anchorBefore: prov.anchor_before || '(detected by pattern)',
        anchorAfter: prov.anchor_after || '(detected by pattern)',
        candidateQuote: prov.candidate_quote || ext.sequence || '',
        anchorBeforeMatched: prov.anchors_verified ? 'matched' : 'not_checked',
        anchorAfterMatched: prov.anchors_verified ? 'matched' : 'not_checked',
        candidateOccurrences: ext.sequence ? 1 : 0,
        recoveryStrategy: (ext.recovery_method as RecoveryStrategy) || 'none',
        recoverySucceeded: ext.validation_status === 'verified',
        finalDecision: extractionStatus,
        finalReason: ext.message || 'Extracted and verified for database identification.',
      },
      provenance: {
        sourceOffsetStart: ext.source_span?.start ?? null,
        sourceOffsetEnd: ext.source_span?.end ?? null,
        sourceField: req.targetField,
        normalizationOps: prov.normalization_ops || [],
      },
      validationErrors: ext.error_code ? [ext.message || ext.error_code] : [],
      candidateSpans: ext.candidate_spans || [],
      redactedProvenance: ext.redacted_provenance || null,
      formatDetected: ext.format_detected || undefined,
      inputHmac: prov.input_hmac || undefined,
      plainLanguageVerdict: ext.plain_language_verdict || (ext.validation_status === 'verified'
        ? 'Verified: authentic sequence deterministically matched and validated.'
        : `Not sure — ${ext.message || 'evidence weak'}`),
    };

    const topMatch = ident?.closest_match;
    const alignmentResult: AlignmentResult = {
      referenceSequence: topMatch ? `[${topMatch.accession}] ${topMatch.organism}` : 'RefSeq Viral Database',
      querySequence: ext.sequence || '',
      alignedReference: topMatch ? `bp ${topMatch.target_start}–${topMatch.target_end}` : '',
      alignedQuery: ext.sequence || '',
      alignmentScore: topMatch?.alignment_score || 0,
      maxScoringCell: { row: 0, col: 0, value: topMatch?.alignment_score || 0 },
      dpMatrix: [],
      scoringParams: { match: 2, mismatch: -1, gap: -1 },
      skipped: !topMatch || ident?.abstain,
      skipReason: ident?.abstain_reason || undefined,
    };

    const isSuccess = ext.validation_status === 'verified';
    const isAbstained = extractionStatus === 'abstained' || ident?.abstain;
    const pipelineState: PipelineState = {
      currentStage: 'complete',
      stages: {
        input: 'success',
        localization: ext.source_match ? 'success' : (isAbstained ? 'warning' : 'error'),
        verification: isSuccess ? 'success' : (isAbstained ? 'warning' : 'error'),
        alignment: ident && ident.status === 'success' ? 'success' : (ident?.abstain ? 'warning' : 'skipped'),
      },
    };

    let genomeIdentification: any = undefined;
    if (ident) {
      genomeIdentification = {
        status: ident.status,
        querySequence: ident.query_sequence,
        queryLength: ident.query_length,
        totalCandidatesEvaluated: ident.total_candidates_evaluated,
        topCandidates: (ident.top_candidates || []).map((c: any) => ({
          rank: c.rank,
          accession: c.accession,
          organism: c.organism,
          alignmentScore: c.alignment_score,
          matchedLength: c.matched_length,
          targetStart: c.target_start,
          targetEnd: c.target_end,
          sharedKmers: c.shared_kmers,
          lowComplexity: c.low_complexity,
          hasPolyATail: c.has_poly_a_tail,
        })),
        closestMatch: topMatch ? {
          rank: topMatch.rank,
          accession: topMatch.accession,
          organism: topMatch.organism,
          alignmentScore: topMatch.alignment_score,
          matchedLength: topMatch.matched_length,
          targetStart: topMatch.target_start,
          targetEnd: topMatch.target_end,
          sharedKmers: topMatch.shared_kmers,
          lowComplexity: topMatch.low_complexity,
          hasPolyATail: topMatch.has_poly_a_tail,
        } : null,
        abstain: ident.abstain,
        abstainReason: ident.abstain_reason,
        searchTimeMs: ident.search_time_ms,
      };
    }

    return {
      extractionResult,
      alignmentResult,
      pipelineState,
      genomeIdentification,
    };
  }


  async runScenario(scenarioId: string): Promise<HelixGuardApiResponse> {
    const scenario = ALL_SCENARIOS[scenarioId];
    if (!scenario) {
      throw new Error(`Unknown scenario: ${scenarioId}`);
    }

    // Try executing through real backend if reachable
    try {
      return await this.runExtraction({
        documentText: scenario.documentText,
        referenceSequence: scenario.referenceSequence,
        targetField: scenario.targetField,
        alphabet: scenario.alphabet,
      });
    } catch (err) {
      console.warn('Real backend call failed for scenario, falling back to cached scenario data:', err);
      return {
        extractionResult: scenario.extractionResult,
        alignmentResult: scenario.alignmentResult,
        pipelineState: scenario.pipelineState,
        genomeIdentification: (scenario as any).genomeIdentification,
      };
    }
  }

  private transformBackendResponse(
    data: any,
    req: ExtractionRequest
  ): HelixGuardApiResponse {
    const ext = data.extraction || {};
    const align = data.alignment;
    const overallStatus = data.status; // success, abstained, rejected, error

    // Map backend status to frontend ExtractionStatus
    let extractionStatus: ExtractionStatus = 'unverified' as any;
    if (ext.validation_status === 'verified') extractionStatus = 'verified';
    else if (ext.validation_status === 'abstained' || overallStatus === 'abstained') extractionStatus = 'abstained';
    else if (ext.validation_status === 'rejected' || overallStatus === 'rejected') extractionStatus = 'rejected';
    else if (ext.source_match) extractionStatus = 'candidate';
    else extractionStatus = 'abstained';

    const prov = ext.provenance || {};
    const provAnchors = prov.anchor_verification || {};

    // Map recovery strategy
    let recoveryMethod: RecoveryStrategy = 'none';
    const rawMethod = (ext.recovery_method || '').toLowerCase();
    if (rawMethod.includes('quote')) recoveryMethod = 'exact_quote_search';
    else if (rawMethod.includes('fuzzy')) recoveryMethod = 'fuzzy_search';
    else if (rawMethod.includes('field') || rawMethod.includes('heuristic')) recoveryMethod = 'field_heuristic';
    else if (rawMethod.includes('fail')) recoveryMethod = 'failed';

    const extractionResult: ExtractionResult = {
      extractedSequence: ext.sequence || '',
      extractionStatus,
      sourceFidelityStatus: ext.source_match ? 'verified' : 'failed',
      boundaryVerificationStatus: ext.boundaries_verified ? 'verified' : 'failed',
      completenessStatus: ext.completeness_verified ? 'complete' : (ext.sequence ? 'truncated' : 'unknown'),
      recoveryMethod,
      anchorVerification: {
        anchorBefore: prov.anchor_before || '(detected by pattern)',
        anchorAfter: prov.anchor_after || '(detected by pattern)',
        candidateQuote: prov.candidate_quote || ext.sequence || '',
        anchorBeforeMatched: provAnchors.anchor_before_found ? 'matched' : (prov.anchor_before ? 'failed' : 'not_checked'),
        anchorAfterMatched: provAnchors.anchor_after_found ? 'matched' : (prov.anchor_after ? 'failed' : 'not_checked'),
        candidateOccurrences: ext.sequence ? 1 : 0,
        recoveryStrategy: recoveryMethod,
        recoverySucceeded: ext.validation_status === 'verified',
        finalDecision: extractionStatus,
        finalReason: ext.message || prov.reason || (ext.validation_status === 'verified'
          ? 'Deterministically extracted and verified against source document.'
          : 'Could not establish authentic sequence with sufficient evidence.'),
      },
      provenance: {
        sourceOffsetStart: ext.source_span?.start ?? prov.source_span?.start ?? null,
        sourceOffsetEnd: ext.source_span?.end ?? prov.source_span?.end ?? null,
        sourceField: req.targetField,
        normalizationOps: prov.normalization_ops || [],
      },
      validationErrors: ext.message && ext.validation_status !== 'verified' ? [ext.message] : [],
      candidateSpans: ext.candidate_spans || [],
      redactedProvenance: ext.redacted_provenance || null,
      formatDetected: ext.format_detected || undefined,
      inputHmac: prov.input_hmac || undefined,
      plainLanguageVerdict: ext.plain_language_verdict || (ext.validation_status === 'verified'
        ? 'Verified: authentic sequence deterministically matched and validated.'
        : `Not sure — ${ext.message || 'evidence weak'}`),
    };

    // Construct AlignmentResult
    let alignmentResult: AlignmentResult;
    if (align && align.status === 'success') {
      const scoring = align.scoring || { match: 2, mismatch: -1, gap: -1 };
      const tb = align.traceback || {};
      alignmentResult = {
        referenceSequence: req.referenceSequence,
        querySequence: ext.sequence || '',
        alignedReference: tb.aligned_reference || req.referenceSequence,
        alignedQuery: tb.aligned_query || ext.sequence || '',
        alignmentScore: align.alignment_score ?? 0,
        maxScoringCell: {
          row: align.max_cell?.row ?? 0,
          col: align.max_cell?.column ?? 0,
          value: align.alignment_score ?? 0,
        },
        dpMatrix: align.matrix || [],
        scoringParams: scoring,
        skipped: false,
      };
    } else {
      alignmentResult = {
        referenceSequence: req.referenceSequence,
        querySequence: ext.sequence || '',
        alignedReference: '',
        alignedQuery: '',
        alignmentScore: 0,
        maxScoringCell: { row: 0, col: 0, value: 0 },
        dpMatrix: [],
        scoringParams: { match: 2, mismatch: -1, gap: -1 },
        skipped: true,
        skipReason: ext.validation_status !== 'verified'
          ? 'Alignment skipped: unverified extracted sequence blocked by safety gating rule.'
          : (ext.message || 'Alignment service unavailable or rejected input.'),
      };
    }

    // Determine pipeline state stages
    const isSuccess = ext.validation_status === 'verified';
    const isAbstained = extractionStatus === 'abstained';
    const pipelineState: PipelineState = {
      currentStage: 'complete',
      stages: {
        input: 'success',
        localization: ext.source_match ? 'success' : (isAbstained ? 'warning' : 'error'),
        verification: isSuccess ? 'success' : (isAbstained ? 'warning' : 'error'),
        alignment: align && align.status === 'success' ? 'success' : 'skipped',
      },
    };

    return {
      extractionResult,
      alignmentResult,
      pipelineState,
    };
  }
}

export const realHelixGuardApi = new RealHelixGuardApi();
