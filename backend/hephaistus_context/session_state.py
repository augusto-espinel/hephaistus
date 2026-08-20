"""
Session state management for HephAIstus.

Tracks the current schematic state, simulation results, and user directives.
"""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class ExpertiseLevel(str, Enum):
    """User expertise level controlling LLM behavior."""
    STUDENT = "student"
    HOBBYIST = "hobbyist"
    PROFESSIONAL = "professional"


class ChangeAggression(str, Enum):
    """How aggressively the LLM should propose changes."""
    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"


class SimulationStatus(str, Enum):
    """Status of simulation results relative to current schematic."""
    CURRENT = "current"       # Simulation matches schematic
    STALE = "stale"           # Schematic modified since last simulation
    NO_SIMULATION = "none"    # No simulation run yet


@dataclass
class UserDirectives:
    """User-configurable parameters controlling LLM behavior."""
    
    expertise_level: ExpertiseLevel = ExpertiseLevel.PROFESSIONAL
    change_aggression: ChangeAggression = ChangeAggression.MODERATE
    explain_steps: bool = False
    show_alternatives: bool = False
    verbose_reasoning: bool = False
    pause_before_apply: bool = True  # Always ask before applying
    target_metrics: List[str] = field(default_factory=lambda: ["performance"])
    
    def to_dict(self) -> dict:
        return {
            "expertise_level": self.expertise_level.value,
            "change_aggression": self.change_aggression.value,
            "explain_steps": self.explain_steps,
            "show_alternatives": self.show_alternatives,
            "verbose_reasoning": self.verbose_reasoning,
            "pause_before_apply": self.pause_before_apply,
            "target_metrics": self.target_metrics,
        }
    
    def behavior_description(self) -> str:
        """Generate natural language description of current behavior settings."""
        parts = []
        
        if self.expertise_level == ExpertiseLevel.STUDENT:
            parts.append("Explain each step thoroughly. Suggest alternatives. Ask before applying.")
        elif self.expertise_level == ExpertiseLevel.HOBBYIST:
            parts.append("Balance explanation and action. Moderate caution.")
        else:
            parts.append("Propose complete solutions. Minimal explanation. Trust validation.")
        
        if self.change_aggression == ChangeAggression.CONSERVATIVE:
            parts.append("One change at a time. Wait for acceptance before proceeding.")
        elif self.change_aggression == ChangeAggression.MODERATE:
            parts.append("Propose related changes together. Still ask before applying.")
        else:
            parts.append("Propose complete solutions. Batch related changes.")
        
        if self.explain_steps:
            parts.append("Explain reasoning for each step.")
        
        if self.show_alternatives:
            parts.append("Show alternative approaches when available.")
        
        return " ".join(parts)


@dataclass
class SchematicState:
    """Current state of the schematic."""
    
    path: str = ""
    hash: str = ""
    last_modified: Optional[datetime] = None
    component_count: int = 0
    net_count: int = 0
    components: List[Dict[str, Any]] = field(default_factory=list)
    nets: List[Dict[str, Any]] = field(default_factory=list)
    directives: List[Dict[str, Any]] = field(default_factory=list)
    
    def compute_hash(self) -> str:
        """Compute hash of schematic file for staleness detection."""
        if self.path and Path(self.path).exists():
            content = Path(self.path).read_bytes()
            return hashlib.sha256(content).hexdigest()[:16]
        return self.hash
    
    def summary(self) -> dict:
        """Generate compact summary for context."""
        refs = [c.get("reference", "?") for c in self.components[:20]]
        return {
            "path": self.path,
            "components": self.component_count,
            "nets": self.net_count,
            "references": refs,
            "directives": [
                {"type": d.get("directive_type"), "text": d.get("text")}
                for d in self.directives
            ],
            "last_modified": self.last_modified.isoformat() if self.last_modified else None,
        }


@dataclass
class SimulationState:
    """Current state of simulation results."""
    
    status: SimulationStatus = SimulationStatus.NO_SIMULATION
    last_run_id: Optional[str] = None
    last_run_timestamp: Optional[datetime] = None
    analysis_type: Optional[str] = None
    converged: Optional[bool] = None
    staleness_warning: Optional[str] = None
    
    # Summary data (always available)
    op_points: List[Dict[str, Any]] = field(default_factory=list)
    signal_summaries: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    
    def mark_stale(self, reason: str = "Schematic modified after last simulation") -> None:
        """Mark simulation results as stale."""
        self.status = SimulationStatus.STALE
        self.staleness_warning = reason
    
    def summary(self) -> dict:
        """Generate compact summary for context."""
        result = {
            "status": self.status.value,
            "converged": self.converged,
        }
        
        if self.analysis_type:
            result["analysis_type"] = self.analysis_type
        
        if self.staleness_warning:
            result["staleness_warning"] = self.staleness_warning
        
        if self.op_points:
            result["op_points_count"] = len(self.op_points)
        
        if self.signal_summaries:
            result["signals"] = self.signal_summaries
        
        if self.warnings:
            result["warnings_count"] = len(self.warnings)
        
        if self.errors:
            result["errors"] = self.errors
        
        return result


@dataclass
class SessionState:
    """
    Complete session state combining schematic, simulation, and user directives.
    
    This is the single source of truth for Layer 1 context.
    """
    
    session_id: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    schematic: SchematicState = field(default_factory=SchematicState)
    simulation: SimulationState = field(default_factory=SimulationState)
    directives: UserDirectives = field(default_factory=UserDirectives)
    
    # Pending changes
    pending_patch_plan: Optional[Dict[str, Any]] = None
    pending_validation: Optional[Dict[str, Any]] = None
    
    def refresh_schematic(self, schematic_path: str, parsed_state: Optional[Dict] = None) -> None:
        """
        Refresh schematic state from file.
        
        Args:
            schematic_path: Path to .kicad_sch file
            parsed_state: Pre-parsed state (if available)
        """
        self.schematic.path = schematic_path
        self.schematic.last_modified = datetime.now(timezone.utc)
        
        if parsed_state:
            self.schematic.hash = self.schematic.compute_hash()
            self.schematic.components = parsed_state.get("components", [])
            self.schematic.nets = parsed_state.get("nets", [])
            self.schematic.directives = parsed_state.get("simulation_directives", [])
            self.schematic.component_count = len(self.schematic.components)
            self.schematic.net_count = len(self.schematic.nets)
            
            # Check if simulation is now stale
            if self.simulation.status == SimulationStatus.CURRENT:
                self.simulation.mark_stale()
        
        self.last_updated = datetime.now(timezone.utc)
    
    def to_dict(self) -> dict:
        """Serialize session state."""
        return {
            "session_id": self.session_id,
            "created_at": self.created_at.isoformat(),
            "last_updated": self.last_updated.isoformat(),
            "schematic": self.schematic.summary(),
            "simulation": self.simulation.summary(),
            "directives": self.directives.to_dict(),
            "has_pending_patch": self.pending_patch_plan is not None,
        }
