"""
Context assembly for HephAIstus LLM orchestration.

Combines schematic state with simulation results into a unified context
suitable for LLM prompt construction.
"""

from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path

from .run_metadata import (
    SimulationRun,
    RunMetadata,
    CorrelationStatus,
    check_correlation,
)
from .parser import parse_ngspice_output
from .waveform import (
    WaveformConfig,
    WaveformSummary,
    summarize_waveforms,
    format_summaries_for_context,
)


@dataclass
class SimulationContext:
    """
    Assembled context for LLM orchestration.
    
    Combines:
    - Schematic state (components, nets)
    - Simulation results (console, op points, waveforms)
    - Correlation status (freshness)
    - Summary for LLM consumption
    """
    # Schematic reference
    schematic_path: str
    schematic_hash: str
    components_summary: dict  # {"count": N, "references": [...]}
    nets_summary: dict  # {"count": N, "names": [...]}
    
    # Simulation run
    run: Optional[SimulationRun] = None
    
    # Correlation
    is_current: bool = True
    staleness_warning: Optional[str] = None
    
    # LLM-friendly summaries
    circuit_summary: str = ""
    simulation_summary: str = ""
    warnings_summary: str = ""
    
    def to_dict(self) -> dict:
        """Convert to dict for JSON serialization."""
        return {
            "schematic_path": self.schematic_path,
            "schematic_hash": self.schematic_hash,
            "components_summary": self.components_summary,
            "nets_summary": self.nets_summary,
            "run": self.run.to_dict() if self.run else None,
            "is_current": self.is_current,
            "staleness_warning": self.staleness_warning,
            "circuit_summary": self.circuit_summary,
            "simulation_summary": self.simulation_summary,
            "warnings_summary": self.warnings_summary,
        }
    
    def get_llm_context(self, max_console_chars: int = 10000, waveform_config: WaveformConfig = None) -> str:
        """
        Generate LLM-friendly context string.
        
        Args:
            max_console_chars: Maximum characters from console output
            waveform_config: Configuration for waveform processing
            
        Returns:
            Formatted context string for LLM prompt
        """
        waveform_config = waveform_config or WaveformConfig()
        lines = []
        
        # Circuit overview
        lines.append("## Circuit Overview")
        lines.append(f"Schematic: {self.schematic_path}")
        lines.append(f"Components: {self.components_summary.get('count', 0)}")
        lines.append(f"Nets: {self.nets_summary.get('count', 0)}")
        lines.append(f"Component references: {', '.join(self.components_summary.get('references', [])[:20])}")
        if len(self.components_summary.get('references', [])) > 20:
            lines.append(f"  ... and {len(self.components_summary['references']) - 20} more")
        lines.append("")
        
        # Staleness warning
        if self.staleness_warning:
            lines.append("## ⚠️ Staleness Warning")
            lines.append(self.staleness_warning)
            lines.append("")
        
        # Simulation results
        if self.run:
            lines.append("## Simulation Results")
            lines.append(f"Analysis: {self.run.metadata.analysis_type}")
            lines.append(f"Status: {'Converged ✓' if self.run.metadata.converged else 'Failed ✗'}")
            
            if not self.run.metadata.converged and self.run.metadata.error_message:
                lines.append(f"Error: {self.run.metadata.error_message}")
            
            lines.append("")
            
            # DC operating points
            if self.run.op_points:
                lines.append("### DC Operating Points")
                for op in self.run.op_points[:50]:  # Limit for context
                    lines.append(f"  {op['name']}: {op['value']:.6e} {op['unit']}")
                if len(self.run.op_points) > 50:
                    lines.append(f"  ... and {len(self.run.op_points) - 50} more")
                lines.append("")
            
            # Console output
            if self.run.console_summary:
                lines.append("### Console Output")
                
                # Analysis summary
                for analysis in self.run.console_summary.get("analyses", []):
                    lines.append(f"  {analysis['type']}: {analysis['status']}")
                
                # Warnings
                warnings = self.run.console_summary.get("warnings", [])
                if warnings:
                    lines.append(f"  Warnings ({len(warnings)}):")
                    for w in warnings[:5]:
                        lines.append(f"    - {w}")
                    if len(warnings) > 5:
                        lines.append(f"    ... and {len(warnings) - 5} more")
                
                # Errors
                errors = self.run.console_summary.get("errors", [])
                if errors:
                    lines.append(f"  Errors ({len(errors)}):")
                    for e in errors:
                        lines.append(f"    - {e}")
                
                # Raw output (truncated)
                raw = self.run.console_summary.get("raw", "")
                if raw:
                    lines.append("  Raw output (last 2000 chars):")
                    lines.append("  " + raw[-2000:].replace("\n", "\n  "))
                
                lines.append("")
            
            # Waveform summary (processed)
            if self.run.waveform_summary:
                signals = self.run.waveform_summary.get("signals", {})
                if signals and signals.get("time"):
                    # Process waveforms with config
                    summaries = summarize_waveforms(signals, waveform_config)
                    lines.append(format_summaries_for_context(summaries, waveform_config))
                    lines.append("")
        else:
            lines.append("## Simulation Results")
            lines.append("No simulation run loaded.")
            lines.append("")
        
        # Warnings summary
        if self.warnings_summary:
            lines.append("## Warnings")
            lines.append(self.warnings_summary)
            lines.append("")
        
        return "\n".join(lines)


def assemble_context(
    schematic_path: Path,
    schematic_state: dict,
    run: Optional[SimulationRun] = None,
    include_raw_console: bool = False,
) -> SimulationContext:
    """
    Assemble LLM context from schematic state and simulation run.
    
    Args:
        schematic_path: Path to the schematic file
        schematic_state: Parsed schematic state (from hephaistus_circuit.parser)
        run: Optional simulation run
        include_raw_console: Whether to include raw console output
        
    Returns:
        SimulationContext ready for LLM consumption
    """
    # Extract schematic summaries
    components = schematic_state.get("components", [])
    nets = schematic_state.get("nets", [])
    
    components_summary = {
        "count": len(components),
        "references": [c.get("reference", "?") for c in components],
    }
    
    nets_summary = {
        "count": len(nets),
        "names": [n.get("name", "?") for n in nets],
    }
    
    # Check correlation
    is_current = True
    staleness_warning = None
    
    if run:
        correlation = check_correlation(run.metadata, schematic_path)
        is_current = correlation == CorrelationStatus.CURRENT
        
        if not is_current:
            staleness_warning = (
                f"Warning: This simulation was run against an older version of the schematic. "
                f"Simulation timestamp: {run.metadata.timestamp.isoformat()}. "
                f"Schematic has been modified since then. Results may not reflect current circuit."
            )
    
    # Generate summaries
    circuit_summary = _generate_circuit_summary(schematic_state)
    simulation_summary = _generate_simulation_summary(run) if run else ""
    warnings_summary = _generate_warnings_summary(run) if run else ""
    
    # Load parsed outputs if run provided
    if run and run.console_summary is None:
        # Parse console output if available
        if run.metadata.console_output_path:
            try:
                with open(run.metadata.console_output_path, "r") as f:
                    console_output = f.read()
                
                op_output = None
                if run.metadata.op_file_path:
                    with open(run.metadata.op_file_path, "r") as f:
                        op_output = f.read()
                
                raw_file = None
                if run.metadata.raw_file_path:
                    raw_file = Path(run.metadata.raw_file_path)
                
                parsed = parse_ngspice_output(
                    console_output=console_output,
                    op_output=op_output,
                    raw_file=raw_file,
                )
                
                run.console_summary = parsed["console"]
                run.op_points = parsed["op_points"]
                run.waveform_summary = parsed.get("waveform")
                
            except Exception as e:
                run.console_summary = {"error": str(e)}
    
    return SimulationContext(
        schematic_path=str(schematic_path),
        schematic_hash=run.metadata.schematic_hash if run else "",
        components_summary=components_summary,
        nets_summary=nets_summary,
        run=run,
        is_current=is_current,
        staleness_warning=staleness_warning,
        circuit_summary=circuit_summary,
        simulation_summary=simulation_summary,
        warnings_summary=warnings_summary,
    )


def _generate_circuit_summary(schematic_state: dict) -> str:
    """Generate human-readable circuit summary."""
    components = schematic_state.get("components", [])
    nets = schematic_state.get("nets", [])
    
    lines = []
    lines.append(f"Circuit has {len(components)} components and {len(nets)} nets.")
    
    # Group components by type
    by_lib = {}
    for comp in components:
        lib_id = comp.get("libId", "?")
        if "/" in lib_id:
            lib = lib_id.split("/")[0]
        else:
            lib = lib_id.split(":")[0] if ":" in lib_id else "unknown"
        by_lib.setdefault(lib, []).append(comp.get("reference", "?"))
    
    for lib, refs in sorted(by_lib.items()):
        lines.append(f"  {lib}: {len(refs)} components")
    
    return "\n".join(lines)


def _generate_simulation_summary(run: SimulationRun) -> str:
    """Generate human-readable simulation summary."""
    lines = []
    
    lines.append(f"Analysis: {run.metadata.analysis_type}")
    
    params = run.metadata.parameters
    if params:
        param_str = ", ".join(f"{k}={v}" for k, v in params.items())
        lines.append(f"Parameters: {param_str}")
    
    if run.metadata.converged:
        lines.append("Status: Converged successfully")
    else:
        lines.append(f"Status: Failed ({run.metadata.error_type or 'unknown'})")
        if run.metadata.error_message:
            lines.append(f"  {run.metadata.error_message}")
    
    if run.op_points:
        lines.append(f"Operating points: {len(run.op_points)} nodes/currents")
    
    if run.waveform_summary:
        signals = run.waveform_summary.get("signal_names", [])
        lines.append(f"Waveform data: {len(signals)} signals")
    
    return "\n".join(lines)


def _generate_warnings_summary(run: SimulationRun) -> str:
    """Generate warnings summary for LLM context."""
    if not run.console_summary:
        return ""
    
    warnings = run.console_summary.get("warnings", [])
    errors = run.console_summary.get("errors", [])
    
    lines = []
    
    if warnings:
        lines.append(f"Ngspice issued {len(warnings)} warnings:")
        for w in warnings[:5]:
            lines.append(f"  - {w}")
        if len(warnings) > 5:
            lines.append(f"  ... and {len(warnings) - 5} more")
    
    if errors:
        if lines:
            lines.append("")
        lines.append(f"Ngspice issued {len(errors)} errors:")
        for e in errors:
            lines.append(f"  - {e}")
    
    return "\n".join(lines)