import type { ExtractionResult } from '../types/helixguard';
import { StatusBadge } from './StatusBadge';

interface Props {
  result: ExtractionResult;
}

function RowItem({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="evidence-row">
      <span className="evidence-label">{label}</span>
      <span className="evidence-value">{children}</span>
    </div>
  );
}

function recoveryLabel(m: string) {
  const map: Record<string, string> = {
    none: 'None (anchor verification)',
    exact_quote_search: 'Exact quote search',
    fuzzy_search: 'Fuzzy search',
    field_heuristic: 'Field heuristic',
    failed: 'Failed',
  };
  return map[m] ?? m;
}

export function ExtractionEvidence({ result }: Props) {
  const { extractedSequence, extractionStatus, sourceFidelityStatus,
          boundaryVerificationStatus, completenessStatus, recoveryMethod,
          anchorVerification, provenance, validationErrors } = result;

  return (
    <div className="card">
      <div className="card-header">
        <span className="card-title">Extraction Evidence</span>
        <StatusBadge status={extractionStatus} />
      </div>
      <div className="card-body space-y-0">

        {/* Extracted sequence */}
        <RowItem label="Extracted sequence">
          {extractedSequence ? (
            <code className="seq bg-slate-50 px-2 py-0.5 rounded border border-slate-200 block break-all">
              {extractedSequence}
            </code>
          ) : (
            <span className="text-slate-400 italic text-xs">None</span>
          )}
        </RowItem>

        <RowItem label="Extraction status">
          <StatusBadge status={extractionStatus} />
        </RowItem>

        <RowItem label="Source-fidelity status">
          <StatusBadge status={sourceFidelityStatus} />
        </RowItem>

        <RowItem label="Boundary verification">
          <StatusBadge status={boundaryVerificationStatus} />
        </RowItem>

        <RowItem label="Completeness">
          <StatusBadge
            status={completenessStatus === 'complete' ? 'verified' : completenessStatus === 'truncated' ? 'warning' : 'not_checked'}
            label={completenessStatus}
          />
        </RowItem>

        <RowItem label="Recovery method">
          <span className="text-xs">{recoveryLabel(recoveryMethod)}</span>
        </RowItem>

        <RowItem label="Anchor verification">
          <StatusBadge status={anchorVerification.finalDecision} />
        </RowItem>

        {provenance.sourceOffsetStart !== null && (
          <RowItem label="Source offsets">
            <span className="text-xs font-mono">
              [{provenance.sourceOffsetStart}, {provenance.sourceOffsetEnd})
              {provenance.sourceField && ` · field: ${provenance.sourceField}`}
            </span>
          </RowItem>
        )}

        {provenance.normalizationOps.length > 0 && (
          <RowItem label="Normalization ops">
            <span className="text-xs">{provenance.normalizationOps.join(', ')}</span>
          </RowItem>
        )}

        {/* Validation errors */}
        {validationErrors.length > 0 && (
          <div className="mt-3 space-y-1">
            {validationErrors.map((e, i) => (
              <p key={i} className="text-xs text-red-700 bg-red-50 border border-red-200 rounded px-2.5 py-1.5">
                {e}
              </p>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
