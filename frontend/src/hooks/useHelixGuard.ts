import { useState, useCallback } from 'react';
import type {
  ExtractionRequest,
  HelixGuardApiResponse,
  PipelineState,
} from '../types/helixguard';
import { mockHelixGuardApi } from '../services/mockHelixguardApi';

const useMock = import.meta.env.VITE_USE_MOCK_API !== 'false';
const api = useMock ? mockHelixGuardApi : mockHelixGuardApi; // swap for real api when available

export type HelixGuardError = { message: string; field?: string };

interface UseHelixGuardState {
  result: HelixGuardApiResponse | null;
  loading: boolean;
  errors: HelixGuardError[];
  pipelineState: PipelineState;
}

const idlePipeline: PipelineState = {
  currentStage: 'idle',
  stages: { input: 'pending', localization: 'pending', verification: 'pending', alignment: 'pending' },
};

export function useHelixGuard() {
  const [state, setState] = useState<UseHelixGuardState>({
    result: null,
    loading: false,
    errors: [],
    pipelineState: idlePipeline,
  });

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
    try {
      const res = await api.runExtraction(req);
      setState({ loading: false, errors: [], result: res, pipelineState: res.pipelineState });
    } catch (e) {
      setState((s) => ({
        ...s,
        loading: false,
        errors: [{ message: String(e) }],
      }));
    }
  }, []);

  const runScenario = useCallback(async (scenarioId: string) => {
    setState((s) => ({ ...s, loading: true, errors: [], result: null }));
    try {
      const res = await api.runScenario(scenarioId);
      setState({ loading: false, errors: [], result: res, pipelineState: res.pipelineState });
    } catch (e) {
      setState((s) => ({
        ...s,
        loading: false,
        errors: [{ message: String(e) }],
      }));
    }
  }, []);

  const reset = useCallback(() => {
    setState({ result: null, loading: false, errors: [], pipelineState: idlePipeline });
  }, []);

  const clearErrors = useCallback(() => {
    setState((s) => ({ ...s, errors: [] }));
  }, []);

  return { ...state, run, runScenario, reset, clearErrors };
}
