#!/usr/bin/env python3
"""Delta computation between schematic and ledger (production-ready)."""
import json
from typing import Dict, List


def compute_delta(schematic: Dict, ledger: Dict) -> Dict:
    """Compute delta between in-memory schematic and ledger JSON.

    schematic: {
      "symbols": [{"ref": str, "value": str, "pos": {"x": int, "y": int}}, ...],
      "wires": [...],
      "labels": [...]
    }
    ledger: {
      "components": [{"ref": str, "value": str, "nets": [str], "footprint": str, "lib_id": str}, ...]
    }

    Returns:
      {"updated_values": [{ref, old_value, new_value, target_nets}],
       "new_parts": [{ref, footprint, lib_id, value, nets}]}
    """
    updated_values: List[Dict] = []
    new_parts: List[Dict] = []

    existing = {s.get("ref"): s for s in schematic.get("symbols", [])}

    for comp in ledger.get("components", []):
        ref = comp.get("ref")
        new_value = comp.get("value")
        old_sym = existing.get(ref)
        if old_sym:
            old_value = old_sym.get("value")
            if old_value != new_value:
                updated_values.append({
                    "ref": ref,
                    "old_value": old_value,
                    "new_value": new_value,
                    "target_nets": comp.get("nets", [])
                })
        else:
            new_parts.append({
                "ref": ref,
                "footprint": comp.get("footprint"),
                "lib_id": comp.get("lib_id"),
                "value": new_value,
                "nets": comp.get("nets", [])
            })

    return {"updated_values": updated_values, "new_parts": new_parts}
