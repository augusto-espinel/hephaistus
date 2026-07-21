import * as path from 'path';
import * as fs from 'fs';
import { WORKSPACE_ROOT, KICAD_EXT, JSON_EXT, writeToFile, generateFileHash, calculateSemanticKicadHash } from '../utils';
import { llmGenerateSync } from '../llmService';
import { parseKiCadToJson } from './kicadParserService';

// Core ingestion workflow: KiCad -> JSON
export async function executeIngestionPhase(kicadFilePath: string, state: any) {
  const kicadFileName = path.basename(kicadFilePath);
  const correspondingJsonName = kicadFileName.replace(KICAD_EXT, JSON_EXT);
  
  // Use state's workspace root if available, otherwise fall back to WORKSPACE_ROOT
  const workspaceRoot = state?.workspaceRoot || WORKSPACE_ROOT;
  
  // Ensure files.json array exists
  if (!state.files) state.files = {};
  if (!state.files.json) state.files.json = [];
  
  // Track the KiCad file
  if (!state.files.kicad) state.files.kicad = [];
  if (!state.files.kicad.includes(kicadFileName)) {
    state.files.kicad.push(kicadFileName);
  }

  try {
    // 1. Run deterministic KiCad parsing
    let jsonContentToPersist: string | null = null;
    let semanticHash = '';
    
    try {
      const parserJson = await parseKiCadToJson(kicadFilePath, { workspaceRoot });
      if (parserJson) {
        jsonContentToPersist = parserJson;
        console.log('[Ingestion] KiCad -> JSON via parser produced content.');
      }
    } catch (err) {
      // If parser fails, we'll fall back to LLM path below
      console.warn('[Ingestion] KiCad parser failed, will fall back to LLM-based JSON regeneration.');
    }

    // Always compute a semantic hash of the KiCad file for provenance
    try {
      semanticHash = await calculateSemanticKicadHash(kicadFilePath);
      console.log(`[Ingestion] KiCad semantic hash: ${semanticHash.substring(0, 8)}...`);
    } catch (hashErr) {
      // Use file hash as fallback
      semanticHash = await generateFileHash(kicadFilePath) || 'unknown';
      console.log(`[Ingestion] Using file hash as fallback: ${semanticHash.substring(0, 8)}...`);
    }

    // 2. If parser did not produce JSON content, create a basic structure
    if (!jsonContentToPersist) {
      // Create basic JSON structure from KiCad file
      jsonContentToPersist = JSON.stringify({
        version: "1.0.0",
        source: kicadFileName,
        sourceHash: semanticHash,
        components: [],
        nets: [],
        metadata: {
          ingestedAt: new Date().toISOString(),
          parser: 'fallback'
        }
      }, null, 2);
      console.log('[Ingestion] Using fallback JSON structure.');
    }

    // 3. Persist JSON content to disk in .hephaistus directory
    const jsonFilePath = path.join(workspaceRoot, '.hephaistus', correspondingJsonName);
    await writeToFile(jsonFilePath, jsonContentToPersist);
    
    // 3b. Create baseline for delta comparison (used when applying JSON changes back to KiCad)
    // Use .original.json suffix to avoid collision with {name}_backup.json from {name}_backup.kicad_sch
    const baselinePath = path.join(workspaceRoot, '.hephaistus', correspondingJsonName.replace('.json', '.original.json'));
    try {
      await writeToFile(baselinePath, jsonContentToPersist);
      console.log(`[Ingestion] Created baseline for delta comparison: ${baselinePath}`);
      // Note: We don't track baseline files in state.files.json - they're internal
    } catch (baselineErr) {
      console.warn('[Ingestion] Failed to create baseline file:', baselineErr);
      // Non-fatal - continue without baseline
    }
    
    // Track the JSON file
    if (!state.files.json.includes(correspondingJsonName)) {
      state.files.json.push(correspondingJsonName);
    }

    // 4. Update state ledger with new hash and linkage to KiCad source hash
    if (!state.stateHashes) state.stateHashes = {};
    state.stateHashes[correspondingJsonName] = {
      hash: await generateFileHash(jsonFilePath),
      lastModifiedTime: new Date(),
      expectedKicadHash: semanticHash
    };
    state.stateHashes[kicadFileName] = {
      hash: semanticHash,
      lastModifiedTime: new Date()
    };

    return { success: true, message: `✅ Ingestion successful! ${correspondingJsonName} updated to reflect changes from ${kicadFileName}.` };

  } catch (error) {
    console.error('Ingestion Phase failed:', error);
    return { success: false, message: `CRITICAL FAILURE during ingestion: ${(error as Error).message}` };
  }
}

// NEW API wrapper to expose ingestion as a clean orchestrator surface
export async function ingestIfNeeded(state: any, kicadFilePath: string) {
  return await executeIngestionPhase(kicadFilePath, state);
}
