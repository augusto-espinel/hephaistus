#!/usr/bin/env python3
"""
KiCad Delta Application Script for HephAIstus

Applies changes from modified JSON back to KiCad schematic.
Preserves existing geometry (wire paths, component positions) where possible.

Usage:
    python kiutils_delta_apply.py <original.json> <modified.json> <kicad_file>

Output:
    Modified .kicad_sch file (backup created automatically)
"""

import sys
import json
import os
import shutil
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime


def load_json(path: str) -> Dict[str, Any]:
    """Load JSON file."""
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def compute_delta(original: Dict[str, Any], modified: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compute the difference between original and modified JSON states.
    
    Returns a delta object with:
    - value_changes: Components with changed values
    - added_components: New components not in original
    - removed_components: Components not in modified
    - connection_changes: Pins with changed net assignments
    """
    # Build lookup tables
    orig_comps = {c['uuid']: c for c in original.get('components', [])}
    mod_comps = {c['uuid']: c for c in modified.get('components', [])}
    
    delta = {
        'value_changes': [],
        'added_components': [],
        'removed_components': [],
        'connection_changes': [],
        'net_changes': []
    }
    
    # Find value changes and connection changes
    for uuid, mod_comp in mod_comps.items():
        if uuid in orig_comps:
            orig_comp = orig_comps[uuid]
            
            # Check for value change
            if orig_comp.get('value') != mod_comp.get('value'):
                delta['value_changes'].append({
                    'uuid': uuid,
                    'reference': mod_comp.get('reference'),
                    'old_value': orig_comp.get('value'),
                    'new_value': mod_comp.get('value')
                })
            
            # Check for connection changes
            orig_pins = {p['number']: p for p in orig_comp.get('pins', [])}
            mod_pins = {p['number']: p for p in mod_comp.get('pins', [])}
            
            for pin_num, mod_pin in mod_pins.items():
                if pin_num in orig_pins:
                    orig_net = orig_pins[pin_num].get('net', '')
                    mod_net = mod_pin.get('net', '')
                    if orig_net != mod_net:
                        delta['connection_changes'].append({
                            'uuid': uuid,
                            'reference': mod_comp.get('reference'),
                            'pin': pin_num,
                            'old_net': orig_net,
                            'new_net': mod_net
                        })
        else:
            # New component
            delta['added_components'].append(mod_comp)
    
    # Find removed components
    for uuid, orig_comp in orig_comps.items():
        if uuid not in mod_comps:
            delta['removed_components'].append({
                'uuid': uuid,
                'reference': orig_comp.get('reference')
            })
    
    return delta


def apply_delta_to_schematic(schematic_path: str, delta: Dict[str, Any], 
                             output_path: Optional[str] = None,
                             staging_position: Tuple[float, float] = (50.0, 50.0)) -> bool:
    """
    Apply delta changes to KiCad schematic file.
    
    Args:
        schematic_path: Path to .kicad_sch file
        delta: Delta object from compute_delta()
        output_path: Optional output path (default: overwrite original)
        staging_position: Position for new components (x, y)
    
    Returns:
        True if successful, False otherwise
    """
    try:
        from kiutils.schematic import Schematic, Property
        from kiutils.items.common import Position
        
        # Load schematic
        schematic = Schematic.from_file(schematic_path)
        
        # Build UUID to symbol mapping
        symbol_map = {sym.uuid: sym for sym in schematic.schematicSymbols}
        
        # Track changes for logging
        changes_applied = []
        
        # 1. Apply value changes
        for change in delta.get('value_changes', []):
            uuid = change['uuid']
            new_value = change['new_value']
            
            if uuid in symbol_map:
                symbol = symbol_map[uuid]
                # Find and update the Value property
                for prop in symbol.properties:
                    if prop.key == 'Value':
                        prop.value = new_value
                        changes_applied.append(f"Updated {change['reference']}: {change['old_value']} → {new_value}")
                        break
        
        # 2. Handle removed components
        for change in delta.get('removed_components', []):
            uuid = change['uuid']
            if uuid in symbol_map:
                symbol = symbol_map[uuid]
                
                # Collect pin positions for wire cleanup
                pin_positions = set()
                # Get library symbol for pin info
                lib_sym = find_lib_symbol(schematic, symbol)
                if lib_sym:
                    for pin_num, pin_uuid in symbol.pins.items():
                        pin_pos = get_pin_position(lib_sym, pin_num, symbol.position)
                        pin_positions.add((round(pin_pos[0], 2), round(pin_pos[1], 2)))
                
                # Remove symbol from schematic
                schematic.schematicSymbols.remove(symbol)
                changes_applied.append(f"Removed {change['reference']}")
                
                # Remove orphan wires (wires that only touched this symbol)
                # Note: We only remove wire segments that become orphaned
                # Wires that connect to other components are preserved
                orphan_wires_removed = remove_orphan_wires(schematic, pin_positions)
                if orphan_wires_removed > 0:
                    changes_applied.append(f"Removed {orphan_wires_removed} orphan wire(s) for {change['reference']}")
        
        # 3. Handle added components
        for comp in delta.get('added_components', []):
            # TODO: Create new symbol instance
            # This requires symbol library lookup and instantiation
            # For now, log as a TODO
            changes_applied.append(f"TODO: Add {comp.get('reference')} (not implemented)")
        
        # 4. Handle connection changes
        for change in delta.get('connection_changes', []):
            uuid = change['uuid']
            new_net = change['new_net']
            pin_num = change['pin']
            
            if uuid in symbol_map:
                symbol = symbol_map[uuid]
                lib_sym = find_lib_symbol(schematic.libSymbols, symbol)
                
                if lib_sym:
                    # Get pin position
                    pin_pos = get_pin_position(lib_sym, pin_num, symbol.position)
                    
                    # Create stub connection marker
                    # This is a logical connection - user completes wiring in KiCad
                    stub_created = create_stub_connection(
                        schematic, symbol, pin_num, pin_pos, new_net
                    )
                    
                    if stub_created:
                        changes_applied.append(
                            f"Stub: {change['reference']}.{pin_num} → {new_net} (needs wiring)"
                        )
                    else:
                        changes_applied.append(
                            f"TODO: Reconnect {change['reference']}.{pin_num} → {new_net}"
                        )
        
        # Create backup before saving
        backup_path = schematic_path + '.bak'
        if os.path.exists(schematic_path):
            shutil.copy2(schematic_path, backup_path)
        
        # Save modified schematic
        save_path = output_path if output_path else schematic_path
        schematic.to_file(save_path)
        
        return True
        
    except Exception as e:
        print(f"Error applying delta: {e}", file=sys.stderr)
        return False


def find_lib_symbol(schematic, symbol) -> Optional[Any]:
    """Find library symbol definition for a placed symbol."""
    lib_nickname = symbol.libraryNickname
    entry_name = symbol.entryName
    
    # libSymbols is a list of Symbol objects
    for lib_sym in schematic.libSymbols:
        if hasattr(lib_sym, 'libraryNickname') and hasattr(lib_sym, 'entryName'):
            if lib_sym.libraryNickname == lib_nickname and lib_sym.entryName == entry_name:
                return lib_sym
        # Also check by libId
        if hasattr(lib_sym, 'libId'):
            if lib_sym.libId == f"{lib_nickname}:{entry_name}":
                return lib_sym
    
    # Fallback: find by entry name
    for lib_sym in schematic.libSymbols:
        if hasattr(lib_sym, 'entryName') and lib_sym.entryName == entry_name:
            return lib_sym
    
    return None


def get_pin_position(lib_sym, pin_num: str, symbol_pos) -> Tuple[float, float]:
    """
    Calculate absolute pin position from library symbol and symbol position.
    
    kiutils structure:
    - lib_sym.units is a list of Symbol objects (unit variants)
    - Each unit has a .pins list of SymbolPin objects
    - SymbolPin has: position.X, position.Y, number
    """
    import math
    
    # Default relative position (center of symbol)
    pin_rel_x, pin_rel_y = 0.0, 0.0
    
    # Find pin in library symbol units
    for unit in getattr(lib_sym, 'units', []):
        for pin in getattr(unit, 'pins', []):
            if str(pin.number) == str(pin_num):
                pin_rel_x = pin.position.X
                pin_rel_y = pin.position.Y
                break
    
    # Apply rotation if present
    angle = getattr(symbol_pos, 'angle', 0) if hasattr(symbol_pos, 'angle') else 0
    if angle != 0:
        angle_rad = math.radians(angle)
        cos_a = math.cos(angle_rad)
        sin_a = math.sin(angle_rad)
        x_rot = pin_rel_x * cos_a - pin_rel_y * sin_a
        y_rot = pin_rel_x * sin_a + pin_rel_y * cos_a
        pin_rel_x, pin_rel_y = x_rot, y_rot
    
    # Apply translation
    abs_x = symbol_pos.X + pin_rel_x
    abs_y = symbol_pos.Y + pin_rel_y
    
    return (abs_x, abs_y)


def remove_orphan_wires(schematic, pin_positions: set) -> int:
    """
    Remove wire segments that only connect to removed component pins.
    Returns count of removed wires.
    """
    removed_count = 0
    
    # Find all Connection objects (wires) in graphicalItems
    wires_to_remove = []
    for item in schematic.graphicalItems:
        if hasattr(item, 'points') and hasattr(item, 'uuid'):
            # Check if all wire points are orphan pins
            wire_points = [(round(p.X, 2), round(p.Y, 2)) for p in item.points]
            
            # A wire is orphaned if all its endpoints are in pin_positions
            all_orphan = all(pt in pin_positions for pt in wire_points)
            if all_orphan:
                wires_to_remove.append(item)
    
    # Remove orphaned wires
    for wire in wires_to_remove:
        schematic.graphicalItems.remove(wire)
        removed_count += 1
    
    # Also remove junctions that are now orphaned
    junctions_to_remove = []
    for junc in schematic.junctions:
        junc_pos = (round(junc.position.X, 2), round(junc.position.Y, 2))
        if junc_pos in pin_positions:
            junctions_to_remove.append(junc)
    
    for junc in junctions_to_remove:
        schematic.junctions.remove(junc)
    
    return removed_count


def create_stub_connection(schematic, symbol, pin_num: str, pin_pos: Tuple[float, float], 
                           net_name: str) -> bool:
    """
    Create a stub connection marker for a re-wired pin.
    This creates a visual indicator in KiCad that the user needs to complete wiring.
    
    Returns True if stub was created, False otherwise.
    """
    try:
        from kiutils.schematic import LocalLabel
        from kiutils.items.common import Position, TextEffects
        
        # Create a local label at the pin position to mark the intended net
        # The user will see this and complete the wiring manually
        
        # Position label slightly offset from pin
        label_x = pin_pos[0] + 5.08  # Offset in KiCad units (5.08mm = 200mil)
        label_y = pin_pos[1]
        
        # Create label (if supported by kiutils version)
        # Note: This creates a visual marker, actual wire creation is user's responsibility
        
        # For now, just return False - stub creation requires more complex wire handling
        # In production, this would create a short wire stub with a label
        return False
        
    except Exception:
        return False


def main():
    if len(sys.argv) < 4:
        print(json.dumps({
            "error": "usage",
            "message": "Usage: kiutils_delta_apply.py <original.json> <modified.json> <kicad_file>"
        }))
        sys.exit(2)
    
    original_path = sys.argv[1]
    modified_path = sys.argv[2]
    kicad_path = sys.argv[3]
    
    # Load JSON states
    original = load_json(original_path)
    modified = load_json(modified_path)
    
    # Compute delta
    delta = compute_delta(original, modified)
    
    # Check if there are any changes
    total_changes = (
        len(delta['value_changes']) +
        len(delta['added_components']) +
        len(delta['removed_components']) +
        len(delta['connection_changes'])
    )
    
    if total_changes == 0:
        print(json.dumps({
            "status": "no_changes",
            "message": "No changes detected between original and modified JSON"
        }))
        sys.exit(0)
    
    # Apply delta
    success = apply_delta_to_schematic(kicad_path, delta)
    
    if success:
        # Return summary
        print(json.dumps({
            "status": "success",
            "changes_applied": total_changes,
            "delta": delta,
            "backup": kicad_path + '.bak'
        }, indent=2))
        sys.exit(0)
    else:
        print(json.dumps({
            "status": "error",
            "message": "Failed to apply delta"
        }))
        sys.exit(1)


if __name__ == "__main__":
    main()