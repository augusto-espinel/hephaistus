#!/usr/bin/env python3
import json
from pathlib import Path
FIXTURE_DIR = Path(__file__).parent / 'fixtures'
LEDGER_ALIGNED = FIXTURE_DIR / 'ledger_aligned.json'
SCHEMATIC = FIXTURE_DIR / 'schematic.kicad_sch'

def load_json(p: Path):
    with open(p, 'r') as f:
        return json.load(f)

def main():
    schematic = load_json(SCHEMATIC)
    ledger = load_json(LEDGER_ALIGNED)
    # Build map of schematic refs to values
    refs = {s.get('ref'): s for s in schematic.get('symbols', [])}
    delta_updated = []
    delta_new = []
    for comp in ledger.get('components', []):
        ref = comp.get('ref')
        val = comp.get('value')
        if ref in refs:
            old = refs[ref].get('value')
            if old != val:
                delta_updated.append({'ref': ref, 'old_value': old, 'new_value': val, 'nets': comp.get('nets', [])})
        else:
            delta_new.append({'ref': ref, 'value': val, 'nets': comp.get('nets', [])})
    # Print Markdown table
    print('RefDes | Change Type | Old Value | New Value | Target Net(s)')
    print('---------|-------------|-----------|-----------|-----------------')
    for u in delta_updated:
        nets = ', '.join(u.get('nets', []))
        print(f"{u['ref']} | UPDATE | {u['old_value']} | {u['new_value']} | {nets}")
    for n in delta_new:
        nets = ', '.join(n.get('nets', []))
        print(f"{n['ref']} | NEW PART | - | {n['value']} | {nets}")

if __name__ == '__main__':
    main()
