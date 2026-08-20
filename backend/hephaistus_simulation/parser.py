"""
Ngspice output parser for HephAIstus.

Parses console output, DC operating points, and waveform data.
"""

import re
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path


@dataclass
class DCOperatingPoint:
    """A single DC operating point (node voltage or branch current)."""
    name: str
    value: float
    unit: str = ""  # V, A, etc.


@dataclass
class ConvergenceInfo:
    """Convergence status from ngspice output."""
    converged: bool
    error_type: Optional[str] = None  # "timestep", "gmin", "iteration", etc.
    message: Optional[str] = None
    timestep: Optional[float] = None  # If timestep-related failure


@dataclass
class ConsoleAnalysis:
    """Parsed analysis from console output."""
    analysis_type: str  # "tran", "ac", "dc", "op", etc.
    parameters: dict = field(default_factory=dict)
    status: str = "unknown"  # "running", "completed", "failed"
    messages: list = field(default_factory=list)


@dataclass
class ParsedConsole:
    """Parsed ngspice console output."""
    analyses: list = field(default_factory=list)
    convergence: Optional[ConvergenceInfo] = None
    warnings: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    raw_output: str = ""


def parse_console_output(output: str) -> ParsedConsole:
    """
    Parse ngspice console output (stdout/stderr).
    
    Extracts:
    - Analysis types and parameters
    - Convergence status
    - Warnings and errors
    - Raw output for context
    
    Args:
        output: Raw ngspice console output
        
    Returns:
        ParsedConsole with structured data
    """
    result = ParsedConsole(raw_output=output)
    lines = output.split('\n')
    
    # Pattern for analysis start
    # Example: "Transient Analysis ... 0.00 seconds"
    analysis_pattern = re.compile(
        r'^(Transient|AC|DC|Operating\s*Point|Noise|Distortion)\s*(Analysis|Sweep)?',
        re.IGNORECASE
    )
    
    # Pattern for convergence errors
    timestep_error = re.compile(
        r'timestep\s*(too\s*small|error|decreased)',
        re.IGNORECASE
    )
    gmin_error = re.compile(
        r'gmin\s*(step\s*failed|error)',
        re.IGNORECASE
    )
    iteration_error = re.compile(
        r'(iteration|convergence)\s*(limit|failed|error)',
        re.IGNORECASE
    )
    
    # Pattern for successful completion
    completed_pattern = re.compile(
        r'(analysis\s*complete|simulation\s*finished|no\s*errors)',
        re.IGNORECASE
    )
    
    # Pattern for warnings
    warning_pattern = re.compile(
        r'^(warning|note):\s*',
        re.IGNORECASE
    )
    
    # Pattern for errors
    error_pattern = re.compile(
        r'^(error|fatal|failed):\s*',
        re.IGNORECASE
    )
    
    current_analysis = None
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Check for analysis start
        analysis_match = analysis_pattern.match(line)
        if analysis_match:
            if current_analysis:
                result.analyses.append(current_analysis)
            analysis_type = analysis_match.group(1).lower()
            if 'operating' in analysis_type:
                analysis_type = 'op'
            elif 'transient' in analysis_type:
                analysis_type = 'tran'
            current_analysis = ConsoleAnalysis(
                analysis_type=analysis_type,
                status="running"
            )
            continue
        
        # Check for completion
        if completed_pattern.search(line):
            if current_analysis:
                current_analysis.status = "completed"
        
        # Check for convergence errors
        if timestep_error.search(line):
            result.convergence = ConvergenceInfo(
                converged=False,
                error_type="timestep",
                message=line
            )
            if current_analysis:
                current_analysis.status = "failed"
                current_analysis.messages.append(line)
        
        if gmin_error.search(line):
            result.convergence = ConvergenceInfo(
                converged=False,
                error_type="gmin",
                message=line
            )
            if current_analysis:
                current_analysis.status = "failed"
                current_analysis.messages.append(line)
        
        if iteration_error.search(line):
            result.convergence = ConvergenceInfo(
                converged=False,
                error_type="iteration",
                message=line
            )
            if current_analysis:
                current_analysis.status = "failed"
                current_analysis.messages.append(line)
        
        # Check for warnings
        if warning_pattern.match(line):
            result.warnings.append(line)
            if current_analysis:
                current_analysis.messages.append(line)
            continue
        
        # Check for errors
        if error_pattern.match(line):
            result.errors.append(line)
            if current_analysis:
                current_analysis.status = "failed"
                current_analysis.messages.append(line)
            continue
    
    # Add last analysis
    if current_analysis:
        result.analyses.append(current_analysis)
    
    # Set default convergence status if not detected
    if result.convergence is None:
        # Check if any analysis failed
        any_failed = any(a.status == "failed" for a in result.analyses)
        result.convergence = ConvergenceInfo(converged=not any_failed)
    
    return result


def parse_dc_op_points(output: str) -> list[DCOperatingPoint]:
    """
    Parse DC operating points from ngspice output.
    
    Looks for the standard ngspice operating point format:
    
        Node        Voltage
        ----        -------
        v(inp)      1.234
        v(out)      5.678
        ...
        
        Source      Current
        ------      -------
        v1#branch   0.00123
    
    Args:
        output: Ngspice console output or .op results
        
    Returns:
        List of DCOperatingPoint objects
    """
    points = []
    lines = output.split('\n')
    
    # Pattern for voltage/current table
    # Header: "Node/Voltage" or "Source/Current"
    in_voltage_section = False
    in_current_section = False
    
    # Pattern for data lines: "v(node)   1.234"
    voltage_pattern = re.compile(r'^v\(([^)]+)\)\s+([\d.eE+-]+)', re.IGNORECASE)
    # Pattern for branch currents: "v1#branch   0.00123"
    current_pattern = re.compile(r'^([a-z][a-z0-9_]*)#branch\s+([\d.eE+-]+)', re.IGNORECASE)
    # Alternative pattern for node voltages without parens: "node_name   1.234"
    alt_voltage_pattern = re.compile(r'^([a-z][a-z0-9_]*)\s+([\d.eE+-]+)', re.IGNORECASE)
    
    for line in lines:
        stripped = line.strip().lower()
        
        # Detect section headers
        if 'node' in stripped and 'voltage' in stripped:
            in_voltage_section = True
            in_current_section = False
            continue
        elif 'source' in stripped and 'current' in stripped:
            in_voltage_section = False
            in_current_section = True
            continue
        elif stripped.startswith('---'):
            continue
        
        # Parse voltage lines
        if in_voltage_section:
            match = voltage_pattern.match(stripped)
            if match:
                node_name = match.group(1)
                try:
                    value = float(match.group(2))
                    points.append(DCOperatingPoint(
                        name=f"v({node_name})",
                        value=value,
                        unit="V"
                    ))
                except ValueError:
                    pass
                continue
            
            # Try alternative pattern
            match = alt_voltage_pattern.match(stripped)
            if match and not stripped.startswith('v('):
                # Check if this looks like a voltage node
                try:
                    value = float(match.group(2))
                    points.append(DCOperatingPoint(
                        name=f"v({match.group(1)})",
                        value=value,
                        unit="V"
                    ))
                except ValueError:
                    pass
        
        # Parse current lines
        if in_current_section:
            match = current_pattern.match(stripped)
            if match:
                source_name = match.group(1)
                try:
                    value = float(match.group(2))
                    points.append(DCOperatingPoint(
                        name=f"{source_name}#branch",
                        value=value,
                        unit="A"
                    ))
                except ValueError:
                    pass
    
    return points


def parse_waveform_raw(filepath: Path) -> dict:
    """
    Parse ngspice raw/binary waveform data.
    
    Ngspice raw format is ASCII with structure:
        Title: ...
        Date: ...
        Plotname: ...
        Variables: N
        0  time  time
        1  v(inp)  voltage
        ...
        Values:
        0  0.000  0.001  0.002  ...
        1  1e-06  0.001  0.002  ...
        ...
        
    Each Values row has: index followed by N values (one per variable).
    
    Args:
        filepath: Path to .raw file
        
    Returns:
        Dict with metadata and signal data
    """
    result = {
        "metadata": {},
        "variables": [],
        "signals": {},
        "points": 0,
        "error": None
    }
    
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except FileNotFoundError:
        result["error"] = f"File not found: {filepath}"
        return result
    except Exception as e:
        result["error"] = str(e)
        return result
    
    lines = content.split('\n')
    
    # Parse header
    in_variables = False
    in_values = False
    variables = []
    var_count = 0
    signal_data = {}
    
    for line in lines:
        line = line.strip()
        
        if line.startswith('Title:'):
            result["metadata"]["title"] = line[6:].strip()
        elif line.startswith('Date:'):
            result["metadata"]["date"] = line[5:].strip()
        elif line.startswith('Plotname:'):
            result["metadata"]["plotname"] = line[9:].strip()
        elif line.startswith('Plottype:'):
            result["metadata"]["plottype"] = line[9:].strip()
        elif line.startswith('Dimensions:'):
            result["metadata"]["dimensions"] = line[11:].strip()
        elif line.startswith('Variables:'):
            in_variables = True
            # Variables: N
            var_count = int(line[10:].strip().split()[0])
            continue
        elif line.startswith('Values:'):
            in_variables = False
            in_values = True
            continue
        
        # Parse variables
        if in_variables:
            # Format: "0  time  time"
            # or: "1  v(inp)  voltage"
            parts = line.split()
            if len(parts) >= 2:
                try:
                    var_idx = int(parts[0])
                    var_name = parts[1]
                    var_type = parts[2] if len(parts) > 2 else "unknown"
                    variables.append({
                        "index": var_idx,
                        "name": var_name,
                        "type": var_type
                    })
                except ValueError:
                    pass
            continue
        
        # Parse values
        if in_values and variables:
            # Format: "0  0.000  0.001  0.002  ..."
            # Index followed by one value per variable
            parts = line.split()
            if len(parts) >= len(variables):
                try:
                    idx = int(parts[0])
                    # Initialize signal arrays if not done
                    for var in variables:
                        if var["name"] not in signal_data:
                            signal_data[var["name"]] = []
                    
                    # Parse values for each variable
                    for i, var in enumerate(variables):
                        value = float(parts[i + 1])
                        signal_data[var["name"]].append(value)
                    
                    result["points"] = idx + 1
                except (ValueError, IndexError):
                    pass
    
    result["variables"] = variables
    result["signals"] = signal_data
    
    return result


def parse_ngspice_output(console_output: str, op_output: Optional[str] = None, raw_file: Optional[Path] = None) -> dict:
    """
    Parse complete ngspice output for LLM context.
    
    Combines console parsing, DC operating points, and waveform data
    into a unified structure suitable for context assembly.
    
    Args:
        console_output: Ngspice stdout/stderr
        op_output: Optional DC operating point section (if separate)
        raw_file: Optional path to .raw waveform file
        
    Returns:
        Dict with all parsed data
    """
    result = {
        "console": None,
        "op_points": [],
        "waveform": None,
        "summary": {
            "analyses": [],
            "converged": None,
            "warnings_count": 0,
            "errors_count": 0
        }
    }
    
    # Parse console output
    if console_output:
        parsed_console = parse_console_output(console_output)
        result["console"] = {
            "analyses": [{"type": a.analysis_type, "status": a.status, "messages": a.messages} for a in parsed_console.analyses],
            "convergence": {
                "converged": parsed_console.convergence.converged if parsed_console.convergence else None,
                "error_type": parsed_console.convergence.error_type if parsed_console.convergence else None,
                "message": parsed_console.convergence.message if parsed_console.convergence else None
            },
            "warnings": parsed_console.warnings,
            "errors": parsed_console.errors,
            "raw": parsed_console.raw_output[:50000]  # Truncate to 50KB
        }
        result["summary"]["analyses"] = [a.analysis_type for a in parsed_console.analyses]
        result["summary"]["converged"] = parsed_console.convergence.converged if parsed_console.convergence else None
        result["summary"]["warnings_count"] = len(parsed_console.warnings)
        result["summary"]["errors_count"] = len(parsed_console.errors)
    
    # Parse DC operating points
    op_source = op_output if op_output else console_output
    if op_source:
        op_points = parse_dc_op_points(op_source)
        if op_points:
            result["op_points"] = [
                {"name": p.name, "value": p.value, "unit": p.unit}
                for p in op_points
            ]
    
    # Parse waveform data
    if raw_file:
        waveform = parse_waveform_raw(raw_file)
        if waveform.get("error"):
            result["waveform"] = {"error": waveform["error"]}
        else:
            result["waveform"] = {
                "metadata": waveform["metadata"],
                "variables": waveform["variables"],
                "points": waveform["points"],
                # Include signal names and basic stats, not full data
                "signal_names": list(waveform["signals"].keys()),
                "signal_stats": {
                    name: {
                        "min": min(data) if data else None,
                        "max": max(data) if data else None,
                        "samples": len(data)
                    }
                    for name, data in waveform["signals"].items()
                    if name != "time"
                }
            }
    
    return result