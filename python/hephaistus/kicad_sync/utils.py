#!/usr/bin/env python3
"""Utility helpers for kicad_sync"""
import json
from pathlib import Path


def load_json(path: Path):
    with open(path, 'r') as f:
        return json.load(f)


def load_schematic(path: Path):
    """Load schematic from KiCad or JSON file."""
    # Placeholder: actual KiCad parsing would go here
    if path.suffix == '.json':
        return load_json(path)
    # For now, return empty scaffold for .kicad_sch files
    return {"symbols": [], "wires": [], "labels": []}


def save_schematic(schematic: dict, path: Path):
    """Save schematic to file."""
    with open(path, 'w') as f:
        json.dump(schematic, f, indent=2)
