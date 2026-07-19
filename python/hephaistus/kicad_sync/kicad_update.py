#!/usr/bin/env python3
import json
import argparse
from pathlib import Path

def load_json(path: Path):
    with open(path, 'r') as f:
        return json.load(f)

def compute_delta(schematic: dict, ledger: dict) -> dict:
    updated_values = []
    new_parts = []
    existing = {s.get('ref'): s for s in schematic.get('symbols', [])}
    for comp in ledger.get('components', []):
        ref = comp.get('ref')
        val = comp.get('value')
        sym = existing.get(ref)
        if sym:
            old = sym.get('value')
            if old != val:
                updated_values.append({'ref': ref, 'old_value': old, 'new_value': val, 'nets': comp.get('nets', [])})
        else:
            new_parts.append({'ref': ref, 'value': val, 'nets': comp.get('nets', []), 'footprint': comp.get('footprint'), 'lib_id': comp.get('lib_id')})
    return {'updated_values': updated_values, 'new_parts': new_parts}

def render_table(delta: dict) -> str:
    lines = ["RefDes | Change Type | Old Value | New Value | Target Net(s)",
             "---------|-------------|-----------|-----------|-----------------"]
    for u in delta.get('updated_values', []):
        nets = ', '.join(u.get('nets', []))
        lines.append(f"{u['ref']} | UPDATE | {u['old_value']} | {u['new_value']} | {nets}")
    for p in delta.get('new_parts', []):
        nets = ', '.join(p.get('nets', []))
        lines.append(f"{p['ref']} | NEW PART | - | {p.get('value')} | {nets}")
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description="Kicad Sync - dry-run / lightweight test path")
    parser.add_argument('--dry-run', dest='dry_run', action='store_true')
    parser.add_argument('--ledger_path', default='ledger.json')
    parser.add_argument('--schematic_path', default='schematic.kicad_sch')
    args = parser.parse_args()

    ledger = load_json(Path(args.ledger_path))
    schematic = load_json(Path(args.schematic_path))

    delta = compute_delta(schematic, ledger)

    if getattr(args, 'dry_run', False):
        print('DRY-RUN DELTA:')
        print(render_table(delta))
        return

    print('Live update not implemented in test environment.')

if __name__ == '__main__':
    main()
