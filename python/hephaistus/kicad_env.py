"""
KiCad 10 Environment Setup

Sets up environment variables for KiCad 10 compatibility with skidl and kiutils.
This must be called BEFORE importing skidl or kiutils.

Based on the ClawSpice project's solution for KiCad 10 on macOS.
"""

import os
import sys

# KiCad 10 installation path (macOS default)
KICAD10_MACOS_PATH = '/Applications/KiCad/KiCad.app/Contents/SharedSupport/'

def setup_kicad_env(kicad_path: str = None) -> dict:
    """
    Set up KiCad environment variables for all supported versions.
    
    This silences warnings from skidl/kiutils about missing KICAD*_SYMBOL_DIR
    and enables proper library lookups.
    
    Args:
        kicad_path: Optional custom KiCad path. Defaults to macOS location.
    
    Returns:
        Dict of environment variables that were set.
    """
    if kicad_path is None:
        # Try macOS default
        kicad_path = KICAD10_MACOS_PATH
        if not os.path.exists(kicad_path):
            # Try Linux
            for linux_path in ['/usr/share/kicad', '/usr/local/share/kicad']:
                if os.path.exists(linux_path):
                    kicad_path = linux_path
                    break
    
    if not os.path.exists(kicad_path):
        return {}
    
    symbols_path = os.path.join(kicad_path, 'symbols')
    footprints_path = os.path.join(kicad_path, 'footprints')
    
    set_vars = {}
    
    # Set for all KiCad versions (6, 7, 8, 9, 10, and default)
    for version in ['6', '7', '8', '9', '10', '']:
        prefix = f'KICAD{version}_' if version else 'KICAD_'
        
        symbol_var = f'{prefix}SYMBOL_DIR'
        footprint_var = f'{prefix}FOOTPRINT_DIR'
        
        if os.path.exists(symbols_path) and symbol_var not in os.environ:
            os.environ[symbol_var] = symbols_path
            set_vars[symbol_var] = symbols_path
            
        if os.path.exists(footprints_path) and footprint_var not in os.environ:
            os.environ[footprint_var] = footprints_path
            set_vars[footprint_var] = footprints_path
    
    return set_vars


def inject_skidl_library_paths():
    """
    Inject KiCad 10 library paths into skidl's search paths.
    
    This must be called AFTER skidl is imported.
    """
    try:
        import skidl
        
        kicad_path = KICAD10_MACOS_PATH
        if not os.path.exists(kicad_path):
            return False
        
        symbols_path = os.path.join(kicad_path, 'symbols')
        
        # Inject into kicad8 search path (KiCad 8/9/10 compatible)
        for version in ['kicad8', 'kicad9', 'kicad10']:
            if version not in skidl.lib_search_paths:
                skidl.lib_search_paths[version] = []
            
            if symbols_path not in skidl.lib_search_paths[version]:
                skidl.lib_search_paths[version].append(symbols_path)
        
        return True
    except ImportError:
        return False


# Auto-setup on import (optional - can be disabled)
_auto_setup = os.environ.get('HEPHAISTUS_AUTO_KICAD_SETUP', '1').lower() in ('1', 'true', 'yes')

if _auto_setup:
    setup_kicad_env()