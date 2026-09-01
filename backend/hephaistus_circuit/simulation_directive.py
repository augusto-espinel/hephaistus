"""
Simulation directive operations for HephAIstus patch plans.

Handles KiCad schematic text elements that contain SPICE directives
like .tran, .ac, .op, .dc, .options, etc.
"""

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class SimulationDirective:
    """A simulation directive text element in a KiCad schematic."""
    
    uuid: str
    text: str
    position: tuple  # (x, y, angle)
    exclude_from_sim: bool = False
    
    # Parsed directive info
    directive_type: Optional[str] = None  # "tran", "ac", "dc", "op", "options", etc.
    parameters: dict = None
    
    def __post_init__(self):
        self.parameters = self.parameters or {}
        if self.text and self.text.startswith("."):
            self._parse_directive()
    
    def _parse_directive(self):
        """Parse SPICE directive into type and parameters."""
        text = self.text.strip()
        
        # Match directive type
        match = re.match(r'\.(\w+)\s*(.*)', text)
        if not match:
            return
        
        self.directive_type = match.group(1).lower()
        params_str = match.group(2).strip()
        
        # Parse parameters based on directive type
        if self.directive_type == "tran":
            # .tran <step> <stop> [start] [max_step]
            parts = params_str.split()
            if len(parts) >= 2:
                self.parameters = {
                    "step": parts[0],
                    "stop": parts[1],
                }
                if len(parts) >= 3:
                    self.parameters["start"] = parts[2]
                if len(parts) >= 4:
                    self.parameters["max_step"] = parts[3]
        
        elif self.directive_type == "ac":
            # .ac <dec/oct/lin> <points> <start> <stop>
            parts = params_str.split()
            if len(parts) >= 4:
                self.parameters = {
                    "type": parts[0],
                    "points": parts[1],
                    "start": parts[2],
                    "stop": parts[3],
                }
        
        elif self.directive_type == "dc":
            # .dc <source> <start> <stop> <step>
            parts = params_str.split()
            if len(parts) >= 4:
                self.parameters = {
                    "source": parts[0],
                    "start": parts[1],
                    "stop": parts[2],
                    "step": parts[3],
                }
        
        elif self.directive_type == "op":
            # .op (no parameters)
            self.parameters = {}
        
        elif self.directive_type == "options":
            # .options key=value key2=value2 ...
            self.parameters = {}
            for part in params_str.split():
                if "=" in part:
                    key, value = part.split("=", 1)
                    self.parameters[key] = value
                else:
                    self.parameters[part] = True
        
        elif self.directive_type == "ic":
            # .ic V(node1)=value1 V(node2)=value2 ...
            self.parameters = {}
            for part in params_str.split():
                if "=" in part:
                    # Handle V(/node)=value format
                    match = re.match(r'(V\([^)]+\))\s*=\s*(.+)', part)
                    if match:
                        node_expr = match.group(1)
                        value = match.group(2)
                        self.parameters[node_expr] = value
                    else:
                        # Generic key=value
                        key, value = part.split("=", 1)
                        self.parameters[key] = value
        
        elif self.directive_type == "nodeset":
            # .nodeset V(node)=value (similar to .ic)
            self.parameters = {}
            for part in params_str.split():
                if "=" in part:
                    match = re.match(r'(V\([^)]+\))\s*=\s*(.+)', part)
                    if match:
                        self.parameters[match.group(1)] = match.group(2)
                    else:
                        key, value = part.split("=", 1)
                        self.parameters[key] = value
        
        else:
            # Generic: store as raw string
            self.parameters = {"raw": params_str}
    
    def to_directive_text(self) -> str:
        """Convert parameters back to directive text."""
        if not self.directive_type:
            return self.text
        
        if self.directive_type == "tran":
            parts = [self.parameters.get("step", "1u"), self.parameters.get("stop", "1m")]
            if "start" in self.parameters:
                parts.append(self.parameters["start"])
            if "max_step" in self.parameters:
                parts.append(self.parameters["max_step"])
            return f".tran {' '.join(parts)}"
        
        elif self.directive_type == "ac":
            return f".ac {self.parameters.get('type', 'dec')} {self.parameters.get('points', '10')} {self.parameters.get('start', '1')} {self.parameters.get('stop', '1k')}"
        
        elif self.directive_type == "dc":
            return f".dc {self.parameters.get('source', 'V1')} {self.parameters.get('start', '0')} {self.parameters.get('stop', '5')} {self.parameters.get('step', '0.1')}"
        
        elif self.directive_type == "op":
            return ".op"
        
        elif self.directive_type == "options":
            opts = " ".join(f"{k}={v}" if isinstance(v, str) else k for k, v in self.parameters.items())
            return f".options {opts}"
        
        elif self.directive_type == "ic":
            # .ic V(/node1)=value1 V(/node2)=value2
            parts = [f"{k}={v}" for k, v in self.parameters.items()]
            return f".ic {' '.join(parts)}" if parts else ".ic"
        
        elif self.directive_type == "nodeset":
            # .nodeset V(/node)=value
            parts = [f"{k}={v}" for k, v in self.parameters.items()]
            return f".nodeset {' '.join(parts)}" if parts else ".nodeset"
        
        else:
            return self.text


def parse_text_elements(schematic) -> list:
    """
    Extract text elements from a KiCad schematic.
    
    Args:
        schematic: kiutils Schematic object
        
    Returns:
        List of SimulationDirective objects
    """
    directives = []
    
    # Check for texts attribute (KiCad 10+)
    if hasattr(schematic, 'texts') and schematic.texts:
        for item in schematic.texts:
            text = getattr(item, 'text', '')
            if text and text.startswith('.'):
                uuid = getattr(item, 'uuid', 'unknown')
                position = (0, 0, 0)
                if hasattr(item, 'position') and item.position:
                    position = (
                        getattr(item.position, 'X', 0),
                        getattr(item.position, 'Y', 0),
                        getattr(item.position, 'angle', 0),
                    )
                exclude_from_sim = getattr(item, 'exclude_from_sim', False)
                
                directives.append(SimulationDirective(
                    uuid=uuid,
                    text=text,
                    position=position,
                    exclude_from_sim=exclude_from_sim,
                ))
    
    # Also check graphicalItems for older KiCad versions
    if hasattr(schematic, 'graphicalItems'):
        for item in schematic.graphicalItems:
            # Check if this is a text element
            item_type = type(item).__name__
            
            if item_type == 'Text':
                # kiutils Text object
                text = getattr(item, 'text', '')
                if text and text.startswith('.'):
                    uuid = getattr(item, 'uuid', 'unknown')
                    position = (0, 0, 0)
                    if hasattr(item, 'position') and item.position:
                        position = (
                            getattr(item.position, 'X', 0),
                            getattr(item.position, 'Y', 0),
                            getattr(item.position, 'angle', 0),
                        )
                    exclude_from_sim = getattr(item, 'exclude_from_sim', False)
                    
                    directives.append(SimulationDirective(
                        uuid=uuid,
                        text=text,
                        position=position,
                        exclude_from_sim=exclude_from_sim,
                    ))
            
            elif item_type == 'TextBox':
                # kiutils TextBox object
                text = getattr(item, 'text', '')
                if text and text.startswith('.'):
                    uuid = getattr(item, 'uuid', 'unknown')
                    position = (0, 0, 0)
                    if hasattr(item, 'position') and item.position:
                        position = (
                            getattr(item.position, 'X', 0),
                            getattr(item.position, 'Y', 0),
                            getattr(item.position, 'angle', 0),
                        )
                    exclude_from_sim = getattr(item, 'exclude_from_sim', False)
                    
                    directives.append(SimulationDirective(
                        uuid=uuid,
                        text=text,
                        position=position,
                        exclude_from_sim=exclude_from_sim,
                    ))
    
    return directives


def find_directive_by_type(directives: list, directive_type: str) -> Optional[SimulationDirective]:
    """
    Find a simulation directive by type.
    
    Args:
        directives: List of SimulationDirective objects
        directive_type: Type to find (e.g., "tran", "ac", "op")
        
    Returns:
        SimulationDirective or None
    """
    for d in directives:
        if d.directive_type == directive_type:
            return d
    return None


def validate_directive_type(directive_type: str) -> bool:
    """
    Validate that a directive type is supported.
    
    Args:
        directive_type: Type to validate
        
    Returns:
        True if supported
    """
    supported = {
        "tran",      # Transient analysis
        "ac",        # AC analysis
        "dc",        # DC sweep
        "op",        # Operating point
        "options",   # Simulation options
        "param",     # Parameter definitions
        "model",     # Model definitions
        "include",   # Include files
        "lib",       # Library includes
        "ic",        # Initial conditions
        "nodeset",   # Node voltage hints
        "save",      # Save variables
        "probe",     # Probe variables
    }
    return directive_type.lower() in supported


def create_directive_text(directive_type: str, parameters: dict) -> str:
    """
    Create directive text from type and parameters.
    
    Args:
        directive_type: Directive type
        parameters: Parameters dict
        
    Returns:
        Directive text string
    """
    temp = SimulationDirective(
        uuid="temp",
        text="",  # Will be generated
        position=(0, 0, 0),
    )
    temp.directive_type = directive_type.lower()
    temp.parameters = parameters
    return temp.to_directive_text()