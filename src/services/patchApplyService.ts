import * as fs from 'fs';
import * as path from 'path';

// Simple patch applier: supports a small, explicit patch language or a JSON payload
// that describes per-file find/replace operations. This is designed to be deterministic
// and auditable, with logs for each patch application.

export type PatchResult = {
  success: boolean;
  changedFiles?: string[];
  patchSummary?: string;
  logPath?: string;
};

const PATCH_LOG_DIR = path.resolve('/Users/aespinel/.openclaw/workspace/hephaistus/patch-logs');

export function ensureLogDir(): void {
  try {
    if (!fs.existsSync(PATCH_LOG_DIR)) {
      fs.mkdirSync(PATCH_LOG_DIR, { recursive: true });
    }
  } catch {
    // Graceful degradation if log dir cannot be created
  }
}

type SimpleChange = { file: string; find: string; replace: string };

function parsePatchAsChanges(patch: string): SimpleChange[] | null {
  if (!patch) return null;
  // Attempt JSON payload first: an array of { file, find, replace }
  try {
    const parsed = JSON.parse(patch);
    if (Array.isArray(parsed)) {
      const changes = parsed.map((c: any) => ({
        file: String(c.file || c.path || ''),
        find: String(c.find || ''),
        replace: String(c.replace || '')
      } as SimpleChange));
      const valid = changes.filter(z => z.file && z.find !== undefined && z.replace !== undefined);
      return valid;
    }
  } catch {
    // Not JSON, ignore
  }
  // DSL: simple file-based patch format
  // PATCH-FILE: <path>
  // REPLACE <find> WITH <replace>
  // (repeat) PATCH-FILE: ... END-PATCH
  const lines = patch.split(/\r?\n/);
  const changes: SimpleChange[] = [];
  let currentFile = '';
  for (const raw of lines) {
    const line = raw.trim();
    if (!line) continue;
    if (line.startsWith('PATCH-FILE:')) {
      currentFile = line.substring('PATCH-FILE:'.length).trim();
      continue;
    }
    if (line.startsWith('REPLACE')) {
      const rest = line.substring('REPLACE'.length).trim();
      const m = rest.match(/^(.*) WITH (.*)$/);
      if (m) {
        changes.push({ file: currentFile, find: m[1], replace: m[2] });
      }
      continue;
    }
    // ignore other lines (like END or context)
  }
  return changes.length > 0 ? changes : null;
}

export function applyPatch(patch: string, state: any): PatchResult {
  ensureLogDir();
  const ts = new Date().toISOString().replace(/[:.]/g, '-');
  const logPath = path.join(PATCH_LOG_DIR, `patch-${ts}.log`);
  const changes = parsePatchAsChanges(patch);
  let changedFiles: string[] = [];

  if (changes && changes.length > 0) {
    changes.forEach(ch => {
      try {
        const filePath = path.resolve('/Users/aespinel/.openclaw/workspace/hephaistus', ch.file);
        if (fs.existsSync(filePath) && fs.statSync(filePath).isFile()) {
          const content = fs.readFileSync(filePath, 'utf8');
          const newContent = content.split(ch.find).join(ch.replace);
          if (newContent !== content) {
            fs.writeFileSync(filePath, newContent, 'utf8');
            changedFiles.push(filePath);
          }
        } else {
          // If file does not exist, still record the path for audit
          changedFiles.push(filePath);
        }
      } catch {
        // Ignore per-file errors to keep the patch engine robust
      }
    });
    const contentLog = [
      'PATCH BLOCK',
      '--- PATCH START ---',
      patch || '(empty patch)',
      '--- PATCH END ---',
      'STATE DUMP:',
      JSON.stringify(state, null, 2),
      'FILES_CHANGED:',
      JSON.stringify(changedFiles, null, 2)
    ].join('\n');
    try {
      fs.writeFileSync(logPath, contentLog, 'utf8');
    } catch {
      // ignore
    }
    // Trigger asynchronous post-patch sync to refresh state
    (async () => {
      try {
        const mod = await import('../syncOrchestrator');
        const res = await mod.runSyncCycle(state);
        console.log('[Hephaistu] Post-patch async sync result:', res);
      } catch (err) {
        console.error('[Hephaistu] Post-patch async sync failed', err);
      }
    })();
    return { success: true, changedFiles, logPath, patchSummary: 'Applied patch to files (if existed)' };
  } else {
    const contentLog = [
      'PATCH BLOCK (NO JSON CHANGES)',
      '--- PATCH START ---',
      patch || '(empty patch)',
      '--- PATCH END ---',
      'STATE DUMP:',
      JSON.stringify(state, null, 2)
    ].join('\n');
    try {
      fs.writeFileSync(logPath, contentLog, 'utf8');
    } catch {}
    return { success: false, logPath, patchSummary: 'No actionable changes found in patch' };
  }
}
