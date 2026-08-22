"""
Layer 4: Simulation results context for HephAIstus.

Summaries by default, full data on request.
"""

from typing import Any, Dict, List, Optional

from ..session_state import SimulationState, SimulationStatus
from ..token_budget import TokenBudget, LayerPriority


class SimulationLayer:
    """
    Layer 4: Simulation results context.
    
    Two modes:
    - Summary: Always included, compact (DC op points, signal stats, convergence)
    - Full: On request, includes waveform summaries and detailed data
    """
    
    def __init__(
        self, 
        simulation: SimulationState,
        include_full_data: bool = False,
        max_op_points: int = 30,
        max_signals: int = 10,
    ):
        self.simulation = simulation
        self.include_full_data = include_full_data
        self.max_op_points = max_op_points
        self.max_signals = max_signals
    
    def generate(self) -> str:
        """
        Generate the simulation results context string.
        
        Returns:
            Formatted simulation results for LLM prompt
        """
        lines = ["## Simulation Results"]
        
        if self.simulation.status == SimulationStatus.NO_SIMULATION:
            lines.append("No simulation run available.")
            lines.append("To get simulation context, run a simulation in KiCad/ngspice, then load the results.")
            return "\n".join(lines)
        
        # Status and convergence
        if self.simulation.status == SimulationStatus.STALE:
            lines.append(f"⚠️ {self.simulation.staleness_warning or 'Results may not reflect current schematic'}")
            lines.append("")
        
        if self.simulation.analysis_type:
            lines.append(f"Analysis: {self.simulation.analysis_type}")
        
        if self.simulation.converged is not None:
            status = "Converged ✓" if self.simulation.converged else "Failed ✗"
            lines.append(f"Convergence: {status}")
        
        # DC operating points (always included)
        if self.simulation.op_points:
            lines.append("")
            lines.append("### DC Operating Points")
            for op in self.simulation.op_points[:self.max_op_points]:
                name = op.get("name", "?")
                value = op.get("value", 0)
                unit = op.get("unit", "")
                if isinstance(value, (int, float)):
                    lines.append(f"  {name}: {value:.6e} {unit}")
                else:
                    lines.append(f"  {name}: {value} {unit}")
            if len(self.simulation.op_points) > self.max_op_points:
                lines.append(f"  ... and {len(self.simulation.op_points) - self.max_op_points} more")
        
        # Signal summaries
        if self.simulation.signal_summaries:
            lines.append("")
            lines.append("### Signal Summaries")
            for sig in self.simulation.signal_summaries[:self.max_signals]:
                name = sig.get("name", "?")
                lines.append(f"  {name}:")
                for key, val in sig.items():
                    if key != "name" and val is not None:
                        # Format floats in engineering notation
                        if isinstance(val, float):
                            # Use appropriate precision
                            if abs(val) >= 100:
                                lines.append(f"    {key}: {val:.3f}")
                            elif abs(val) >= 1:
                                lines.append(f"    {key}: {val:.4f}")
                            else:
                                lines.append(f"    {key}: {val:.6e}")
                        else:
                            lines.append(f"    {key}: {val}")
            if len(self.simulation.signal_summaries) > self.max_signals:
                lines.append(f"  ... and {len(self.simulation.signal_summaries) - self.max_signals} more signals")
        
        # Warnings and errors
        if self.simulation.warnings:
            lines.append("")
            lines.append(f"Warnings ({len(self.simulation.warnings)}):")
            for w in self.simulation.warnings[:5]:
                lines.append(f"  - {w}")
        
        if self.simulation.errors:
            lines.append("")
            lines.append(f"Errors ({len(self.simulation.errors)}):")
            for e in self.simulation.errors:
                lines.append(f"  - {e}")
        
        # Full data hint
        if not self.include_full_data:
            lines.append("")
            lines.append("_Full waveform data available on request (e.g., 'show waveform V(out)')_")
        
        return "\n".join(lines)
