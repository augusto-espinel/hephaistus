"""
SPICE library context extraction for HephAIstus.

Finds and loads .lib files referenced by schematics, strips comments,
and includes complete library content in the LLM context.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Optional, Set


@dataclass
class SpiceLibrary:
    """A loaded SPICE library file."""
    name: str
    path: str
    content: str  # Full content with comments stripped
    models: List[str] = field(default_factory=list)  # Model names
    subcircuits: List[str] = field(default_factory=list)  # Subcircuit names
    token_estimate: int = 0


@dataclass
class SpiceLibraryContext:
    """Collection of SPICE libraries for a schematic."""
    libraries: List[SpiceLibrary] = field(default_factory=list)
    total_tokens: int = 0
    errors: List[str] = field(default_factory=list)


# Regex patterns for SPICE library references in KiCad schematics
LIBRARY_PROPERTY_PATTERNS = [
    r'\(property\s+"Sim\.Library"\s+"([^"]+)"',
    r'\(property\s+"Spice_Lib"\s+"([^"]+)"',
    r'\(property\s+"Model_File"\s+"([^"]+)"',
]


def extract_library_references(schematic_content: str) -> Set[str]:
    """
    Extract SPICE library file references from KiCad schematic.
    
    Args:
        schematic_content: Raw .kicad_sch file content
    
    Returns:
        Set of library filenames referenced
    """
    libraries = set()
    
    for pattern in LIBRARY_PROPERTY_PATTERNS:
        matches = re.findall(pattern, schematic_content)
        libraries.update(matches)
    
    return libraries


def find_library_file(
    lib_name: str,
    project_root: Path,
    search_paths: Optional[List[Path]] = None,
) -> Optional[Path]:
    """
    Find a SPICE library file.
    
    Searches in order:
    1. Project root
    2. Project/models/ subdirectory
    3. KiCad global library paths
    
    Args:
        lib_name: Library filename (e.g., "FUJI_2MBI1500XYF170.lib")
        project_root: Path to KiCad project directory
        search_paths: Optional additional search paths
    
    Returns:
        Path to library file or None if not found
    """
    # Default search paths
    candidates = [
        project_root / lib_name,
        project_root / "models" / lib_name,
        project_root / "spice" / lib_name,
    ]
    
    # Add custom search paths
    if search_paths:
        for sp in search_paths:
            candidates.append(Path(sp) / lib_name)
    
    # Try each path
    for candidate in candidates:
        if candidate.exists():
            return candidate
    
    return None


def load_library(lib_path: Path) -> SpiceLibrary:
    """
    Load a SPICE library file.
    
    Strips comments, extracts model/subcircuit names, and estimates tokens.
    
    Args:
        lib_path: Path to .lib file
    
    Returns:
        SpiceLibrary with loaded content
    """
    with open(lib_path, 'r', encoding='utf-8', errors='replace') as f:
        raw_content = f.read()
    
    # Strip comments
    content = strip_spice_comments(raw_content)
    
    # Extract model names
    models = re.findall(r'\.MODEL\s+(\w+)', content)
    
    # Extract subcircuit names
    subcircuits = re.findall(r'\.SUBCKT\s+(\w+)', content)
    
    # Estimate tokens (roughly 4 chars per token)
    token_estimate = len(content) // 4
    
    return SpiceLibrary(
        name=lib_path.name,
        path=str(lib_path),
        content=content,
        models=models,
        subcircuits=subcircuits,
        token_estimate=token_estimate,
    )


def strip_spice_comments(content: str) -> str:
    """
    Strip comments from SPICE library content.
    
    Removes lines starting with * (comments) while preserving
    all circuit definitions (.MODEL, .SUBCKT, components).
    
    Keeps inline comments on the same line are preserved (rare in SPICE).
    
    Args:
        content: Raw SPICE library content
    
    Returns:
        Content with comment lines stripped
    """
    lines = content.split('\n')
    stripped = []
    
    for line in lines:
        stripped_line = line.strip()
        # Keep non-comment lines
        if stripped_line and not stripped_line.startswith('*'):
            stripped.append(line)
    
    # Remove excessive blank lines
    result = '\n'.join(stripped)
    result = re.sub(r'\n{3,}', '\n\n', result)
    
    return result


def load_libraries_for_schematic(
    schematic_path: str,
    search_paths: Optional[List[str]] = None,
) -> SpiceLibraryContext:
    """
    Load all SPICE libraries referenced by a schematic.
    
    Args:
        schematic_path: Path to .kicad_sch file
        search_paths: Optional additional library search paths
    
    Returns:
        SpiceLibraryContext with all loaded libraries
    """
    schematic_path = Path(schematic_path)
    project_root = schematic_path.parent
    
    # Read schematic
    try:
        with open(schematic_path, 'r', encoding='utf-8') as f:
            schematic_content = f.read()
    except Exception as e:
        return SpiceLibraryContext(
            errors=[f"Failed to read schematic: {e}"]
        )
    
    # Extract library references
    lib_names = extract_library_references(schematic_content)
    
    if not lib_names:
        return SpiceLibraryContext()
    
    # Load each library
    context = SpiceLibraryContext()
    search_path_objs = [Path(p) for p in search_paths] if search_paths else None
    
    for lib_name in lib_names:
        lib_path = find_library_file(lib_name, project_root, search_path_objs)
        
        if lib_path:
            try:
                lib = load_library(lib_path)
                context.libraries.append(lib)
                context.total_tokens += lib.token_estimate
            except Exception as e:
                context.errors.append(f"Failed to load {lib_name}: {e}")
        else:
            context.errors.append(f"Library not found: {lib_name}")
    
    return context


def format_library_context(context: SpiceLibraryContext) -> str:
    """
    Format SPICE libraries for LLM context.
    
    Args:
        context: Loaded library context
    
    Returns:
        Formatted string for inclusion in prompt
    """
    if not context.libraries:
        return ""
    
    lines = ["## SPICE Models\n"]
    
    for lib in context.libraries:
        lines.append(f"### {lib.name}")
        
        # List models and subcircuits
        if lib.subcircuits:
            lines.append(f"Subcircuits: {', '.join(lib.subcircuits)}")
        if lib.models:
            lines.append(f"Models: {', '.join(lib.models)}")
        
        lines.append("")  # Blank line before content
        
        # Include full content (comments already stripped)
        lines.append(lib.content)
        lines.append("")  # Blank line after
    
    if context.errors:
        lines.append("\n### Warnings")
        for error in context.errors:
            lines.append(f"- {error}")
    
    return '\n'.join(lines)


def estimate_context_size(context: SpiceLibraryContext) -> dict:
    """
    Estimate context size for token budgeting.
    
    Args:
        context: Loaded library context
    
    Returns:
        Dict with size estimates
    """
    return {
        "library_count": len(context.libraries),
        "total_tokens": context.total_tokens,
        "total_chars": sum(len(lib.content) for lib in context.libraries),
        "models": sum(len(lib.models) for lib in context.libraries),
        "subcircuits": sum(len(lib.subcircuits) for lib in context.libraries),
        "errors": len(context.errors),
    }