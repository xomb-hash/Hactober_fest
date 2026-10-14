import { useState } from 'react';
import { Play, CheckCircle } from 'lucide-react';
import { TEST_CASES } from '../data/demoScenarios';
import type { HelixGuardApiResponse } from '../types/helixguard';
import { AlignmentMatrix } from '../components/AlignmentMatrix';
import { ExtractionEvidence } from '../components/ExtractionEvidence';

interface Props {
  onRunScenario: (id: string) => void;
  result: HelixGuardApiResponse | null;
  lastScenarioId: string | null;
}

export function TestCases({ onRunScenario, result, lastScenarioId }: Props) {
  const [runningId, setRunningId] = useState<string | null>(null);

  const handleRun = (scenarioId: string) => {
    setRunningId(scenarioId);
    onRunScenario(scenarioId);
  };

  return (
    <div className="space-y-4">
      {/* Notice */}
      <div className="px-4 py-3 bg-slate-50 border border-slate-200 rounded-md">
        <p className="text-xs text-slate-600 leading-relaxed">
          <strong>Note:</strong> Clicking "Run Demo" executes a predefined mock scenario and updates the interface below.
          This does not execute the real backend test suite — that requires the C++ engine and Python middleware.
        </p>
      </div>

      <div className="grid lg:grid-cols-2 gap-4">
        {/* Test case list */}
        <div className="space-y-2">
          {TEST_CASES.map((tc) => {
            const isActive = lastScenarioId === tc.scenarioId;
            return (
              <div
                key={tc.id}
                className={`card transition-colors ${isActive ? 'border-accent-300' : ''}`}
              >
                <div className="p-3 flex items-start gap-3">
                  <div className={`w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5 ${
                    isActive ? 'bg-accent-100' : 'bg-slate-100'
                  }`}>
                    {isActive
                      ? <CheckCircle size={12} className="text-accent-700" />
                      : <span className="text-[10px] font-mono text-slate-400">{tc.id.split('-')[1]}</span>
                    }
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-semibold text-slate-800">{tc.name}</p>
                    <p className="text-[11px] text-slate-500 mt-0.5 leading-snug">{tc.description}</p>
                    <p className="text-[11px] text-slate-600 mt-1">
                      <strong>Expected:</strong> {tc.expectedOutcome}
                    </p>
                  </div>
                  <button
                    id={`run-tc-${tc.id}`}
                    onClick={() => handleRun(tc.scenarioId)}
                    disabled={runningId === tc.scenarioId && !result}
                    className={`btn-secondary flex-shrink-0 text-xs mt-0.5 ${isActive ? 'bg-accent-100 border-accent-300 text-accent-700' : ''}`}
                    aria-label={`Run demo for ${tc.name}`}
                  >
                    <Play size={11} />
                    Run
                  </button>
                </div>
              </div>
            );
          })}
        </div>

        {/* Result panel */}
        <div className="space-y-4">
          {result ? (
            <>
              <AlignmentMatrix result={result.alignmentResult} />
              <ExtractionEvidence result={result.extractionResult} />
            </>
          ) : (
            <div className="card">
              <div className="card-header"><span className="card-title">Results</span></div>
              <div className="card-body">
                <p className="text-xs text-slate-400 italic">Select and run a test case to see results here.</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
