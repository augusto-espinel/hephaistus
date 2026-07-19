import { runSyncCycle } from './syncOrchestrator';

export async function activate(state: any) {
  console.log('[Hephaistu] Activation: starting orchestrator with initial state');
  try {
    const result = await runSyncCycle(state);
    console.log('[Hephaistu] Activation: sync cycle completed', result);
  } catch (e) {
    console.error('[Hephaistu] Activation: sync cycle failed', e);
  }
}

// Wire a simple exported API for triggering a manual sync from UI
export async function triggerSync(state: any) {
  return runSyncCycle(state);
}
