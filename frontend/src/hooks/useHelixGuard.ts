import { useState, useCallback, useEffect } from 'react';
import type {
  ExtractionRequest,
  HelixGuardApiResponse,
  PipelineState,
} from '../types/helixguard';
import { mockHelixGuardApi } from '../services/mockHelixguardApi';
import { realHelixGuardApi } from '../services/realHelixguardApi';

export type HelixGuardError = { message: string; field?: string };

interface UseHelixGuardState {
  result: HelixGuardApiResponse | null;
  loading: boolean;
  errors: HelixGuardError[];
  pipelineState: PipelineState;
  isLiveMode: boolean;
  backendReachable: boolean;
}

const idlePipeline: PipelineState = {
  currentStage: 'idle',
  stages: { input: 'pending', localization: 'pending', verification: 'pending', alignment: 'pending' },
};

export function useHelixGuard() {
  const initialLive = import.meta.env.VITE_USE_MOCK_API !== 'true';

  const [state, setState] = useState<UseHelixGuardState>({
    result: null,
    loading: false,
    errors: [],
    pipelineState: idlePipeline,
    isLiveMode: initialLive,
    backendReachable: false,
  });

  // Check backend health periodically
  useEffect(() => {
    let mounted = true;
    const checkHealth = async () => {
      const ok = await realHelixGuardApi.isAvailable();
      if (mounted) {
        setState((s) => ({ ...s, backendReachable: ok }));
      }
    };
    checkHealth();
    const interval = setInterval(checkHealth, 5000);
    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []);

  const setLiveMode = useCallback((live: boolean) => {
    setState((s) => ({ ...s, isLiveMode: live }));
  }, []);

  const validate = (req: ExtractionRequest): HelixGuardError[] => {
    const errs: HelixGuardError[] = [];
    if (!req.documentText.trim()) errs.push({ message: 'Document text is required.', field: 'documentText' });
    if (!req.referenceSequence.trim()) errs.push({ message: 'Reference sequence is required.', field: 'referenceSequence' });
    return errs;
  };

  const run = useCallback(async (req: ExtractionRequest) => {
    const errs = validate(req);
    if (errs.length > 0) {
      setState((s) => ({ ...s, errors: errs }));
      return;
    }
    setState((s) => ({ ...s, loading: true, errors: [], result: null }));

    const api = state.isLiveMode ? realHelixGuardApi : mockHelixGuardApi;

    try {
      const res = await api.runExtraction(req);
      setState((s) => ({ ...s, loading: false, errors: [], result: res, pipelineState: res.pipelineState }));
    } catch (e: any) {
      const msg = e?.message || String(e);
      setState((s) => ({
        ...s,
        loading: false,
        errors: [{ message: `Backend error: ${msg}. You can toggle to Demo Mode to test offline scenarios.` }],
      }));
    }
  }, [state.isLiveMode]);

  const runScenario = useCallback(async (scenarioId: string) => {
    setState((s) => ({ ...s, loading: true, errors: [], result: null }));
    const api = state.isLiveMode ? realHelixGuardApi : mockHelixGuardApi;
    try {
      const res = await api.runScenario(scenarioId);
      setState((s) => ({ ...s, loading: false, errors: [], result: res, pipelineState: res.pipelineState }));
    } catch (e: any) {
      setState((s) => ({
        ...s,
        loading: false,
        errors: [{ message: String(e?.message || e) }],
      }));
    }
  }, [state.isLiveMode]);

  const reset = useCallback(() => {
    setState((s) => ({ ...s, result: null, loading: false, errors: [], pipelineState: idlePipeline }));
  }, []);

  const clearErrors = useCallback(() => {
    setState((s) => ({ ...s, errors: [] }));
  }, []);

  return {
    ...state,
    setLiveMode,
    run,
    runScenario,
    reset,
    clearErrors,
  };
}
