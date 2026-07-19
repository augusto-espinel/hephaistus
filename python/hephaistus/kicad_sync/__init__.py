"""
KiCad Synchronization Module

Provides bidirectional synchronization between KiCad schematics and
the JSON state ledger used for LLM reasoning and optimization.
"""

from .delta import compute_delta
from .updater import apply_updates
from .staging import locate_staging_origin as compute_staging_origin
from .utils import load_schematic, save_schematic

__all__ = [
    "compute_delta",
    "apply_updates",
    "compute_staging_origin",
    "load_schematic",
    "save_schematic",
]