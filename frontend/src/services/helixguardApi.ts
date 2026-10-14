import type { ExtractionRequest, HelixGuardApiResponse } from '../types/helixguard';

/**
 * Abstract interface for the HelixGuard backend.
 * The mock implementation satisfies this interface.
 * When a real backend exists, replace the implementation in helixguardApi.ts
 * without modifying any component that depends on this interface.
 */
export interface IHelixGuardApi {
  runExtraction(request: ExtractionRequest): Promise<HelixGuardApiResponse>;
  runScenario(scenarioId: string): Promise<HelixGuardApiResponse>;
  isAvailable(): Promise<boolean>;
}
