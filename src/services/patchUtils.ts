import { PatchResult, applyPatch } from './patchApplyService';

// Lightweight patch utility: parse and apply patch blocks in a deterministic way.
// For now, this module delegates to the dry-run patch applier, but centralizes the patch
// application logic so we can extend with real diff parsing later.

export function parseUnifiedDiff(diff: string): { pythonDiff: string; jsonDiff: string; kiCadDiff: string; summary: string } {
  // Naive placeholder: split the diff into three channels if possible.
  // In future, implement a proper unified-diff parser to extract per-file changes.
  const trimmed = (diff || '').trim();
  const pythonDiff = trimmed;
  const jsonDiff = '';
  const kiCadDiff = '';
  const summary = trimmed.length > 0 ? 'Patch produced by LLM' : 'No patch content';
  return { pythonDiff, jsonDiff, kiCadDiff, summary };
}

export function applyUnifiedDiff(diff: string, state: any): PatchResult {
  // Currently, reuse the existing applyPatch path which writes a log and returns a PatchResult
  return applyPatch(diff, state);
}
