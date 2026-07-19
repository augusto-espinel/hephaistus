import * as fs from 'fs';
import * as path from 'path';
import * as crypto from 'crypto';

// Workspace and file type constants
export const WORKSPACE_ROOT = process.env.WORKSPACE_ROOT || '/Users/aespinel/.openclaw/workspace';
export const KICAD_EXT = '.kicad_sch';
export const JSON_EXT = '.json';

export async function writeToFile(filePath: string, content: string): Promise<void> {
  await fs.promises.mkdir(path.dirname(filePath), { recursive: true });
  await fs.promises.writeFile(filePath, content, 'utf8');
}

export async function generateFileHash(filePath: string): Promise<string> {
  try {
    const data = await fs.promises.readFile(filePath);
    return crypto.createHash('sha256').update(data).digest('hex');
  } catch {
    return '';
  }
}

export async function calculateSemanticKicadHash(filePath: string): Promise<string> {
  // For now, reuse the same hashing as semantic hash; in real world this could be content-aware hashing
  return await generateFileHash(filePath);
}
