import { useState, useCallback } from 'react';
import { Sidebar, type NavPage } from './components/Sidebar';
import { Header } from './components/Header';
import { Dashboard } from './pages/Dashboard';
import { SequenceExtraction } from './pages/SequenceExtraction';
import { Alignment } from './pages/Alignment';
import { TestCases } from './pages/TestCases';
import { About } from './pages/About';
import { useHelixGuard } from './hooks/useHelixGuard';
import { SAMPLE_REPORT_TEXT } from './services/mockHelixguardApi';
import type { ExtractionRequest } from './types/helixguard';

const PAGE_META: Record<NavPage, { title: string; description: string }> = {
  dashboard:  { title: 'Dashboard',           description: 'Overview of the HelixGuard verification pipeline.' },
  extraction: { title: 'Sequence Extraction',  description: 'Extract and verify a genomic sequence from a source document.' },
  alignment:  { title: 'Alignment',            description: 'Smith–Waterman local alignment of the verified sequence against the reference.' },
  'test-cases': { title: 'Test Cases',         description: 'Predefined demo scenarios covering key verification outcomes.' },
  about:      { title: 'About / Limitations',  description: 'Design decisions, system limitations, and disclaimers.' },
};

function App() {
  const [page, setPage] = useState<NavPage>('dashboard');
  const [lastScenarioId, setLastScenarioId] = useState<string | null>(null);

  const {
    result,
    loading,
    errors,
    pipelineState,
    run,
    runScenario,
    reset,
    isLiveMode,
    setLiveMode,
    backendReachable,
  } = useHelixGuard();

  const meta = PAGE_META[page];

  const handleRun = useCallback((req: ExtractionRequest) => {
    setLastScenarioId(null);
    run(req);
  }, [run]);

  const handleRunScenario = useCallback((id: string) => {
    setLastScenarioId(id);
    runScenario(id);
  }, [runScenario]);

  const [sampleTrigger, setSampleTrigger] = useState(0);

  const handleLoadSample = useCallback(() => {
    setPage('extraction');
    setSampleTrigger((prev) => prev + 1);
  }, []);

  return (
    <div className="flex h-screen overflow-hidden bg-slate-50">
      <Sidebar currentPage={page} onNavigate={setPage} />

      <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
        <Header
          title={meta.title}
          description={meta.description}
          isLiveMode={isLiveMode}
          onToggleMode={setLiveMode}
          backendReachable={backendReachable}
        />

        <main
          id="main-content"
          className="flex-1 overflow-y-auto p-4 md:p-6"
          role="main"
          aria-label={meta.title}
        >
          {page === 'dashboard' && (
            <Dashboard pipelineState={pipelineState} onNavigate={(p) => setPage(p as NavPage)} />
          )}
          {page === 'extraction' && (
            <SequenceExtraction
              result={result}
              pipelineState={pipelineState}
              loading={loading}
              errors={errors}
              onRun={handleRun}
              onRunScenario={handleRunScenario}
              onLoadSample={handleLoadSample}
              onClear={reset}
              sampleText={SAMPLE_REPORT_TEXT}
              sampleTrigger={sampleTrigger}
            />
          )}
          {page === 'alignment' && (
            <Alignment result={result} pipelineState={pipelineState} />
          )}
          {page === 'test-cases' && (
            <TestCases
              onRunScenario={handleRunScenario}
              result={result}
              lastScenarioId={lastScenarioId}
            />
          )}
          {page === 'about' && <About />}
        </main>
      </div>
    </div>
  );
}

export default App;
