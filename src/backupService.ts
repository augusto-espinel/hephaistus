/**
 * backupService.ts
 * Handles backup and restore operations for HephAIstus.
 * Creates snapshots before structural changes and allows reverting.
 */

import * as vscode from 'vscode';
import * as fs from 'fs/promises';
import * as path from 'path';
import { getBackupConfig } from './configService';

// --- TYPE DEFINITIONS ---

export interface BackupMetadata {
    id: string;
    timestamp: string;
    description: string;
    files: string[];
}

// --- CONSTANTS ---

const BACKUP_DIR = '.hephaistus/backups';
const METADATA_FILE = 'metadata.json';

// --- UTILITY FUNCTIONS ---

/**
 * Get the backup directory path for a given workspace.
 */
function getBackupDir(workspaceRoot: string): string {
    return path.join(workspaceRoot, BACKUP_DIR);
}

/**
 * Generate a unique backup ID based on timestamp.
 */
function generateBackupId(): string {
    const now = new Date();
    return now.toISOString().replace(/[:.]/g, '-');
}

/**
 * Get the workspace root path.
 */
function getWorkspaceRoot(): string | undefined {
    const workspaceFolders = vscode.workspace.workspaceFolders;
    if (!workspaceFolders || workspaceFolders.length === 0) {
        return undefined;
    }
    return workspaceFolders[0].uri.fsPath;
}

// --- BACKUP OPERATIONS ---

/**
 * Create a backup of the current project state.
 * @param description - Human-readable description of what's being backed up
 * @returns The backup ID if successful, undefined if failed
 */
export async function createBackup(description: string): Promise<string | undefined> {
    const config = getBackupConfig();
    if (!config.enabled) {
        console.log('[BackupService] Backups are disabled in configuration.');
        return undefined;
    }

    const workspaceRoot = getWorkspaceRoot();
    if (!workspaceRoot) {
        console.error('[BackupService] No workspace root found.');
        return undefined;
    }

    const backupDir = getBackupDir(workspaceRoot);
    const backupId = generateBackupId();
    const backupPath = path.join(backupDir, backupId);

    try {
        // Ensure backup directory exists
        await fs.mkdir(backupPath, { recursive: true });

        // Files to backup
        const filesToBackup = [
            { src: path.join(workspaceRoot, '.hephaistus', 'state.json'), dest: 'state.json' },
            { src: workspaceRoot, pattern: '*.kicad_sch', dest: 'schematics/' },
            { src: workspaceRoot, pattern: '*.json', dest: 'json/' },
            { src: workspaceRoot, pattern: '*.py', dest: 'python/' }
        ];

        const backedUpFiles: string[] = [];

        for (const fileSpec of filesToBackup) {
            try {
                const stat = await fs.stat(fileSpec.src);
                if (stat.isFile()) {
                    await fs.copyFile(fileSpec.src, path.join(backupPath, fileSpec.dest));
                    backedUpFiles.push(fileSpec.dest);
                }
            } catch {
                // File doesn't exist, skip
            }
        }

        // Save metadata
        const metadata: BackupMetadata = {
            id: backupId,
            timestamp: new Date().toISOString(),
            description,
            files: backedUpFiles
        };
        await fs.writeFile(path.join(backupPath, METADATA_FILE), JSON.stringify(metadata, null, 2));

        // Clean up old backups if exceeding maxBackups
        await cleanupOldBackups(workspaceRoot, config.maxBackups);

        console.log(`[BackupService] Created backup: ${backupId}`);
        return backupId;

    } catch (error) {
        console.error('[BackupService] Failed to create backup:', error);
        return undefined;
    }
}

/**
 * Restore from a backup.
 * @param backupId - The backup ID to restore from
 * @returns True if successful, false otherwise
 */
export async function restoreBackup(backupId: string): Promise<boolean> {
    const workspaceRoot = getWorkspaceRoot();
    if (!workspaceRoot) {
        console.error('[BackupService] No workspace root found.');
        return false;
    }

    const backupDir = getBackupDir(workspaceRoot);
    const backupPath = path.join(backupDir, backupId);
    const metadataPath = path.join(backupPath, METADATA_FILE);

    try {
        // Read metadata
        const metadataRaw = await fs.readFile(metadataPath, 'utf-8');
        const metadata: BackupMetadata = JSON.parse(metadataRaw);

        // Restore files
        for (const file of metadata.files) {
            const srcPath = path.join(backupPath, file);
            const destPath = path.join(workspaceRoot, file);

            try {
                await fs.copyFile(srcPath, destPath);
                console.log(`[BackupService] Restored: ${file}`);
            } catch (error) {
                console.warn(`[BackupService] Failed to restore ${file}:`, error);
            }
        }

        console.log(`[BackupService] Restored from backup: ${backupId}`);
        return true;

    } catch (error) {
        console.error('[BackupService] Failed to restore backup:', error);
        return false;
    }
}

/**
 * List all available backups.
 * @returns Array of backup metadata
 */
export async function listBackups(): Promise<BackupMetadata[]> {
    const workspaceRoot = getWorkspaceRoot();
    if (!workspaceRoot) {
        return [];
    }

    const backupDir = getBackupDir(workspaceRoot);
    const backups: BackupMetadata[] = [];

    try {
        const entries = await fs.readdir(backupDir, { withFileTypes: true });

        for (const entry of entries) {
            if (!entry.isDirectory()) continue;

            const metadataPath = path.join(backupDir, entry.name, METADATA_FILE);
            try {
                const metadataRaw = await fs.readFile(metadataPath, 'utf-8');
                const metadata: BackupMetadata = JSON.parse(metadataRaw);
                backups.push(metadata);
            } catch {
                // Invalid backup, skip
            }
        }

        // Sort by timestamp, newest first
        backups.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());

    } catch (error) {
        // Backup directory doesn't exist yet
    }

    return backups;
}

/**
 * Delete a backup.
 * @param backupId - The backup ID to delete
 */
export async function deleteBackup(backupId: string): Promise<void> {
    const workspaceRoot = getWorkspaceRoot();
    if (!workspaceRoot) {
        return;
    }

    const backupDir = getBackupDir(workspaceRoot);
    const backupPath = path.join(backupDir, backupId);

    try {
        await fs.rm(backupPath, { recursive: true });
        console.log(`[BackupService] Deleted backup: ${backupId}`);
    } catch (error) {
        console.error(`[BackupService] Failed to delete backup ${backupId}:`, error);
    }
}

/**
 * Clean up old backups to stay within maxBackups limit.
 */
async function cleanupOldBackups(workspaceRoot: string, maxBackups: number): Promise<void> {
    const backups = await listBackups();

    if (backups.length <= maxBackups) {
        return;
    }

    // Delete oldest backups
    const toDelete = backups.slice(maxBackups);
    for (const backup of toDelete) {
        await deleteBackup(backup.id);
    }
}

// --- VS CODE COMMAND REGISTRATION ---

/**
 * Register backup-related commands with VS Code.
 */
export function registerBackupCommands(context: vscode.ExtensionContext): void {
    // Create Backup command
    context.subscriptions.push(
        vscode.commands.registerCommand('hephaistus.createBackup', async () => {
            const description = await vscode.window.showInputBox({
                prompt: 'Enter a description for this backup',
                placeHolder: 'e.g., Before optimization session'
            });

            if (!description) {
                vscode.window.showWarningMessage('Backup cancelled: No description provided.');
                return;
            }

            const backupId = await createBackup(description);
            if (backupId) {
                vscode.window.showInformationMessage(`Backup created: ${backupId}`);
            } else {
                vscode.window.showErrorMessage('Failed to create backup.');
            }
        })
    );

    // Restore Backup command
    context.subscriptions.push(
        vscode.commands.registerCommand('hephaistus.restoreBackup', async () => {
            const backups = await listBackups();

            if (backups.length === 0) {
                vscode.window.showWarningMessage('No backups available.');
                return;
            }

            const items = backups.map(b => ({
                label: `${b.timestamp.split('T')[0]} ${b.timestamp.split('T')[1].split('.')[0]}`,
                description: b.description,
                backup: b
            }));

            const selected = await vscode.window.showQuickPick(items, {
                placeHolder: 'Select a backup to restore'
            });

            if (!selected) {
                return;
            }

            const confirm = await vscode.window.showWarningMessage(
                `Restore from ${selected.label}? This will overwrite current files.`,
                { modal: true },
                'Restore',
                'Cancel'
            );

            if (confirm === 'Restore') {
                const success = await restoreBackup(selected.backup.id);
                if (success) {
                    vscode.window.showInformationMessage('Backup restored successfully.');
                } else {
                    vscode.window.showErrorMessage('Failed to restore backup.');
                }
            }
        })
    );

    // List Backups command
    context.subscriptions.push(
        vscode.commands.registerCommand('hephaistus.listBackups', async () => {
            const backups = await listBackups();

            if (backups.length === 0) {
                vscode.window.showInformationMessage('No backups found.');
                return;
            }

            const items = backups.map(b => ({
                label: `${b.timestamp.split('T')[0]} ${b.timestamp.split('T')[1].split('.')[0]}`,
                description: b.description
            }));

            await vscode.window.showQuickPick(items, {
                placeHolder: `Found ${backups.length} backup(s)`
            });
        })
    );
}

export default {
    createBackup,
    restoreBackup,
    listBackups,
    deleteBackup,
    registerBackupCommands
};