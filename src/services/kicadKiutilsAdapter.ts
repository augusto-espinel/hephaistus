import * as fs from 'fs';
import * as path from 'path';
import { spawn } from 'child_process';

export async function parseKiCadWithKiUtils(
  filePath: string, 
  options?: { timeoutMs?: number; workspaceRoot?: string }
): Promise<string | null> {
  const backend = (process.env.KICAD_PARSER_BACKEND || 'kiutils').toLowerCase();
  if (backend === 'mock') {
    return null; // Explicitly disabled
  }

  // Find the HephAIstus project root (where package.json with 'hephaistus' name exists)
  // This is needed to locate the Python venv and wrapper script
  const hephaistusRoot = findHephaistusRoot();
  
  // VS Code workspace root (may be a subfolder like tests/user)
  const vscodeWorkspace = options?.workspaceRoot || process.env.WORKSPACE_ROOT || process.cwd();
  
  console.log(`[KiUtilsAdapter] HephAIstus root: ${hephaistusRoot || 'not found'}`);
  console.log(`[KiUtilsAdapter] VS Code workspace: ${vscodeWorkspace}`);

  // Try multiple possible Python locations - prefer HephAIstus project root
  const projectRoot = hephaistusRoot || vscodeWorkspace;
  
  const possiblePythonBins = [
    process.env.KIUTILS_PYTHON_BIN,
    path.join(projectRoot, 'python', '.venv', 'bin', 'python'),
    path.join(projectRoot, 'python', '.venv', 'Scripts', 'python.exe'),
    path.join(projectRoot, '.venv', 'bin', 'python'),
    '/usr/bin/python3',
    '/usr/local/bin/python3',
  ].filter(Boolean) as string[];
  
  let pythonBin: string | null = null;
  for (const candidate of possiblePythonBins) {
    if (candidate && fs.existsSync(candidate)) {
      pythonBin = candidate;
      break;
    }
  }
  
  // If not found, try system python
  if (!pythonBin) {
    try {
      const whichResult = require('child_process').execSync(
        process.platform === 'win32' ? 'where python' : 'which python3',
        { encoding: 'utf8', stdio: ['pipe', 'pipe', 'pipe'] }
      ).trim().split('\n')[0];
      if (whichResult && fs.existsSync(whichResult)) {
        pythonBin = whichResult;
      }
    } catch { /* ignore */ }
  }
  
  // Try multiple possible wrapper locations - always use HephAIstus project root
  const possibleWrapperPaths = [
    process.env.KIUTILS_WRAPPER_PATH,
    hephaistusRoot ? path.join(hephaistusRoot, 'scripts', 'wrappers', 'kiutils_parser_wrapper.py') : null,
    hephaistusRoot ? path.join(hephaistusRoot, 'tools', 'kiutils_parser_wrapper.py') : null,
    path.join(projectRoot, 'scripts', 'wrappers', 'kiutils_parser_wrapper.py'),
    path.join(projectRoot, 'tools', 'kiutils_parser_wrapper.py'),
  ].filter(Boolean) as string[];
  
  let wrapperPath: string | null = null;
  for (const candidate of possibleWrapperPaths) {
    if (candidate && fs.existsSync(candidate)) {
      wrapperPath = candidate;
      break;
    }
  }

  if (!pythonBin) {
    console.warn('[KiUtilsAdapter] Python binary not found in any location');
    console.warn('[KiUtilsAdapter] Tried:', possiblePythonBins);
    return null;
  }
  if (!wrapperPath) {
    console.warn('[KiUtilsAdapter] KiUtils wrapper not found in any location');
    console.warn('[KiUtilsAdapter] Tried:', possibleWrapperPaths);
    return null;
  }

  console.log(`[KiUtilsAdapter] Using Python: ${pythonBin}`);
  console.log(`[KiUtilsAdapter] Using wrapper: ${wrapperPath}`);

  const timeout = options?.timeoutMs ?? 60000;
  return await new Promise<string | null>((resolve) => {
    const proc = spawn(pythonBin!, [wrapperPath!, filePath], {
      stdio: ['ignore', 'pipe', 'pipe']
    });

    let stdout = '';
    let stderr = '';

    const timer = setTimeout(() => {
      try { proc.kill(); } catch { /* ignore */ }
      console.warn('[KiUtilsAdapter] Timeout after', timeout, 'ms');
      resolve(null);
    }, timeout);

    proc.stdout.on('data', (data: Buffer) => {
      stdout += data.toString();
    });
    proc.stderr.on('data', (data: Buffer) => {
      stderr += data.toString();
    });

    proc.on('close', (code: number) => {
      clearTimeout(timer);
      if (code === 0 && stdout.trim()) {
        console.log('[KiUtilsAdapter] Parse successful');
        resolve(stdout.trim());
      } else {
        console.warn('[KiUtilsAdapter] wrapper exited with code', code);
        if (stderr.trim()) {
          console.warn('[KiUtilsAdapter] stderr:', stderr.trim());
        }
        resolve(null);
      }
    });

    proc.on('error', (err: Error) => {
      clearTimeout(timer);
      console.error('[KiUtilsAdapter] Process error:', err.message);
      resolve(null);
    });
  });
}

/**
 * Find the HephAIstus project root by looking for package.json
 * Uses multiple strategies: extension directory, process.cwd(), parent directories
 */
function findHephaistusRoot(): string | null {
  // Strategy 1: Use __dirname (extension's installed location)
  // This file is at src/services/kicadKiutilsAdapter.ts, so go up to project root
  try {
    const adapterDir = __dirname;
    const servicesDir = path.dirname(adapterDir);
    const srcDir = path.dirname(servicesDir);
    const projectRoot = path.dirname(srcDir);
    
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

export default { parseKiCadWithKiUtils };