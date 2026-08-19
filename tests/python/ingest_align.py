#!/usr/bin/env python3
import json
from pathlib import Path

FIXTURE_DIR = Path(__file__).parent / 'fixtures'
SCHEMATIC_PATH = FIXTURE_DIR / 'schematic.kicad_sch'
LEDGER_PATH = FIXTURE_DIR / 'ledger.json'

def load_json(p: Path):
    with open(p, 'r') as f:
        return json.load(f)

def main():
    schematic = load_json(SCHEMATIC_PATH)
    ledger = load_json(LEDGER_PATH)

    schematic_refs = {s.get('ref'): s for s in schematic.get('symbols', [])}
    aligned = {
        'components': []
    }
    # Copy ledger components, aligning values if refs exist in schematic
    for comp in ledger.get('components', []):
        ref = comp.get('ref')
        if ref in schematic_refs:
            aligned_comp = dict(comp)
            # align value to the schematic value if present
            aligned_comp['value'] = schematic_refs[ref].get('value', comp.get('value'))
            aligned['components'].append(aligned_comp)
        else:
            # keep as-is (to be NEW_PART in update step)
            aligned['components'].append(dict(comp))
    # Additionally, add any schematic refs not present in ledger as potential entries? We'll ignore for alignment here

    out = FIXTURE_DIR / 'ledger_aligned.json'
    with open(out, 'w') as f:
        json.dump(aligned, f, indent=2)
    print(f"Aligned ledger written to {out}")

if __name__ == '__main__':
    main()
