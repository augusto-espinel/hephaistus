/**
 * Delta Apply Service
 * Applies JSON modifications back to KiCad schematic files.
 * This completes the round-trip: KiCad → JSON → (LLM modification) → JSON → KiCad
 */

import * as path from 'path';
import * as fs from 'fs';
import { spawn } from 'child_process';

/**
 * Find the HephAIstus project root by looking for package.json
 * Uses multiple strategies: extension directory, process.cwd(), parent directories
 */
function findHephaistusRoot(): string | null {
  // Strategy 1: Use __dirname (extension's compiled location)
  // This file is at dist/services/deltaApplyService.js, so go up to project root
  try {
    const adapterDir = __dirname;
    const servicesDir = path.dirname(adapterDir);
    const srcDir = path.dirname(servicesDir);
    const projectRoot = path.dirname(srcDir);
    
    // Check for package.json
    const packageJsonPath = path.join(projectRoot, 'package.json');
    if (fs.existsSync(packageJsonPath)) {
      try {
        const content = JSON.parse(fs.readFileSync(packageJsonPath, 'utf8'));
        if (content.name === 'hephaistus' || content.name?.includes('hephaistus')) {
          return projectRoot;
        }
      } catch { /* ignore */ }
    }
  } catch { /* ignore */ }
  
  // Strategy 2: Walk up from cwd
  let dir = process.cwd();
  const maxDepth = 10;
  
  for (let i = 0; i < maxDepth; i++) {
    const packageJson = path.join(dir, 'package.json');
    if (fs.existsSync(packageJson)) {
      try {
        const content = JSON.parse(fs.readFileSync(packageJson, 'utf8'));
        if (content.name === 'hephaistus' || content.name?.includes('hephaistus')) {
          return dir;
        }
      } catch { /* ignore */ }
    }
    const parent = path.dirname(dir);
    if (parent === dir) break; // reached root
    dir = parent;
  }
  
  // Strategy 3: Check common locations
  const commonLocations = [
    '/Users/aespinel/.openclaw/workspace/hephaistus',
    path.join(process.cwd(), '..', '..'),
    path.join(process.cwd(), '..'),
  ];
  
  for (const loc of commonLocations) {
    const packageJson = path.join(loc, 'package.json');
    if (fs.existsSync(packageJson)) {
      try {
        const content = JSON.parse(fs.readFileSync(packageJson, 'utf8'));
        if (content.name === 'hephaistus' || content.name?.includes('hephaistus')) {
          return loc;
        }
      } catch { /* ignore */ }
    }
  }
  
  return null;
}

export interface DeltaWarning {
  type: 'series_insertion' | 'missing_labels' | 'manual_action';
  component: string;
  net?: string;
  nets?: string[];
  message: string;
  action_required: string;
}

export interface DeltaResult {
  success: boolean;
  changesApplied: number;
  changes?: string[];
  warnings: DeltaWarning[];
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
      // Check for value change (properties.Value)
      const origValue = (origComp as any).properties?.Value ?? (origComp as any).value ?? '';
      const modValue = (modComp as any).properties?.Value ?? (modComp as any).value ?? '';
      
      if (origValue !== modValue) {
        valueChanges.push({
          uuid,
          reference: (modComp as any).reference,
          oldValue: origValue,
          newValue: modValue
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
  // Find the HephAIstus project root using the same strategy as kicadKiutilsAdapter
  const hephaistusRoot = findHephaistusRoot();
  const workspaceRoot = process.env.HEPHAISTUS_WORKSPACE || hephaistusRoot || process.cwd();
  const scriptPath = path.join(workspaceRoot, 'scripts', 'wrappers', 'kiutils_delta_apply.py');

  // Check if script exists
  if (!fs.existsSync(scriptPath)) {
    return {
      success: false,
      changesApplied: 0,
      changes: [],
      warnings: [],
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
            changes: result.changes || [],
            warnings: result.warnings || [],
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
            changes: [],
            warnings: [],
            delta: { valueChanges: [], addedComponents: [], removedComponents: [], connectionChanges: [] },
            backup: '',
            message: 'No changes detected between original and modified JSON'
          });
        } else {
          resolve({
            success: false,
            changesApplied: 0,
            changes: [],
            warnings: [],
            delta: { valueChanges: [], addedComponents: [], removedComponents: [], connectionChanges: [] },
            backup: '',
            message: result.message || 'Unknown error applying delta'
          });
        }
      } catch (parseError) {
        resolve({
          success: false,
          changesApplied: 0,
          changes: [],
          warnings: [],
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
        changes: [],
        warnings: [],
        delta: { valueChanges: [], addedComponents: [], removedComponents: [], connectionChanges: [] },
        backup: '',
        message: `Failed to run delta apply: ${err.message}`
      });
    });
  });
}

/**
 * Find the original JSON file for a modified JSON path.
 * Convention: original is stored as .original.json suffix
 * Note: We use .original.json to avoid collision with {name}_backup.json 
 *       which could be the JSON for {name}_backup.kicad_sch
 */
export function findOriginalJson(modifiedJsonPath: string): string | null {
  const dir = path.dirname(modifiedJsonPath);
  const base = path.basename(modifiedJsonPath, '.json');
  
  // Primary: .original.json baseline (created during Parse KiCad → JSON)
  const baselinePath = path.join(dir, `${base}.original.json`);
  if (fs.existsSync(baselinePath)) {
    return baselinePath;
  }
  
  // Legacy fallback: check for old naming conventions
  const candidates = [
    path.join(dir, `${base}.original.json`),
    path.join(dir, `${base}.bak.json`),
    path.join(dir, `${base}_backup.json`),  // Legacy (may collide with actual schematic JSON)
    path.join(dir, '.hephaistus', 'backups', `${base}.json`),
    path.join(dir, '.hephaistus', `${base}.original.json`),
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