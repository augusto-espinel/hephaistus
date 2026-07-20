/**
 * Delta Apply Service
 * Applies JSON modifications back to KiCad schematic files.
 * This completes the round-trip: KiCad → JSON → (LLM modification) → JSON → KiCad
 */

import * as path from 'path';
import * as fs from 'fs';
import { spawn } from 'child_process';
import { WORKSPACE_ROOT } from '../utils';

export interface DeltaResult {
  success: boolean;
  changesApplied: number;
  delta: {
    valueChanges: Array<{ uuid: string; reference: string; oldValue: string; newValue: string }>;
    addedComponents: any[];
    removedComponents: any[];
    connectionChanges: any[];
  };
  backup: string;
  message: string;
}

export interface DeltaOptions {
  createBackup?: boolean;
  dryRun?: boolean;
}

/**
 * Compute the difference between original and modified JSON states.
 * Returns the delta object for inspection.
 */
export async function computeDelta(
  originalJsonPath: string,
  modifiedJsonPath: string
): Promise<{ valueChanges: any[]; addedComponents: any[]; removedComponents: any[]; connectionChanges: any[] }> {
  const original = JSON.parse(fs.readFileSync(originalJsonPath, 'utf8'));
  const modified = JSON.parse(fs.readFileSync(modifiedJsonPath, 'utf8'));

  const origComps = new Map<string, any>((original.components || []).map((c: any) => [c.uuid, c]));
  const modComps = new Map<string, any>((modified.components || []).map((c: any) => [c.uuid, c]));

  const valueChanges: any[] = [];
  const addedComponents: any[] = [];
  const removedComponents: any[] = [];
  const connectionChanges: any[] = [];

  // Find value changes and connection changes
  for (const [uuid, modComp] of modComps) {
    const origComp = origComps.get(uuid);
    if (origComp) {
      // Check for value change
      if ((origComp as any).value !== (modComp as any).value) {
        valueChanges.push({
          uuid,
          reference: (modComp as any).reference,
          oldValue: (origComp as any).value,
          newValue: (modComp as any).value
        });
      }

      // Check for connection changes
      const origPins = new Map<string, any>(((origComp as any).pins || []).map((p: any) => [p.number, p]));
      for (const modPin of ((modComp as any).pins || [])) {
        const origPin = origPins.get((modPin as any).number);
        if (origPin && (origPin as any).net !== (modPin as any).net) {
          connectionChanges.push({
            uuid,
            reference: (modComp as any).reference,
            pin: (modPin as any).number,
            oldNet: (origPin as any).net,
            newNet: (modPin as any).net
          });
        }
      }
    } else {
      // New component
      addedComponents.push(modComp);
    }
  }

  // Find removed components
  for (const [uuid, origComp] of origComps) {
    if (!modComps.has(uuid as string)) {
      removedComponents.push({
        uuid,
        reference: (origComp as any).reference
      });
    }
  }

  return { valueChanges, addedComponents, removedComponents, connectionChanges };
}

/**
 * Apply JSON delta back to KiCad schematic using Python script.
 */
export async function applyDeltaToKiCad(
  originalJsonPath: string,
  modifiedJsonPath: string,
  kicadFilePath: string,
  options: DeltaOptions = {}
): Promise<DeltaResult> {
  const workspaceRoot = process.env.HEPHAISTUS_WORKSPACE || WORKSPACE_ROOT;
  const scriptPath = path.join(workspaceRoot, 'scripts', 'wrappers', 'kiutils_delta_apply.py');

  // Check if script exists
  if (!fs.existsSync(scriptPath)) {
    return {
      success: false,
      changesApplied: 0,
      delta: { valueChanges: [], addedComponents: [], removedComponents: [], connectionChanges: [] },
      backup: '',
      message: `Delta apply script not found: ${scriptPath}`
    };
  }

  // Check if Python venv exists
  const venvPython = path.join(workspaceRoot, 'python', '.venv', 'bin', 'python');
  const python = fs.existsSync(venvPython) ? venvPython : 'python3';

  return new Promise((resolve) => {
    const args = [scriptPath, originalJsonPath, modifiedJsonPath, kicadFilePath];
    
    console.log(`[DeltaApply] Running: ${python} ${args.join(' ')}`);

    const proc = spawn(python, args, {
      cwd: workspaceRoot,
      env: { ...process.env, PYTHONPATH: path.join(workspaceRoot, 'python') }
    });

    let stdout = '';
    let stderr = '';

    proc.stdout.on('data', (data) => {
      stdout += data.toString();
    });

    proc.stderr.on('data', (data) => {
      stderr += data.toString();
    });

    proc.on('close', (code) => {
      if (stderr) {
        console.error('[DeltaApply] Stderr:', stderr);
      }

      try {
        const result = JSON.parse(stdout);
        
        if (result.status === 'success') {
          resolve({
            success: true,
            changesApplied: result.changes_applied || 0,
            delta: {
              valueChanges: result.delta?.value_changes || [],
              addedComponents: result.delta?.added_components || [],
              removedComponents: result.delta?.removed_components || [],
              connectionChanges: result.delta?.connection_changes || []
            },
            backup: result.backup || '',
            message: `Applied ${result.changes_applied || 0} change(s) to KiCad schematic`
          });
        } else if (result.status === 'no_changes') {
          resolve({
            success: true,
            changesApplied: 0,
            delta: { valueChanges: [], addedComponents: [], removedComponents: [], connectionChanges: [] },
            backup: '',
            message: 'No changes detected between original and modified JSON'
          });
        } else {
          resolve({
            success: false,
            changesApplied: 0,
            delta: { valueChanges: [], addedComponents: [], removedComponents: [], connectionChanges: [] },
            backup: '',
            message: result.message || 'Unknown error applying delta'
          });
        }
      } catch (parseError) {
        resolve({
          success: false,
          changesApplied: 0,
          delta: { valueChanges: [], addedComponents: [], removedComponents: [], connectionChanges: [] },
          backup: '',
          message: `Failed to parse delta apply output: ${(parseError as Error).message}\nStdout: ${stdout}\nStderr: ${stderr}`
        });
      }
    });

    proc.on('error', (err) => {
      resolve({
        success: false,
        changesApplied: 0,
        delta: { valueChanges: [], addedComponents: [], removedComponents: [], connectionChanges: [] },
        backup: '',
        message: `Failed to run delta apply: ${err.message}`
      });
    });
  });
}

/**
 * Find the original JSON file for a modified JSON path.
 * Convention: original is stored alongside modified, or in .hephaistus/backups/
 */
export function findOriginalJson(modifiedJsonPath: string): string | null {
  const dir = path.dirname(modifiedJsonPath);
  const base = path.basename(modifiedJsonPath, '.json');
  
  // Check for backup/original alongside
  const candidates = [
    path.join(dir, `${base}.original.json`),
    path.join(dir, `${base}.bak.json`),
    path.join(dir, '.hephaistus', 'backups', `${base}.json`),
    path.join(dir, '.hephaistus', `${base}.json`)
  ];

  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) {
      return candidate;
    }
  }

  return null;
}

/**
 * Detect if a JSON file is a state file that should trigger delta application.
 */
export function isStateJson(filePath: string): boolean {
  const fileName = path.basename(filePath);
  
  // Check if it's in .hephaistus directory
  const dir = path.dirname(filePath);
  if (dir.includes('.hephaistus')) {
    return true;
  }
  
  // Check for state.json naming
  if (fileName === 'state.json' || fileName.endsWith('.state.json')) {
    return true;
  }
  
  return false;
}

export default {
  computeDelta,
  applyDeltaToKiCad,
  findOriginalJson,
  isStateJson
};