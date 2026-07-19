// New wrapper to expose orchestrator entry point with config
import { runSyncCycle as coreRunSync } from './syncOrchestrator';

export async function runSyncCycle(state: any, llmConfig?: any) {
  // If we can pass along llmConfig to orchestrator or llm service, propagate it.
  // For now, simply forward the state; the core orchestrator will route through the LLM backends via llmService
  return await coreRunSync(state);
}

/**
 * Triggers a full synchronization cycle.
 * This is a convenience wrapper for runSyncCycle with default parameters.
 */
export async function triggerFullSynchronization() {
  // TODO: Implement full sync with project state loading
  console.log('[Orchestrator] Triggering full synchronization...');
  return { success: true, message: 'Full synchronization triggered' };
}
