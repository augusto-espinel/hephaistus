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
    """
    min_x, min_y = float('inf'), float('inf')
    max_x, max_y = float('-inf'), float('-inf')
    
    # Find all (at x y angle) within symbol instances
    # Symbol instances are (symbol (lib_id ...)) blocks
    at_pattern = r'\(at\s+([\d.\-]+)\s+([\d.\-]+)\s+[\d.\-]+\)'
    
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
        
        # Extract positions from this symbol block
        symbol_block = content[start:end]
        for at_match in re.finditer(at_pattern, symbol_block):
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
    4. Preserves all KiCad 10 properties
    
    Note: This creates a STUB - user must wire in KiCad.
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
    instance = f'''(symbol
		(lib_id "{lib_id}")
		(at {position[0]:.2f} {position[1]:.2f} 0)
		(uuid "{new_uuid}")
		(property "Reference" "{reference}"
			(at {position[0]:.2f} {position[1] + 1.27:.2f} 0)
			(show_name no)
			(do_not_autoplace no)
			(effects
				(font
					(size 1.27 1.27)
				)
			)
		)
		(property "Value" "{value}"
			(at {position[0]:.2f} {position[1] - 1.27:.2f} 0)
			(show_name no)
			(do_not_autoplace no)
			(effects
				(font
					(size 1.27 1.27)
				)
			)
		)
		(property "Footprint" ""
			(at {position[0]:.2f} {position[1]:.2f} 0)
			(show_name no)
			(do_not_autoplace no)
			(hide yes)
			(effects
				(font
					(size 1.27 1.27)
				)
			)
		)
		(property "Datasheet" ""
			(at {position[0]:.2f} {position[1]:.2f} 0)
			(show_name no)
			(do_not_autoplace no)
			(hide yes)
			(effects
				(font
					(size 1.27 1.27)
				)
			)
		)
		(in_bom yes)
		(on_board yes)
		(dnp no)
		(fields_autoplaced yes)
	)'''
    
    return instance


def extract_existing_nets(json_state: Dict[str, Any]) -> set:
    """
    Extract all net names from the JSON state.
    
    Returns a set of net names.
    """
    nets = set()
    for wire in json_state.get('wires', []):
        if 'net' in wire:
            nets.add(wire['net'])
    for junction in json_state.get('junctions', []):
        if 'net' in junction:
            nets.add(junction['net'])
    for comp in json_state.get('components', []):
        for pin in comp.get('pins', []):
            if 'net' in pin and pin['net']:
                nets.add(pin['net'])
    return nets


def extract_nets_with_labels(content: str) -> set:
    """
    Extract nets that currently have labels in the KiCad schematic.
    
    Returns a set of net names that have labels.
    """
    nets_with_labels = set()
    
    # Find all (label "net_name" ...) blocks
    label_pattern = r'\(label\s+"([^"]+)"'
    for match in re.finditer(label_pattern, content):
        nets_with_labels.add(match.group(1))
    
    # Also check global labels
    global_label_pattern = r'\(global_label\s+"([^"]+)"'
    for match in re.finditer(global_label_pattern, content):
        nets_with_labels.add(match.group(1))
    
    # Check hierarchical labels
    hier_label_pattern = r'\(hierarchical_label\s+"([^"]+)"'
    for match in re.finditer(hier_label_pattern, content):
        nets_with_labels.add(match.group(1))
    
    return nets_with_labels


def detect_series_insertion(connections: Dict[str, str], existing_nets: set) -> Tuple[bool, Optional[str]]:
    """
    Detect if component insertion requires breaking existing net.
    
    Series insertion: All pins connect to the same existing net.
    This means the user needs to break the net and insert component.
    
    Returns: (is_series_insertion, net_name_if_series)
    """
    if not connections:
        return False, None
    
    unique_nets = set(connections.values())
    
    # If all pins connect to same existing net → series insertion
    if len(unique_nets) == 1:
        net_name = unique_nets.pop()
        if net_name in existing_nets:
            return True, net_name
    
    return False, None


def detect_missing_labels(connections: Dict[str, str], 
                          existing_nets: set,
                          nets_with_labels: set) -> Tuple[bool, List[str]]:
    """
    Detect if component connects to nets that don't have labels.
    
    Parallel insertion: Different pins to different nets.
    If any of those nets exist but don't have labels, user needs to add them.
    
    Returns: (needs_labels, list_of_nets_missing_labels)
    """
    if not connections:
        return False, []
    
    unique_nets = set(connections.values())
    missing_labels = []
    
    for net in unique_nets:
        if net in existing_nets and net not in nets_with_labels:
            missing_labels.append(net)
    
    return len(missing_labels) > 0, missing_labels


def create_text_annotation(text: str, position: Tuple[float, float], 
                            uuid_str: str = None, font_size: float = 1.5) -> str:
    """
    Create a KiCad text annotation (non-electrical text).
    
    Used for warnings and hints in the schematic.
    """
    if uuid_str is None:
        uuid_str = str(__import__('uuid').uuid4())
    
    # Escape special characters for S-expression
    escaped_text = text.replace('"', '\\"').replace('\n', '\\n')
    
    return f'''(text "{escaped_text}"
	(at {position[0]:.2f} {position[1]:.2f} 0)
	(effects
		(font
			(size {font_size} {font_size})
			(thickness 0.3)
		)
		(justify left)
	)
	(uuid "{uuid_str}")
)'''


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


def find_existing_nets_from_json(content: str) -> set:
    """
    Extract existing net names from a KiCad schematic file.
    
    Returns a set of net names found in labels.
    """
    nets = set()
    
    # Find all (label "net_name" ...) blocks
    label_pattern = r'\(label\s+"([^"]+)"'
    for match in re.finditer(label_pattern, content):
        nets.add(match.group(1))
    
    # Also check global labels
    global_label_pattern = r'\(global_label\s+"([^"]+)"'
    for match in re.finditer(global_label_pattern, content):
        nets.add(match.group(1))
    
    # Check hierarchical labels
    hier_label_pattern = r'\(hierarchical_label\s+"([^"]+)"'
    for match in re.finditer(hier_label_pattern, content):
        nets.add(match.group(1))
    
    return nets


def apply_component_addition_text(content: str, added_components: List[Dict[str, Any]],
                                   modified_json: Dict[str, Any]) -> Tuple[str, List[str], List[Dict[str, Any]]]:
    """
    Add components using text-based editing.
    
    Creates STUB connections with net labels - user must verify connections.
    Detects series insertions and missing labels, adds warning annotations.
    
    Returns (modified_content, list_of_changes_applied, list_of_warnings).
    """
    changes_applied = []
    warnings = []
    
    # Extract existing nets from both JSON and schematic
    existing_nets_json = extract_existing_nets(modified_json)
    existing_nets_sch = find_existing_nets_from_json(content)
    existing_nets = existing_nets_json | existing_nets_sch
    
    # Extract nets that already have labels
    nets_with_labels = extract_nets_with_labels(content)
    
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
    
    # Track where to insert annotations (after all components)
    annotations = []
    
    for comp in added_components:
        lib_id = comp.get('libId', '')
        reference = comp.get('reference', 'U?')
        value = comp.get('properties', {}).get('Value', comp.get('value', ''))
        uuid = comp.get('uuid', generate_uuid())
        connections = comp.get('connections', {})  # {"1": "net_name", "2": "GND"}
        
        # Find the library symbol definition
        lib_symbol = find_lib_symbol_block(content, lib_id)
        if lib_symbol is None:
            changes_applied.append(f"WARNING: Library symbol '{lib_id}' not found. "
                                   f"Add it to KiCad first, then try again.")
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
        
        # Insert after the last symbol instance
        insert_pos = last_symbol_end
        indented_instance = '\n\t' + instance.replace('\n', '\n\t')
        content = content[:insert_pos] + indented_instance + content[insert_pos:]
        last_symbol_end = insert_pos + len(indented_instance)
        
        # Check for series insertion
        is_series, series_net = detect_series_insertion(connections, existing_nets)
        
        # Check for missing labels
        needs_labels, missing_nets = detect_missing_labels(connections, existing_nets, nets_with_labels)
        
        if is_series:
            # Create warning annotation
            warning_text = f"⚠ {reference} requires series insertion.\nBreak wire on net '{series_net}' and connect labels."
            annotation_pos = (position[0], position[1] + 5.0)  # Below component
            warning = {
                "type": "series_insertion",
                "component": reference,
                "net": series_net,
                "message": f"⚠ {reference} requires series insertion. Break wire on net '{series_net}' and connect labels.",
                "action_required": "break_wire"
            }
            warnings.append(warning)
            changes_applied.append(f"WARNING: {reference} - SERIES INSERTION on net '{series_net}'")
            changes_applied.append(f"  User must break wire and connect labels manually")
            
            # Add annotation to schematic
            annotation = create_text_annotation(warning_text, annotation_pos)
            annotations.append(annotation)
        
        elif needs_labels:
            # Create warning for missing labels
            nets_str = "', '".join(missing_nets)
            warning_text = f"⚠ {reference} requires labels on existing nets.\nAdd net labels '{nets_str}' to existing wires."
            annotation_pos = (position[0], position[1] + 5.0)  # Below component
            warning = {
                "type": "missing_labels",
                "component": reference,
                "nets": missing_nets,
                "message": f"⚠ {reference} requires labels on existing nets. Add net labels '{nets_str}' to existing wires.",
                "action_required": "add_labels"
            }
            warnings.append(warning)
            changes_applied.append(f"WARNING: {reference} - MISSING LABELS on nets: {nets_str}")
            changes_applied.append(f"  User must add labels to existing wires")
            
            # Add annotation to schematic
            annotation = create_text_annotation(warning_text, annotation_pos)
            annotations.append(annotation)
        
        # Add net labels for connections
        if connections:
            # Extract pin positions from library symbol for label placement
            pin_positions = extract_pin_positions_from_symbol(lib_symbol_block)
            
            for pin_num, net_name in connections.items():
                if not net_name:
                    continue
                
                # Calculate label position based on pin position
                # Label offset from pin (small offset toward outside)
                if pin_num in pin_positions:
                    pin_pos = pin_positions[pin_num]
                    # Offset label from pin position
                    label_offset = 2.54  # 2.54mm offset
                    label_pos = (position[0] + pin_pos[0] + label_offset, 
                                position[1] + pin_pos[1])
                else:
                    # Default position if pin not found
                    label_pos = (position[0] + 5.0, position[1])
                
                # Create and insert label
                label = create_net_label(net_name, label_pos)
                content = content[:last_symbol_end] + '\n\t' + label.replace('\n', '\n\t') + content[last_symbol_end:]
                last_symbol_end += len(label) + 2  # Account for newlines and tab
                
                changes_applied.append(f"Added label '{net_name}' at {reference} pin {pin_num}")
        
        if not is_series and not needs_labels:
            changes_applied.append(f"Added {reference} ({lib_id}) at staging position ({position[0]:.1f}, {position[1]:.1f})")
            if connections:
                changes_applied.append(f"  Labels: {', '.join(f'{k}={v}' for k, v in connections.items())}")
    
    # Insert all annotations at the end
    for annotation in annotations:
        content = content[:last_symbol_end] + '\n\t' + annotation.replace('\n', '\n\t') + content[last_symbol_end:]
    
    return content, changes_applied, warnings


def extract_pin_positions_from_symbol(symbol_block: str) -> Dict[str, Tuple[float, float]]:
    """
    Extract pin positions from a library symbol definition.
    
    Returns a dict mapping pin number to (x, y) position.
    """
    pin_positions = {}
    
    # Find pin definitions in the symbol
    # KiCad 10 format: (pin "1" (at x y angle) ...)
    pin_pattern = r'\(pin\s+"(\d+)"\s+\(at\s+([\d.\-]+)\s+([\d.\-]+)'
    for match in re.finditer(pin_pattern, symbol_block):
        pin_num = match.group(1)
        x = float(match.group(2))
        y = float(match.group(3))
        pin_positions[pin_num] = (x, y)
    
    return pin_positions


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
        
        # 3. Handle added components (text-based addition with net labels)
        if delta.get('added_components'):
            if modified_json is None:
                changes_applied.append("WARNING: modified_json required for component addition")
            else:
                content, addition_changes, addition_warnings = apply_component_addition_text(
                    content, delta['added_components'], modified_json
                )
                changes_applied.extend(addition_changes)
                warnings.extend(addition_warnings)
        
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
        
        return True, changes_applied, warnings
        
    except Exception as e:
        print(f"Error applying delta: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return False, [f"Error: {e}"], []


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
    
    # Apply delta (pass original JSON for component removal, modified JSON for addition)
    success, changes_log, warnings = apply_delta_to_schematic(kicad_path, delta, original_json=original, modified_json=modified)
    
    if success:
        # Return summary
        print(json.dumps({
            "status": "success",
            "changes_applied": len(changes_log),
            "changes": changes_log,
            "warnings": warnings,
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