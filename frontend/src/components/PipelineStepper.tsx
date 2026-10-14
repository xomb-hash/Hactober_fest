import { CheckCircle, AlertTriangle, XCircle, Clock, SkipForward } from 'lucide-react';
import type { PipelineState, StageStatus } from '../types/helixguard';

interface Props {
  pipelineState: PipelineState;
}

const STAGES = [
  { key: 'input' as const,        label: 'Document Input',       desc: 'Paste and validate report text' },
  { key: 'localization' as const, label: 'Sequence Localization', desc: 'Anchor detection & recovery' },
  { key: 'verification' as const, label: 'Source Verification',  desc: 'Fidelity & boundary checks' },
  { key: 'alignment' as const,    label: 'Alignment',            desc: 'Smith–Waterman DP alignment' },
];

function StageIcon({ status }: { status: StageStatus }) {
  const cls = 'w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 ring-2';
  if (status === 'success') return <div className={`${cls} bg-emerald-100 ring-emerald-200`}><CheckCircle size={14} className="text-emerald-700" /></div>;
  if (status === 'warning') return <div className={`${cls} bg-amber-100 ring-amber-200`}><AlertTriangle size={14} className="text-amber-700" /></div>;
  if (status === 'error')   return <div className={`${cls} bg-red-100 ring-red-200`}><XCircle size={14} className="text-red-700" /></div>;
  if (status === 'skipped') return <div className={`${cls} bg-slate-100 ring-slate-200`}><SkipForward size={14} className="text-slate-400" /></div>;
  if (status === 'running') return <div className={`${cls} bg-sky-100 ring-sky-200 animate-pulse`}><Clock size={14} className="text-sky-600" /></div>;
  return <div className={`${cls} bg-slate-100 ring-slate-200`}><Clock size={14} className="text-slate-300" /></div>;
}

function stepLabel(status: StageStatus) {
  const map: Record<StageStatus, string> = {
    pending: 'Pending', running: 'Running', success: 'Complete',
    warning: 'Warning', error: 'Error', skipped: 'Skipped',
  };
  return map[status];
}

export function PipelineStepper({ pipelineState }: Props) {
  return (
    <div className="card">
      <div className="card-header">
        <span className="card-title">Pipeline</span>
        <span className="text-xs text-slate-400">Document Input → Localization → Verification → Alignment</span>
      </div>
      <div className="card-body">
        {/* Desktop: horizontal */}
        <div className="hidden sm:flex items-start gap-0">
          {STAGES.map((stage, idx) => {
            const status = pipelineState.stages[stage.key];
            return (
              <div key={stage.key} className="flex items-start flex-1 min-w-0">
                <div className="flex flex-col items-center w-full">
                  <div className="flex items-center w-full">
                    <StageIcon status={status} />
                    {idx < STAGES.length - 1 && <div className="step-connector mx-2" />}
                  </div>
                  <div className="mt-2 text-center pr-4 min-w-0">
                    <p className="text-xs font-semibold text-slate-700 leading-tight">{stage.label}</p>
                    <p className="text-[10px] text-slate-400 mt-0.5">{stepLabel(status)}</p>
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* Mobile: vertical */}
        <div className="flex sm:hidden flex-col gap-3">
          {STAGES.map((stage) => {
            const status = pipelineState.stages[stage.key];
            return (
              <div key={stage.key} className="flex items-center gap-3">
                <StageIcon status={status} />
                <div className="min-w-0">
                  <p className="text-xs font-semibold text-slate-700">{stage.label}</p>
                  <p className="text-[10px] text-slate-400">{stage.desc} · {stepLabel(status)}</p>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
