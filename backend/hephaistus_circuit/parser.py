#!/usr/bin/env python3
"""
KiCad Schematic Parser Wrapper for HephAIstus

Uses kiutils to parse .kicad_sch files and output JSON.
Falls back to metadata extraction if kiutils fails.
"""

import sys
import json
import os
from typing import Optional, Dict, List, Any
from .simulation_directive import parse_text_elements, SimulationDirective

# Setup KiCad environment before importing kiutils
def setup_kicad_env():
    """Set up KiCad environment variables for library lookups."""
    kicad_paths = [
        '/Applications/KiCad/KiCad.app/Contents/SharedSupport/',  # macOS
        '/usr/share/kicad',  # Linux
        '/usr/local/share/kicad',  # Linux alternative
    ]
    
    for kicad_path in kicad_paths:
        if os.path.exists(kicad_path):
            symbols_path = os.path.join(kicad_path, 'symbols')
            footprints_path = os.path.join(kicad_path, 'footprints')
            
            for version in ['6', '7', '8', '9', '10', '']:
                prefix = f'KICAD{version}_' if version else 'KICAD_'
                if os.path.exists(symbols_path):
                    os.environ.setdefault(f'{prefix}SYMBOL_DIR', symbols_path)
                if os.path.exists(footprints_path):
                    os.environ.setdefault(f'{prefix}FOOTPRINT_DIR', footprints_path)
            break

setup_kicad_env()


def parse_with_kiutils(path: str) -> Optional[Dict[str, Any]]:
    """Parse KiCad schematic using kiutils library."""
    try:
        from kiutils.schematic import Schematic, Connection, Junction, LocalLabel
        from kiutils.symbol import Symbol
        import math
        
        schematic = Schematic.from_file(path)
        
        # Build library symbol lookup
        lib_symbols = {}
        for lib_sym in schematic.libSymbols:
            key = f"{lib_sym.libraryNickname}:{lib_sym.entryName}" if lib_sym.libraryNickname else lib_sym.entryName
            lib_symbols[key] = lib_sym
        
        # Build wire connectivity graph
        # Wires are Connection objects in graphicalItems
        wire_segments = []
        for item in schematic.graphicalItems:
            if isinstance(item, Connection):
                wire_segments.append({
                    "uuid": item.uuid,
                    "points": [(p.X, p.Y) for p in item.points]
                })
        
        # Build junction positions (where wires connect)
        junction_positions = set()
        for junc in schematic.junctions:
            junction_positions.add((junc.position.X, junc.position.Y))
        
        # Build label positions (net names)
        label_positions = {}
        for label in schematic.labels:
            pos = (label.position.X, label.position.Y)
            label_positions[pos] = label.text
        
        # Build a spatial index: map each point to all wires that contain it
        point_to_wires = {}  # (x, y) -> set of wire uuids
        for wire in wire_segments:
            for point in wire["points"]:
                if point not in point_to_wires:
                    point_to_wires[point] = set()
                point_to_wires[point].add(wire["uuid"])
        
        # Build net propagation: labels propagate through connected wires
        # A net propagates through:
        # 1. Wires that share a point
        # 2. Junctions (wires that touch the same junction are connected)
        # 3. Wires that touch the same label position
        
        def point_on_segment(pt, p1, p2, tol):
            """Check if point pt lies on the line segment from p1 to p2 (within tolerance)."""
            px, py = pt
            x1, y1 = p1
            x2, y2 = p2
            
            # Check if point is within bounding box of segment
            if not (min(x1, x2) - tol <= px <= max(x1, x2) + tol and
                    min(y1, y2) - tol <= py <= max(y1, y2) + tol):
                return False
            
            # For vertical/horizontal lines, simpler check
            if abs(x2 - x1) < tol:  # Vertical line
                return abs(px - x1) < tol
            if abs(y2 - y1) < tol:  # Horizontal line
                return abs(py - y1) < tol
            
            # For diagonal lines, check distance from point to line
            # Using cross product method
            line_len_sq = (x2 - x1)**2 + (y2 - y1)**2
            if line_len_sq < 1e-10:
                return (px - x1)**2 + (py - y1)**2 < tol**2
            
            # Distance from point to infinite line
            t = max(0, min(1, ((px - x1) * (x2 - x1) + (py - y1) * (y2 - y1)) / line_len_sq))
            proj_x = x1 + t * (x2 - x1)
            proj_y = y1 + t * (y2 - y1)
            return (px - proj_x)**2 + (py - proj_y)**2 < tol**2
        
        def propagate_net_label(start_pos, tolerance=0.5):
            """Propagate net label through connected wires and junctions."""
            visited_positions = set()
            visited_wires = set()
            positions_with_net = set()
            
            # BFS through wire segments and junctions
            to_visit = [start_pos]
            
            while to_visit:
                current_pos = to_visit.pop(0)
                if current_pos in visited_positions:
                    continue
                visited_positions.add(current_pos)
                positions_with_net.add(current_pos)
                
                # Find all wires that touch this position (endpoint OR anywhere along segment)
                for wire in wire_segments:
                    if wire["uuid"] in visited_wires:
                        continue
                    
                    wire_connected = False
                    
                    # Check if current_pos is at any wire endpoint
                    for wire_point in wire["points"]:
                        if abs(wire_point[0] - current_pos[0]) < tolerance and abs(wire_point[1] - current_pos[1]) < tolerance:
                            wire_connected = True
                            break
                    
                    # Check if current_pos lies ON the wire segment (not just at endpoints)
                    if not wire_connected and len(wire["points"]) >= 2:
                        for i in range(len(wire["points"]) - 1):
                            if point_on_segment(current_pos, wire["points"][i], wire["points"][i+1], tolerance):
                                wire_connected = True
                                break
                    
                    if wire_connected:
                        visited_wires.add(wire["uuid"])
                        # Add all points on this wire
                        for point in wire["points"]:
                            positions_with_net.add(point)
                            to_visit.append(point)
                
                # Check if this position is at a junction
                # If so, find all other wires at this junction
                for junc_pos in junction_positions:
                    if abs(junc_pos[0] - current_pos[0]) < tolerance and abs(junc_pos[1] - current_pos[1]) < tolerance:
                        # This is a junction - add all wires touching this junction
                        for wire in wire_segments:
                            if wire["uuid"] in visited_wires:
                                continue
                            for wire_point in wire["points"]:
                                if abs(wire_point[0] - junc_pos[0]) < tolerance and abs(wire_point[1] - junc_pos[1]) < tolerance:
                                    visited_wires.add(wire["uuid"])
                                    for point in wire["points"]:
                                        positions_with_net.add(point)
                                        to_visit.append(point)
                                    break
            
            return positions_with_net, visited_wires
        
        # Build net coverage: which positions belong to which net.
        # Multiple labels may carry the SAME net name on DISJOINT wire
        # islands (stub-based connectivity) — accumulate, never overwrite.
        net_coverage = {}  # net_name -> set of positions
        for pos, net_name in label_positions.items():
            if net_name:  # Skip empty labels
                positions, wires = propagate_net_label(pos)
                net_coverage.setdefault(net_name, set()).update(positions)
        
        # Power symbols create implicit global nets.
        # lib_id "power:GND" means Value property is the net name.
        # We need to collect these BEFORE processing components
        # so pins can find the net at power symbol positions.
        power_symbols = []  # Store for later inclusion in components
        
        # NOTE: get_pin_position is defined below, so we use a simpler approach here.
        # Power symbols typically have a single pin at or near the symbol position.
        # We'll use the symbol position directly for net propagation.
        
        for symbol in schematic.schematicSymbols:
            props = {p.key: p.value for p in symbol.properties}
            lib_nickname = getattr(symbol, 'libraryNickname', '') or ''
            entry_name = getattr(symbol, 'entryName', '') or ''
            lib_id = f"{lib_nickname}:{entry_name}" if lib_nickname else entry_name
            
            # Check if this is a power symbol
            if lib_id.startswith('power:') or lib_id.startswith('Power:'):
                net_name = props.get('Value', '')  # e.g., "GND", "VCC", "+5V"
                if not net_name:
                    net_name = entry_name  # Fallback to library entry name
                
                # Get symbol position
                if hasattr(symbol, 'position') and symbol.position:
                    sym_x = getattr(symbol.position, 'X', 0)
                    sym_y = getattr(symbol.position, 'Y', 0)
                    angle = getattr(symbol.position, 'angle', 0) if hasattr(symbol.position, 'angle') else 0
                else:
                    sym_x, sym_y, angle = 0, 0, 0
                
                # For power symbols, the connection point is typically at or near the symbol position
                # The pin is usually at the origin of the symbol, so we use the symbol position directly
                # This is a simplification but works for most power symbols
                pin_pos = (sym_x, sym_y)
                
                # Add to net_coverage (propagate through connected wires)
                if net_name:
                    positions, wires = propagate_net_label(pin_pos)
                    net_coverage.setdefault(net_name, set()).update(positions)
                    
                    # Track power symbol for component list
                    power_symbols.append({
                        'uuid': getattr(symbol, 'uuid', 'unknown'),
                        'reference': props.get('Reference', ''),
                        'lib_id': lib_id,
                        'net_name': net_name,
                        'position': {'x': sym_x, 'y': sym_y},
                        'pin_position': {'x': pin_pos[0], 'y': pin_pos[1]}
                    })
        
        # Also check junctions - they may connect wires from different nets
        for junc_pos in junction_positions:
            # Check if this junction is in any net's coverage
            for net_name, positions in net_coverage.items():
                if junc_pos in positions:
                    # Junction connects wires, propagate to all wires at junction
                    pass  # Already handled by propagate_net_label
        
        # Function to find net at a position or near a pin line segment
        def find_net_at_position(pin_info, tolerance=0.5):
            """Find net name near a pin's line segment (body to tip).
            
            pin_info can be:
            - (x, y) for single point check (backward compatible)
            - (body_x, body_y, tip_x, tip_y, pin_name) for pin line segment check
            - (body_x, body_y, tip_x, tip_y) for pin line segment check
            
            KiCad connects a wire to a pin if the wire touches any part
            of the pin graphic (the line from body to tip).
            """
            if len(pin_info) == 2:
                # Legacy: single point
                px, py = pin_info
                # Check net coverage
                for net_name, positions in net_coverage.items():
                    for net_pos in positions:
                        if abs(net_pos[0] - px) < tolerance and abs(net_pos[1] - py) < tolerance:
                            return net_name
                # Check junctions
                for junc_pos in junction_positions:
                    if abs(junc_pos[0] - px) < tolerance and abs(junc_pos[1] - py) < tolerance:
                        for net_name, positions in net_coverage.items():
                            if junc_pos in positions:
                                return net_name
                return ""
            
            # Pin line segment: check proximity to entire line from body to tip
            body_x, body_y, tip_x, tip_y = pin_info[0], pin_info[1], pin_info[2], pin_info[3]
            
            # Check net coverage against both endpoints and intermediate points
            for net_name, positions in net_coverage.items():
                for net_pos in positions:
                    # Check if net_pos is near the pin line segment
                    nx, ny = net_pos
                    
                    # Quick check: near body or tip endpoint?
                    if abs(nx - body_x) < tolerance and abs(ny - body_y) < tolerance:
                        return net_name
                    if abs(nx - tip_x) < tolerance and abs(ny - tip_y) < tolerance:
                        return net_name
                    
                    # Check if point lies ON the pin line segment
                    # Line segment: (body_x, body_y) to (tip_x, tip_y)
                    # Point is on segment if it's within tolerance of the infinite line
                    # AND between the endpoints
                    
                    dx = tip_x - body_x
                    dy = tip_y - body_y
                    seg_len = math.sqrt(dx*dx + dy*dy)
                    
                    if seg_len < 0.001:
                        continue
                    
                    # Distance from point to line segment
                    # Parametric form: P(t) = body + t*(tip-body), t in [0,1]
                    # Project net_pos onto the line
                    t = ((nx - body_x) * dx + (ny - body_y) * dy) / (seg_len * seg_len)
                    
                    # Clamp to segment
                    t = max(0, min(1, t))
                    
                    closest_x = body_x + t * dx
                    closest_y = body_y + t * dy
                    dist = math.sqrt((nx - closest_x)**2 + (ny - closest_y)**2)
                    
                    if dist < tolerance:
                        return net_name
            
            # Check junctions against the pin line segment
            for junc_pos in junction_positions:
                jx, jy = junc_pos
                # Quick check: near body or tip?
                if abs(jx - body_x) < tolerance and abs(jy - body_y) < tolerance:
                    for net_name, positions in net_coverage.items():
                        if junc_pos in positions:
                            return net_name
                if abs(jx - tip_x) < tolerance and abs(jy - tip_y) < tolerance:
                    for net_name, positions in net_coverage.items():
                        if junc_pos in positions:
                            return net_name
                
                # Check if junction lies on pin line segment
                dx = tip_x - body_x
                dy = tip_y - body_y
                seg_len = math.sqrt(dx*dx + dy*dy)
                
                if seg_len < 0.001:
                    continue
                
                t = ((jx - body_x) * dx + (jy - body_y) * dy) / (seg_len * seg_len)
                t = max(0, min(1, t))
                
                closest_x = body_x + t * dx
                closest_y = body_y + t * dy
                dist = math.sqrt((jx - closest_x)**2 + (jy - closest_y)**2)
                
                if dist < tolerance:
                    for net_name, positions in net_coverage.items():
                        if junc_pos in positions:
                            return net_name
            
            return ""
        
        # Function to get pin position from libSymbol
        def get_pin_position(lib_sym, pin_num, symbol_pos, symbol_angle=0):
            """Get absolute pin position from libSymbol and symbol placement.
            
            Returns: (body_x, body_y, tip_x, tip_y, pin_name)
            pin_name is the electrical name from the library (e.g., "C", "G", "E" or "").
            
            KiCad coordinate system note:
            - Library symbols use Y-UP (Cartesian) coordinates
            - Schematics use Y-DOWN (screen) coordinates
            - The Y coordinate must be NEGATED when transforming from library
              to schematic space: schematic_y = symbol_y - library_y
            
            Pin definition in library: (at X Y angle) (length L)
            - (X, Y) is where the pin attaches to the symbol body (in Y-up coords)
            - angle is the direction the pin extends OUTWARD from the body
            - The pin graphic runs from body (X,Y) to tip (X+L*cos(a), Y+L*sin(a))
            
            For wire connectivity, KiCad considers a pin connected if a wire
            touches any part of the pin graphic line (body to tip). We compute
            both body and tip positions in schematic coordinates to enable
            line-segment proximity checks in find_net_at_position.
            """
            # Find the pin in libSymbol
            pin_pos_rel = (0, 0)
            pin_length = 0
            pin_angle = 0
            pin_name = ""
            
            # libSymbol has pins in units[1].pins for the main unit
            if hasattr(lib_sym, 'units') and lib_sym.units:
                for unit in lib_sym.units:
                    if hasattr(unit, 'pins') and unit.pins:
                        for pin in unit.pins:
                            if pin.number == pin_num:
                                # Pin body position relative to symbol origin (Y-up)
                                pin_pos_rel = (pin.position.X, pin.position.Y)
                                pin_length = pin.length if hasattr(pin, 'length') else 0
                                pin_angle = pin.position.angle if hasattr(pin.position, 'angle') else 0
                                pin_name = pin.name if hasattr(pin, 'name') else ''
                                break
            
            # Convert library body position to schematic Y-down coordinates
            # Library Y-up → Schematic Y-down: negate Y
            body_sch_x = pin_pos_rel[0]
            body_sch_y = -pin_pos_rel[1]
            
            # Apply rotation transformation to body position
            # Rotation is counter-clockwise in KiCad (standard math convention)
            x, y = body_sch_x, body_sch_y
            if symbol_angle != 0:
                angle_rad = math.radians(symbol_angle)
                cos_a = math.cos(angle_rad)
                sin_a = math.sin(angle_rad)
                x_rot = x * cos_a - y * sin_a
                y_rot = x * sin_a + y * cos_a
                x, y = x_rot, y_rot
            
            # Apply translation (symbol position in schematic coords)
            abs_body_x = symbol_pos[0] + x
            abs_body_y = symbol_pos[1] + y
            
            # Also compute tip (connection endpoint) for line-segment checks
            if pin_length > 0:
                # In library Y-up, tip = body + length * direction(angle)
                tip_lib_x = pin_pos_rel[0] + pin_length * math.cos(math.radians(pin_angle))
                tip_lib_y = pin_pos_rel[1] + pin_length * math.sin(math.radians(pin_angle))
                # Convert to schematic Y-down
                tip_sch_x = tip_lib_x
                tip_sch_y = -tip_lib_y
                # Apply rotation
                tx, ty = tip_sch_x, tip_sch_y
                if symbol_angle != 0:
                    angle_rad = math.radians(symbol_angle)
                    cos_a = math.cos(angle_rad)
                    sin_a = math.sin(angle_rad)
                    tx_rot = tx * cos_a - ty * sin_a
                    ty_rot = tx * sin_a + ty * cos_a
                    tx, ty = tx_rot, ty_rot
                abs_tip_x = symbol_pos[0] + tx
                abs_tip_y = symbol_pos[1] + ty
                # Return body position (primary) and tip (secondary)
                # The find_net_at_position function should check proximity
                # to the pin line segment from body to tip
                return (abs_body_x, abs_body_y, abs_tip_x, abs_tip_y, pin_name)
            
            return (abs_body_x, abs_body_y, abs_body_x, abs_body_y, pin_name)
        
        components = []
        
        # Parse schematic symbols (components placed on the schematic)
        # Note: Power symbols were already processed above for net coverage
        for symbol in schematic.schematicSymbols:
            # Extract properties from symbol.properties list
            props = {p.key: p.value for p in symbol.properties}
            
            # Build libId from library nickname and entry name
            lib_nickname = getattr(symbol, 'libraryNickname', '') or ''
            entry_name = getattr(symbol, 'entryName', '') or ''
            lib_id = f"{lib_nickname}:{entry_name}" if lib_nickname else entry_name
            
            # Find library symbol for pin positions AND inherited properties
            lib_sym = lib_symbols.get(lib_id)
            
            # Extract position from symbol.position object
            position = {"x": 0, "y": 0}
            angle = 0
            if hasattr(symbol, 'position') and symbol.position:
                position = {
                    "x": getattr(symbol.position, 'X', 0),
                    "y": getattr(symbol.position, 'Y', 0)
                }
                # KiCad stores rotation in position.angle
                if hasattr(symbol.position, 'angle'):
                    angle = symbol.position.angle
            
            # Merge library properties with instance properties
            # Library properties provide defaults; instance properties override
            lib_props = {}
            if lib_sym and hasattr(lib_sym, 'properties'):
                lib_props = {p.key: p.value for p in lib_sym.properties}
            
            # Instance properties override library defaults
            merged_props = {**lib_props, **props}
            
            # Extract SPICE simulation properties from merged properties
            # This ensures SPICE symbols inherit Sim.* props from library definition
            spice_props = {
                "device": merged_props.get('Sim.Device', ''),
                "type": merged_props.get('Sim.Type', ''),
                "params": merged_props.get('Sim.Params', ''),
                "pins": merged_props.get('Sim.Pins', ''),
                "library": merged_props.get('Sim.Library', ''),
            }
            
            # Extract pins with net connectivity
            pins = []
            if hasattr(symbol, 'pins') and symbol.pins:
                for pin_num, pin_uuid in symbol.pins.items():
                    # Get absolute pin positions (body and tip) with rotation and pin name
                    pin_info = get_pin_position(lib_sym, pin_num, (position['x'], position['y']), angle) if lib_sym else (position['x'], position['y'], position['x'], position['y'], '')
                    
                    # Find net near the pin line segment
                    net_name = find_net_at_position(pin_info)
                    
                    pins.append({
                        "number": pin_num,
                        "uuid": pin_uuid,
                        "name": pin_info[4],  # Pin name from library
                        "net": net_name,
                        "position": {"x": pin_info[0], "y": pin_info[1]}
                    })
            
            comp = {
                "uuid": getattr(symbol, 'uuid', 'unknown'),
                "reference": props.get('Reference', ''),
                "lib_id": lib_id,  # snake_case for consistency
                "value": props.get('Value', ''),  # extracted directly
                "footprint": props.get('Footprint', ''),
                "position": position,
                "properties": {
                    "Reference": props.get('Reference', ''),
                    "Value": props.get('Value', ''),
                    "Footprint": props.get('Footprint', ''),
                    "Datasheet": props.get('Datasheet', ''),
                    "Description": merged_props.get('Description', ''),
                    # SPICE properties: use merged (instance overrides library)
                    "Sim.Device": merged_props.get('Sim.Device', ''),
                    "Sim.Type": merged_props.get('Sim.Type', ''),
                    "Sim.Params": merged_props.get('Sim.Params', ''),
                    "Sim.Pins": merged_props.get('Sim.Pins', ''),
                    "Sim.Library": merged_props.get('Sim.Library', ''),
                    "Sim.Name": merged_props.get('Sim.Name', ''),
                },
                "spice": spice_props,
                "pins": pins,
                "is_power_symbol": lib_id.lower().startswith('power:') if lib_id else False
            }
            components.append(comp)
        
        # Parse symbol instances (provides reference designators)
        symbol_instances = []
        for inst in schematic.symbolInstances:
            instance = {
                "path": getattr(inst, 'path', ''),
                "reference": getattr(inst, 'reference', ''),
                "unit": getattr(inst, 'unit', 0)
            }
            symbol_instances.append(instance)
        
        # Parse labels (net names)
        nets = []
        for label in schematic.labels:
            net = {
                "name": getattr(label, 'text', 'unnamed'),
                "uuid": getattr(label, 'uuid', 'unknown'),
                "type": type(label).__name__
            }
            nets.append(net)
        
        # Global labels (ports/connections)
        for glabel in schematic.globalLabels:
            net = {
                "name": getattr(glabel, 'text', 'unnamed'),
                "uuid": getattr(glabel, 'uuid', 'unknown'),
                "type": "global"
            }
            nets.append(net)
        
        # Build reverse net mapping: net_name -> [connected pins]
        net_pins = {}
        for comp in components:
            for pin in comp["pins"]:
                if pin["net"]:
                    net_pins.setdefault(pin["net"], []).append(f"{comp['reference']}.{pin['number']}")
        
        # Find unnamed nets - pins connected together without a label
        # Group pins by connectivity through wires and junctions
        # Use a helper to normalize positions to KiCad precision (0.001mm)
        # to avoid floating-point mismatch between computed pin positions and wire endpoints
        def normalize_pos(pos, precision=0.001):
            """Round position to KiCad precision to handle floating-point imprecision."""
            return (round(pos[0] / precision) * precision,
                    round(pos[1] / precision) * precision)
        
        unnamed_pin_positions = {}  # normalized position -> [(ref, pin_num), ...]
        pin_to_normalized_pos = {}  # (ref, pin_num) -> normalized position for reverse lookup
        for comp in components:
            for pin in comp["pins"]:
                if not pin["net"]:  # Unnamed pin
                    raw_pos = (pin.get("position", {}).get("x", 0), pin.get("position", {}).get("y", 0))
                    pos = normalize_pos(raw_pos)
                    if pos not in unnamed_pin_positions:
                        unnamed_pin_positions[pos] = []
                    unnamed_pin_positions[pos].append((comp["reference"], pin["number"]))
                    pin_to_normalized_pos[(comp["reference"], pin["number"])] = pos
        
        # Propagate connectivity through wires for unnamed pins
        # Normalize wire and junction positions to match pin precision
        def normalize_wire_points(wire_pts, precision=0.001):
            return [(round(p[0] / precision) * precision,
                     round(p[1] / precision) * precision) for p in wire_pts]
        
        normalized_wire_segments = [
            {"uuid": w["uuid"], "points": normalize_wire_points(w["points"])}
            for w in wire_segments
        ]
        normalized_junction_positions = {normalize_pos(j) for j in junction_positions}
        
        def find_connected_pins(start_pos, tolerance=0.5):
            """Find all pin positions connected to start_pos through wires and junctions."""
            connected_positions = set()
            to_visit = [start_pos]
            
            while to_visit:
                pos = to_visit.pop(0)
                if pos in connected_positions:
                    continue
                connected_positions.add(pos)
                
                # Find wires at this position
                for wire in normalized_wire_segments:
                    for wire_point in wire["points"]:
                        if abs(wire_point[0] - pos[0]) < tolerance and abs(wire_point[1] - pos[1]) < tolerance:
                            for point in wire["points"]:
                                if point not in connected_positions:
                                    to_visit.append(point)
                            break
                
                # Check junctions
                for junc_pos in normalized_junction_positions:
                    if abs(junc_pos[0] - pos[0]) < tolerance and abs(junc_pos[1] - pos[1]) < tolerance:
                        for wire in normalized_wire_segments:
                            for wire_point in wire["points"]:
                                if abs(wire_point[0] - junc_pos[0]) < tolerance and abs(wire_point[1] - junc_pos[1]) < tolerance:
                                    for point in wire["points"]:
                                        if point not in connected_positions:
                                            to_visit.append(point)
                                    break
            
            return connected_positions
        
        # Group unnamed pins into nets
        unnamed_net_groups = []
        processed_positions = set()
        
        for pos in unnamed_pin_positions:
            if pos in processed_positions:
                continue
            
            # Find all positions connected to this pin
            connected = find_connected_pins(pos)
            processed_positions.update(connected)
            
            # Collect all pins at these positions
            group_pins = []
            for conn_pos in connected:
                if conn_pos in unnamed_pin_positions:
                    group_pins.extend(unnamed_pin_positions[conn_pos])
            
            if group_pins:
                unnamed_net_groups.append(group_pins)
        
        # Generate names for unnamed nets
        # IMPORTANT: Avoid collision with existing label names!
        # Labels create NAMED nets (N$3, N$4, etc.) and we must not reuse
        # those names for unnamed nets, or we'll incorrectly merge electrically
        # separate nets.
        existing_label_names = set(label_positions.values())
        
        # Use KiCad's Net-(Ref-PadName) convention for unnamed nets.
        # This ensures parser net names match what appears in simulation logs
        # and netlist exports, so the LLM can cross-reference them.
        #
        # Convention:
        #   Pin name empty/numeric → Net-(Ref-Pad1)
        #   Pin name non-numeric  → Net-(Ref-Name)  e.g. Net-(B_gate3-N+)
        #
        # We pick the alphabetically first (ref, pin) on the net as the
        # canonical name, matching KiCad's deterministic ordering.
        
        # Build a lookup: (ref, pin_num) -> pin_name
        pin_name_lookup = {}
        for comp in components:
            for pin in comp.get("pins", []):
                pin_name_lookup[(comp["reference"], pin["number"])] = pin.get("name", "")
        
        def kicad_net_name(ref, pin_num):
            """Generate KiCad-compatible net name for an unnamed net."""
            p_name = pin_name_lookup.get((ref, pin_num), "")
            # KiCad uses the pin name; if empty or numeric, use Pad<pin_num>
            if not p_name or p_name.isdigit():
                pad_id = f"Pad{pin_num}"
            else:
                pad_id = p_name
            return f"Net-({ref}-{pad_id})"
        
        for group_pins in unnamed_net_groups:
            # Sort to get deterministic "first pin" (matches KiCad's ordering)
            sorted_pins = sorted(group_pins, key=lambda x: (x[0], int(x[1]) if x[1].isdigit() else x[1]))
            ref, pin_num = sorted_pins[0]
            net_name = kicad_net_name(ref, pin_num)
            
            # Avoid collision with existing label names
            if net_name in existing_label_names:
                # Fallback: try subsequent pins in the group
                for ref2, pin_num2 in sorted_pins[1:]:
                    candidate = kicad_net_name(ref2, pin_num2)
                    if candidate not in existing_label_names:
                        net_name = candidate
                        break
            
            # Update component pins with net name
            for ref, pin_num in group_pins:
                for comp in components:
                    if comp["reference"] == ref:
                        for pin in comp["pins"]:
                            if pin["number"] == pin_num:
                                pin["net"] = net_name
            
            # Add to net_pins
            net_pins[net_name] = [f"{ref}.{pin_num}" for ref, pin_num in group_pins]
        
        # ============================================================
        # Note: No Net Merge Through Components
        # ============================================================
        # KiCad's netlist assigns nets purely based on WIRES, not through
        # component electrical connectivity. If a resistor bridges two
        # separate wire islands, those remain DIFFERENT nets in KiCad's
        # model. The parser must faithfully reproduce this behavior.
        #
        # For simulation purposes, the LLM orchestration layer may later
        # decide to treat certain low-value components as shorts, but
        # the parser's job is to report the physical wire connectivity.
        # ============================================================
        
        # Build net objects with connected pins
        nets = []
        all_net_names = set(net_pins.keys())
        all_net_names.update(label_positions.values())
        
        def filter_pwr_pins(pin_list):
            """Keep power symbol pins - they show GND/VCC connectivity for LLM context."""
            return pin_list  # No longer filtering out power pins
        
        for label in schematic.labels:
            net_name = label.text if label.text else ""
            if net_name:
                pins_for_net = net_pins.get(net_name, [])
                nets.append({
                    "name": net_name,
                    "uuid": getattr(label, 'uuid', 'unknown'),
                    "type": type(label).__name__,
                    "position": {
                        "x": label.position.X,
                        "y": label.position.Y
                    },
                    "connectedPins": filter_pwr_pins(pins_for_net)
                })
        
        # Add power nets (from power symbols like power:GND)
        # These create implicit global nets without explicit labels
        for pwr_sym in power_symbols:
            net_name = pwr_sym['net_name']
            if net_name and net_name not in [n["name"] for n in nets]:
                # Find pins connected to this power net
                connected_pins = net_pins.get(net_name, [])
                # Add the power symbol's pin
                pwr_ref = pwr_sym['reference']
                if pwr_ref:
                    connected_pins = [f"{pwr_ref}.1"] + [p for p in connected_pins if not p.startswith(pwr_ref)]
                
                nets.append({
                    "name": net_name,
                    "uuid": pwr_sym['uuid'],
                    "type": "power",
                    "position": {
                        "x": pwr_sym['position']['x'],
                        "y": pwr_sym['position']['y']
                    },
                    "connectedPins": connected_pins,
                    "is_power_net": True
                })
        
        # Add unnamed nets (nets without labels but with connections)
        for net_name, pins in net_pins.items():
            if net_name and net_name not in [n["name"] for n in nets]:
                nets.append({
                    "name": net_name,
                    "uuid": "",
                    "type": "Unnamed",
                    "position": {"x": 0, "y": 0},
                    "connectedPins": filter_pwr_pins(pins)
                })
        
        # Get title block info
        title_block = schematic.titleBlock if hasattr(schematic, 'titleBlock') else None
        title_info = {}
        if title_block:
            title_info = {
                "title": getattr(title_block, 'title', ''),
                "date": getattr(title_block, 'date', ''),
                "rev": getattr(title_block, 'rev', ''),
                "company": getattr(title_block, 'company', ''),
                "comment": getattr(title_block, 'comment', [])
            }
        
        # Parse simulation directives (text elements starting with '.')
        directives = parse_text_elements(schematic)
        
        # Power symbols are now included in components with is_power_symbol flag.
        # The reference "#PWRnn" indicates a virtual power symbol (not in BOM),
        # but we keep them for LLM context since they define net connectivity.
        # 
        # Previously filtered out, but LLM needs to see:
        # - Which pins connect to GND/VCC
        # - Ground references for circuit topology
        # - Power net connections for SPICE simulation
        filtered_components = components  # Keep all, including power symbols
        
        # Count power symbols for metadata
        power_symbol_count = sum(1 for c in components if c.get('is_power_symbol', False))
        
        # Extract unique SPICE library references
        spice_libraries = list(set(
            c["spice"]["library"]
            for c in components
            if c.get("spice", {}).get("library")
        ))
        
        return {
            "schemaVersion": "1.2.0",  # Bumped for power symbol support
            "source": os.path.basename(path),
            "circuitName": os.path.splitext(os.path.basename(path))[0],
            "components": filtered_components,
            "nets": nets,
            "wires": [{"uuid": w["uuid"], "points": [{"x": p[0], "y": p[1]} for p in w["points"]]} for w in wire_segments],
            "junctions": [{"uuid": j, "position": {"x": p[0], "y": p[1]}} for j, p in [(j, list(junction_positions)[i]) for i, j in enumerate(list(junction_positions))]],
            "simulation_directives": [{
                "uuid": d.uuid,
                "text": d.text,
                "directive_type": d.directive_type,
                "parameters": d.parameters,
                "position": list(d.position),
                "exclude_from_sim": d.exclude_from_sim
            } for d in directives],
            "spice_libraries": spice_libraries,
            "titleBlock": title_info,
            "metadata": {
                "parser": "kiutils",
                "componentCount": len(components) - power_symbol_count,  # Exclude power symbols from count
                "powerSymbolCount": power_symbol_count,
                "netCount": len(nets),
                "generator": getattr(schematic, 'generator', 'unknown'),
                "uuid": getattr(schematic, 'uuid', ''),
                "enhanced": True,
                "hasProperties": all(c['properties']['Reference'] for c in components),
                "hasSpiceParams": any(c['spice']['params'] for c in components if c['spice']),
                "hasConnectivity": all(len(c['pins']) > 0 for c in components),
                "hasPowerSymbols": power_symbol_count > 0
            }
        }
    except Exception as e:
        print(f"// kiutils parse error: {e}", file=sys.stderr)
        return None


def parse_fallback(path: str) -> Dict[str, Any]:
    """Fallback parser - extracts basic metadata from file."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
            lines = content.count('\n') + 1
            
        # Try to extract component count from KiCad file
        component_count = content.count('(symbol')
        wire_count = content.count('(wire')
        label_count = content.count('(label')
        
        # Try to extract circuit name
        circuit_name = os.path.splitext(os.path.basename(path))[0]
        
        return {
            "schemaVersion": "1.0.0",
            "source": os.path.basename(path),
            "circuitName": circuit_name,
            "components": [],
            "nets": [],
            "metadata": {
                "parser": "fallback",
                "lineCount": lines,
                "componentHint": component_count,
                "wireHint": wire_count,
                "labelHint": label_count
            }
        }
    except Exception as e:
        return {
            "schemaVersion": "1.0.0",
            "source": os.path.basename(path) if path else "unknown",
            "circuitName": "unknown",
            "components": [],
            "nets": [],
            "metadata": {
                "parser": "error",
                "error": str(e)
            }
        }


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "no-file", "message": "No file path provided"}))
        sys.exit(2)
    
    path = sys.argv[1]
    
    if not os.path.exists(path):
        print(json.dumps({"error": "file-not-found", "path": path}))
        sys.exit(3)
    
    # Try kiutils first
    result = parse_with_kiutils(path)
    
    # Fall back to basic parsing if kiutils fails
    if result is None:
        result = parse_fallback(path)
    
    print(json.dumps(result, indent=2))
    sys.exit(0)


if __name__ == "__main__":
    main()