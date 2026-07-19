import * as vscode from 'vscode';

// Import services
import { registerConfigListener } from './configService';
import { registerBackupCommands } from './backupService';
import { registerReviewCommands } from './reviewService';
import { initializeState, loadState, checkPermission } from './stateManager';
import { 
    initializeSync, 
    runSyncCycle, 
    triggerFullSynchronization,
    resetSync,
    getSyncStatus,
    onSyncComplete 
} from './syncOrchestrator';

// Constants for command IDs
const HEPHAISTUS_START_SESSION_COMMAND = 'hephaistus.startSession';
const HEPHAISTUS_APPROVE_PATCH_COMMAND = 'hephaistus.approvePatch';
const HEPHAISTUS_REJECT_PATCH_COMMAND = 'hephaistus.rejectPatch';
const HEPHAISTUS_SYNC_COMMAND = 'hephaistus.sync';
const HEPHAISTUS_STATUS_COMMAND = 'hephaistus.status';
const HEPHAISTUS_RESET_ITERATIONS_COMMAND = 'hephaistus.resetIterations';

// Define logger function for consistent output
const log = (message: string, level: 'info' | 'warn' | 'error' = 'info') => {
    const prefix = `[HephAIstus ${level.toUpperCase()}]`;
    switch (level) {
        case 'info':
            console.log(`${prefix}: ${message}`);
            break;
        case 'warn':
            console.warn(`${prefix}: ${message}`);
            break;
        case 'error':
            console.error(`${prefix}: ${message}`);
            break;
    }
};

export async function activate(context: vscode.ExtensionContext) {
    log('HephAIstus extension activation started.');

    // Dynamically resolve workspace folder
    let workspaceRoot: vscode.Uri | undefined;
    if (vscode.workspace.workspaceFolders && vscode.workspace.workspaceFolders.length > 0) {
        workspaceRoot = vscode.workspace.workspaceFolders[0].uri;
        log(`Workspace root found at: ${workspaceRoot.fsPath}`);
    } else {
        log('No workspace folder found. Extension functionality may be limited.', 'warn');
    }

    // Register configuration listener
    registerConfigListener(context);
    log('Configuration listener registered.');

    // Register backup commands
    registerBackupCommands(context);
    log('Backup commands registered.');

    // Register review commands
    registerReviewCommands(context);
    log('Review commands registered.');

    // Initialize sync system
    try {
        await initializeSync(context);
        log('Sync system initialized.');
    } catch (error) {
        log(`Failed to initialize sync system: ${error}`, 'error');
    }

    // Listen for sync complete events
    context.subscriptions.push(
        onSyncComplete((result) => {
            log(`Sync completed: ${result.status} - ${result.message}`);
            if (result.status === 'ok') {
                vscode.window.setStatusBarMessage('$(check) HephAIstus: Sync complete', 3000);
            } else if (result.status === 'error') {
                vscode.window.showErrorMessage(`HephAIstus sync failed: ${result.message}`);
            } else if (result.status === 'checkpoint-required') {
                vscode.window.showWarningMessage(`HephAIstus: ${result.message}`);
            }
        })
    );

    // --- Command Registrations ---

    // Command: hephaistus.startSession
    const startSessionDisposable = vscode.commands.registerCommand(HEPHAISTUS_START_SESSION_COMMAND, async () => {
        log(`Command "${HEPHAISTUS_START_SESSION_COMMAND}" executed.`);
        
        try {
            // Initialize or load state
            const state = await loadState();
            if (state) {
                log(`Loaded existing state. Permission level: ${state.permissionLevel}`);
            } else {
                const newState = await initializeState();
                log(`Initialized new state. Permission level: ${newState.permissionLevel}`);
            }
            
            const status = await getSyncStatus();
            vscode.window.showInformationMessage(
                `HephAIstus: Session started. Permission: ${status.state?.permissionLevel || 'unknown'}, Iterations: ${status.state?.currentIteration || 0}/${status.state?.maxIterations || 0}`
            );
        } catch (error) {
            log(`Failed to initialize session: ${error}`, 'error');
            vscode.window.showErrorMessage(`HephAIstus: Failed to initialize session.`);
        }
    });
    context.subscriptions.push(startSessionDisposable);
    log(`Registered command: ${HEPHAISTUS_START_SESSION_COMMAND}`);

    // Command: hephaistus.sync
    const syncDisposable = vscode.commands.registerCommand(HEPHAISTUS_SYNC_COMMAND, async () => {
        log(`Command "${HEPHAISTUS_SYNC_COMMAND}" executed.`);
        
        await vscode.window.withProgress(
            {
                location: vscode.ProgressLocation.Notification,
                title: 'HephAIstus: Syncing...',
                cancellable: false
            },
            async () => {
                const result = await runSyncCycle({ createCheckpoint: true });
                return result;
            }
        );
    });
    context.subscriptions.push(syncDisposable);
    log(`Registered command: ${HEPHAISTUS_SYNC_COMMAND}`);

    // Command: hephaistus.status
    const statusDisposable = vscode.commands.registerCommand(HEPHAISTUS_STATUS_COMMAND, async () => {
        log(`Command "${HEPHAISTUS_STATUS_COMMAND}" executed.`);
        
        const status = await getSyncStatus();
        if (!status.state) {
            vscode.window.showInformationMessage('HephAIstus: No state found. Start a session first.');
            return;
        }
        
        const message = `Permission: ${status.state.permissionLevel}\n` +
            `Iterations: ${status.state.currentIteration}/${status.state.maxIterations}\n` +
            `Issues: ${status.issues.length}\n` +
            `Can Continue: ${status.canContinue ? 'Yes' : 'No'}`;
        
        vscode.window.showInformationMessage(message, { modal: true });
    });
    context.subscriptions.push(statusDisposable);
    log(`Registered command: ${HEPHAISTUS_STATUS_COMMAND}`);

    // Command: hephaistus.resetIterations
    const resetIterationsDisposable = vscode.commands.registerCommand(HEPHAISTUS_RESET_ITERATIONS_COMMAND, async () => {
        log(`Command "${HEPHAISTUS_RESET_ITERATIONS_COMMAND}" executed.`);
        
        const result = await resetSync();
        if (result.status === 'ok') {
            vscode.window.showInformationMessage('HephAIstus: Iterations reset successfully.');
        } else {
            vscode.window.showErrorMessage(`HephAIstus: Failed to reset iterations: ${result.message}`);
        }
    });
    context.subscriptions.push(resetIterationsDisposable);
    log(`Registered command: ${HEPHAISTUS_RESET_ITERATIONS_COMMAND}`);

    // Command: hephaistus.approvePatch
    const approvePatchDisposable = vscode.commands.registerCommand(HEPHAISTUS_APPROVE_PATCH_COMMAND, async () => {
        log(`Command "${HEPHAISTUS_APPROVE_PATCH_COMMAND}" executed.`);
        // Check if operation is allowed at current permission level
        const state = await loadState();
        if (state) {
            const check = checkPermission(state, 'modifyValue');
            if (!check.allowed) {
                vscode.window.showWarningMessage(check.message || 'Operation not allowed at current permission level.');
                return;
            }
        }
        vscode.window.showInformationMessage('HephAIstus: Patch approval triggered.');
        // TODO: Implement patch approval logic
    });
    context.subscriptions.push(approvePatchDisposable);
    log(`Registered command: ${HEPHAISTUS_APPROVE_PATCH_COMMAND}`);

    // Command: hephaistus.rejectPatch
    const rejectPatchDisposable = vscode.commands.registerCommand(HEPHAISTUS_REJECT_PATCH_COMMAND, async () => {
        log(`Command "${HEPHAISTUS_REJECT_PATCH_COMMAND}" executed.`);
        vscode.window.showInformationMessage('HephAIstus: Patch rejection triggered.');
        // TODO: Implement patch rejection logic
    });
    context.subscriptions.push(rejectPatchDisposable);
    log(`Registered command: ${HEPHAISTUS_REJECT_PATCH_COMMAND}`);

    // --- File System Watcher ---
    // Watch for changes in KiCad schematic files to trigger background processes.
    // The pattern '**/*.kicad_sch' should dynamically resolve within the workspace.
    const kicadFilePattern = '**/*.kicad_sch';
    const fileWatcher = vscode.workspace.createFileSystemWatcher(kicadFilePattern);

    fileWatcher.onDidCreate(async (uri: vscode.Uri) => {
        log(`KiCad schematic file created: ${uri.fsPath}. Triggering ingestion...`);
        try {
            const result = await runSyncCycle({ forceIngestion: true });
            if (result.status === 'ok') {
                log(`Ingestion completed successfully for new file.`);
                vscode.window.setStatusBarMessage('$(check) HephAIstus: Schematic ingested', 3000);
            } else {
                log(`Ingestion result: ${result.status} - ${result.message}`, 'warn');
            }
        } catch (error) {
            log(`Error during ingestion: ${(error as Error).message}`, 'error');
        }
    });

    fileWatcher.onDidDelete(async (uri: vscode.Uri) => {
        log(`KiCad schematic file deleted: ${uri.fsPath}. Cleaning up associated data.`);
        // Future: Remove from stateHashes and files list
    });

    fileWatcher.onDidChange(async (uri: vscode.Uri) => {
        log(`KiCad schematic file changed: ${uri.fsPath}. Triggering analysis...`);
        try {
            const result = await runSyncCycle({ forceIngestion: true });
            if (result.status === 'ok') {
                log(`Sync completed successfully.`);
                vscode.window.setStatusBarMessage('$(sync) HephAIstus: Synced', 3000);
            } else {
                log(`Sync result: ${result.status} - ${result.message}`, 'warn');
            }
        } catch (error) {
            log(`Error during sync: ${(error as Error).message}`, 'error');
        }
    });
    log(`FileSystemWatcher started for pattern: ${kicadFilePattern}`);

    // --- Initialization Complete ---
    log('HephAIstus extension activated successfully.');
}

export function deactivate() {
    log('HephAIstus extension deactivated.');
    // Clean up any resources if necessary
}
