/**
 * Sync Panel Provider for HephAIstus
 * 
 * Provides a VS Code sidebar panel for user-controlled synchronization:
 * - Shows which direction needs syncing (KiCad → JSON or JSON → KiCad)
 * - Displays pending changes and modification times
 * - Manual trigger buttons for both directions
 * - Prevents parsing of incomplete work-in-progress schematics
 */

import * as vscode from 'vscode';
import * as path from 'path';
import * as fs from 'fs';
import { loadState, saveState, ProjectState } from '../stateManager';

interface SyncStatus {
  kicadFile: string;
  jsonFile: string;
  kicadLastModified: Date | null;
  jsonLastModified: Date | null;
  direction: 'kicad-to-json' | 'json-to-kicad' | 'synced' | 'unknown';
  pendingChanges: number;
  lastSyncTime: Date | null;
}

export class SyncPanelProvider implements vscode.TreeDataProvider<SyncItem> {
  private _onDidChangeTreeData: vscode.EventEmitter<SyncItem | undefined | null> = new vscode.EventEmitter<SyncItem | undefined | null>();
  readonly onDidChangeTreeData: vscode.Event<SyncItem | undefined | null> = this._onDidChangeTreeData.event;

  private status: SyncStatus | null = null;
  private state: ProjectState | null = null;

  constructor(private readonly extensionUri: vscode.Uri) {}

  refresh(): void {
    this._onDidChangeTreeData.fire(undefined);
  }

  getTreeItem(element: SyncItem): vscode.TreeItem {
    return element;
  }

  async getChildren(element?: SyncItem): Promise<SyncItem[]> {
    if (!element) {
      // Root level - show sync status and actions
      await this.updateStatus();
      return this.buildStatusItems();
    }
    return [];
  }

  private async updateStatus(): Promise<void> {
    try {
      this.state = await loadState();
      if (!this.state) {
        this.status = null;
        return;
      }

      const workspaceRoot = this.state.workspaceRoot || process.cwd();
      
      // Find KiCad and JSON files
      const kicadFiles = this.state.files?.kicad || [];
      const jsonFiles = this.state.files?.json || [];

      if (kicadFiles.length === 0) {
        this.status = {
          kicadFile: '',
          jsonFile: '',
          kicadLastModified: null,
          jsonLastModified: null,
          direction: 'unknown',
          pendingChanges: 0,
          lastSyncTime: null
        };
        return;
      }

      // Use first KiCad file for now (TODO: support multiple)
      const kicadFile = kicadFiles[0];
      const kicadPath = path.isAbsolute(kicadFile) ? kicadFile : path.join(workspaceRoot, kicadFile);
      const jsonFile = kicadFile.replace('.kicad_sch', '.json');
      const jsonPath = path.join(workspaceRoot, '.hephaistus', jsonFile);

      // Get modification times
      let kicadMtime: Date | null = null;
      let jsonMtime: Date | null = null;

      try {
        const kicadStat = fs.statSync(kicadPath);
        kicadMtime = kicadStat.mtime;
      } catch {}

      try {
        const jsonStat = fs.statSync(jsonPath);
        jsonMtime = jsonStat.mtime;
      } catch {}

      // Determine direction
      let direction: SyncStatus['direction'] = 'unknown';
      if (kicadMtime && jsonMtime) {
        if (kicadMtime > jsonMtime) {
          direction = 'kicad-to-json';
        } else if (jsonMtime > kicadMtime) {
          direction = 'json-to-kicad';
        } else {
          direction = 'synced';
        }
      } else if (kicadMtime && !jsonMtime) {
        direction = 'kicad-to-json';
      } else if (!kicadMtime && jsonMtime) {
        direction = 'json-to-kicad';
      }

      this.status = {
        kicadFile: path.basename(kicadFile),
        jsonFile: path.basename(jsonFile),
        kicadLastModified: kicadMtime,
        jsonLastModified: jsonMtime,
        direction,
        pendingChanges: 0, // TODO: compute delta count
        lastSyncTime: this.state.metadata?.updatedAt ? new Date(this.state.metadata.updatedAt) : null
      };
    } catch (error) {
      console.error('[SyncPanel] Error updating status:', error);
      this.status = null;
    }
  }

  private buildStatusItems(): SyncItem[] {
    const items: SyncItem[] = [];

    if (!this.status) {
      items.push(new SyncItem(
        '⚠️ No schematic tracked',
        'Open a KiCad schematic to begin',
        vscode.TreeItemCollapsibleState.None,
        'no-status'
      ));
      return items;
    }

    // Status header
    const statusIcon = this.getDirectionIcon(this.status.direction);
    const statusText = this.getDirectionText(this.status.direction);
    
    items.push(new SyncItem(
      `${statusIcon} ${statusText}`,
      this.status.kicadFile,
      vscode.TreeItemCollapsibleState.None,
      'status-header'
    ));

    // File info
    if (this.status.kicadLastModified) {
      items.push(new SyncItem(
        `📄 KiCad: ${this.formatTime(this.status.kicadLastModified)}`,
        this.status.kicadFile,
        vscode.TreeItemCollapsibleState.None,
        'kicad-info'
      ));
    }

    if (this.status.jsonLastModified) {
      items.push(new SyncItem(
        `📋 JSON: ${this.formatTime(this.status.jsonLastModified)}`,
        this.status.jsonFile,
        vscode.TreeItemCollapsibleState.None,
        'json-info'
      ));
    }

    // Action buttons
    items.push(new SyncItem(
      '─────────────',
      '',
      vscode.TreeItemCollapsibleState.None,
      'separator'
    ));

    // Parse KiCad → JSON button
    items.push(new SyncItem(
      '🔄 Parse KiCad → JSON',
      'Parse schematic and update JSON state',
      vscode.TreeItemCollapsibleState.None,
      'action-parse-kicad',
      {
        command: 'hephaistus.parseKicad',
        title: 'Parse KiCad'
      }
    ));

    // Apply JSON → KiCad button
    items.push(new SyncItem(
      '✏️ Apply JSON → KiCad',
      'Apply JSON changes to KiCad schematic',
      vscode.TreeItemCollapsibleState.None,
      'action-apply-delta',
      {
        command: 'hephaistus.applyDelta',
        title: 'Apply Delta'
      }
    ));

    // Sync both directions button
    items.push(new SyncItem(
      '⟳ Full Sync',
      'Parse KiCad, then apply any JSON changes',
      vscode.TreeItemCollapsibleState.None,
      'action-full-sync',
      {
        command: 'hephaistus.fullSync',
        title: 'Full Sync'
      }
    ));

    return items;
  }

  private getDirectionIcon(direction: SyncStatus['direction']): string {
    switch (direction) {
      case 'kicad-to-json':
        return '🔴'; // KiCad is newer
      case 'json-to-kicad':
        return '🔵'; // JSON is newer
      case 'synced':
        return '🟢'; // In sync
      default:
        return '⚪'; // Unknown
    }
  }

  private getDirectionText(direction: SyncStatus['direction']): string {
    switch (direction) {
      case 'kicad-to-json':
        return 'KiCad newer - Parse needed';
      case 'json-to-kicad':
        return 'JSON newer - Apply needed';
      case 'synced':
        return 'In sync';
      default:
        return 'Status unknown';
    }
  }

  private formatTime(date: Date): string {
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const minutes = Math.floor(diff / 60000);
    
    if (minutes < 1) return 'just now';
    if (minutes < 60) return `${minutes}m ago`;
    
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    
    return date.toLocaleDateString();
  }
}

class SyncItem extends vscode.TreeItem {
  constructor(
    public readonly label: string,
    public readonly description: string,
    public readonly collapsibleState: vscode.TreeItemCollapsibleState,
    public readonly contextValue: string,
    public readonly command?: vscode.Command
  ) {
    super(label, collapsibleState);
    this.description = description;
    this.tooltip = description;
    this.contextValue = contextValue;
    
    if (command) {
      this.command = command;
    }
  }
}

// Register the sync panel
export function registerSyncPanel(context: vscode.ExtensionContext): SyncPanelProvider {
  const provider = new SyncPanelProvider(context.extensionUri);
  
  const treeView = vscode.window.createTreeView('hephaistus-sync-panel', {
    treeDataProvider: provider,
    showCollapseAll: false
  });

  // Register commands
  context.subscriptions.push(
    vscode.commands.registerCommand('hephaistus.parseKicad', async () => {
      vscode.window.showInformationMessage('HephAIstus: Parsing KiCad schematic...');
      // Import and call the sync orchestrator
      const { runSyncCycle } = await import('../syncOrchestrator');
      const result = await runSyncCycle({ forceIngestion: true });
      if (result.status === 'ok') {
        vscode.window.showInformationMessage('HephAIstus: KiCad parsed successfully');
      } else {
        vscode.window.showErrorMessage(`HephAIstus: Parse failed - ${result.message}`);
      }
      provider.refresh();
    }),

    vscode.commands.registerCommand('hephaistus.applyDelta', async () => {
      vscode.window.showInformationMessage('HephAIstus: Applying JSON changes to KiCad...');
      // This will be triggered when user has manually edited JSON
      // The delta apply is handled by the file watcher when JSON changes
      vscode.window.showInformationMessage('HephAIstus: Save your JSON file to trigger delta application');
      provider.refresh();
    }),

    vscode.commands.registerCommand('hephaistus.fullSync', async () => {
      vscode.window.showInformationMessage('HephAIstus: Running full sync...');
      const { runSyncCycle } = await import('../syncOrchestrator');
      const result = await runSyncCycle({ forceIngestion: true, createCheckpoint: true });
      if (result.status === 'ok') {
        vscode.window.showInformationMessage('HephAIstus: Full sync completed');
      } else {
        vscode.window.showErrorMessage(`HephAIstus: Sync failed - ${result.message}`);
      }
      provider.refresh();
    }),

    vscode.commands.registerCommand('hephaistus.refreshSyncPanel', () => {
      provider.refresh();
    }),

    treeView
  );

  return provider;
}