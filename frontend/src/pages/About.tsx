import { AlertTriangle } from 'lucide-react';

const LIMITATIONS = [
  {
    title: 'LLMs assist with localization only',
    body: 'In the full system, LLMs may propose anchor text and a candidate quote to help locate a sequence within a document. They do not author or modify the extracted nucleotide content. The extracted sequence must be found verbatim in the source document.',
  },
  {
    title: 'Deterministic verification controls acceptance',
    body: 'Acceptance or rejection of a candidate sequence is determined by deterministic source matching, boundary verification, and completeness checks — not by the LLM\'s confidence or the sequence\'s apparent validity.',
  },
  {
    title: 'Anchor recovery may succeed when an anchor is wrong',
    body: 'If an anchor fails, exact-quote or fuzzy recovery may independently locate the candidate. A successful recovery still produces a lower-confidence result than both anchors matching.',
  },
  {
    title: 'Ambiguous or incomplete evidence results in abstention',
    body: 'If the candidate quote appears in more than one location in the source, or if boundaries cannot be verified, the system abstains. Alignment is not run on an abstained result.',
  },
  {
    title: 'Alphabet validation ≠ source-fidelity verification',
    body: 'A sequence that passes DNA/RNA alphabet checks is not thereby verified as extracted faithfully from the source. The invalid characters may exist in the source document; the sequence may still be syntactically valid but sourced incorrectly.',
  },
  {
    title: 'Smith–Waterman alignment is not a clinical diagnosis',
    body: 'Alignment scores quantify local sequence similarity using the configured scoring parameters. They do not constitute a clinical variant call, diagnosis, or treatment recommendation.',
  },
  {
    title: 'Current application uses predefined mock scenarios',
    body: 'All results in this Phase 1 frontend are produced by deterministic mock data. No real C++ engine, Python middleware, or LLM agent is connected. The mock is clearly labelled throughout the UI.',
  },
];

export function About() {
  return (
    <div className="space-y-4 max-w-2xl">
      {/* Header card */}
      <div className="card">
        <div className="card-header">
          <span className="card-title">About HelixGuard</span>
        </div>
        <div className="card-body space-y-2">
          <p className="text-sm text-slate-700 leading-relaxed">
            HelixGuard is a <strong>verification-first</strong> genomic sequence extraction and alignment system.
            Its design premise is that a language model's proposed sequence must be traceable to and verifiable
            against the source document before any alignment is performed.
          </p>
          <p className="text-sm text-slate-600 leading-relaxed">
            This Phase 1 frontend demonstrates the intended workflow using predefined mock scenarios.
            The backend C++ Smith–Waterman engine, Python middleware, and LLM agents are not yet connected.
          </p>
        </div>
      </div>

      {/* Limitations */}
      <div className="card">
        <div className="card-header">
          <div className="flex items-center gap-2">
            <AlertTriangle size={14} className="text-amber-600" />
            <span className="card-title">Design decisions &amp; limitations</span>
          </div>
        </div>
        <div className="card-body space-y-4">
          {LIMITATIONS.map((lim, i) => (
            <div key={i} className="flex items-start gap-3">
              <span className="mt-0.5 text-[10px] font-mono text-slate-400 flex-shrink-0 w-5 text-right">{i + 1}.</span>
              <div>
                <p className="text-xs font-semibold text-slate-800">{lim.title}</p>
                <p className="text-[11px] text-slate-500 mt-0.5 leading-relaxed">{lim.body}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Version info */}
      <div className="px-4 py-3 bg-slate-50 border border-slate-200 rounded-md flex items-center justify-between">
        <div className="space-y-0.5">
          <p className="text-xs font-semibold text-slate-700">HelixGuard — Phase 1 Frontend</p>
          <p className="text-[10px] text-slate-400">React · TypeScript · Vite · Tailwind CSS · Demo Mode</p>
        </div>
        <span className="badge-demo badge text-[10px]">DEMO</span>
      </div>
    </div>
  );
}
