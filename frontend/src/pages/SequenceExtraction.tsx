import type { HelixGuardApiResponse } from '../types/helixguard';
import { DocumentInput } from '../components/DocumentInput';
import { ExtractionEvidence } from '../components/ExtractionEvidence';
import { AnchorRecoveryInspector } from '../components/AnchorRecoveryInspector';
import { PipelineStepper } from '../components/PipelineStepper';
import { SAMPLE_REPORT_TEXT } from '../services/mockHelixguardApi';
import type { ExtractionRequest, PipelineState } from '../types/helixguard';

interface Props {
  result: HelixGuardApiResponse | null;
  pipelineState: PipelineState;
  loading: boolean;
  errors: { message: string; field?: string }[];
  onRun: (req: ExtractionRequest) => void;
  onRunScenario: (id: string) => void;
  onLoadSample: () => void;
  sampleText: string;
}

export function SequenceExtraction({
  result,
  pipelineState,
  loading,
  errors,
  onRun,
  onRunScenario,
  onLoadSample,
}: Props) {
  return (
    <div className="space-y-4">
      <PipelineStepper pipelineState={pipelineState} />

      <div className="grid lg:grid-cols-2 gap-4">
        {/* Left column */}
        <div className="space-y-4">
          <DocumentInput
            onRun={onRun}
            onLoadSample={onLoadSample}
            errors={errors}
            loading={loading}
            initialDocumentText={SAMPLE_REPORT_TEXT}
          />
          <AnchorRecoveryInspector
            anchorVerification={result?.extractionResult.anchorVerification}
            onRunScenario={onRunScenario}
          />
        </div>

        {/* Right column */}
        <div className="space-y-4">
          {result ? (
            <ExtractionEvidence result={result.extractionResult} />
          ) : (
            <div className="card">
              <div className="card-header"><span className="card-title">Extraction Evidence</span></div>
              <div className="card-body">
                <p className="text-xs text-slate-400 italic">
                  Run a demo scenario or click "Extract &amp; Align" to see extraction evidence here.
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
