/**
 * fileWatcherService.ts
 * Manages filesystem watching to react asynchronously to user edits in the project folder.
 */

import * as vscode from 'vscode';
import * as path from 'path';
import { generateFileHash, calculateSemanticKicadHash } from './hephaistusService';

/** File extension constants */
const KICAD_EXT = '.kicad_sch';
const JSON_EXT = '.json';
const PY_EXT = '.py';

/** @type {vscode.FileSystemWatcher} */
let watcher: vscode.FileSystemWatcher | undefined;

/**
 * Sets up and manages the file system watcher for the HephAIstus project directory.
 * This must be called during extension activation.
 * @param {string} rootPath - The workspace folder URI to watch.
 * @returns {vscode.Disposable} A disposable object that can clean up the watcher when deactivated.
 */
export function startFileWatcher(rootPath: string): vscode.Disposable {
    if (watcher) {
        console.warn("File watcher is already active.");
        return new vscode.Disposable(() => {});
    }

    // Create a glob pattern for the files we want to watch
    const pattern = new vscode.RelativePattern(rootPath, '**/*{.kicad_sch,.json,.py}');

    watcher = vscode.workspace.createFileSystemWatcher(pattern);

    // Attach event listeners to handle changes asynchronously
    watcher.onDidChange(uri => {
        if (uri.fsPath.startsWith(rootPath)) {
            console.log(`[FileWatcher] Change detected on: ${path.basename(uri.fsPath)}. Re-analyzing state...`);
            // In a full implementation, this would trigger a context update event
            // passed to the main Activity/Panel owner service.
        }
    });

    watcher.onDidCreate(uri => {
        if (uri.fsPath.startsWith(rootPath)) {
            console.log(`[FileWatcher] File created: ${path.basename(uri.fsPath)}. State update required.`);
        }
    });

    watcher.onDidDelete(uri => {
        if (uri.fsPath.startsWith(rootPath)) {
            console.log(`[FileWatcher] File deleted: ${path.basename(uri.fsPath)}. State update required.`);
        }
    });

    // Also listen for save events on text documents
    vscode.workspace.onDidSaveTextDocument((document: vscode.TextDocument) => {
        const uri = document.uri;
        if (uri.fsPath.startsWith(rootPath)) {
            console.log(`[FileWatcher] File saved: ${path.basename(uri.fsPath)}. State update required.`);
            // Trigger state re-hashing logic here using 'hephaistusService' functions
            handleFileSave(uri.fsPath);
        }
    });

    console.info("[FileWatcher] Successfully attached watchers to key file types.");

    return new vscode.Disposable(() => {
        if (watcher) {
            watcher.dispose();
            watcher = undefined;
        }
        console.log("[FileWatcher] Watchers disposed successfully.");
    });
}

/**
 * Placeholder function to re-hash a specific file after a save event.
 * @param {string} filePath - Absolute path of the saved file.
 */
export async function handleFileSave(filePath: string): Promise<void> {
    const ext = path.extname(filePath);
    let hash: string | null = null;

    if (ext === KICAD_EXT) {
        hash = await calculateSemanticKicadHash(filePath);
    } else if (ext === JSON_EXT) {
        hash = await generateFileHash(filePath);
    } else if (ext === PY_EXT) {
        hash = await generateFileHash(filePath);
    }

    if (hash) {
        console.log(`[FileWatcher] Re-hashed ${path.basename(filePath)}: ${hash.substring(0, 8)}...`);
        // Logic to update the in-memory ProjectState with the new hash goes here.
    }
}