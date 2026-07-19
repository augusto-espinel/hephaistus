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
        from kiutils.schematic import Schematic
        
        schematic = Schematic.from_file(path)
        
        components = []
        
        # Parse schematic symbols (components placed on the schematic)
        for symbol in schematic.schematicSymbols:
            comp = {
                "uuid": getattr(symbol, 'uuid', 'unknown'),
                "libId": getattr(symbol, 'libId', ''),
                "reference": getattr(symbol, 'reference', ''),
                "value": getattr(symbol, 'value', ''),
                "footprint": getattr(symbol, 'footprint', ''),
                "position": {
                    "x": getattr(symbol, 'positionX', 0),
                    "y": getattr(symbol, 'positionY', 0)
                }
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
        
        return {
            "schemaVersion": "1.0.0",
            "source": os.path.basename(path),
            "circuitName": os.path.splitext(os.path.basename(path))[0],
            "components": components,
            "symbolInstances": symbol_instances,
            "nets": nets,
            "titleBlock": title_info,
            "metadata": {
                "parser": "kiutils",
                "componentCount": len(components),
                "netCount": len(nets),
                "generator": getattr(schematic, 'generator', 'unknown'),
                "uuid": getattr(schematic, 'uuid', '')
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