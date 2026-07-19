import * as fs from 'fs';
import * as path from 'path';
import { parseKiCadWithKiUtils } from './kicadKiutilsAdapter';

export async function parseKiCadToJson(kicadFilePath: string, options?: { model?: string; workspaceRoot?: string }): Promise<string | null> {
  // KiUtils is the default backend for parsing KiCad files
  const backend = (process.env.KICAD_PARSER_BACKEND || 'kiutils').toLowerCase();
  
  if (backend === 'kiutils' || backend === 'kiutils-node') {
    try {
      const kiJson = await parseKiCadWithKiUtils(kicadFilePath, { 
        timeoutMs: 60000,
        workspaceRoot: options?.workspaceRoot
      });
      if (kiJson) return kiJson;
    } catch (err) {
      console.warn('[KiCadParser] KiUtils adapter threw:', (err as Error).message);
    }
  }

  // Fallback to mock KiCad parsing
  try {
    const content = await fs.promises.readFile(kicadFilePath, 'utf8');
    const lines = content.split(/\r?\n/).length;
    const parsed = {
      schemaVersion: "1.0",
      circuitName: path.basename(kicadFilePath, path.extname(kicadFilePath)),
      components: [
        { uuid: "generated-1", type: "GENERIC", value: `${lines}-lines`, coords: { x: 0, y: 0 } }
      ],
      metadata: { source: "mock-kicad-parser" }
    };
    return JSON.stringify(parsed, null, 2);
  } catch (err) {
    console.error('[KiCadParser] Failed to parse KiCad file:', err);
    return null;
  }
}

export default { parseKiCadToJson };
