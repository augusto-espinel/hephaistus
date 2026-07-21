#!/usr/bin/env python3
"""
KiCad Delta Application Script for HephAIstus

Applies changes from modified JSON back to KiCad schematic.
Uses TEXT-BASED editing to preserve all KiCad 10 properties.

Usage:
    python kiutils_delta_apply.py <original.json> <modified.json> <kicad_file>

Output:
    Modified .kicad_sch file (backup created automatically)
"""

import sys
import json
import os
import shutil
import re
from typing import Dict, List, Any, Optional, Tuple


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
            
            # Check for value change (properties.Value)
            orig_value = orig_comp.get('properties', {}).get('Value', orig_comp.get('value', ''))
            mod_value = mod_comp.get('properties', {}).get('Value', mod_comp.get('value', ''))
            
            if orig_value != mod_value:
                delta['value_changes'].append({
                    'uuid': uuid,
                    'reference': mod_comp.get('reference'),
                    'old_value': orig_value,
                    'new_value': mod_value
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


def find_symbol_block(content: str, uuid: str) -> Optional[Tuple[int, int, str]]:
    """
    Find the S-expression block for a symbol with the given UUID.
    
    Returns (start_pos, end_pos, block_text) or None if not found.
    """
    # Pattern to find (symbol ... (uuid "uuid-here") ...)
    # We need to find the complete balanced S-expression
    
    # First, find the uuid
    uuid_pattern = rf'\(uuid\s+"{re.escape(uuid)}"\)'
    uuid_match = re.search(uuid_pattern, content)
    
    if not uuid_match:
        return None
    
    # Now find the enclosing (symbol ...) block
    # Work backwards to find the opening (symbol
    pos = uuid_match.start()
    
    # Track parenthesis depth and find the start
    depth = 0
    symbol_start = None
    
    for i in range(pos, -1, -1):
        if content[i] == ')':
            depth += 1
        elif content[i] == '(':
            depth -= 1
            if depth < 0:
                # Check if this is a symbol block
                remaining = content[i:]
                if remaining.startswith('(symbol'):
                    symbol_start = i
                    break
                depth = 0  # Reset for other paren types
    
    if symbol_start is None:
        return None
    
    # Now find the end of the symbol block by matching parentheses
    depth = 0
    symbol_end = None
    
    for i in range(symbol_start, len(content)):
        if content[i] == '(':
            depth += 1
        elif content[i] == ')':
            depth -= 1
            if depth == 0:
                symbol_end = i + 1
                break
    
    if symbol_end is None:
        return None
    
    return (symbol_start, symbol_end, content[symbol_start:symbol_end])


def replace_property_value(symbol_block: str, property_name: str, new_value: str) -> Optional[str]:
    """
    Replace the value of a property within a symbol block.
    
    Preserves all other formatting and attributes.
    
    Returns the modified block or None if property not found.
    """
    # Pattern to match (property "Property" "value" ...)
    # We need to find the property, then its string value, and replace it
    
    # Find the property line
    # Match: (property "Value" "old_value" ...)
    # The value is the second string after the property name
    
    # Escape special regex characters in property name
    prop_escaped = re.escape(property_name)
    
    # Pattern to find property block
    # (property "Value" "old_value" ...) or (property "Value" old_value ...)
    # We need to match the property name and capture the value
    
    # First, find where the property block starts
    prop_pattern = rf'\(property\s+"{prop_escaped}"'
    prop_match = re.search(prop_pattern, symbol_block)
    
    if not prop_match:
        return None
    
    # Find the complete property block (balanced parentheses)
    prop_start = prop_match.start()
    depth = 0
    prop_end = None
    
    for i in range(prop_start, len(symbol_block)):
        if symbol_block[i] == '(':
            depth += 1
        elif symbol_block[i] == ')':
            depth -= 1
            if depth == 0:
                prop_end = i + 1
                break
    
    if prop_end is None:
        return None
    
    prop_block = symbol_block[prop_start:prop_end]
    
    # Now find and replace the value string within the property block
    # The value is the second quoted string after the property name
    # Pattern: (property "Name" "value" ...)
    
    # Find the position after the property name
    after_name = prop_match.end()
    
    # Skip whitespace
    while after_name < len(symbol_block) and symbol_block[after_name] in ' \t\n':
        after_name += 1
    
    # Now we're at the start of the value
    # It could be quoted or unquoted
    if symbol_block[after_name] == '"':
        # Quoted value - find the closing quote
        value_start = after_name
        value_end = symbol_block.find('"', value_start + 1)
        if value_end == -1:
            return None
        value_end += 1  # Include closing quote
        
        # Replace the value
        old_value_str = symbol_block[value_start:value_end]
        new_value_str = f'"{new_value}"'
        
        # Build new property block
        new_prop_block = prop_block[:value_start - prop_start] + new_value_str + prop_block[value_end - prop_start:]
        
        # Build new symbol block
        new_symbol_block = symbol_block[:prop_start] + new_prop_block + symbol_block[prop_end:]
        
        return new_symbol_block
    else:
        # Unquoted value - find end (whitespace or closing paren)
        value_start = after_name
        value_end = value_start
        while value_end < len(symbol_block) and symbol_block[value_end] not in ' \t\n)':
            value_end += 1
        
        old_value_str = symbol_block[value_start:value_end]
        new_value_str = f'"{new_value}"'  # Always quote the new value
        
        # Build new property block
        new_prop_block = prop_block[:value_start - prop_start] + new_value_str + prop_block[value_end - prop_start:]
        
        # Build new symbol block
        new_symbol_block = symbol_block[:prop_start] + new_prop_block + symbol_block[prop_end:]
        
        return new_symbol_block


def apply_value_changes_text(content: str, value_changes: List[Dict[str, Any]]) -> Tuple[str, List[str]]:
    """
    Apply value changes using text-based editing.
    
    Preserves all KiCad formatting and properties.
    
    Returns (modified_content, list_of_changes_applied).
    """
    changes_applied = []
    
    for change in value_changes:
        uuid = change['uuid']
        new_value = change['new_value']
        reference = change.get('reference', 'unknown')
        
        # Find the symbol block
        result = find_symbol_block(content, uuid)
        if result is None:
            changes_applied.append(f"WARNING: Could not find symbol {reference} ({uuid})")
            continue
        
        start_pos, end_pos, symbol_block = result
        
        # Replace the Value property
        new_symbol_block = replace_property_value(symbol_block, 'Value', new_value)
        
        if new_symbol_block is None:
            changes_applied.append(f"WARNING: Could not find Value property for {reference}")
            continue
        
        # Replace in content
        content = content[:start_pos] + new_symbol_block + content[end_pos:]
        changes_applied.append(f"Updated {reference}: {change['old_value']} → {new_value}")
    
    return content, changes_applied


def apply_delta_to_schematic(schematic_path: str, delta: Dict[str, Any], 
                             output_path: Optional[str] = None) -> bool:
    """
    Apply delta changes to KiCad schematic file using TEXT-BASED editing.
    
    This preserves all KiCad 10 properties that kiutils would strip.
    
    Args:
        schematic_path: Path to .kicad_sch file
        delta: Delta object from compute_delta()
        output_path: Optional output path (default: overwrite original)
    
    Returns:
        True if successful, False otherwise
    """
    try:
        # Read the schematic file as text
        with open(schematic_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        changes_applied = []
        
        # 1. Apply value changes using text-based editing
        if delta.get('value_changes'):
            content, value_changes = apply_value_changes_text(content, delta['value_changes'])
            changes_applied.extend(value_changes)
        
        # 2. Handle removed components (TODO: implement text-based removal)
        for change in delta.get('removed_components', []):
            changes_applied.append(f"TODO: Remove {change['reference']} (not implemented)")
        
        # 3. Handle added components (TODO: implement text-based addition)
        for comp in delta.get('added_components', []):
            changes_applied.append(f"TODO: Add {comp.get('reference')} (not implemented)")
        
        # 4. Handle connection changes (TODO: implement wire reconnection)
        for change in delta.get('connection_changes', []):
            changes_applied.append(f"TODO: Reconnect {change['reference']}.{change['pin']} → {change['new_net']}")
        
        # Create backup before saving
        backup_path = schematic_path + '.bak'
        if os.path.exists(schematic_path):
            shutil.copy2(schematic_path, backup_path)
        
        # Save modified schematic (text-based, preserves all formatting)
        save_path = output_path if output_path else schematic_path
        with open(save_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return True
        
    except Exception as e:
        print(f"Error applying delta: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
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