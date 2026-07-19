/**
 * syncOrchestrator.ts
 * Central orchestrator: coordinates two-mode sync paths for HephAIstus.
 * - Programmatic KiCad (.kicad_sch) -> JSON ingestion (deterministic)
 * - Semantic Python <-> JSON synchronization via LLM (state interpretation)
 *
 * Exposed API:
 * - runSyncCycle(): Promise<SyncResult>
 * - triggerFullSynchronization(): Promise<SyncResult>
 * - startWatching(): void
 * - stopWatching(): void
 */

import * as vscode from 'vscode';
import * as path from 'path';
import { 
    loadState, 
    saveState, 
    createCheckpoint, 
    restoreCheckpoint,
    checkPermission,
    analyzeState,
    incrementIteration,
    canContinueIterating,
    resetIterations,
    updateFileHashes,
    scanWorkspaceFiles,
    ProjectState
} from './stateManager';
import { getPermissionLevel, getIterationConfig, onDidChangeConfig } from './configService';
import { executeIngestionPhase } from './services/ingestionService';
import { updateScriptsIfNeeded } from './services/scriptUpdateService';

// --- TYPE DEFINITIONS ---

export interface SyncResult {
    status: 'ok' | 'needs-ingestion' | 'needs-update' | 'error' | 'checkpoint-required';
    message: string;
    state?: ProjectState;
    issues?: Array<{ type: string; description: string }>;
}

export interface SyncOptions {
    forceIngestion?: boolean;
    createCheckpoint?: boolean;
    dryRun?: boolean;
}

// --- EVENT EMITTERS ---

const syncEventEmitter = new vscode.EventEmitter<SyncResult>();
export const onSyncComplete = syncEventEmitter.event;

// --- STATE WATCHER ---

let watcher: vscode.FileSystemWatcher | undefined;
let isWatching = false;
let lastSyncTime = 0;
const MIN_SYNC_INTERVAL_MS = 1000; // Debounce: 1 second

// --- CORE SYNC FUNCTIONS ---

/**
 * Initialize the sync system and start watching for file changes.
 */
export async function initializeSync(context: vscode.ExtensionContext): Promise<void> {
    console.log('[SyncOrchestrator] Initializing sync system...');
    
    // Load or create initial state
    let state = await loadState();
    if (!state) {
        console.log('[SyncOrchestrator] No existing state, creating initial state...');
        state = await initializeState();
    }
    
    // Register for config changes
    context.subscriptions.push(
        onDidChangeConfig(async (newConfig) => {
            console.log('[SyncOrchestrator] Configuration changed, updating state...');
            state = await loadState();
            if (state) {
                state.permissionLevel = newConfig.permissions.level;
                state.maxIterations = newConfig.iteration.maxAutonomousIterations;
                await saveState(state);
            }
        })
    );
    
    // Start file watcher
    startWatching(context);
    
    console.log('[SyncOrchestrator] Sync system initialized.');
}

/**
 * Import missing function
 */
async function initializeState(): Promise<ProjectState> {
    const { initializeState: initState } = await import('./stateManager');
    return initState();
}

/**
 * Start watching for file changes in the workspace.
 */
export function startWatching(context: vscode.ExtensionContext): vscode.Disposable {
    if (isWatching) {
        console.log('[SyncOrchestrator] Already watching, skipping.');
        return new vscode.Disposable(() => {});
    }
    
    const workspaceFolders = vscode.workspace.workspaceFolders;
    if (!workspaceFolders || workspaceFolders.length === 0) {
        console.warn('[SyncOrchestrator] No workspace folder, cannot start watching.');
        return new vscode.Disposable(() => {});
    }
    
    const rootPath = workspaceFolders[0].uri.fsPath;
    
    // Watch for KiCad, JSON, and Python files
    const pattern = new vscode.RelativePattern(rootPath, '**/*.{kicad_sch,json,py}');
    watcher = vscode.workspace.createFileSystemWatcher(pattern);
    
    watcher.onDidChange(async (uri) => {
        await handleFileChange(uri, 'changed');
    });
    
    watcher.onDidCreate(async (uri) => {
        await handleFileChange(uri, 'created');
    });
    
    watcher.onDidDelete(async (uri) => {
        await handleFileChange(uri, 'deleted');
    });
    
    // Also listen for save events
    context.subscriptions.push(
        vscode.workspace.onDidSaveTextDocument(async (doc) => {
            const ext = path.extname(doc.fileName);
            if (['.kicad_sch', '.json', '.py'].includes(ext)) {
                await handleFileChange(doc.uri, 'saved');
            }
        })
    );
    
    isWatching = true;
    console.log('[SyncOrchestrator] File watcher started.');
    
    return new vscode.Disposable(() => stopWatching());
}

/**
 * Stop watching for file changes.
 */
export function stopWatching(): void {
    if (watcher) {
        watcher.dispose();
        watcher = undefined;
    }
    isWatching = false;
    console.log('[SyncOrchestrator] File watcher stopped.');
}

/**
 * Handle a file change event.
 */
async function handleFileChange(uri: vscode.Uri, event: string): Promise<void> {
    // Debounce: don't sync too frequently
    const now = Date.now();
    if (now - lastSyncTime < MIN_SYNC_INTERVAL_MS) {
        console.log(`[SyncOrchestrator] Debouncing file ${event} event.`);
        return;
    }
    lastSyncTime = now;
    
    const filePath = uri.fsPath;
    const fileName = path.basename(filePath);
    const ext = path.extname(filePath);
    
    console.log(`[SyncOrchestrator] File ${event}: ${fileName}`);
    
    // Update file hashes
    try {
        const state = await loadState();
        if (state) {
            await updateFileHashes(state, [filePath]);
            
            // Check if we need to trigger a sync
            const analysis = analyzeState(state);
            if (analysis.needsIngestion || analysis.needsPythonUpdate) {
                console.log('[SyncOrchestrator] State analysis indicates sync needed.');
                // Don't auto-sync, just notify
                vscode.window.setStatusBarMessage('$(sync~spin) HephAIstus: Changes detected', 3000);
            }
        }
    } catch (error) {
        console.error('[SyncOrchestrator] Error handling file change:', error);
    }
}

/**
 * Run a full synchronization cycle.
 */
export async function runSyncCycle(options: SyncOptions = {}): Promise<SyncResult> {
    console.log('[SyncOrchestrator] Starting sync cycle...');
    
    try {
        // Load current state
        let state = await loadState();
        if (!state) {
            state = await initializeState();
        }
        
        // Create checkpoint if requested
        if (options.createCheckpoint) {
            const checkpoint = await createCheckpoint(state, 'Pre-sync backup');
            console.log(`[SyncOrchestrator] Created checkpoint: ${checkpoint.id}`);
        }
        
        // Analyze state for issues
        const analysis = analyzeState(state);
        
        // Check if we can continue
        if (!canContinueIterating(state)) {
            return {
                status: 'checkpoint-required',
                message: `Maximum iterations (${state.maxIterations}) reached. Create a checkpoint or reset.`,
                state,
                issues: analysis.issues
            };
        }
        
        // Check permissions for operations
        const permissionCheck = checkPermission(state, 'modifyValue');
        if (!permissionCheck.allowed) {
            return {
                status: 'error',
                message: permissionCheck.message || 'Insufficient permissions for sync operation.',
                state
            };
        }
        
        // Run ingestion if needed
        if (analysis.needsIngestion || options.forceIngestion) {
            console.log('[SyncOrchestrator] Running ingestion...');
            
            // Find KiCad files that need ingestion
            // Check both state.files.kicad (explicit) and stateHashes (detected)
            const kicadFiles = new Set<string>();
            
            // From explicit files list
            for (const f of (state.files.kicad || [])) {
                kicadFiles.add(f);
            }
            
            // From stateHashes (files tracked by watcher)
            for (const filePath of Object.keys(state.stateHashes)) {
                if (filePath.endsWith('.kicad_sch')) {
                    kicadFiles.add(filePath);
                }
            }
            
            // Process each KiCad file
            for (const kicadFile of kicadFiles) {
                // Resolve to absolute path if needed
                const absolutePath = path.isAbsolute(kicadFile) 
                    ? kicadFile 
                    : path.join(state.workspaceRoot, kicadFile);
                
                try {
                    const result = await executeIngestionPhase(absolutePath, state);
                    if (!result.success) {
                        console.warn(`[SyncOrchestrator] Ingestion failed for ${kicadFile}:`, result.message);
                    } else {
                        console.log(`[SyncOrchestrator] Ingestion successful for ${kicadFile}`);
                    }
                } catch (error) {
                    console.error(`[SyncOrchestrator] Ingestion error for ${kicadFile}:`, error);
                }
            }
            // Note: Iteration counter NOT incremented for ingestion - only for autonomous optimization
        }
        
        // Run script updates if needed
        if (analysis.needsPythonUpdate) {
            console.log('[SyncOrchestrator] Running script updates...');
            try {
                const updateResult = await updateScriptsIfNeeded(state);
                if (updateResult?.needsUpdate) {
                    console.log('[SyncOrchestrator] Scripts updated:', updateResult.reportMessage);
                }
            } catch (error) {
                console.error('[SyncOrchestrator] Script update error:', error);
            }
        }
        
        // Save updated state
        await saveState(state);
        
        // Note: Iteration counter NOT incremented for sync - only for autonomous optimization
        // Only increment if this was an optimization cycle (future: when optimization is implemented)
        
        const result: SyncResult = {
            status: 'ok',
            message: 'Sync cycle completed successfully.',
            state,
            issues: analysis.issues
        };
        
        // Emit event
        syncEventEmitter.fire(result);
        
        console.log('[SyncOrchestrator] Sync cycle complete.');
        return result;
        
    } catch (error) {
        const errorMessage = (error as Error).message;
        console.error('[SyncOrchestrator] Sync cycle failed:', errorMessage);
        
        return {
            status: 'error',
            message: errorMessage
        };
    }
}

/**
 * Trigger a full synchronization (convenience wrapper).
 */
export async function triggerFullSynchronization(): Promise<SyncResult> {
    return runSyncCycle({ createCheckpoint: true });
}

/**
 * Reset the sync state and start fresh.
 */
export async function resetSync(): Promise<SyncResult> {
    try {
        const loadedState = await loadState();
        if (loadedState) {
            resetIterations(loadedState);
            await saveState(loadedState);
        }
        
        return {
            status: 'ok',
            message: 'Sync state reset successfully.',
            state: loadedState ?? undefined
        };
    } catch (error) {
        return {
            status: 'error',
            message: (error as Error).message
        };
    }
}

/**
 * Get the current sync status.
 */
export async function getSyncStatus(): Promise<{
    state: ProjectState | undefined;
    canContinue: boolean;
    issues: Array<{ type: string; description: string }>;
}> {
    const state = await loadState();
    if (!state) {
        return {
            state: undefined,
            canContinue: false,
            issues: []
        };
    }
    
    const analysis = analyzeState(state);
    
    return {
        state,
        canContinue: canContinueIterating(state),
        issues: analysis.issues
    };
}

export default {
    initializeSync,
    startWatching,
    stopWatching,
    runSyncCycle,
    triggerFullSynchronization,
    resetSync,
    getSyncStatus,
    onSyncComplete
};