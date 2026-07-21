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
import { applyDeltaToKiCad, computeDelta } from '../services/deltaApplyService';

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

  async refreshAsync(): Promise<void> {
    await this.updateStatus();
    this._onDidChangeTreeData.fire(undefined);
  }

  getStatus(): SyncStatus | null {
    return this.status;
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
        console.log('[SyncPanel] updateStatus: No state, status = null');
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
        console.log('[SyncPanel] updateStatus: No KiCad files, direction = unknown');
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

      // Determine direction based on sync state and timestamps
      let direction: SyncStatus['direction'] = 'unknown';
      
      console.log('[SyncPanel] updateStatus: lastSync =', this.state.lastSync, 'kicadMtime =', kicadMtime, 'jsonMtime =', jsonMtime);
      
      if (this.state.lastSync) {
        // We have a previous sync - compare against it
        const syncTime = new Date(this.state.lastSync.timestamp).getTime();
        const syncSource = this.state.lastSync.source;
        const kicadTime = kicadMtime?.getTime() || 0;
        const jsonTime = jsonMtime?.getTime() || 0;
        
        // Allow 2 second tolerance for file system timing
        const tolerance = 2000;
        
        console.log('[SyncPanel] updateStatus: syncSource =', syncSource, 'syncTime =', syncTime, 'kicadTime =', kicadTime, 'jsonTime =', jsonTime, 'tolerance =', tolerance);
        console.log('[SyncPanel] updateStatus: kicadTime > syncTime + tolerance =', kicadTime > syncTime + tolerance, 'jsonTime > syncTime + tolerance =', jsonTime > syncTime + tolerance);
        
        if (syncSource === 'kicad') {
          // Last sync was from KiCad → JSON
          // JSON being newer is expected and means synced
          // Unless KiCad was modified after sync
          if (kicadTime > syncTime + tolerance) {
            direction = 'kicad-to-json';
            console.log('[SyncPanel] updateStatus: direction = kicad-to-json (KiCad modified after sync)');
          } else if (jsonTime > syncTime + tolerance) {
            // JSON was modified after sync
            direction = 'json-to-kicad';
            console.log('[SyncPanel] updateStatus: direction = json-to-kicad (JSON modified after sync)');
          } else {
            direction = 'synced';
            console.log('[SyncPanel] updateStatus: direction = synced');
          }
        } else if (syncSource === 'json') {
          // Last sync was from JSON → KiCad
          // KiCad being newer is expected and means synced
          // Unless JSON was modified after sync
          if (jsonTime > syncTime + tolerance) {
            direction = 'json-to-kicad';
            console.log('[SyncPanel] updateStatus: direction = json-to-kicad (JSON modified after sync)');
          } else if (kicadTime > syncTime + tolerance) {
            // KiCad was modified after sync
            direction = 'kicad-to-json';
            console.log('[SyncPanel] updateStatus: direction = kicad-to-json (KiCad modified after sync)');
          } else {
            direction = 'synced';
            console.log('[SyncPanel] updateStatus: direction = synced');
          }
        }
      } else {
        // No previous sync - use simple timestamp comparison
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

    // Determine recommended action based on status
    const isParseRecommended = this.status?.direction === 'kicad-to-json';
    const isApplyRecommended = this.status?.direction === 'json-to-kicad';

    // Parse KiCad → JSON button - add indicator if recommended
    const parseLabel = isParseRecommended 
      ? '→ 🔄 Parse KiCad → JSON (recommended)'
      : '🔄 Parse KiCad → JSON';
    const parseDesc = isParseRecommended
      ? 'KiCad has newer changes - click to update JSON'
      : 'Parse schematic and update JSON state';
    
    items.push(new SyncItem(
      parseLabel,
      parseDesc,
      vscode.TreeItemCollapsibleState.None,
      'action-parse-kicad',
      {
        command: 'hephaistus.parseKicad',
        title: 'Parse KiCad'
      }
    ));

    // Apply JSON → KiCad button - add indicator if recommended
    const applyLabel = isApplyRecommended
      ? '→ ✏️ Apply JSON → KiCad (recommended)'
      : '✏️ Apply JSON → KiCad';
    const applyDesc = isApplyRecommended
      ? 'JSON has newer changes - click to update KiCad'
      : 'Apply JSON changes to KiCad schematic';
    
    items.push(new SyncItem(
      applyLabel,
      applyDesc,
      vscode.TreeItemCollapsibleState.None,
      'action-apply-delta',
      {
        command: 'hephaistus.applyDelta',
        title: 'Apply Delta'
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
      // Refresh status first to get current file times
      await provider.refreshAsync();
      
      // Check sync status and warn if JSON has newer changes
      const status = provider.getStatus();
      console.log('[ParseKicad] Status:', status?.direction, 'kicadLastModified:', status?.kicadLastModified, 'jsonLastModified:', status?.jsonLastModified);
      
      if (status && status.direction === 'json-to-kicad') {
        console.log('[ParseKicad] JSON is newer, showing warning...');
        const confirm = await vscode.window.showWarningMessage(
          'JSON has newer changes that have not been applied to KiCad.\nParsing now will overwrite those changes. Continue?',
          { modal: true },
          'Overwrite JSON',
          'Cancel'
        );
        console.log('[ParseKicad] User chose:', confirm);
        if (confirm !== 'Overwrite JSON') {
          return;
        }
      }
      
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
      try {
        // Refresh status first to get current file times
        await provider.refreshAsync();
        
        // Check sync status and warn if KiCad has newer changes
        const status = provider.getStatus();
        console.log('[ApplyDelta] Status:', status?.direction, 'kicadLastModified:', status?.kicadLastModified, 'jsonLastModified:', status?.jsonLastModified);
        
        if (status && status.direction === 'kicad-to-json') {
          console.log('[ApplyDelta] KiCad is newer, showing warning...');
          const confirm = await vscode.window.showWarningMessage(
            'KiCad has newer changes that have not been parsed to JSON.\nApplying now will overwrite those changes. Continue?',
            { modal: true },
            'Overwrite KiCad',
            'Cancel'
          );
          console.log('[ApplyDelta] User chose:', confirm);
          if (confirm !== 'Overwrite KiCad') {
            return;
          }
        }
        
        // Load current state to find the JSON file
        const state = await loadState();
        if (!state) {
          vscode.window.showErrorMessage('HephAIstus: No state found. Start a session first.');
          return;
        }

        const workspaceRoot = state.workspaceRoot || process.cwd();
        const jsonFiles = state.files?.json || [];
        
        // Filter to find the main JSON file (not backup files)
        const mainJsonFiles = jsonFiles.filter((f: string) => !f.includes('_backup'));
        
        if (mainJsonFiles.length === 0) {
          vscode.window.showErrorMessage('HephAIstus: No JSON state file found. Parse a KiCad file first.');
          return;
        }

        // Use the first main JSON file
        const jsonFile = mainJsonFiles[0];
        const jsonPath = path.isAbsolute(jsonFile) ? jsonFile : path.join(workspaceRoot, '.hephaistus', jsonFile);
        
        // Check if baseline exists (created during parsing)
        const baselinePath = jsonPath.replace('.json', '.original.json');
        if (!fs.existsSync(baselinePath)) {
          vscode.window.showWarningMessage(
            'HephAIstus: No baseline file found. Please "Parse KiCad → JSON" first to create a baseline.'
          );
          return;
        }

        // Find corresponding KiCad file
        const baseName = path.basename(jsonFile, '.json');
        const kicadFiles = state.files?.kicad || [];
        let kicadFile: string | undefined;
        
        for (const kf of kicadFiles) {
          if (kf.replace('.kicad_sch', '') === baseName || kf.includes(baseName)) {
            kicadFile = path.isAbsolute(kf) ? kf : path.join(workspaceRoot, kf);
            break;
          }
        }
        
        if (!kicadFile) {
          // Try default location
          kicadFile = path.join(workspaceRoot, `${baseName}.kicad_sch`);
          if (!fs.existsSync(kicadFile)) {
            kicadFile = path.join(workspaceRoot, 'tests', 'user', `${baseName}.kicad_sch`);
          }
        }
        
        if (!kicadFile || !fs.existsSync(kicadFile)) {
          vscode.window.showErrorMessage(`HephAIstus: Cannot find KiCad file for ${baseName}`);
          return;
        }

        // Compute delta
        const delta = await computeDelta(baselinePath, jsonPath);
        const totalChanges = delta.valueChanges.length + 
                            delta.addedComponents.length + 
                            delta.removedComponents.length + 
                            delta.connectionChanges.length;
        
        if (totalChanges === 0) {
          // No JSON changes - check if KiCad has unsaved changes
          if (status && status.direction === 'kicad-to-json') {
            // KiCad is newer but JSON unchanged - offer to discard KiCad changes
            const discardConfirm = await vscode.window.showWarningMessage(
              'JSON has no changes to apply, but KiCad has unsaved changes.\n\nDiscard KiCad changes and restore from JSON?',
              { modal: true },
              'Discard KiCad changes',
              'Cancel'
            );
            if (discardConfirm !== 'Discard KiCad changes') {
              return;
            }
            
            // Re-apply JSON to KiCad (effectively discarding KiCad changes)
            vscode.window.setStatusBarMessage('$(sync~spin) HephAIstus: Restoring KiCad from JSON...', 5000);
            
            const result = await applyDeltaToKiCad(baselinePath, jsonPath, kicadFile);
            
            if (result.success) {
              // Update lastSync to mark as synced from JSON
              try {
                const state = await loadState();
                if (state) {
                  const kicadFileName = path.basename(kicadFile);
                  const kicadHash = state.stateHashes[kicadFileName]?.hash || 
                                      state.stateHashes[kicadFile]?.hash;
                  state.lastSync = {
                    source: 'json',
                    timestamp: new Date().toISOString(),
                    kicadHash
                  };
                  await saveState(state);
                }
              } catch (e) {
                console.error('[ApplyDelta] Failed to update lastSync:', e);
              }
              
              vscode.window.showInformationMessage(
                'HephAIstus: KiCad restored from JSON. Unsaved KiCad changes discarded.'
              );
              provider.refresh();
            } else {
              vscode.window.showErrorMessage(`HephAIstus: Failed to restore KiCad - ${result.message}`);
            }
            return;
          } else {
            vscode.window.showInformationMessage('HephAIstus: No changes detected. Edit the JSON file first, save it, then click Apply.');
            return;
          }
        }

        // Show confirmation with change summary
        const changeSummary = [];
        if (delta.valueChanges.length > 0) changeSummary.push(`${delta.valueChanges.length} value(s)`);
        if (delta.addedComponents.length > 0) changeSummary.push(`${delta.addedComponents.length} added`);
        if (delta.removedComponents.length > 0) changeSummary.push(`${delta.removedComponents.length} removed`);
        if (delta.connectionChanges.length > 0) changeSummary.push(`${delta.connectionChanges.length} connection(s)`);
        
        const confirm = await vscode.window.showInformationMessage(
          `Apply ${totalChanges} change(s) to ${path.basename(kicadFile)}?\n${changeSummary.join(', ')}`,
          { modal: true },
          'Apply',
          'Cancel'
        );
        
        if (confirm !== 'Apply') {
          return;
        }

        // Apply delta to KiCad
        vscode.window.setStatusBarMessage('$(sync~spin) HephAIstus: Applying changes...', 5000);
        
        const result = await applyDeltaToKiCad(baselinePath, jsonPath, kicadFile);
        
        if (result.success) {
          vscode.window.showInformationMessage(
            `HephAIstus: Applied ${result.changesApplied} change(s) to ${path.basename(kicadFile)}`
          );
          
          // Update baseline to reflect new state
          try {
            const jsonContent = fs.readFileSync(jsonPath, 'utf-8');
            fs.writeFileSync(baselinePath, jsonContent, 'utf-8');
            console.log('[ApplyDelta] Updated baseline to new state');
          } catch (e) {
            console.error('[ApplyDelta] Failed to update baseline:', e);
          }
          
          // Update lastSync state to mark that we synced from JSON → KiCad
          try {
            const state = await loadState();
            if (state) {
              // Find the relative path for the kicad file in stateHashes
              const kicadFileName = path.basename(kicadFile);
              const kicadHash = state.stateHashes[kicadFileName]?.hash || 
                                state.stateHashes[kicadFile]?.hash;
              state.lastSync = {
                source: 'json',
                timestamp: new Date().toISOString(),
                kicadHash
              };
              await saveState(state);
              console.log('[ApplyDelta] Updated lastSync state');
            }
          } catch (e) {
            console.error('[ApplyDelta] Failed to update lastSync:', e);
          }
          
          provider.refresh();
        } else {
          vscode.window.showErrorMessage(`HephAIstus: Failed to apply changes - ${result.message}`);
        }
      } catch (error) {
        vscode.window.showErrorMessage(`HephAIstus: Error - ${(error as Error).message}`);
      }
    }),

    vscode.commands.registerCommand('hephaistus.refreshSyncPanel', () => {
      provider.refresh();
    }),

    treeView
  );

  return provider;
}