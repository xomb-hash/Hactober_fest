import type { HelixGuardApiResponse, PipelineState } from '../types/helixguard';
import { AlignmentMatrix } from '../components/AlignmentMatrix';
import { ExtractionEvidence } from '../components/ExtractionEvidence';
import { PipelineStepper } from '../components/PipelineStepper';
import { GenomeIdentificationCard } from '../components/GenomeIdentificationCard';

interface Props {
  result: HelixGuardApiResponse | null;
  pipelineState: PipelineState;
}

export function Alignment({ result, pipelineState }: Props) {
  return (
    <div className="space-y-4">
      <PipelineStepper pipelineState={pipelineState} />

      {result ? (
        <div className="space-y-4">
          {result.genomeIdentification && (
            <GenomeIdentificationCard identification={result.genomeIdentification} />
          )}
          <AlignmentMatrix result={result.alignmentResult} />
          <ExtractionEvidence result={result.extractionResult} />
        </div>
      ) : (
        <div className="card">
          <div className="card-header"><span className="card-title">Alignment</span></div>
          <div className="card-body">
            <p className="text-xs text-slate-400 italic">
              No alignment results yet. Go to <strong>Sequence Extraction</strong> and run a demo scenario or click "Extract &amp; Align".
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
