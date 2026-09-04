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
import math
import uuid as uuid_module
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
    - net_changes: Net restructuring operations
    - simulation_changes: Changes to simulation directives
    """
    # Build lookup tables
    orig_comps = {c['uuid']: c for c in original.get('components', [])}
    mod_comps = {c['uuid']: c for c in modified.get('components', [])}
    
    delta = {
        'value_changes': [],
        'added_components': [],
        'removed_components': [],
        'connection_changes': [],
        'net_changes': [],
        'simulation_changes': []
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
    
    # Find simulation directive changes
    orig_directives = {d.get('directive_type', d.get('uuid')): d for d in original.get('simulation_directives', [])}
    mod_directives = {d.get('directive_type', d.get('uuid')): d for d in modified.get('simulation_directives', [])}
    
    for dtype, mod_dir in mod_directives.items():
        if dtype in orig_directives:
            orig_dir = orig_directives[dtype]
            # Check for parameter changes
            orig_params = orig_dir.get('parameters', {})
            mod_params = mod_dir.get('parameters', {})
            if orig_params != mod_params:
                delta['simulation_changes'].append({
                    'type': 'update',
                    'directive_type': dtype,
                    'old_parameters': orig_params,
                    'new_parameters': mod_params,
                    'old_text': orig_dir.get('text', ''),
                    'new_text': mod_dir.get('text', ''),
                })
        else:
            # New directive
            delta['simulation_changes'].append({
                'type': 'add',
                'directive_type': dtype,
                'text': mod_dir.get('text', ''),
                'parameters': mod_dir.get('parameters', {}),
            })
    
    for dtype, orig_dir in orig_directives.items():
        if dtype not in mod_directives:
            # Removed directive
            delta['simulation_changes'].append({
                'type': 'remove',
                'directive_type': dtype,
                'text': orig_dir.get('text', ''),
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
        # Quoted value - find the closing quote (handling escaped quotes)
        value_start = after_name
        i = value_start + 1
        while i < len(symbol_block):
            if symbol_block[i] == '\\' and i + 1 < len(symbol_block) and symbol_block[i + 1] == '"':
                # Escaped quote - skip both characters
                i += 2
            elif symbol_block[i] == '"':
                # Found the closing quote
                value_end = i + 1
                break
            else:
                i += 1
        else:
            # No closing quote found
            return None
        
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
    
    For B-sources (behavioral sources), updates Sim.Params with model formula.
    For regular components, updates the Value property.
    
    Returns (modified_content, list_of_changes_applied).
    """
    changes_applied = []
    
    for change in value_changes:
        uuid = change['uuid']
        new_value = change['new_value']
        reference = change.get('reference', 'unknown')
        lib_id = change.get('lib_id', '')
        
        # Find the symbol block
        result = find_symbol_block(content, uuid)
        if result is None:
            changes_applied.append(f"WARNING: Could not find symbol {reference} ({uuid})")
            continue
        
        start_pos, end_pos, symbol_block = result
        
        # Detect B-source (behavioral source)
        # B-sources have lib_id like "Simulation_SPICE:BSOURCE" or "pspice:BSOURCE"
        # and references like B1, B2, etc.
        is_bsource = (
            ':BSOURCE' in lib_id.upper() or
            reference.upper().startswith('B') or
            'BSOURCE' in lib_id.upper()
        )
        
        if is_bsource:
            # For B-sources, update Sim.Params with model formula
            # Format: type="B" model="I=..." or type="B" model="V=..."
            # The new_value should already include I= or V= prefix
            model_value = new_value if new_value.startswith(('I=', 'V=')) else f'I={new_value}'
            # KiCad requires quotes inside the string to be escaped
            # So type="B" model="I=..." becomes "type=\"B\" model=\"I=...\""
            sim_params_value = f'type=\"B\" model=\"{model_value}\"'
            new_symbol_block = replace_property_value(symbol_block, 'Sim.Params', sim_params_value)
            
            if new_symbol_block is None:
                changes_applied.append(f"WARNING: Could not find Sim.Params property for B-source {reference}")
                continue
            
            content = content[:start_pos] + new_symbol_block + content[end_pos:]
            changes_applied.append(f"Updated B-source {reference} model: {model_value}")
        else:
            # Regular component: update Value property
            new_symbol_block = replace_property_value(symbol_block, 'Value', new_value)
            
            if new_symbol_block is None:
                changes_applied.append(f"WARNING: Could not find Value property for {reference}")
                continue
            
            content = content[:start_pos] + new_symbol_block + content[end_pos:]
            changes_applied.append(f"Updated {reference}: {change.get('old_value', '?')} → {new_value}")
    
    return content, changes_applied


def extract_pin_positions_from_symbol(symbol_block: str) -> List[Tuple[float, float]]:
    """
    Extract pin positions from a symbol block.
    
    Pin positions in schematic symbols are relative to the symbol position.
    Returns list of (x, y) tuples for each pin.
    """
    pins = []
    
    # Find all pins in the symbol block
    # Pin format in KiCad 10: (pin ... (at x y angle) ...)
    # We need to find the pin positions relative to symbol origin
    
    # Pattern to find pin blocks with position
    pin_pattern = r'\(pin\s+[^)]*\(at\s+([\d.\-]+)\s+([\d.\-]+)\s+[\d.\-]+\)'
    
    for match in re.finditer(pin_pattern, symbol_block):
        x = float(match.group(1))
        y = float(match.group(2))
        pins.append((x, y))
    
    return pins


def extract_symbol_position(symbol_block: str) -> Optional[Tuple[float, float]]:
    """
    Extract the symbol position from its block.
    
    Returns (x, y) or None if not found.
    """
    # Pattern: (at x y angle) at the symbol level
    # The symbol has a position attribute
    at_pattern = r'\(at\s+([\d.\-]+)\s+([\d.\-]+)\s+[\d.\-]+\)'
    match = re.search(at_pattern, symbol_block)
    if match:
        return (float(match.group(1)), float(match.group(2)))
    return None


def find_wire_blocks(content: str) -> List[Tuple[int, int, str, List[Tuple[float, float]]]]:
    """
    Find all wire blocks in the schematic.
    
    Returns list of (start_pos, end_pos, block_text, points).
    """
    wires = []
    
    # Pattern to find wire blocks
    # (wire (pts (xy x1 y1) (xy x2 y2)) ...)
    wire_pattern = r'\(wire\s+\(pts\s+((?:\(xy\s+[\d.\-]+\s+[\d.\-]+\)\s*)+)\)'
    
    for match in re.finditer(wire_pattern, content):
        # Find the complete wire block (balanced parentheses)
        start = match.start()
        depth = 0
        end = start
        for i in range(start, len(content)):
            if content[i] == '(':
                depth += 1
            elif content[i] == ')':
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        
        block = content[start:end]
        
        # Extract points
        points = []
        point_pattern = r'\(xy\s+([\d.\-]+)\s+([\d.\-]+)\)'
        for pt_match in re.finditer(point_pattern, block):
            x = float(pt_match.group(1))
            y = float(pt_match.group(2))
            points.append((x, y))
        
        wires.append((start, end, block, points))
    
    return wires


def find_text_block(content: str, uuid: str = None, text_prefix: str = None) -> Optional[Tuple[int, int, str]]:
    """
    Find a text block in the schematic.
    
    Can search by UUID or by text prefix (e.g., ".tran" for simulation directives).
    
    Returns (start_pos, end_pos, block_text) or None if not found.
    """
    if uuid:
        # Pattern to find text block with specific UUID
        uuid_pattern = rf'\(text\s+[^)]*\(uuid\s+"{re.escape(uuid)}"\s*\)'
        uuid_match = re.search(uuid_pattern, content)
        if not uuid_match:
            # Try alternative pattern for text with uuid at end
            uuid_pattern = rf'\(text\s+"[^"]*"[^)]*\(uuid\s+"{re.escape(uuid)}"\s*\)'
            uuid_match = re.search(uuid_pattern, content)
        
        if not uuid_match:
            return None
        
        # Find the complete text block
        start = uuid_match.start()
        depth = 0
        end = start
        for i in range(start, len(content)):
            if content[i] == '(':
                depth += 1
            elif content[i] == ')':
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        
        return (start, end, content[start:end])
    
    elif text_prefix:
        # Pattern to find text blocks starting with specific prefix
        # (text ".tran ..." ...) or (text ".options ..." ...)
        prefix_escaped = re.escape(text_prefix)
        text_pattern = rf'\(text\s+"({prefix_escaped}[^"]*)"'
        
        for match in re.finditer(text_pattern, content):
            # Find the complete text block
            start = match.start()
            depth = 0
            end = start
            for i in range(start, len(content)):
                if content[i] == '(':
                    depth += 1
                elif content[i] == ')':
                    depth -= 1
                if depth == 0:
                    end = i + 1
                    break
            
            return (start, end, content[start:end])
        
        return None
    
    return None


def find_all_text_blocks_by_prefix(content: str, prefix: str) -> List[Tuple[int, int, str, str]]:
    """
    Find all text blocks starting with a given prefix.
    
    Returns list of (start_pos, end_pos, block_text, text_content).
    """
    blocks = []
    prefix_escaped = re.escape(prefix)
    text_pattern = rf'\(text\s+"({prefix_escaped}[^"]*)"'
    
    for match in re.finditer(text_pattern, content):
        start = match.start()
        depth = 0
        end = start
        for i in range(start, len(content)):
            if content[i] == '(':
                depth += 1
            elif content[i] == ')':
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        
        text_content = match.group(1)
        blocks.append((start, end, content[start:end], text_content))
    
    return blocks


def create_text_block(text: str, x: float, y: float, angle: float = 0, 
                       uuid_str: str = None, exclude_from_sim: bool = False) -> str:
    """
    Create a new text block for simulation directive.
    
    Returns the S-expression string for the text block.
    """
    if uuid_str is None:
        uuid_str = str(uuid_module.uuid4())
    
    lines = [f'\t(text "{text}"']
    lines.append(f'\t\t(exclude_from_sim {"yes" if exclude_from_sim else "no"})')
    lines.append(f'\t\t(at {x:.3f} {y:.3f} {angle})')
    lines.append('\t\t(effects')
    lines.append('\t\t\t(font')
    lines.append('\t\t\t\t(size 1.27 1.27)')
    lines.append('\t\t\t)')
    lines.append('\t\t)')
    lines.append(f'\t\t(uuid "{uuid_str}")')
    lines.append('\t)')
    
    return '\n'.join(lines)


def apply_simulation_changes(content: str, changes: List[Dict[str, Any]]) -> Tuple[str, List[str]]:
    """
    Apply simulation directive changes using text-based editing.
    
    Handles:
    - add: Create new text block with directive
    - update: Modify existing text block
    - remove: Delete text block
    
    Returns (modified_content, list_of_changes_applied).
    """
    changes_applied = []
    
    for change in changes:
        change_type = change.get('type')
        directive_type = change.get('directive_type', '')
        
        if change_type == 'add':
            # Create new directive
            text = change.get('text', f'.{directive_type}')
            
            # Find a good position for the new directive
            # Look for existing text blocks and place after them
            existing = find_all_text_blocks_by_prefix(content, '.')
            
            if existing:
                # Place after the last existing directive
                _, last_end, _, _ = existing[-1]
                # Insert after the last text block
                new_block = '\n' + create_text_block(text, 122.682, 51.816 + len(existing) * 12.7)
                content = content[:last_end] + new_block + content[last_end:]
            else:
                # No existing directives - find a good insertion point
                # Insert before the first (junction or (symbol or (wire
                insert_patterns = [
                    r'\n\t\(junction',
                    r'\n\t\(symbol',
                    r'\n\t\(wire',
                ]
                insert_pos = len(content)
                for pattern in insert_patterns:
                    match = re.search(pattern, content)
                    if match:
                        insert_pos = min(insert_pos, match.start())
                
                if insert_pos < len(content):
                    # Insert before this position
                    new_block = '\n' + create_text_block(text, 122.682, 51.816) + '\n'
                    content = content[:insert_pos] + new_block + content[insert_pos:]
                else:
                    # Append at end before final closing paren
                    # Find the last )
                    last_paren = content.rfind(')')
                    if last_paren > 0:
                        new_block = '\n' + create_text_block(text, 122.682, 51.816) + '\n'
                        content = content[:last_paren] + new_block + content[last_paren:]
            
            changes_applied.append(f"Added simulation directive: {text}")
        
        elif change_type == 'update':
            # Update existing directive
            old_text = change.get('old_text', '')
            new_text = change.get('new_text', '')
            
            # Find the text block with the old directive
            result = find_text_block(content, text_prefix=old_text.split()[0] if old_text else f'.{directive_type}')
            
            if result:
                start, end, block = result
                # Replace the text content in the block
                # Pattern: (text "old_text" ...
                new_block = re.sub(
                    rf'\(text\s+"{re.escape(old_text)}"',
                    f'(text "{new_text}"',
                    block
                )
                content = content[:start] + new_block + content[end:]
                changes_applied.append(f"Updated simulation directive: {old_text} → {new_text}")
            else:
                changes_applied.append(f"WARNING: Could not find directive '{old_text}' to update")
        
        elif change_type == 'remove':
            # Remove directive
            text = change.get('text', '')
            
            # Find the text block
            result = find_text_block(content, text_prefix=text.split()[0] if text else f'.{directive_type}')
            
            if result:
                start, end, block = result
                # Remove the block and any surrounding whitespace
                content = content[:start] + content[end:]
                # Clean up any double newlines
                content = re.sub(r'\n\s*\n\s*\n', '\n\n', content)
                changes_applied.append(f"Removed simulation directive: {text}")
            else:
                changes_applied.append(f"WARNING: Could not find directive '{text}' to remove")
    
    return content, changes_applied


def find_junction_blocks(content: str) -> List[Tuple[int, int, str, Tuple[float, float]]]:
    """
    Find all junction blocks in the schematic.
    
    Returns list of (start_pos, end_pos, block_text, position).
    """
    junctions = []
    
    # Pattern to find junction blocks
    # (junction (at x y) ...)
    junction_pattern = r'\(junction\s+\(at\s+([\d.\-]+)\s+([\d.\-]+)\)'
    
    for match in re.finditer(junction_pattern, content):
        # Find the complete junction block
        start = match.start()
        depth = 0
        end = start
        for i in range(start, len(content)):
            if content[i] == '(':
                depth += 1
            elif content[i] == ')':
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        
        block = content[start:end]
        x = float(match.group(1))
        y = float(match.group(2))
        
        junctions.append((start, end, block, (x, y)))
    
    return junctions


def find_lib_symbol_block(content: str, lib_id: str) -> Optional[Tuple[int, int, str]]:
    """
    Find a library symbol definition in the lib_symbols section.
    
    lib_id format: "Library:Symbol" (e.g., "Device:C", "Diode:1N4007")
    
    Returns (start_pos, end_pos, block_text) or None if not found.
    """
    # Parse lib_id into library nickname and entry name
    if ':' in lib_id:
        lib_nickname, entry_name = lib_id.split(':', 1)
    else:
        # Just the entry name, no library prefix
        lib_nickname = None
        entry_name = lib_id
    
    # Pattern to find (symbol "Library:Name" ...)
    # The lib_id appears as the first quoted string after (symbol
    escaped_lib_id = re.escape(lib_id)
    escaped_entry = re.escape(entry_name)
    
    # Try exact match first
    pattern = rf'\(symbol\s+"{escaped_lib_id}"'
    match = re.search(pattern, content)
    
    if not match and lib_nickname:
        # Try just the entry name
        pattern = rf'\(symbol\s+"{escaped_entry}"'
        match = re.search(pattern, content)
    
    if not match:
        return None
    
    # Find the complete symbol block
    start = match.start()
    depth = 0
    end = start
    
    for i in range(start, len(content)):
        if content[i] == '(':
            depth += 1
        elif content[i] == ')':
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    
    return (start, end, content[start:end])


def find_symbol_instances_section(content: str) -> Tuple[int, int, str]:
    """
    Find the last symbol instance in the KiCad 10 schematic.
    
    In KiCad 10, symbols are placed directly in the root (kicad_sch) section,
    not in a schematicSymbols sub-section.
    
    Returns (start_pos_of_last_symbol, end_pos, last_symbol_block) or (0, 0, '') if none found.
    """
    # Find all (symbol (lib_id ...)) blocks at root level
    # These are symbol instances, not library definitions
    
    pattern = r'\(symbol\s+\(lib_id'
    last_match = None
    last_end = 0
    
    for match in re.finditer(pattern, content):
        # Find the complete symbol block
        start = match.start()
        depth = 0
        end = start
        
        for i in range(start, len(content)):
            if content[i] == '(':
                depth += 1
            elif content[i] == ')':
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        
        last_match = (start, end, content[start:end])
        last_end = end
    
    return last_match if last_match else (0, 0, '')


def find_existing_symbols_bounds(content: str) -> Tuple[float, float, float, float]:
    """
    Find the bounding box of existing placed symbols.
    
    Returns (min_x, min_y, max_x, max_y).
    Used for staging new components.
    
    IMPORTANT: Only uses the symbol's position (at x y angle), not property positions.
    Property positions can be offset from the symbol position and would skew the bounds.
    """
    min_x, min_y = float('inf'), float('inf')
    max_x, max_y = float('-inf'), float('-inf')
    
    # Find all symbol instance blocks
    symbol_pattern = r'\(symbol\s+\(lib_id'
    
    for match in re.finditer(symbol_pattern, content):
        # Find the complete symbol block
        start = match.start()
        depth = 0
        end = start
        
        for i in range(start, len(content)):
            if content[i] == '(':
                depth += 1
            elif content[i] == ')':
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        
        # Extract the SYMBOL's position (first (at x y angle) in the block)
        # This is the symbol's position, NOT property positions which come after
        symbol_block = content[start:end]
        at_match = re.search(r'\(at\s+([\d.\-]+)\s+([\d.\-]+)\s+[\d.\-]+\)', symbol_block)
        if at_match:
            x = float(at_match.group(1))
            y = float(at_match.group(2))
            min_x = min(min_x, x)
            min_y = min(min_y, y)
            max_x = max(max_x, x)
            max_y = max(max_y, y)
    
    # Default to reasonable bounds if no symbols found
    if min_x == float('inf'):
        min_x, min_y = 0, 0
        max_x, max_y = 100, 100
    
    return (min_x, min_y, max_x, max_y)


def generate_uuid() -> str:
    """Generate a UUID4 string for new components."""
    import uuid
    return str(uuid.uuid4())


def create_symbol_instance(lib_symbol_block: str, 
                           new_uuid: str,
                           reference: str,
                           value: str,
                           position: Tuple[float, float]) -> str:
    """
    Create a new symbol instance from a library symbol definition.
    
    This is a text-based transformation that:
    1. Takes the library symbol as a template
    2. Replaces the symbol name with an instance
    3. Sets position, UUID, reference, and value
    4. Copies SPICE simulation properties from library symbol (Sim.* props)
    5. Preserves all KiCad 10 properties
    
    Note: This creates a STUB - user must wire in KiCad.
    
    SPICE Property Inheritance:
    KiCad does NOT automatically copy Sim.* properties from library symbols to instances.
    For SPICE symbols (Sim.Device = SUBCKT, etc.), we MUST copy these properties to make
    the instance self-contained for simulation:
    - Sim.Device: Device type (SUBCKT, X, etc.)
    - Sim.Library: Path to SPICE library file
    - Sim.Name: Subcircuit/model name
    - Sim.Pins: Pin-to-SPICE node mapping
    - Sim.Params: Optional parameters
    
    B-Source Handling:
    For behavioral sources (B-sources), the 'value' parameter contains the model formula
    (I=... or V=...). These must be routed to Sim.Params, not Value property:
    - Sim.Device: "B" (behavioral source)
    - Sim.Params: type="B" model="I=..." or type="B" model="V=..."
    - Value: Reference designator (e.g., "B1")
    """
    # The library symbol looks like:
    # (symbol "Device:C" (property "Reference" "C") ...)
    # 
    # We need to transform it to an instance:
    # (symbol (lib_id "Device:C") (reference "C1") (value "100n") 
    #         (at x y angle) (uuid "...") ...)
    
    # Extract library nickname and entry name from the symbol block
    symbol_name_match = re.search(r'\(symbol\s+"([^"]+)"', lib_symbol_block)
    if not symbol_name_match:
        raise ValueError("Could not find symbol name in library block")
    
    lib_id = symbol_name_match.group(1)
    
    # For KiCad 10, symbol instances have a different structure
    # They reference the library symbol and have instance-specific properties
    
    # Detect B-source (behavioral source) - formula goes to Sim.Params, not Value
    # B-sources have lib_id like "Simulation_SPICE:BSOURCE" or "pspice:BSOURCE"
    is_bsource = (
        ':BSOURCE' in lib_id.upper() or
        reference.upper().startswith('B') and reference[1:].isdigit() or
        'BSOURCE' in lib_id.upper()
    )
    
    # Extract SPICE properties from library symbol block
    # These must be copied to instance for simulation symbols
    spice_props = {}
    for prop_name in ['Sim.Device', 'Sim.Type', 'Sim.Params', 'Sim.Pins', 'Sim.Library', 'Sim.Name']:
        # Pattern: (property "Sim.Device" "SUBCKT" ...)
        pattern = rf'\(property\s+"{re.escape(prop_name)}"\s+"([^"]*)"'
        match = re.search(pattern, lib_symbol_block)
        if match:
            spice_props[prop_name] = match.group(1)
    
    # For B-sources: override Sim.Device and Sim.Params from the value parameter
    # The 'value' param contains the formula (I=... or V=...)
    if is_bsource:
        # Ensure formula has I= or V= prefix
        model_value = value if value.startswith(('I=', 'V=')) else f'I={value}'
        # Format: type="B" model="I=..." (with escaped quotes for KiCad)
        spice_props['Sim.Device'] = 'B'
        spice_props['Sim.Params'] = f'type="B" model="{model_value}"'
        # Use reference as display value (e.g., "B1")
        display_value = reference
    else:
        display_value = value
    
    # Build the symbol instance
    # KiCad 10 format:
    # (symbol (lib_id "Device:C") (at x y angle) (uuid "...") 
    #         (property "Reference" "C1" ...) (property "Value" "100n" ...) ...)
    
    # We'll use the library symbol as a template and modify it
    instance = lib_symbol_block
    
    # Replace symbol name with instance structure
    # This is complex - KiCad 10 has a specific format for instances
    # 
    # The safest approach: create a minimal instance that references the library symbol
    
    # KiCad 10 symbol instance format:
    # Build base instance with required properties
    property_blocks = []
    property_blocks.append(f'''		(property "Reference" "{reference}"
			(at {position[0]:.2f} {position[1] + 1.27:.2f} 0)
			(show_name no)
			(do_not_autoplace no)
			(effects
				(font
					(size 1.27 1.27)
				)
			)
		)''')
    
    property_blocks.append(f'''		(property "Value" "{display_value}"
			(at {position[0]:.2f} {position[1] - 1.27:.2f} 0)
			(show_name no)
			(do_not_autoplace no)
			(effects
				(font
					(size 1.27 1.27)
				)
			)
		)''')
    
    property_blocks.append(f'''		(property "Footprint" ""
			(at {position[0]:.2f} {position[1]:.2f} 0)
			(show_name no)
			(do_not_autoplace no)
			(hide yes)
			(effects
				(font
					(size 1.27 1.27)
				)
			)
		)''')
    
    property_blocks.append(f'''		(property "Datasheet" ""
			(at {position[0]:.2f} {position[1]:.2f} 0)
			(show_name no)
			(do_not_autoplace no)
			(hide yes)
			(effects
				(font
					(size 1.27 1.27)
				)
			)
		)''')
    
    # Add SPICE properties if present in library symbol
    # These are CRITICAL for simulation - without them, subcircuits won't be found
    for prop_name in ['Sim.Device', 'Sim.Type', 'Sim.Params', 'Sim.Pins', 'Sim.Library', 'Sim.Name']:
        if prop_name in spice_props:
            property_blocks.append(f'''		(property "{prop_name}" "{spice_props[prop_name]}"
			(at {position[0]:.2f} {position[1]:.2f} 0)
			(show_name no)
			(do_not_autoplace no)
			(hide yes)
			(effects
				(font
					(size 1.27 1.27)
				)
			)
		)''')
    
    # Build complete instance
    properties_text = '\n'.join(property_blocks)
    instance = f'''(symbol
		(lib_id "{lib_id}")
		(at {position[0]:.2f} {position[1]:.2f} 0)
		(uuid "{new_uuid}")
{properties_text}
		(in_bom yes)
		(on_board yes)
		(dnp no)
		(fields_autoplaced yes)
	)'''
    
    # Emit (pin "N" (uuid ...)) blocks — required by the KiCad 6+ instance
    # format; our parser populates symbol.pins from these.
    pin_nums = sorted(extract_pin_definitions(lib_symbol_block).keys(),
                      key=lambda s: (not s.isdigit(), int(s) if s.isdigit() else s))
    if pin_nums:
        pin_blocks = ''.join(
            f'\n\t\t(pin "{n}"\n\t\t\t(uuid "{generate_uuid()}")\n\t\t)'
            for n in pin_nums
        )
        tail = instance.rfind('\n')
        instance = instance[:tail] + pin_blocks + instance[tail:]

    return instance


def create_net_label(net_name: str, position: Tuple[float, float], 
                     uuid_str: str = None, rotation: float = 0) -> str:
    """
    Create a KiCad net label.
    
    Net labels connect wires/terminals with the same label name.
    """
    if uuid_str is None:
        uuid_str = str(__import__('uuid').uuid4())
    
    # Calculate justification based on rotation
    # Rotation 0 = right-facing, 90 = down, 180 = left, 270 = up
    if rotation == 0:
        justify = "left bottom"
    elif rotation == 90:
        justify = "left bottom"
    elif rotation == 180:
        justify = "right bottom"
    elif rotation == 270:
        justify = "right bottom"
    else:
        justify = "left bottom"
    
    return f'''(label "{net_name}"
	(at {position[0]:.2f} {position[1]:.2f} {int(rotation)})
	(effects
		(font
			(size 1.27 1.27)
		)
		(justify {justify})
	)
	(uuid "{uuid_str}")
)'''


# ---------------------------------------------------------------------------
# Stub-based net restructuring (2026-08-03)
#
# The AI expresses series insertions and re-wiring purely as potential (net)
# re-assignments in the JSON state — e.g. moving R2.2 from 'dc_plus' to
# 'dc_plus_shunt' while adding R3 across the two potentials. This pass makes
# it physical: for every ORIGINAL net that loses member pins, all of its
# wires/junctions/labels are stripped and EVERY former member pin receives a
# short stub wire + label carrying its NEW net name. Connectivity is then by
# label name alone, so the schematic is immediately simulatable; the user may
# redraw physical wires later (or ask the parser for wiring suggestions —
# future feature).
# ---------------------------------------------------------------------------

STUB_LENGTH = 5.08   # mm — two 2.54mm grid steps
POS_TOLERANCE = 0.5  # mm — matches the parser's tolerance


def extract_pin_definitions(lib_symbol_block: str) -> Dict[str, Tuple[float, float, float]]:
    """Extract pin number -> (rel_x, rel_y, angle_deg) from a library symbol block.

    KiCad pin angle points from the connect point INTO the symbol body.
    Coordinates are in library Y-UP space and MUST be negated on Y
    before use in schematic (Y-DOWN) space.
    """
    pin_defs: Dict[str, Tuple[float, float, float]] = {}
    for m in re.finditer(r'\(pin\s', lib_symbol_block):
        start = m.start()
        depth = 0
        end = start
        for i in range(start, len(lib_symbol_block)):
            ch = lib_symbol_block[i]
            if ch == '(':
                depth += 1
            elif ch == ')':
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        block = lib_symbol_block[start:end]
        at_m = re.search(r'\(at\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\)', block)
        num_m = re.search(r'\(number\s+"([^"]+)"', block)
        if at_m and num_m:
            num = num_m.group(1)
            if num not in pin_defs:  # first unit definition wins
                pin_defs[num] = (float(at_m.group(1)), float(at_m.group(2)), float(at_m.group(3)))
    return pin_defs


def _rotate(dx: float, dy: float, angle_deg: float) -> Tuple[float, float]:
    """Same rotation convention as the parser (CCW matrix on KiCad coords)."""
    rad = math.radians(angle_deg)
    cos_a, sin_a = math.cos(rad), math.sin(rad)
    return (dx * cos_a - dy * sin_a, dx * sin_a + dy * cos_a)


def _stub_direction_from_lib_angle(pin_angle_deg: float, symbol_rot: float = 0.0) -> Tuple[float, float]:
    """Unit vector pointing AWAY from the symbol body (stub direction).

    KiCad pin angle points from the connect point INTO the body, in KiCad's
    y-down coordinates (0 = +x, 90 = +y). The stub extends the opposite way.
    """
    rad = math.radians(pin_angle_deg)
    dx, dy = -math.cos(rad), -math.sin(rad)
    if symbol_rot:
        dx, dy = _rotate(dx, dy, symbol_rot)
    if abs(dx) < 1e-9:
        dx = 0.0
    if abs(dy) < 1e-9:
        dy = 0.0
    return (dx, dy)


def _normalize(dx: float, dy: float) -> Tuple[float, float]:
    mag = math.hypot(dx, dy)
    if mag == 0:
        return (0.0, -1.0)  # arbitrary: up
    return (dx / mag, dy / mag)


def _point_on_segment(p: Tuple[float, float], a: Tuple[float, float],
                      b: Tuple[float, float], tol: float = POS_TOLERANCE) -> bool:
    """True if point p lies on segment a-b (within tolerance)."""
    px, py = p
    ax, ay = a
    bx, by = b
    if px < min(ax, bx) - tol or px > max(ax, bx) + tol:
        return False
    if py < min(ay, by) - tol or py > max(ay, by) + tol:
        return False
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return abs(px - ax) <= tol and abs(py - ay) <= tol
    dist = abs(dy * px - dx * py + bx * ay - by * ax) / math.hypot(dx, dy)
    return dist <= tol


def _wire_touches_point(wire: Dict[str, Any], p: Tuple[float, float],
                        tol: float = POS_TOLERANCE) -> bool:
    """True if any vertex OR segment of the wire touches point p."""
    pts = wire['points']
    for pt in pts:
        if abs(pt[0] - p[0]) <= tol and abs(pt[1] - p[1]) <= tol:
            return True
    for i in range(len(pts) - 1):
        if _point_on_segment(p, pts[i], pts[i + 1], tol):
            return True
    return False


def _wires_connected(w1: Dict[str, Any], w2: Dict[str, Any],
                     junctions: List[Tuple[float, float]], tol: float = POS_TOLERANCE) -> bool:
    """Wires connect via shared points, endpoint-on-segment, or a shared junction."""
    for p in w1['points']:
        if _wire_touches_point(w2, p, tol):
            return True
    for p in w2['points']:
        if _wire_touches_point(w1, p, tol):
            return True
    for jp in junctions:
        if _wire_touches_point(w1, jp, tol) and _wire_touches_point(w2, jp, tol):
            return True
    return False


def build_wire_topology(schematic_path: str) -> Tuple[List[Dict[str, Any]], List[Tuple[float, float]]]:
    """Load wires and junctions via kiutils.

    Returns (wires, junctions) where wires = [{'uuid', 'points': [(x,y), ...]}]
    and junctions = [(x,y), ...].
    """
    from kiutils.schematic import Schematic, Connection
    sch = Schematic.from_file(schematic_path)
    wires = []
    for item in sch.graphicalItems:
        if isinstance(item, Connection):
            wires.append({'uuid': item.uuid, 'points': [(p.X, p.Y) for p in item.points]})
    junctions = [(j.position.X, j.position.Y) for j in sch.junctions]
    return wires, junctions


def collect_net_island(seed_positions: List[Tuple[float, float]],
                       wires: List[Dict[str, Any]],
                       junctions: List[Tuple[float, float]]) -> Tuple[set, set]:
    """Find the connected component of wires containing any seed position.

    Returns (island_wire_indices, island_junction_positions).
    """
    island: set = set()
    stack: List[int] = []
    for i, w in enumerate(wires):
        for s in seed_positions:
            if _wire_touches_point(w, s):
                stack.append(i)
                break
    while stack:
        i = stack.pop()
        if i in island:
            continue
        island.add(i)
        for j in range(len(wires)):
            if j in island:
                continue
            if _wires_connected(wires[i], wires[j], junctions):
                stack.append(j)
    island_junctions = set()
    for jp in junctions:
        for i in island:
            if _wire_touches_point(wires[i], jp):
                island_junctions.add((round(jp[0], 4), round(jp[1], 4)))
                break
    return island, island_junctions


def _direction_from_island(pin_pos: Tuple[float, float],
                           wires: List[Dict[str, Any]], island: set) -> Optional[Tuple[float, float]]:
    """Direction of the old wire leaving the pin (away from the symbol body)."""
    for i in island:
        pts = wires[i]['points']
        for idx, pt in enumerate(pts):
            if abs(pt[0] - pin_pos[0]) <= POS_TOLERANCE and abs(pt[1] - pin_pos[1]) <= POS_TOLERANCE:
                if len(pts) < 2:
                    continue
                if idx == 0:
                    return _normalize(pts[1][0] - pt[0], pts[1][1] - pt[1])
                if idx == len(pts) - 1:
                    return _normalize(pts[-2][0] - pt[0], pts[-2][1] - pt[1])
                return _normalize(pts[idx + 1][0] - pt[0], pts[idx + 1][1] - pt[1])
        for k in range(len(pts) - 1):
            if _point_on_segment(pin_pos, pts[k], pts[k + 1]):
                return _normalize(pts[k + 1][0] - pts[k][0], pts[k + 1][1] - pts[k][1])
    return None


def _pin_geometry_from_content(content: str, comp_uuid: str,
                               pin_num: str) -> Optional[Tuple[Tuple[float, float], Tuple[float, float]]]:
    """Compute (absolute_position, stub_direction) for a pin from schematic text.

    Fallback when the JSON state lacks pin positions. Mirrors the parser's math.
    """
    sym = find_symbol_block(content, comp_uuid)
    if not sym:
        return None
    block = sym[2]
    at_m = re.search(r'\(at\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\)', block)
    lib_m = re.search(r'\(lib_id\s+"([^"]+)"\)', block)
    if not at_m or not lib_m:
        return None
    sx, sy, rot = float(at_m.group(1)), float(at_m.group(2)), float(at_m.group(3))
    lib = find_lib_symbol_block(content, lib_m.group(1))
    if not lib:
        return None
    pin_defs = extract_pin_definitions(lib[2])
    if pin_num not in pin_defs:
        return None
    rel_x, rel_y, pin_angle = pin_defs[pin_num]
    # Negate Y: library coords are Y-UP, schematic coords are Y-DOWN
    rel_y = -rel_y
    rx, ry = _rotate(rel_x, rel_y, rot)
    return ((sx + rx, sy + ry), _stub_direction_from_lib_angle(pin_angle, rot))


def create_wire_block(p1: Tuple[float, float], p2: Tuple[float, float],
                      uuid_str: Optional[str] = None) -> str:
    """Create a KiCad 10 wire block."""
    if uuid_str is None:
        uuid_str = generate_uuid()
    return f'''(wire
\t\t(pts
\t\t\t(xy {p1[0]:.2f} {p1[1]:.2f}) (xy {p2[0]:.2f} {p2[1]:.2f})
\t\t)
\t\t(stroke
\t\t\t(width 0)
\t\t\t(type default)
\t\t)
\t\t(uuid "{uuid_str}")
\t)'''


def _find_blocks(content: str, keyword: str) -> List[Tuple[int, int, str]]:
    """Find all (keyword ...) blocks. keyword is matched literally after '('."""
    blocks = []
    pattern = r'\(' + keyword + r'[\s"]'
    for m in re.finditer(pattern, content):
        start = m.start()
        depth = 0
        end = start
        for i in range(start, len(content)):
            if content[i] == '(':
                depth += 1
            elif content[i] == ')':
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        blocks.append((start, end, content[start:end]))
    return blocks


def remove_net_geometry(content: str, island_wire_uuids: set,
                        island_junctions: set, label_names: set) -> Tuple[str, int, int, int]:
    """Remove wire/junction/label blocks belonging to a cleared net.

    Returns (content, wires_removed, junctions_removed, labels_removed).
    """
    spans: List[Tuple[int, int]] = []
    n_wires = n_junctions = n_labels = 0
    for start, end, block in _find_blocks(content, 'wire'):
        m = re.search(r'\(uuid\s+"([^"]+)"\)', block)
        if m and m.group(1) in island_wire_uuids:
            spans.append((start, end))
            n_wires += 1
    for start, end, block in _find_blocks(content, 'junction'):
        m = re.search(r'\(at\s+([-\d.]+)\s+([-\d.]+)\)', block)
        if m and (round(float(m.group(1)), 4), round(float(m.group(2)), 4)) in island_junctions:
            spans.append((start, end))
            n_junctions += 1
    for start, end, block in _find_blocks(content, 'label'):
        m = re.match(r'\(label\s+"([^"]+)"', block)
        if m and m.group(1) in label_names:
            spans.append((start, end))
            n_labels += 1
    for start, end in sorted(spans, reverse=True):
        content = content[:start] + content[end:]
    return content, n_wires, n_junctions, n_labels


def _append_blocks_after_last_symbol(content: str, blocks: List[str]) -> str:
    """Insert top-level blocks after the last placed symbol instance.

    Advances by the ACTUAL inserted string length (post-indentation) — see the
    offset-accounting rule in docs/architecture.md §4.4.
    """
    if not blocks:
        return content
    start, end, _ = find_symbol_instances_section(content)
    if end == 0:
        end = content.rfind(')')
    insertion = ''.join('\n\t' + b.replace('\n', '\n\t') for b in blocks)
    return content[:end] + insertion + content[end:]


def _is_unnamed_net(net_name: str) -> bool:
    """Check if a net name is a parser-assigned unnamed net (N$X pattern)."""
    if not net_name:
        return False
    # Pattern: N$ followed by digits (N$1, N$2, N$15, etc.)
    # These are generated by the parser for nets without explicit labels
    return net_name.startswith('N$') and net_name[2:].isdigit()


def _find_wire_network_positions(original_json: Dict[str, Any], net_name: str) -> List[Tuple[float, float]]:
    """
    Find positions where we can place labels for an unnamed net.
    
    Returns positions near pins that are on this net, suitable for label placement.
    For unnamed nets, these are the wire endpoints where pins connect.
    """
    positions = []
    
    # Find pins connected to this net
    for net in original_json.get('nets', []):
        if net.get('name') == net_name:
            connected_pins = net.get('connectedPins', [])
            for pin_ref in connected_pins:
                # Parse pin reference like "C3.2"
                parts = pin_ref.split('.')
                if len(parts) != 2:
                    continue
                ref, pin_num = parts
                
                # Find this component's pin position
                for comp in original_json.get('components', []):
                    if comp.get('reference') == ref:
                        for pin in comp.get('pins', []):
                            if str(pin.get('number')) == pin_num:
                                pos = pin.get('position', {})
                                if 'x' in pos and 'y' in pos:
                                    positions.append((pos['x'], pos['y']))
                                break
                        break
            break
    
    return positions


def _make_stub(pin_pos: Tuple[float, float], direction: Tuple[float, float],
               net_name: str) -> List[str]:
    """Stub = short wire from the pin + label at its free end."""
    end = (round(pin_pos[0] + direction[0] * STUB_LENGTH, 2),
           round(pin_pos[1] + direction[1] * STUB_LENGTH, 2))
    return [create_wire_block(pin_pos, end), create_net_label(net_name, end)]


def analyze_net_migrations(original: Dict[str, Any], modified: Dict[str, Any]
                           ) -> Tuple[Dict[str, List[Dict[str, Any]]], List[Dict[str, Any]]]:
    """Compare pin net assignments between original and modified states.

    Returns (migrations, gains):
      migrations: {origin_net: [{uuid, reference, pin, new_net}]} — pins that LEFT a net
                  (new_net may be '' meaning the pin was disconnected)
      gains:      [{uuid, reference, pin, new_net}] — previously unconnected pins
                  that GAINED a net (stub-only, no wire clearing)
    """
    orig_pins: Dict[Tuple[str, str], Tuple[str, str]] = {}
    for comp in original.get('components', []):
        for pin in comp.get('pins', []):
            orig_pins[(comp.get('uuid', ''), str(pin.get('number')))] = (
                pin.get('net', ''), comp.get('reference', ''))

    migrations: Dict[str, List[Dict[str, Any]]] = {}
    gains: List[Dict[str, Any]] = []
    for comp in modified.get('components', []):
        cuuid = comp.get('uuid', '')
        ref = comp.get('reference', '')
        for pin in comp.get('pins', []):
            key = (cuuid, str(pin.get('number')))
            if key not in orig_pins:
                continue  # new component — handled by the addition path
            old_net, _ = orig_pins[key]
            new_net = pin.get('net', '')
            if old_net == new_net:
                continue
            entry = {'uuid': cuuid, 'reference': ref, 'pin': key[1], 'new_net': new_net}
            if old_net:
                migrations.setdefault(old_net, []).append(entry)
            elif new_net:
                gains.append(entry)
    return migrations, gains


def apply_net_restructure(content: str, schematic_path: str,
                          original: Dict[str, Any], modified: Dict[str, Any]
                          ) -> Tuple[str, List[str], List[Dict[str, Any]]]:
    """Clear-and-stub pass for nets whose pin assignments changed.

    For each original net that loses member pins: remove ALL its wires,
    junctions and labels, then place a stub (wire + label) on every former
    member pin carrying its NEW net name. Previously unconnected pins that
    gained a net receive a stub as well.
    """
    changes: List[str] = []
    warnings: List[Dict[str, Any]] = []
    migrations, gains = analyze_net_migrations(original, modified)
    if not migrations and not gains:
        return content, changes, warnings

    wires, junctions = build_wire_topology(schematic_path)

    # Original pin table: (uuid, pin) -> (net, reference, position)
    orig_pin_table: Dict[Tuple[str, str], Tuple[str, str, Tuple[float, float]]] = {}
    for comp in original.get('components', []):
        ref = comp.get('reference', '')
        for pin in comp.get('pins', []):
            pos = pin.get('position') or {}
            orig_pin_table[(comp.get('uuid', ''), str(pin.get('number')))] = (
                pin.get('net', ''), ref, (pos.get('x', 0.0), pos.get('y', 0.0)))

    mod_net: Dict[Tuple[str, str], str] = {}
    mod_uuids = set()
    for comp in modified.get('components', []):
        mod_uuids.add(comp.get('uuid', ''))
        for pin in comp.get('pins', []):
            mod_net[(comp.get('uuid', ''), str(pin.get('number')))] = pin.get('net', '')

    stub_blocks: List[str] = []

    for origin_net, moved in migrations.items():
        all_members = [(k, v) for k, v in orig_pin_table.items() if v[0] == origin_net]
        surviving = [(k, v) for k, v in all_members if k[0] in mod_uuids]

        # Power symbols anchor their net — they cannot be moved to a new net.
        moved_refs = {m['reference'] for m in moved}
        power_moved = [v[1] for k, v in all_members
                       if v[1].startswith('#PWR') and v[1] in moved_refs]
        if power_moved:
            warnings.append({
                "type": "power_anchor_move",
                "net": origin_net,
                "components": power_moved,
                "message": f"⚠ Power symbol(s) {', '.join(power_moved)} anchor net "
                           f"'{origin_net}' and cannot be moved. Net restructure skipped.",
                "action_required": "fix_net_assignment"
            })
            changes.append(f"WARNING: net '{origin_net}' restructure skipped (power anchor move)")
            continue

        seeds = [v[2] for k, v in all_members]
        island, island_junctions = collect_net_island(seeds, wires, junctions)
        island_uuids = {wires[i]['uuid'] for i in island}

        # Directions from the OLD wiring (computed before removal)
        directions: Dict[Tuple[str, str], Optional[Tuple[float, float]]] = {}
        for (cuuid, pnum), (net, ref, pos) in surviving:
            directions[(cuuid, pnum)] = _direction_from_island(pos, wires, island)

        content, n_wires, n_junc, n_labels = remove_net_geometry(
            content, island_uuids, island_junctions, {origin_net})

        stubbed: List[str] = []
        for (cuuid, pnum), (net, ref, pos) in surviving:
            if ref.startswith('#PWR'):
                continue  # power symbols need no stub — they anchor the net
            new_net = mod_net.get((cuuid, pnum), origin_net)
            if not new_net:
                changes.append(f"  disconnected {ref}.{pnum} (was '{origin_net}')")
                continue
            d = directions.get((cuuid, pnum))
            pos_ok = pos and pos != (0.0, 0.0)
            if d is None or not pos_ok:
                geom = _pin_geometry_from_content(content, cuuid, pnum)
                if geom:
                    if not pos_ok:
                        pos = geom[0]
                    if d is None:
                        d = geom[1]
            if d is None:
                d = (0.0, -1.0)
            stub_blocks.extend(_make_stub(pos, d, new_net))
            stubbed.append(f"{ref}.{pnum} → '{new_net}'")

        changes.append(
            f"Net '{origin_net}' restructured: removed {n_wires} wires, "
            f"{n_junc} junctions, {n_labels} labels; placed {len(stubbed)} stubs")
        for s in stubbed:
            changes.append(f"  stub {s}")

    # Pins that gained a net from unconnected state: stub only, no clearing.
    for g in gains:
        geom = _pin_geometry_from_content(content, g['uuid'], g['pin'])
        if geom is None:
            warnings.append({
                "type": "stub_failed",
                "component": g['reference'],
                "message": f"⚠ Could not locate {g['reference']}.{g['pin']} to place stub "
                           f"for net '{g['new_net']}'.",
                "action_required": "wire_manually"
            })
            continue
        stub_blocks.extend(_make_stub(geom[0], geom[1], g['new_net']))
        changes.append(f"  stub {g['reference']}.{g['pin']} → '{g['new_net']}' (was unconnected)")

    content = _append_blocks_after_last_symbol(content, stub_blocks)
    return content, changes, warnings


# ---------------------------------------------------------------------------
# Library symbol embedding
#
# KiCad schematics embed every used symbol in (lib_symbols ...). When the AI
# adds a component whose libId is not embedded yet, resolve it against the
# user's symbol libraries (sym-lib-table → .kicad_sym) and embed a copy.
# If the symbol cannot be found, emit a warning — the legitimate case where
# the user must import/provide the library in KiCad first.
# ---------------------------------------------------------------------------

def _ensure_kicad_env() -> None:
    """Populate KICAD*_SYMBOL_DIR env vars (mirrors the parser's setup)."""
    for base in ['/Applications/KiCad/KiCad.app/Contents/SharedSupport',
                 '/usr/share/kicad', '/usr/local/share/kicad']:
        symbols_path = os.path.join(base, 'symbols')
        if os.path.isdir(symbols_path):
            for version in ['6', '7', '8', '9', '10', '']:
                prefix = f'KICAD{version}_' if version else 'KICAD_'
                os.environ.setdefault(f'{prefix}SYMBOL_DIR', symbols_path)
            break


def _resolve_symbol_library(nickname: str, schematic_dir: str) -> Optional[str]:
    """Map a library nickname to a .kicad_sym path via sym-lib-table or heuristics."""
    _ensure_kicad_env()
    tables: List[str] = []
    project_table = os.path.join(schematic_dir, 'sym-lib-table')
    if os.path.exists(project_table):
        tables.append(project_table)
    pref_root = os.path.expanduser('~/Library/Preferences/kicad')
    if os.path.isdir(pref_root):
        for ver in sorted(os.listdir(pref_root), reverse=True):
            t = os.path.join(pref_root, ver, 'sym-lib-table')
            if os.path.exists(t):
                tables.append(t)
    for table in tables:
        try:
            with open(table, 'r', encoding='utf-8') as f:
                txt = f.read()
        except OSError:
            continue
        m = re.search(r'\(lib\s+\(name\s+"' + re.escape(nickname) + r'"\).*?\(uri\s+"([^"]+)"\)',
                      txt, re.S)
        if m:
            uri = m.group(1)
            uri = re.sub(r'\$\{([^}]+)\}', lambda mm: os.environ.get(mm.group(1), mm.group(0)), uri)
            uri = re.sub(r'\$\(([^)]+)\)', lambda mm: os.environ.get(mm.group(1), mm.group(0)), uri)
            if os.path.exists(uri):
                return uri
    # Heuristic: <nickname.lower()>.kicad_sym in the KiCad symbol dir
    for key, val in os.environ.items():
        if key.endswith('SYMBOL_DIR') and os.path.isdir(val):
            cand = os.path.join(val, nickname.lower() + '.kicad_sym')
            if os.path.exists(cand):
                return cand
    return None


def _extract_symbol_entry(sym_file: str, entry_name: str, lib_id: str) -> Optional[str]:
    """Extract a top-level (symbol "<entry>" ...) block from a .kicad_sym file
    and rename it to the full lib_id for embedding in lib_symbols."""
    try:
        with open(sym_file, 'r', encoding='utf-8') as f:
            txt = f.read()
    except OSError:
        return None
    # Top-level entries are indented with exactly one tab
    m = re.search(r'(?m)^\t\(symbol\s+"' + re.escape(entry_name) + r'"(?=[\s)])', txt)
    if not m:
        return None
    start = m.start()
    depth = 0
    end = start
    for i in range(start, len(txt)):
        if txt[i] == '(':
            depth += 1
        elif txt[i] == ')':
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    block = txt[start:end]
    # Dedent one tab (lib file base indent) so the block starts at column 0
    lines = block.split('\n')
    dedented = '\n'.join(l[1:] if l.startswith('\t') else l for l in lines)
    dedented = dedented.replace(f'(symbol "{entry_name}"', f'(symbol "{lib_id}"', 1)
    return dedented


def _insert_into_lib_symbols(content: str, lib_block: str) -> str:
    """Insert a library symbol block into the schematic's lib_symbols section."""
    m = re.search(r'\(lib_symbols', content)
    if not m:
        return content
    depth = 0
    end = None
    for i in range(m.start(), len(content)):
        if content[i] == '(':
            depth += 1
        elif content[i] == ')':
            depth -= 1
            if depth == 0:
                end = i
                break
    if end is None:
        return content
    insertion = '\n\t\t' + lib_block.replace('\n', '\n\t') + '\n\t'
    return content[:end] + insertion + content[end:]


def ensure_lib_symbol_embedded(content: str, lib_id: str,
                               schematic_dir: str) -> Tuple[str, bool, str]:
    """Ensure lib_id is present in the schematic's lib_symbols section.

    Returns (content, success, message). On failure the content is unchanged
    and the message explains what to do (import the library in KiCad).
    """
    if find_lib_symbol_block(content, lib_id) is not None:
        return content, True, 'already embedded'
    if ':' in lib_id:
        nickname, entry_name = lib_id.split(':', 1)
    else:
        nickname, entry_name = '', lib_id
    sym_file = _resolve_symbol_library(nickname, schematic_dir) if nickname else None
    if not sym_file:
        return content, False, (f"no symbol library found for nickname '{nickname}' — "
                                f"add it to KiCad's symbol library table")
    block = _extract_symbol_entry(sym_file, entry_name, lib_id)
    if block is None:
        return content, False, f"symbol '{entry_name}' not found in {sym_file}"
    if '(extends' in block:
        return content, False, (f"symbol '{lib_id}' uses library inheritance (extends) "
                                f"which is not yet supported for embedding")
    content = _insert_into_lib_symbols(content, block)
    return content, True, f"embedded from {sym_file}"


def apply_component_addition_text(content: str, added_components: List[Dict[str, Any]],
                                   schematic_dir: str,
                                   original_json: Optional[Dict[str, Any]] = None) -> Tuple[str, List[str], List[Dict[str, Any]]]:
    """
    Add components using text-based editing.

    Each new component is placed at a staging area and every connected pin
    receives a stub (short wire + net label), so the schematic is electrically
    complete by label-name connectivity alone. Missing library symbols are
    embedded from the user's KiCad symbol libraries when possible.

    For pins connected to UNNAMED nets (parser-assigned names like N$5), this
    function also adds labels to the existing wire network to ensure proper
    electrical connectivity. Without this, a new component's stub labels would
    create SEPARATE nets instead of connecting to the existing wire network.

    Args:
        content: KiCad schematic text
        added_components: List of components to add
        schematic_dir: Directory for library lookups
        original_json: Original schematic JSON (needed to find wire networks for unnamed nets)

    Returns (modified_content, list_of_changes_applied, list_of_warnings).
    """
    changes_applied: List[str] = []
    warnings: List[Dict[str, Any]] = []

    # Embed missing library symbols FIRST — the insertion shifts all later
    # offsets, so it must happen before we locate the append point.
    lib_failures: Dict[str, str] = {}
    for comp in added_components:
        lib_id = comp.get('libId', '')
        if not lib_id or lib_id in lib_failures:
            continue
        if find_lib_symbol_block(content, lib_id) is None:
            content, ok, msg = ensure_lib_symbol_embedded(content, lib_id, schematic_dir)
            if ok:
                changes_applied.append(f"Embedded library symbol '{lib_id}' ({msg})")
            else:
                lib_failures[lib_id] = msg

    # Find the last symbol instance in KiCad 10 format
    last_symbol = find_symbol_instances_section(content)

    if last_symbol == (0, 0, ''):
        changes_applied.append("ERROR: Could not find any existing symbols to append after")
        return content, changes_applied, warnings

    last_symbol_start, last_symbol_end, last_symbol_block = last_symbol

    # Find bounding box of existing symbols for staging position
    min_x, min_y, max_x, max_y = find_existing_symbols_bounds(content)

    # Staging position: offset from the right edge of existing components
    staging_offset = 25.4  # 25.4mm = 1 inch in KiCad units
    staging_x = max_x + staging_offset
    staging_y = min_y

    for comp in added_components:
        lib_id = comp.get('libId', '')
        reference = comp.get('reference', 'U?')
        # Top-level 'value' wins (same precedence as compute_delta);
        # properties.Value may be stale in hand/LLM-edited JSON.
        value = comp.get('value', comp.get('properties', {}).get('Value', ''))
        uuid = comp.get('uuid', generate_uuid())
        connections = comp.get('connections', {})  # {"1": "net_name", "2": "GND"}
        if not connections:
            # JSON state contract: nets live on pins[] — derive the map
            connections = {
                str(p.get('number')): p.get('net')
                for p in comp.get('pins', [])
                if p.get('net')
            }

        # Library symbol must exist (embedded above or already present)
        if lib_id in lib_failures:
            warnings.append({
                "type": "missing_library_symbol",
                "component": reference,
                "message": f"⚠ {reference}: library symbol '{lib_id}' could not be embedded "
                           f"({lib_failures[lib_id]}). Import it in KiCad, then re-apply.",
                "action_required": "import_symbol"
            })
            changes_applied.append(f"WARNING: {reference} skipped - {lib_failures[lib_id]}")
            continue

        lib_symbol = find_lib_symbol_block(content, lib_id)
        if lib_symbol is None:
            changes_applied.append(f"WARNING: Library symbol '{lib_id}' not found unexpectedly.")
            continue

        start, end, lib_symbol_block = lib_symbol

        # Calculate staging position (offset for each new component)
        position = (staging_x, staging_y)
        staging_y += staging_offset  # Move down for next component

        # Create symbol instance
        try:
            instance = create_symbol_instance(
                lib_symbol_block,
                new_uuid=uuid,
                reference=reference,
                value=value,
                position=position
            )
        except ValueError as e:
            changes_applied.append(f"WARNING: Could not create instance for {reference}: {e}")
            continue

        # Append an (instances ...) block cloned from an existing symbol —
        # KiCad requires it for the instance to belong to the sheet/project.
        if last_symbol_block:
            im = re.search(r'\(instances', last_symbol_block)
            if im:
                depth = 0
                iend = im.start()
                for i in range(im.start(), len(last_symbol_block)):
                    if last_symbol_block[i] == '(':
                        depth += 1
                    elif last_symbol_block[i] == ')':
                        depth -= 1
                        if depth == 0:
                            iend = i + 1
                            break
                inst_block = last_symbol_block[im.start():iend]
                inst_block = re.sub(r'\(reference\s+"[^"]*"\)',
                                    f'(reference "{reference}")', inst_block, count=1)
                tail = instance.rfind('\n')
                instance = (instance[:tail] + '\n\t\t'
                            + inst_block.replace('\n', '\n\t') + instance[tail:])

        # Insert after the last symbol instance
        insert_pos = last_symbol_end
        indented_instance = '\n\t' + instance.replace('\n', '\n\t')
        content = content[:insert_pos] + indented_instance + content[insert_pos:]
        last_symbol_end = insert_pos + len(indented_instance)

        changes_applied.append(f"Added {reference} ({lib_id}) at staging position "
                               f"({position[0]:.1f}, {position[1]:.1f})")

        # Stub every connected pin: short wire from the pin + label at its end.
        # Staged instances are unrotated (angle 0), so pin offsets apply directly.
        #
        # For UNNAMED nets (N$X pattern), we must first establish the label on
        # the existing wire network. Otherwise, the stub's label creates a NEW
        # net instead of connecting to the existing wire network.
        if connections:
            pin_defs = extract_pin_definitions(lib_symbol_block)
            stub_blocks: List[str] = []
            
            # Track unnamed nets we've already labeled to avoid duplicates
            labeled_unnamed_nets = set()
            
            for pin_num, net_name in connections.items():
                if not net_name:
                    continue
                    
                # For unnamed nets, add label to existing wire network FIRST
                if original_json and _is_unnamed_net(net_name) and net_name not in labeled_unnamed_nets:
                    positions = _find_wire_network_positions(original_json, net_name)
                    if positions:
                        # Place label at first pin position on this net
                        # This establishes the net name on the existing wire network
                        # IMPORTANT: Place label AT the pin position (on the wire endpoint)
                        # so the parser recognizes it as connected to the same net
                        label_pos = positions[0]
                        label_block = create_net_label(net_name, label_pos)
                        content = _append_blocks_after_last_symbol(content, [label_block])
                        labeled_unnamed_nets.add(net_name)
                        changes_applied.append(f"Label '{net_name}' placed on existing wire network at ({label_pos[0]:.1f}, {label_pos[1]:.1f})")
                    else:
                        changes_applied.append(f"WARNING: No positions found for unnamed net '{net_name}'")
                elif original_json and _is_unnamed_net(net_name):
                    # Already labeled this net (duplicate connection to same net)
                    pass
                
                pd = pin_defs.get(str(pin_num))
                if pd:
                    # Negate Y: library coords are Y-UP, schematic coords are Y-DOWN
                    pin_abs = (position[0] + pd[0], position[1] - pd[1])
                    direction = _stub_direction_from_lib_angle(pd[2])
                else:
                    pin_abs = (position[0], position[1])
                    direction = (1.0, 0.0)
                stub_blocks.extend(_make_stub(pin_abs, direction, net_name))
                changes_applied.append(f"Stub {reference}.{pin_num} → '{net_name}'")
            
            content = _append_blocks_after_last_symbol(content, stub_blocks)

    return content, changes_applied, warnings




def apply_component_removal_text(content: str, removed_components: List[Dict[str, Any]], 
                                  original_json: Dict[str, Any]) -> Tuple[str, List[str]]:
    """
    Remove components using text-based editing.
    
    Also removes orphaned wires and junctions connected only to removed components.
    
    Returns (modified_content, list_of_changes_applied).
    """
    changes_applied = []
    
    # Build a map of component UUIDs to their pin positions from original JSON
    comp_pin_positions = {}
    for comp in original_json.get('components', []):
        comp_uuid = comp['uuid']
        pins = comp.get('pins', [])
        pin_positions = [(p['position']['x'], p['position']['y']) for p in pins]
        comp_pin_positions[comp_uuid] = pin_positions
    
    # Collect all pin positions from removed components
    removed_pin_positions = set()
    
    for change in removed_components:
        uuid = change['uuid']
        reference = change.get('reference', 'unknown')
        
        # Find the symbol block
        result = find_symbol_block(content, uuid)
        if result is None:
            changes_applied.append(f"WARNING: Could not find symbol {reference} ({uuid})")
            continue
        
        start_pos, end_pos, symbol_block = result
        
        # Get pin positions from JSON (more reliable than parsing symbol)
        if uuid in comp_pin_positions:
            for pos in comp_pin_positions[uuid]:
                # Round to 2 decimal places for matching
                removed_pin_positions.add((round(pos[0], 2), round(pos[1], 2)))
        
        # Remove the symbol block
        content = content[:start_pos] + content[end_pos:]
        changes_applied.append(f"Removed {reference}")
    
    # Find and remove orphaned wires
    # A wire is orphaned if ALL its endpoints are at removed pin positions
    wires = find_wire_blocks(content)
    orphan_wires = []
    
    # Sort by position descending (remove from end to preserve positions)
    for start, end, block, points in sorted(wires, key=lambda w: w[0], reverse=True):
        # Check if all wire endpoints are at removed pin positions
        all_orphan = all(
            (round(pt[0], 2), round(pt[1], 2)) in removed_pin_positions
            for pt in points
        )
        if all_orphan:
            orphan_wires.append((start, end))
    
    # Remove orphaned wires (from end to preserve positions)
    for start, end in orphan_wires:
        content = content[:start] + content[end:]
    
    if orphan_wires:
        changes_applied.append(f"Removed {len(orphan_wires)} orphan wire(s)")
    
    # Find and remove orphaned junctions at removed pin positions
    junctions = find_junction_blocks(content)
    orphan_junctions = []
    
    for start, end, block, pos in sorted(junctions, key=lambda j: j[0], reverse=True):
        pos_rounded = (round(pos[0], 2), round(pos[1], 2))
        if pos_rounded in removed_pin_positions:
            orphan_junctions.append((start, end))
    
    # Remove orphaned junctions
    for start, end in orphan_junctions:
        content = content[:start] + content[end:]
    
    if orphan_junctions:
        changes_applied.append(f"Removed {len(orphan_junctions)} orphan junction(s)")
    
    return content, changes_applied


def apply_delta_to_schematic(schematic_path: str, delta: Dict[str, Any], 
                             output_path: Optional[str] = None,
                             original_json: Optional[Dict[str, Any]] = None,
                             modified_json: Optional[Dict[str, Any]] = None) -> Tuple[bool, List[str], List[Dict[str, Any]]]:
    """
    Apply delta changes to KiCad schematic file using TEXT-BASED editing.
    
    This preserves all KiCad 10 properties that kiutils would strip.
    
    Args:
        schematic_path: Path to .kicad_sch file
        delta: Delta object from compute_delta()
        output_path: Optional output path (default: overwrite original)
        original_json: Original JSON (needed for component removal to get pin positions)
        modified_json: Modified JSON (needed for component addition to get new component data)
    
    Returns:
        Tuple of (success: bool, changes_applied: List[str], warnings: List[Dict])
    """
    try:
        # Read the schematic file as text
        with open(schematic_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        changes_applied = []
        warnings = []
        
        # 1. Apply value changes using text-based editing
        if delta.get('value_changes'):
            content, value_changes = apply_value_changes_text(content, delta['value_changes'])
            changes_applied.extend(value_changes)
        
        # 2. Handle removed components (text-based removal)
        if delta.get('removed_components'):
            if original_json is None:
                changes_applied.append("WARNING: original_json required for component removal")
            else:
                content, removal_changes = apply_component_removal_text(
                    content, delta['removed_components'], original_json
                )
                changes_applied.extend(removal_changes)
        
        # 3. Net restructuring (stub pass): for every original net that loses
        #    member pins (series insertion / re-wiring), strip its wires,
        #    junctions and labels, then give every former member pin a stub
        #    (wire + label) carrying its NEW net name. Previously unconnected
        #    pins that gained a net receive a stub as well.
        if original_json is not None and modified_json is not None:
            content, restructure_changes, restructure_warnings = apply_net_restructure(
                content, schematic_path, original_json, modified_json
            )
            changes_applied.extend(restructure_changes)
            warnings.extend(restructure_warnings)

        # 4. Handle added components (staging placement + stub connections,
        #    with automatic library symbol embedding)
        if delta.get('added_components'):
            content, addition_changes, addition_warnings = apply_component_addition_text(
                content, delta['added_components'],
                os.path.dirname(os.path.abspath(schematic_path)),
                original_json=original_json  # Needed for unnamed net labeling
            )
            changes_applied.extend(addition_changes)
            warnings.extend(addition_warnings)

        # 5. Connection changes were realized by the restructure pass (step 3)
        for change in delta.get('connection_changes', []):
            changes_applied.append(
                f"Reconnect {change['reference']}.{change['pin']}: "
                f"{change['old_net'] or '(unconnected)'} → {change['new_net']} (stub)"
            )
        
        # 6. Apply simulation directive changes
        if delta.get('simulation_changes'):
            content, sim_changes = apply_simulation_changes(content, delta['simulation_changes'])
            changes_applied.extend(sim_changes)
        
        # Create backup before saving
        backup_path = schematic_path + '.bak'
        if os.path.exists(schematic_path):
            shutil.copy2(schematic_path, backup_path)
        
        # Save modified schematic (text-based, preserves all formatting)
        save_path = output_path if output_path else schematic_path
        with open(save_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return True, changes_applied, warnings
        
    except Exception as e:
        print(f"Error applying delta: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return False, [f"Error: {e}"], []


def validate_state_integrity(state: Dict[str, Any], label: str) -> List[str]:
    """
    Validate JSON state integrity BEFORE delta computation.

    compute_delta() keys components by uuid, so a duplicated component uuid
    (e.g. hand-copying R2's block to add R3) silently reclassifies the new
    component as a value change on the EXISTING symbol: the addition is
    dropped without warning and the existing symbol's value is corrupted
    (root cause of the UT-06 failure, 2026-07-31).

    Returns a list of human-readable violation messages (empty if valid).
    """
    errors: List[str] = []
    components = state.get('components', [])

    # 1. Components must have reference and uuid
    for idx, comp in enumerate(components):
        if not comp.get('reference'):
            errors.append(f"[{label}] component at index {idx} is missing 'reference'")
        if not comp.get('uuid'):
            errors.append(
                f"[{label}] component '{comp.get('reference', f'index {idx}')}' is missing 'uuid'"
            )

    # 2. Duplicate component references
    ref_counts: Dict[str, int] = {}
    for comp in components:
        ref = comp.get('reference', '<missing>')
        ref_counts[ref] = ref_counts.get(ref, 0) + 1
    for ref, count in ref_counts.items():
        if count > 1:
            errors.append(f"[{label}] duplicate component reference '{ref}' ({count} occurrences)")

    # 3. Duplicate component uuids
    uuid_to_refs: Dict[str, List[str]] = {}
    for comp in components:
        cuuid = comp.get('uuid', '<missing>')
        uuid_to_refs.setdefault(cuuid, []).append(comp.get('reference', '<missing>'))
    for cuuid, refs in uuid_to_refs.items():
        if len(refs) > 1:
            errors.append(
                f"[{label}] duplicate component uuid '{cuuid}' shared by references: {', '.join(refs)}"
            )

    # 4. Duplicate pin uuids (must be unique across the whole state)
    pin_uuid_to_owner: Dict[str, str] = {}
    for comp in components:
        ref = comp.get('reference', '<missing>')
        for pin in comp.get('pins', []):
            puuid = pin.get('uuid')
            if not puuid:
                continue
            owner = f"{ref}.{pin.get('number', '?')}"
            if puuid in pin_uuid_to_owner:
                errors.append(
                    f"[{label}] duplicate pin uuid '{puuid}' shared by "
                    f"{pin_uuid_to_owner[puuid]} and {owner}"
                )
            else:
                pin_uuid_to_owner[puuid] = owner

    return errors


def _new_uuid() -> str:
    return str(uuid_module.uuid4())


def repair_state_integrity(
    state: Dict[str, Any],
    original: Optional[Dict[str, Any]],
    label: str
) -> Tuple[List[str], List[str]]:
    """
    Attempt to auto-repair integrity violations in `state` (mutates in place).

    Repairable:
      - missing component/pin uuids          -> assign fresh uuid
      - duplicate component uuids            -> keep the "rightful owner" (the
        component whose reference matches the original state's reference for
        that uuid, else the first occurrence); assign fresh component AND pin
        uuids to the others
      - duplicate pin uuids                  -> assign fresh uuid to later uses

    Not repairable (ambiguous identity):
      - missing or duplicate component references

    Returns (repairs, unfixable_errors).
    """
    repairs: List[str] = []
    unfixable: List[str] = []
    components = state.get('components', [])

    # --- references cannot be auto-repaired ---
    ref_counts: Dict[str, int] = {}
    for comp in components:
        ref = comp.get('reference')
        if not ref:
            unfixable.append(f"[{label}] component missing 'reference' — cannot auto-repair")
        else:
            ref_counts[ref] = ref_counts.get(ref, 0) + 1
    for ref, count in ref_counts.items():
        if count > 1:
            unfixable.append(
                f"[{label}] duplicate component reference '{ref}' ({count} occurrences) — cannot auto-repair"
            )
    if unfixable:
        return repairs, unfixable

    orig_ref_by_uuid = {
        c.get('uuid'): c.get('reference')
        for c in (original or {}).get('components', [])
    }

    # --- pass 1: duplicated component uuids ---
    by_uuid: Dict[str, List[Dict[str, Any]]] = {}
    for comp in components:
        by_uuid.setdefault(comp.get('uuid') or '', []).append(comp)

    for cuuid, comps in by_uuid.items():
        if not cuuid or len(comps) <= 1:
            continue
        orig_ref = orig_ref_by_uuid.get(cuuid)
        owner = next((c for c in comps if c.get('reference') == orig_ref), comps[0])
        for comp in comps:
            if comp is owner:
                continue
            comp['uuid'] = _new_uuid()
            for pin in comp.get('pins', []):
                pin['uuid'] = _new_uuid()
            repairs.append(
                f"[{label}] assigned fresh component+pin uuids to '{comp.get('reference')}' "
                f"(previously duplicated uuid of '{owner.get('reference')}')"
            )

    # --- pass 2: missing uuids + duplicate pin uuids ---
    seen_comp_uuids = set()
    seen_pin_uuids = set()
    for comp in components:
        ref = comp.get('reference')
        if not comp.get('uuid'):
            comp['uuid'] = _new_uuid()
            repairs.append(f"[{label}] assigned fresh uuid to component '{ref}' (was missing)")
        if comp['uuid'] in seen_comp_uuids:  # safety net, should not trigger after pass 1
            comp['uuid'] = _new_uuid()
            repairs.append(f"[{label}] assigned fresh uuid to component '{ref}' (duplicate)")
        seen_comp_uuids.add(comp['uuid'])

        for pin in comp.get('pins', []):
            owner = f"{ref}.{pin.get('number', '?')}"
            if not pin.get('uuid'):
                pin['uuid'] = _new_uuid()
                repairs.append(f"[{label}] assigned fresh uuid to pin {owner} (was missing)")
            elif pin['uuid'] in seen_pin_uuids:
                pin['uuid'] = _new_uuid()
                repairs.append(f"[{label}] assigned fresh uuid to pin {owner} (duplicate)")
            seen_pin_uuids.add(pin['uuid'])

    return repairs, unfixable


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
    repair_mode = '--repair' in sys.argv[4:]

    # Load JSON states
    original = load_json(original_path)
    modified = load_json(modified_path)

    # Validate integrity BEFORE computing the delta. Duplicate uuids or
    # references silently corrupt the result (see docs/architecture.md §4.4).
    original_errors = validate_state_integrity(original, 'original')
    modified_errors = validate_state_integrity(modified, 'modified')

    # --repair: attempt to auto-repair the MODIFIED state (fresh uuids for
    # hand/LLM-added components). The original baseline is never repaired —
    # it must stay exactly as parsed from KiCad.
    repairs: List[str] = []
    if modified_errors and repair_mode and not original_errors:
        repairs, unfixable = repair_state_integrity(modified, original, 'modified')
        if unfixable:
            print(json.dumps({
                "status": "error",
                "error": "integrity_validation_failed",
                "message": "JSON state has integrity problems that cannot be auto-repaired; delta NOT applied.",
                "violations": unfixable
            }, indent=2))
            sys.exit(3)
        modified_errors = validate_state_integrity(modified, 'modified')
        if not modified_errors:
            # Persist repaired state so the extension's JSON stays consistent
            with open(modified_path, 'w', encoding='utf-8') as f:
                json.dump(modified, f, indent=2)

    integrity_errors = original_errors + modified_errors
    if integrity_errors:
        print(json.dumps({
            "status": "error",
            "error": "integrity_validation_failed",
            "message": "JSON state failed integrity validation; delta NOT applied. "
                       "Assign fresh uuids to hand-added components and ensure "
                       "references are unique.",
            "violations": integrity_errors
        }, indent=2))
        sys.exit(3)

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
    
    # Apply delta (pass original JSON for component removal, modified JSON for addition)
    success, changes_log, warnings = apply_delta_to_schematic(kicad_path, delta, original_json=original, modified_json=modified)
    
    if success:
        # Return summary
        print(json.dumps({
            "status": "success",
            "changes_applied": len(changes_log),
            "changes": changes_log,
            "warnings": warnings,
            "repairs": repairs,
            "delta": delta,
            "backup": kicad_path + '.bak'
        }, indent=2))
        sys.exit(0)
    else:
        print(json.dumps({
            "status": "error",
            "message": "Failed to apply delta",
            "changes": changes_log,
            "warnings": warnings
        }))
        sys.exit(1)


if __name__ == "__main__":
    main()