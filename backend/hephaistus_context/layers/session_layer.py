"""
Layer 1: Session state context for HephAIstus.

Dynamic context reflecting the current schematic, simulation, and user directives.
Refreshed on every request.
"""

import json
from typing import Optional

from ..session_state import SessionState, UserDirectives, ExpertiseLevel


class SessionLayer:
    """
    Layer 1: Dynamic session state context.
    
    Always reflects the latest schematic and simulation state.
    Includes user directives controlling LLM behavior.
    """
    
    def __init__(self, session: SessionState):
        self.session = session
    
    def generate(self) -> str:
        """
        Generate the session state context string.
        
        Returns:
            Formatted session state for LLM prompt
        """
        lines = ["## Current Session State"]
        
        # Schematic summary
        lines.append("### Schematic")
        sch = self.session.schematic
        lines.append(f"File: {sch.path or '(none loaded)'}")
        lines.append(f"Components: {sch.component_count}")
        lines.append(f"Nets: {sch.net_count}")
        
        if sch.components:
            refs = [c.get("reference", "?") for c in sch.components[:25]]
            lines.append(f"References: {', '.join(refs)}")
            if sch.component_count > 25:
                lines.append(f"  ... and {sch.component_count - 25} more")
        
        if sch.directives:
            lines.append("Simulation directives:")
            for d in sch.directives:
                dtype = d.get("directive_type", "unknown")
                text = d.get("text", "")
                lines.append(f"  {text}")
        
        # Simulation state
        lines.append("")
        lines.append("### Simulation State")
        sim = self.session.simulation
        
        status_emoji = {
            "current": "✓",
            "stale": "⚠️",
            "none": "—",
        }
        emoji = status_emoji.get(sim.status.value, "?")
        lines.append(f"Status: {sim.status.value} {emoji}")
        
        if sim.converged is not None:
            lines.append(f"Converged: {'Yes' if sim.converged else 'No'}")
        
        if sim.analysis_type:
            lines.append(f"Analysis: {sim.analysis_type}")
        
        if sim.staleness_warning:
            lines.append(f"⚠️ {sim.staleness_warning}")
        
        if sim.signal_summaries:
            lines.append("Key signals:")
            for sig in sim.signal_summaries[:10]:
                name = sig.get("name", "?")
                final = sig.get("final", "N/A")
                lines.append(f"  {name}: final={final}")
        
        # User directives
        lines.append("")
        lines.append("### User Directives")
        directives = self.session.directives
        lines.append(f"Expertise: {directives.expertise_level.value}")
        lines.append(f"Change aggression: {directives.change_aggression.value}")
        lines.append(f"Behavior: {directives.behavior_description()}")
        
        if directives.target_metrics:
            lines.append(f"Target metrics: {', '.join(directives.target_metrics)}")
        
        return "\n".join(lines)
