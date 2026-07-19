/**
 * configService.ts
 * Type-safe configuration management for HephAIstus.
 * Reads VS Code settings and provides default values.
 */

import * as vscode from 'vscode';

// --- TYPE DEFINITIONS ---

export type LlmProvider = 'ollama' | 'openrouter';
export type PermissionLevel = 'values' | 'add' | 'delete' | 'restructure';
export type UIMode = 'simple' | 'learning' | 'advanced';

export interface ModelConfig {
    provider: LlmProvider;
    model: string;
    endpoint?: string;
    apiKey?: string;
}

export interface IterationConfig {
    maxAutonomousIterations: number;
    checkpointOnStart: boolean;
    autoRevertOnAbort: boolean;
}

export interface BackupConfig {
    enabled: boolean;
    maxBackups: number;
}

export interface ReviewConfig {
    onSave: boolean;
    onRequest: boolean;
}

export interface ExecutionConfig {
    maxSteps: number;
    timeoutSeconds: number;
}

export interface HephaistusConfig {
    models: {
        sync: ModelConfig;
        optimization: ModelConfig;
    };
    permissions: {
        level: PermissionLevel;
    };
    iteration: IterationConfig;
    backup: BackupConfig;
    review: ReviewConfig;
    ui: {
        mode: UIMode;
    };
    execution: ExecutionConfig;
}

// --- DEFAULTS ---

const DEFAULT_CONFIG: HephaistusConfig = {
    models: {
        sync: {
            provider: 'ollama',
            model: 'llama3:8b',
            endpoint: 'http://localhost:11434'
        },
        optimization: {
            provider: 'openrouter',
            model: 'google/gemini-2.5-flash'
        }
    },
    permissions: {
        level: 'add'
    },
    iteration: {
        maxAutonomousIterations: 5,
        checkpointOnStart: true,
        autoRevertOnAbort: true
    },
    backup: {
        enabled: true,
        maxBackups: 10
    },
    review: {
        onSave: false,
        onRequest: true
    },
    ui: {
        mode: 'simple'
    },
    execution: {
        maxSteps: 100,
        timeoutSeconds: 60
    }
};

// --- CONFIG SERVICE ---

/**
 * Get the VS Code configuration for HephAIstus.
 */
function getConfig(): vscode.WorkspaceConfiguration {
    return vscode.workspace.getConfiguration('hephaistus');
}

/**
 * Read a configuration value with a default fallback.
 */
function getConfigValue<T>(key: string, defaultValue: T): T {
    const config = getConfig();
    return config.get<T>(key) ?? defaultValue;
}

/**
 * Get the complete HephAIstus configuration.
 * Merges VS Code settings with defaults.
 */
export function getHephaistusConfig(): HephaistusConfig {
    return {
        models: {
            sync: {
                provider: getConfigValue('models.sync.provider', DEFAULT_CONFIG.models.sync.provider),
                model: getConfigValue('models.sync.model', DEFAULT_CONFIG.models.sync.model),
                endpoint: getConfigValue('models.sync.endpoint', DEFAULT_CONFIG.models.sync.endpoint)
            },
            optimization: {
                provider: getConfigValue('models.optimization.provider', DEFAULT_CONFIG.models.optimization.provider),
                model: getConfigValue('models.optimization.model', DEFAULT_CONFIG.models.optimization.model),
                apiKey: getConfigValue('models.optimization.apiKey', '')
            }
        },
        permissions: {
            level: getConfigValue('permissions.level', DEFAULT_CONFIG.permissions.level)
        },
        iteration: {
            maxAutonomousIterations: getConfigValue('iteration.maxAutonomousIterations', DEFAULT_CONFIG.iteration.maxAutonomousIterations),
            checkpointOnStart: getConfigValue('iteration.checkpointOnStart', DEFAULT_CONFIG.iteration.checkpointOnStart),
            autoRevertOnAbort: getConfigValue('iteration.autoRevertOnAbort', DEFAULT_CONFIG.iteration.autoRevertOnAbort)
        },
        backup: {
            enabled: getConfigValue('backup.enabled', DEFAULT_CONFIG.backup.enabled),
            maxBackups: getConfigValue('backup.maxBackups', DEFAULT_CONFIG.backup.maxBackups)
        },
        review: {
            onSave: getConfigValue('review.onSave', DEFAULT_CONFIG.review.onSave),
            onRequest: getConfigValue('review.onRequest', DEFAULT_CONFIG.review.onRequest)
        },
        ui: {
            mode: getConfigValue('ui.mode', DEFAULT_CONFIG.ui.mode)
        },
        execution: {
            maxSteps: getConfigValue('execution.maxSteps', DEFAULT_CONFIG.execution.maxSteps),
            timeoutSeconds: getConfigValue('execution.timeoutSeconds', DEFAULT_CONFIG.execution.timeoutSeconds)
        }
    };
}

/**
 * Get the model configuration for a specific task type.
 * @param taskType - 'sync' for synchronization tasks, 'optimization' for optimization tasks
 */
export function getModelConfig(taskType: 'sync' | 'optimization'): ModelConfig {
    const config = getHephaistusConfig();
    return config.models[taskType];
}

/**
 * Get the current permission level.
 */
export function getPermissionLevel(): PermissionLevel {
    return getHephaistusConfig().permissions.level;
}

/**
 * Check if a specific operation is allowed at the current permission level.
 * @param operation - The operation to check
 */
export function isOperationAllowed(operation: 'modifyValue' | 'addComponent' | 'deleteComponent' | 'rewire'): boolean {
    const level = getPermissionLevel();
    const permissions: Record<PermissionLevel, Record<string, boolean>> = {
        'values': { modifyValue: true, addComponent: false, deleteComponent: false, rewire: false },
        'add': { modifyValue: true, addComponent: true, deleteComponent: false, rewire: false },
        'delete': { modifyValue: true, addComponent: true, deleteComponent: true, rewire: false },
        'restructure': { modifyValue: true, addComponent: true, deleteComponent: true, rewire: true }
    };
    return permissions[level][operation];
}

/**
 * Get the iteration configuration.
 */
export function getIterationConfig(): IterationConfig {
    return getHephaistusConfig().iteration;
}

/**
 * Get the backup configuration.
 */
export function getBackupConfig(): BackupConfig {
    return getHephaistusConfig().backup;
}

/**
 * Get the review configuration.
 */
export function getReviewConfig(): ReviewConfig {
    return getHephaistusConfig().review;
}

/**
 * Get the UI mode.
 */
export function getUIMode(): UIMode {
    return getHephaistusConfig().ui.mode;
}

/**
 * Get the execution configuration.
 */
export function getExecutionConfig(): ExecutionConfig {
    return getHephaistusConfig().execution;
}

// --- CONFIGURATION CHANGE LISTENER ---

let configChangeEmitter = new vscode.EventEmitter<HephaistusConfig>();

/**
 * Event that fires when configuration changes.
 */
export const onDidChangeConfig = configChangeEmitter.event;

/**
 * Register configuration change listener.
 * Call this during extension activation.
 */
export function registerConfigListener(context: vscode.ExtensionContext): void {
    context.subscriptions.push(
        vscode.workspace.onDidChangeConfiguration(e => {
            if (e.affectsConfiguration('hephaistus')) {
                const newConfig = getHephaistusConfig();
                configChangeEmitter.fire(newConfig);
                console.log('[ConfigService] Configuration changed:', JSON.stringify(newConfig, null, 2));
            }
        })
    );
}

export default {
    getHephaistusConfig,
    getModelConfig,
    getPermissionLevel,
    isOperationAllowed,
    getIterationConfig,
    getBackupConfig,
    getReviewConfig,
    getUIMode,
    getExecutionConfig,
    registerConfigListener,
    onDidChangeConfig
};