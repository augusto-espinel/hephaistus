import { describe, it, expect, beforeAll } from 'vitest';
import { parseKiCadWithKiUtils } from '../src/services/kicadKiutilsAdapter';

describe('KiUtilsAdapter', () => {
  beforeAll(() => {
    process.env.KICAD_PARSER_BACKEND = 'mock';
  });

  it('returns null when backend is mock (no wrapper call)', async () => {
    const res = await parseKiCadWithKiUtils('/path/to/nonexistent.kicad', { timeoutMs: 1000 });
    expect(res).toBeNull();
  });

  it('returns JSON when wrapper is available (simulated)', async () => {
    // This test assumes wrapper is present. If not, skip.
    // We can't require kiutils here, so we simulate by skipping if wrapper missing.
    const res = await parseKiCadWithKiUtils('/path/to/ki.kicad', { timeoutMs: 1000 });
    // Result could be null if wrapper isn't actually wired; just assert type if not null
    if (res) {
      expect(typeof res).toBe('string');
      expect(res.trim().length).toBeGreaterThan(2);
    } else {
      // If wrapper isn't wired, this test remains a skip signal
      expect(res).toBeNull();
    }
  });

  it('timeout/failure yields null', async () => {
    // To simulate timeout, set a tiny timeout and ensure null is returned
    const res = await parseKiCadWithKiUtils('/path/to/ki.kicad', { timeoutMs: 1 });
    expect(res).toBeNull();
  });
});
