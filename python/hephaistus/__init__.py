"""
HephAIstus Python Package

A Python package for KiCad schematic synchronization, SPICE simulation,
and LLM-assisted circuit optimization.

Modules:
    kicad_sync: KiCad schematic parsing and synchronization
    simulation: SPICE simulation orchestration (SKiDL, ngspice)
"""

# Setup KiCad environment BEFORE importing any KiCad-related modules
from .kicad_env import setup_kicad_env, inject_skidl_library_paths

# Auto-setup on import
setup_kicad_env()

__version__ = "0.1.0"
__author__ = "HephAIstus Team"