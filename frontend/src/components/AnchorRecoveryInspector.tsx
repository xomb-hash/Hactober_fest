import { useState } from 'react';
import type { AnchorVerification } from '../types/helixguard';
import { StatusBadge } from './StatusBadge';
import { ANCHOR_SCENARIOS } from '../data/demoScenarios';
import { ChevronRight } from 'lucide-react';

interface Props {
  anchorVerification?: AnchorVerification;
  onRunScenario: (id: string) => void;
}

export function AnchorRecoveryInspector({ anchorVerification, onRunScenario }: Props) {
  const [activeScenario, setActiveScenario] = useState<string | null>(null);

  const handleRun = (id: string) => {
    setActiveScenario(id);
    onRunScenario(id);
  };

  return (
    <div className="card">
      <div className="card-header">
        <span className="card-title">Source Localization &amp; Recovery</span>
      </div>
      <div className="card-body space-y-4">

        {/* Explanation */}
        <div className="px-3 py-2 bg-slate-50 border border-slate-200 rounded-md">
          <p className="text-xs text-slate-600 leading-relaxed">
            <strong>Anchors help locate a sequence.</strong> They do not determine or modify its nucleotide content.
            A failed anchor triggers recovery; successful recovery still produces a lower-confidence result than both anchors matching.
          </p>
        </div>

        {/* Interactive demo scenarios */}
        <div>
          <p className="text-xs font-semibold text-slate-600 uppercase tracking-wider mb-2">
            Predefined demonstration scenarios
          </p>
          <p className="text-[10px] text-slate-400 mb-3">
            These are predefined examples of expected behavior — not real AI inference.
          </p>
          <div className="space-y-2">
            {ANCHOR_SCENARIOS.map((s) => (
              <div
                key={s.id}
                className={`border rounded-md transition-colors ${
                  activeScenario === s.id ? 'border-accent-300 bg-accent-50' : 'border-slate-200 bg-white'
                }`}
              >
                <div className="flex items-start justify-between p-3 gap-3">
                  <div className="min-w-0 flex-1">
                    <p className="text-xs font-semibold text-slate-800">{s.name}</p>
                    <p className="text-[11px] text-slate-500 mt-0.5 leading-snug">{s.description}</p>
                    <p className="text-[11px] text-slate-600 mt-1">
                      <strong>Expected:</strong> {s.expectedOutcome}
                    </p>
                  </div>
                  <button
                    id={`run-scenario-${s.id}`}
                    onClick={() => handleRun(s.id)}
                    className={`btn-secondary flex-shrink-0 text-xs ${
                      activeScenario === s.id ? 'bg-accent-100 border-accent-300 text-accent-700' : ''
                    }`}
                  >
                    Run demo
                    <ChevronRight size={12} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Detail panel */}
        {anchorVerification && (
          <div className="border border-slate-200 rounded-md">
            <div className="px-3 py-2 border-b border-slate-100 bg-slate-50 rounded-t-md">
              <p className="text-xs font-semibold text-slate-700">Anchor detail</p>
            </div>
            <div className="p-3 space-y-0">
              <DetailRow label="anchor_before">
                <code className="seq text-xs bg-slate-50 px-1.5 py-0.5 rounded border border-slate-200">{anchorVerification.anchorBefore}</code>
                <StatusBadge status={anchorVerification.anchorBeforeMatched} />
              </DetailRow>
              <DetailRow label="candidate_quote">
                <code className="seq text-xs bg-slate-50 px-1.5 py-0.5 rounded border border-slate-200 break-all">{anchorVerification.candidateQuote}</code>
              </DetailRow>
              <DetailRow label="anchor_after">
                <code className="seq text-xs bg-slate-50 px-1.5 py-0.5 rounded border border-slate-200">{anchorVerification.anchorAfter}</code>
                <StatusBadge status={anchorVerification.anchorAfterMatched} />
              </DetailRow>
              <DetailRow label="Candidate occurrences">
                <span className={`text-xs font-mono font-semibold ${
                  anchorVerification.candidateOccurrences === 1 ? 'text-emerald-700' :
                  anchorVerification.candidateOccurrences === 0 ? 'text-red-700' : 'text-amber-700'
                }`}>{anchorVerification.candidateOccurrences}</span>
              </DetailRow>
              <DetailRow label="Recovery strategy">
                <span className="text-xs">
                  {anchorVerification.recoveryStrategy === 'none'
                    ? 'None (anchors sufficient)'
                    : anchorVerification.recoveryStrategy.replace(/_/g, ' ')}
                </span>
              </DetailRow>
              <DetailRow label="Final decision">
                <StatusBadge status={anchorVerification.finalDecision} />
              </DetailRow>
              <div className="pt-2 border-t border-slate-50 mt-1">
                <p className="text-[10px] font-medium text-slate-500 mb-1">Reason</p>
                <p className="text-xs text-slate-700 leading-relaxed">{anchorVerification.finalReason}</p>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function DetailRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="evidence-row">
      <span className="evidence-label font-mono">{label}</span>
      <span className="evidence-value flex items-center gap-2 flex-wrap">{children}</span>
    </div>
  );
}
