import type { ExtractionRequest, HelixGuardApiResponse } from '../types/helixguard';
import { mockHelixGuardApi } from './mockHelixguardApi';
import { realHelixGuardApi } from './realHelixguardApi';

/**
 * Abstract interface for the HelixGuard backend.
 * The mock implementation satisfies this interface.
 */
export interface IHelixGuardApi {
  runExtraction(request: ExtractionRequest): Promise<HelixGuardApiResponse>;
  runScenario(scenarioId: string): Promise<HelixGuardApiResponse>;
  isAvailable(): Promise<boolean>;
}

export { mockHelixGuardApi } from './mockHelixguardApi';
export { realHelixGuardApi } from './realHelixguardApi';

export function getHelixGuardApi(forceMock: boolean = false): IHelixGuardApi {
  if (forceMock) {
    return mockHelixGuardApi;
  }
  const useMockEnv = import.meta.env.VITE_USE_MOCK_API === 'true';
  return useMockEnv ? mockHelixGuardApi : realHelixGuardApi;
}
