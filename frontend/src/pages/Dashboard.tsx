import { Dna, GitBranch, ShieldCheck, BarChart2, ExternalLink } from 'lucide-react';
import type { PipelineState } from '../types/helixguard';
import { PipelineStepper } from '../components/PipelineStepper';

interface Props {
  pipelineState: PipelineState;
  onNavigate: (page: string) => void;
}

const PIPELINE_STEPS = [
  {
    icon: <Dna size={18} className="text-slate-600" />,
    title: 'Document Input',
    desc: 'Paste a sequencing report or genomic document. Validate format and load reference sequence.',
  },
  {
    icon: <GitBranch size={18} className="text-slate-600" />,
    title: 'Sequence Localization',
    desc: 'Anchor-based location search. If anchors fail, exact-quote and fuzzy recovery are attempted.',
  },
  {
    icon: <ShieldCheck size={18} className="text-slate-600" />,
    title: 'Source Verification',
    desc: 'Boundary and completeness checks against the source document. Ambiguous results abstain.',
  },
  {
    icon: <BarChart2 size={18} className="text-slate-600" />,
    title: 'Alignment',
    desc: 'Smith–Waterman local alignment of the verified sequence against the reference.',
  },
];

export function Dashboard({ pipelineState, onNavigate }: Props) {
  return (
    <div className="space-y-6">
      {/* Pipeline overview */}
      <PipelineStepper pipelineState={pipelineState} />

      {/* Stage explanations */}
      <div className="card">
        <div className="card-header">
          <span className="card-title">About the pipeline</span>
        </div>
        <div className="card-body grid sm:grid-cols-2 gap-4">
          {PIPELINE_STEPS.map((step, i) => (
            <div key={i} className="flex items-start gap-3 p-3 bg-slate-50 border border-slate-200 rounded-md">
              <div className="w-8 h-8 rounded-md bg-white border border-slate-200 flex items-center justify-center flex-shrink-0">
                {step.icon}
              </div>
              <div>
                <p className="text-xs font-semibold text-slate-800">{step.title}</p>
                <p className="text-[11px] text-slate-500 mt-0.5 leading-snug">{step.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Quick actions */}
      <div className="card">
        <div className="card-header">
          <span className="card-title">Quick start</span>
        </div>
        <div className="card-body space-y-2">
          <p className="text-xs text-slate-500">
            This frontend runs entirely with predefined mock scenarios. No backend is connected.
            Use the links below to explore the application.
          </p>
          <div className="flex flex-wrap gap-2 pt-1">
            {[
              { page: 'extraction', label: 'Open Sequence Extraction' },
              { page: 'test-cases', label: 'Browse Test Cases' },
              { page: 'about', label: 'Read Limitations' },
            ].map(({ page, label }) => (
              <button
                key={page}
                id={`quick-${page}`}
                onClick={() => onNavigate(page)}
                className="btn-secondary text-xs"
              >
                {label}
                <ExternalLink size={11} />
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Disclaimer */}
      <div className="p-3 bg-amber-50 border border-amber-200 rounded-md">
        <p className="text-xs text-amber-800 leading-relaxed">
          <strong>Disclaimer:</strong> HelixGuard is a research prototype. All results shown use synthetic data.
          This application does not provide clinical diagnoses, medical advice, or treatment recommendations.
          Smith–Waterman alignment is a computational tool, not a clinical assay.
        </p>
      </div>
    </div>
  );
}
