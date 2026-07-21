/**
 * stateManager.ts
 * Enhanced state management for HephAIstus with permission tracking,
 * checkpoint/restore functionality, and backup integration.
 */

import * as vscode from 'vscode';
import * as fs from 'fs/promises';
import * as path from 'path';
import * as crypto from 'crypto';
import { 
    getPermissionLevel, 
    getIterationConfig, 
    getBackupConfig,
    PermissionLevel 
} from './configService';
import { createBackup, restoreBackup, listBackups, BackupMetadata } from './backupService';

// --- TYPE DEFINITIONS ---

export interface StateEntry {
    hash: string;
    lastModifiedTime: string; // ISO timestamp
    associatedFiles?: string[];
    expectedKicadHash?: string;
}

export interface FileRegistry {
    kicad?: string[];
    json?: string[];
    py?: string[];
}

export interface CheckpointMetadata {
    id: string;
    createdAt: string;
    permissionLevel: PermissionLevel;
    iteration: number;
    description: string;
}

export interface ProjectState {
    version: string;
    workspaceRoot: string;
    files: FileRegistry;
    stateHashes: Record<string, StateEntry>;
    permissionLevel: PermissionLevel;
    currentIteration: number;
    maxIterations: number;
    lastCheckpoint?: CheckpointMetadata;
    lastBackup?: string; // Backup ID
    lastSync?: {
        source: 'kicad' | 'json';
        timestamp: string;
        kicadHash?: string;
        jsonHash?: string;
    };
    metadata: {
        createdAt: string;
        updatedAt: string;
        schemaVersion: string;
    };
}

// --- CONSTANTS ---

const SCHEMA_VERSION = '1.0.0';
const STATE_DIR = '.hephaistus';
const STATE_FILE = 'state.json';

// --- UTILITY FUNCTIONS ---

/**
 * Get the workspace root path.
 */
function getWorkspaceRoot(): string {
    const workspaceFolders = vscode.workspace.workspaceFolders;
    if (!workspaceFolders || workspaceFolders.length === 0) {
        throw new Error('No workspace folder open');
    }
    return workspaceFolders[0].uri.fsPath;
}

/**
 * Get the state directory path.
 */
function getStateDir(workspaceRoot: string): string {
    return path.join(workspaceRoot, STATE_DIR);
}

/**
 * Get the state file path.
 */
function getStateFilePath(workspaceRoot: string): string {
    return path.join(getStateDir(workspaceRoot), STATE_FILE);
}

/**
 * Generate a unique checkpoint ID.
 */
function generateCheckpointId(): string {
    return `ckpt_${Date.now().toString(36)}_${crypto.randomBytes(4).toString('hex')}`;
}

/**
 * Generate a file hash.
 */
async function generateFileHash(filePath: string): Promise<string> {
    try {
        const content = await fs.readFile(filePath);
        return crypto.createHash('sha256').update(content).digest('hex');
    } catch {
        return '';
    }
}

// --- STATE OPERATIONS ---

/**
 * Initialize a new project state.
 */
export async function initializeState(): Promise<ProjectState> {
    const workspaceRoot = getWorkspaceRoot();
    const stateDir = getStateDir(workspaceRoot);
    
    // Ensure state directory exists
    await fs.mkdir(stateDir, { recursive: true });
    
    const config = getIterationConfig();
    const permissionLevel = getPermissionLevel();
    
    const newState: ProjectState = {
        version: SCHEMA_VERSION,
        workspaceRoot,
        files: {},
        stateHashes: {},
        permissionLevel,
        currentIteration: 0,
        maxIterations: config.maxAutonomousIterations,
        metadata: {
            createdAt: new Date().toISOString(),
            updatedAt: new Date().toISOString(),
            schemaVersion: SCHEMA_VERSION
        }
    };
    
    await saveState(newState);
    console.log(`[StateManager] Initialized new state at ${stateDir}`);
    
    return newState;
}

/**
 * Load the project state from disk.
 */
export async function loadState(): Promise<ProjectState | null> {
    try {
        const workspaceRoot = getWorkspaceRoot();
        const statePath = getStateFilePath(workspaceRoot);
        
        const content = await fs.readFile(statePath, 'utf-8');
        const state = JSON.parse(content) as ProjectState;
        
        // Validate schema version
        if (state.metadata?.schemaVersion !== SCHEMA_VERSION) {
            console.warn('[StateManager] Schema version mismatch, migrating...');
            // Future: add migration logic here
        }
        
        console.log(`[StateManager] Loaded state from ${statePath}`);
        return state;
        
    } catch (error) {
        if ((error as NodeJS.ErrnoException).code === 'ENOENT') {
            console.log('[StateManager] No existing state found, initializing...');
            return initializeState();
        }
        throw error;
    }
}

/**
 * Save the project state to disk.
 */
export async function saveState(state: ProjectState): Promise<void> {
    const statePath = getStateFilePath(state.workspaceRoot);
    
    // Update timestamp
    state.metadata.updatedAt = new Date().toISOString();
    
    // Sync with current config
    const config = getIterationConfig();
    state.maxIterations = config.maxAutonomousIterations;
    state.permissionLevel = getPermissionLevel();
    
    await fs.writeFile(statePath, JSON.stringify(state, null, 2), 'utf-8');
    console.log(`[StateManager] Saved state to ${statePath}`);
}

// --- CHECKPOINT OPERATIONS ---

/**
 * Create a checkpoint before starting an operation.
 * This creates a state snapshot and optionally a backup.
 */
export async function createCheckpoint(
    state: ProjectState, 
    description: string
): Promise<CheckpointMetadata> {
    const checkpointId = generateCheckpointId();
    const config = getBackupConfig();
    
    const checkpoint: CheckpointMetadata = {
        id: checkpointId,
        createdAt: new Date().toISOString(),
        permissionLevel: state.permissionLevel,
        iteration: state.currentIteration,
        description
    };
    
    // Create backup if enabled
    const backupConfig = getBackupConfig();
    const iterConfig = getIterationConfig();
    
    if (backupConfig.enabled && iterConfig.checkpointOnStart) {
        const backupId = await createBackup(`Checkpoint: ${description}`);
        if (backupId) {
            state.lastBackup = backupId;
            console.log(`[StateManager] Created backup ${backupId} for checkpoint ${checkpointId}`);
        }
    }
    
    // Save checkpoint reference
    state.lastCheckpoint = checkpoint;
    await saveState(state);
    
    console.log(`[StateManager] Created checkpoint ${checkpointId}`);
    return checkpoint;
}

/**
 * Restore to the last checkpoint.
 */
export async function restoreCheckpoint(state: ProjectState): Promise<boolean> {
    const checkpoint = state.lastCheckpoint;
    const backupId = state.lastBackup;
    
    if (!backupId) {
        console.warn('[StateManager] No backup available to restore');
        return false;
    }
    
    // Restore from backup
    const success = await restoreBackup(backupId);
    
    if (success) {
        // Reset iteration counter
        if (checkpoint) {
            state.currentIteration = checkpoint.iteration;
            state.permissionLevel = checkpoint.permissionLevel;
        }
        
        // Clear checkpoint after restore
        state.lastCheckpoint = undefined;
        state.lastBackup = undefined;
        
        await saveState(state);
        console.log(`[StateManager] Restored to checkpoint ${checkpoint?.id}`);
    }
    
    return success;
}

// --- ITERATION MANAGEMENT ---

/**
 * Increment the iteration counter.
 * Returns true if under the limit, false if exceeded.
 */
export function incrementIteration(state: ProjectState): boolean {
    state.currentIteration++;
    
    if (state.currentIteration >= state.maxIterations) {
        console.warn(`[StateManager] Iteration limit reached (${state.maxIterations})`);
        return false;
    }
    
    console.log(`[StateManager] Iteration ${state.currentIteration}/${state.maxIterations}`);
    return true;
}

/**
 * Reset the iteration counter.
 */
export function resetIterations(state: ProjectState): void {
    state.currentIteration = 0;
    console.log('[StateManager] Iteration counter reset');
}

/**
 * Check if more iterations are allowed.
 */
export function canContinueIterating(state: ProjectState): boolean {
    return state.currentIteration < state.maxIterations;
}

// --- PERMISSION MANAGEMENT ---

/**
 * Check if an operation is allowed at the current permission level.
 */
export function checkPermission(
    state: ProjectState, 
    operation: 'modifyValue' | 'addComponent' | 'deleteComponent' | 'rewire'
): { allowed: boolean; message?: string } {
    const level = state.permissionLevel;
    
    const permissions: Record<PermissionLevel, Record<string, boolean>> = {
        'values': { 
            modifyValue: true, 
            addComponent: false, 
            deleteComponent: false, 
            rewire: false 
        },
        'add': { 
            modifyValue: true, 
            addComponent: true, 
            deleteComponent: false, 
            rewire: false 
        },
        'delete': { 
            modifyValue: true, 
            addComponent: true, 
            deleteComponent: true, 
            rewire: false 
        },
        'restructure': { 
            modifyValue: true, 
            addComponent: true, 
            deleteComponent: true, 
            rewire: true 
        }
    };
    
    const allowed = permissions[level][operation];
    
    if (!allowed) {
        const levelHierarchy: PermissionLevel[] = ['values', 'add', 'delete', 'restructure'];
        const requiredLevel = levelHierarchy.find(l => permissions[l][operation]);
        return {
            allowed: false,
            message: `Operation '${operation}' requires permission level '${requiredLevel}' (current: '${level}')`
        };
    }
    
    return { allowed: true };
}

/**
 * Update the permission level.
 */
export async function setPermissionLevel(
    state: ProjectState, 
    level: PermissionLevel
): Promise<void> {
    state.permissionLevel = level;
    await saveState(state);
    console.log(`[StateManager] Permission level set to '${level}'`);
}

// --- FILE TRACKING ---

/**
 * Scan workspace for KiCad, JSON, and Python files.
 */
export async function scanWorkspaceFiles(): Promise<FileRegistry> {
    const workspaceRoot = getWorkspaceRoot();
    const registry: FileRegistry = {};
    
    // Find all KiCad files
    const kicadFiles = await vscode.workspace.findFiles('**/*.kicad_sch', '**/node_modules/**');
    registry.kicad = kicadFiles.map(uri => uri.fsPath);
    
    // Find all JSON state files in .hephaistus
    const jsonFiles = await vscode.workspace.findFiles('**/.hephaistus/**/*.json', '**/node_modules/**');
    registry.json = jsonFiles.map(uri => uri.fsPath);
    
    // Find all Python files
    const pyFiles = await vscode.workspace.findFiles('**/*.py', '**/node_modules/**');
    registry.py = pyFiles.map(uri => uri.fsPath);
    
    console.log(`[StateManager] Found ${registry.kicad?.length || 0} KiCad, ${registry.json?.length || 0} JSON, ${registry.py?.length || 0} Python files`);
    
    return registry;
}

/**
 * Update file hashes in state.
 */
export async function updateFileHashes(
    state: ProjectState, 
    filePaths: string[]
): Promise<void> {
    for (const filePath of filePaths) {
        const hash = await generateFileHash(filePath);
        if (hash) {
            const relativePath = path.relative(state.workspaceRoot, filePath);
            state.stateHashes[relativePath] = {
                hash,
                lastModifiedTime: new Date().toISOString()
            };
        }
    }
    await saveState(state);
}

// --- STATE ANALYSIS ---

export interface StateAnalysis {
    issues: Array<{
        type: string;
        severity: 'error' | 'warning' | 'info';
        description: string;
        filePath: string;
    }>;
    needsIngestion: boolean;
    needsPythonUpdate: boolean;
    permissionWarnings: string[];
}

/**
 * Analyze the project state for issues.
 */
export function analyzeState(state: ProjectState): StateAnalysis {
    const issues: StateAnalysis['issues'] = [];
    let needsIngestion = false;
    let needsPythonUpdate = false;
    const permissionWarnings: string[] = [];
    
    // Check for missing JSON files
    for (const kicadPath of state.files.kicad || []) {
        const baseName = path.basename(kicadPath, '.kicad_sch');
        const jsonPath = path.join(state.workspaceRoot, STATE_DIR, `${baseName}.json`);
        
        if (!state.files.json?.includes(jsonPath)) {
            issues.push({
                type: 'MISSING_JSON',
                severity: 'warning',
                description: `No JSON state found for KiCad file: ${path.basename(kicadPath)}`,
                filePath: kicadPath
            });
            needsIngestion = true;
        }
    }
    
    // Check for stale hashes
    for (const [filePath, entry] of Object.entries(state.stateHashes)) {
        const currentHash = entry.hash;
        const expectedHash = entry.expectedKicadHash;
        
        if (expectedHash && currentHash !== expectedHash) {
            issues.push({
                type: 'HASH_MISMATCH',
                severity: 'error',
                description: `File changed since last sync: ${filePath}`,
                filePath
            });
            needsIngestion = true;
        }
    }
    
    // Check iteration limit
    if (state.currentIteration >= state.maxIterations) {
        issues.push({
            type: 'ITERATION_LIMIT',
            severity: 'warning',
            description: `Iteration limit reached (${state.maxIterations})`,
            filePath: state.workspaceRoot
        });
    }
    
    return {
        issues,
        needsIngestion,
        needsPythonUpdate,
        permissionWarnings
    };
}

// --- EXPORT DEFAULT ---

export default {
    initializeState,
    loadState,
    saveState,
    createCheckpoint,
    restoreCheckpoint,
    incrementIteration,
    resetIterations,
    canContinueIterating,
    checkPermission,
    setPermissionLevel,
    scanWorkspaceFiles,
    updateFileHashes,
    analyzeState
};