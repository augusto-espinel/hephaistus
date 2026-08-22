"""
Layer 1: Session state context for HephAIstus.

Dynamic context reflecting the current schematic, simulation, and user directives.
Refreshed on every request.
"""

import json
from typing import Optional

from ..session_state import SessionState, UserDirectives, ExpertiseLevel


def format_engineering(value_str: str) -> str:
    """
    Convert scientific notation to engineering notation for LLM readability.
    
    Examples:
        34e-3 → 34m
        22.5e-3 → 22.5m
        90e3 → 90k
        1.89e-3 → 1.89m
        0.022 → 22m
    """
    if not value_str:
        return value_str
    
    try:
        val = float(value_str)
        abs_val = abs(val)
        if abs_val >= 1e6:
            return f"{val/1e6:.3g}M"
        elif abs_val >= 1e3:
            return f"{val/1e3:.3g}k"
        elif abs_val >= 1:
            return f"{val:.3g}"
        elif abs_val >= 1e-3:
            return f"{val*1e3:.3g}m"
        elif abs_val >= 1e-6:
            return f"{val*1e6:.3g}µ"
        elif abs_val >= 1e-9:
            return f"{val*1e9:.3g}n"
        elif abs_val >= 1e-12:
            return f"{val*1e12:.3g}p"
        else:
            return f"{val:.2e}"
    except (ValueError, TypeError):
        return value_str


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
        
        # Detailed component list
        if sch.components:
            lines.append("")
            lines.append("#### Components")
            for c in sch.components[:50]:  # Limit to avoid token bloat
                ref = c.get("reference", "?")
                lib_id = c.get("lib_id", "")
                value = c.get("value", "")
                # Format: R1 (Device:R) - 10k
                if value:
                    formatted_value = format_engineering(str(value))
                    lines.append(f"- {ref} ({lib_id}): {formatted_value}")
                else:
                    lines.append(f"- {ref} ({lib_id})")
                
                # Include pin-net assignments
                pins = c.get("pins", {})
                if pins:
                    pin_strs = []
                    # Handle both dict format {"1": "net_name"} and list format [{"number": "1", "net": "net_name"}]
                    if isinstance(pins, dict):
                        for pin_num, net_name in pins.items():
                            pin_strs.append(f"{pin_num}→{net_name}")
                    elif isinstance(pins, list):
                        for pin_info in pins:
                            pin_num = pin_info.get("number", "?")
                            net_name = pin_info.get("net", "?")
                            pin_strs.append(f"{pin_num}→{net_name}")
                    if pin_strs:
                        lines.append(f"  Pins: {', '.join(pin_strs)}")
            
            if sch.component_count > 50:
                lines.append(f"  ... and {sch.component_count - 50} more")
        
        # Net list (with pin membership)
        if sch.nets:
            lines.append("")
            lines.append("#### Nets")
            for n in sch.nets[:30]:  # Limit
                name = n.get("name", "?")
                # Use connectedPins from parser if available
                connected = n.get("connectedPins", n.get("pins", []))
                if isinstance(connected, list) and len(connected) > 0:
                    # Show pin list for nets with connections
                    pin_str = ', '.join(str(p) for p in connected[:10])
                    extra = f" +{len(connected)-10} more" if len(connected) > 10 else ""
                    lines.append(f"- {name}: {len(connected)} pins ({pin_str}{extra})")
                else:
                    lines.append(f"- {name}")
            
            if sch.net_count > 30:
                lines.append(f"  ... and {sch.net_count - 30} more")
        
        # Simulation directives
        if sch.directives:
            lines.append("")
            lines.append("#### Simulation Directives")
            for d in sch.directives:
                text = d.get("text", "")
                lines.append(f"{text}")
        
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
        
        # SPICE libraries
        if self.session.spice_libraries:
            lines.append("")
            lines.append("### SPICE Models")
            for lib in self.session.spice_libraries:
                lines.append(f"")
                lines.append(f"#### {lib.name}")
                
                # List subcircuits and models
                if lib.subcircuits:
                    lines.append(f"Subcircuits: {', '.join(lib.subcircuits)}")
                if lib.models:
                    lines.append(f"Models: {', '.join(lib.models)}")
                
                # Include full content (comments already stripped)
                lines.append("")
                lines.append(lib.content)
        
        return "\n".join(lines)
