import { Download, CheckCircle2, AlertTriangle, AlertCircle, ShieldCheck } from 'lucide-react';
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
    field_context_search: 'Field context pattern search',
    user_disambiguation: 'Human-in-the-loop disambiguation',
    failed: 'Failed',
  };
  return map[m] ?? m;
}

export function ExtractionEvidence({ result }: Props) {
  const {
    extractedSequence,
    extractionStatus,
    sourceFidelityStatus,
    boundaryVerificationStatus,
    completenessStatus,
    recoveryMethod,
    anchorVerification,
    provenance,
    validationErrors,
    inputHmac,
    formatDetected,
    plainLanguageVerdict,
    redactedProvenance,
  } = result;

  const handleDownloadFasta = () => {
    if (!extractedSequence) return;
    const hmacStr = inputHmac ? `hmac:${inputHmac.slice(0, 16)}…` : 'synthetic';
    const header = `>helixguard_query | ${hmacStr} | status:${extractionStatus} | offsets:[${provenance.sourceOffsetStart ?? 0},${provenance.sourceOffsetEnd ?? 0})`;
    const fastaContent = `${header}\n${extractedSequence}\n`;
    const blob = new Blob([fastaContent], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'helixguard_verified_query.fasta';
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleDownloadAuditJson = () => {
    const auditData = redactedProvenance || {
      extraction_status: extractionStatus,
      source_fidelity: sourceFidelityStatus,
      boundary_verification: boundaryVerificationStatus,
      completeness: completenessStatus,
      offsets: [provenance.sourceOffsetStart, provenance.sourceOffsetEnd],
      field: provenance.sourceField,
      normalization_ops: provenance.normalizationOps,
      input_hmac: inputHmac,
      format_detected: formatDetected,
      plain_language_verdict: plainLanguageVerdict,
      audit_note: 'Redacted audit export per R2-1: contains zero raw nucleotide sequence content.',
    };
    const blob = new Blob([JSON.stringify(auditData, null, 2)], { type: 'application/json;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'helixguard_redacted_provenance.json';
    a.click();
    URL.revokeObjectURL(url);
  };

  const isVerified = extractionStatus === 'verified';
  const isAbstained = extractionStatus === 'abstained';

  return (
    <div className="card">
      <div className="card-header flex items-center justify-between">
        <span className="card-title">Extraction Evidence</span>
        <div className="flex items-center gap-2">
          {formatDetected && formatDetected !== 'text' && (
            <span className="text-[10px] bg-slate-100 text-slate-700 font-mono uppercase px-1.5 py-0.5 rounded border border-slate-200">
              {formatDetected}
            </span>
          )}
          <StatusBadge status={extractionStatus} />
        </div>
      </div>
      <div className="card-body space-y-3">

        {/* Plain-Language Verdict Banner (R2-2) */}
        {plainLanguageVerdict && (
          <div
            className={`p-3 rounded-md border text-xs flex items-start gap-2.5 ${
              isVerified
                ? 'bg-emerald-50/80 border-emerald-200 text-emerald-900'
                : isAbstained
                ? 'bg-amber-50/80 border-amber-200 text-amber-900'
                : 'bg-red-50/80 border-red-200 text-red-900'
            }`}
          >
            {isVerified ? (
              <CheckCircle2 size={16} className="text-emerald-600 flex-shrink-0 mt-0.5" />
            ) : isAbstained ? (
              <AlertTriangle size={16} className="text-amber-600 flex-shrink-0 mt-0.5" />
            ) : (
              <AlertCircle size={16} className="text-red-600 flex-shrink-0 mt-0.5" />
            )}
            <div className="space-y-0.5">
              <span className="font-semibold block">
                {isVerified ? 'Plain-Language Verdict: Verified' : isAbstained ? 'Plain-Language Verdict: Not Sure (Abstained)' : 'Plain-Language Verdict: Rejected'}
              </span>
              <p className="text-[11px] leading-relaxed">
                {plainLanguageVerdict}
              </p>
            </div>
          </div>
        )}

        <div className="space-y-0 border-t border-slate-100 pt-1">
          {/* Extracted sequence */}
          <RowItem label="Extracted sequence">
            {extractedSequence ? (
              <code className="seq bg-slate-50 px-2 py-0.5 rounded border border-slate-200 block break-all font-mono text-xs">
                {extractedSequence}
              </code>
            ) : (
              <span className="text-slate-400 italic text-xs">None (Gated)</span>
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

          {inputHmac && (
            <RowItem label="Salted HMAC-SHA256">
              <span className="text-[10px] font-mono text-slate-600 bg-slate-50 px-1.5 py-0.5 rounded border border-slate-200 break-all select-all block" title="Cryptographic Salted HMAC for provenance integrity">
                {inputHmac}
              </span>
            </RowItem>
          )}
        </div>

        {/* Validation errors */}
        {validationErrors.length > 0 && (
          <div className="mt-2 space-y-1">
            {validationErrors.map((e, i) => (
              <p key={i} className="text-xs text-red-700 bg-red-50 border border-red-200 rounded px-2.5 py-1.5">
                {e}
              </p>
            ))}
          </div>
        )}

        {/* Action Export Buttons (R2-1 & R2-2) */}
        <div className="pt-2 border-t border-slate-100 flex items-center gap-2">
          <button
            type="button"
            onClick={handleDownloadFasta}
            disabled={!extractedSequence || !isVerified}
            className="btn-secondary text-xs flex-1 justify-center disabled:opacity-40"
            title={isVerified ? 'Export verified sequence as FASTA with cryptographic provenance header' : 'Only verified sequences can be exported as FASTA'}
          >
            <Download size={13} />
            Export FASTA
          </button>
          <button
            type="button"
            onClick={handleDownloadAuditJson}
            className="btn-ghost text-xs flex-1 justify-center border border-slate-200 hover:bg-slate-50"
            title="Download zero-knowledge redacted audit trail JSON (R2-1 Privacy)"
          >
            <ShieldCheck size={13} className="text-emerald-600" />
            Redacted Audit JSON
          </button>
        </div>

      </div>
    </div>
  );
}
