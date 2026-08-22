"""
Session persistence for HephAIstus.

Save and load session state to JSON for continuity across sessions.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from .session_state import (
    SessionState,
    SchematicState,
    SimulationState,
    UserDirectives,
    ExpertiseLevel,
    ChangeAggression,
    SimulationStatus,
)
from .history_manager import HistoryManager, HistoryEntry, HistorySummary
from .reasoning_trace import ReasoningTrace, DecisionPoint


class SessionPersistence:
    """
    Handles saving and loading session state to/from JSON.
    
    Sessions are stored project-relative in <project>/.hephaistus/session.json.
    
    This enables:
    - Project portability (session travels with project)
    - Git-friendly workflow (can .gitignore or commit)
    - Multiple projects without interference
    """
    
    def __init__(self, project_root: Optional[str] = None):
        """
        Initialize persistence for a project.
        
        Args:
            project_root: Path to KiCad project directory. If None, must be set
                          via set_project() before saving/loading.
        """
        self.project_root: Optional[Path] = Path(project_root) if project_root else None
    
    def set_project(self, project_root: str) -> None:
        """Set or update the project root."""
        self.project_root = Path(project_root)
    
    def _ensure_project_dir(self) -> Path:
        """Ensure .hephaistus directory exists and return its path."""
        if not self.project_root:
            raise ValueError("Project root not set. Call set_project() first.")
        
        hephaistus_dir = self.project_root / ".hephaistus"
        hephaistus_dir.mkdir(parents=True, exist_ok=True)
        return hephaistus_dir
    
    def session_file(self) -> Path:
        """Get the session.json path for current project."""
        return self._ensure_project_dir() / "session.json"
    
    def history_file(self) -> Path:
        """Get the history.db path for current project."""
        return self._ensure_project_dir() / "history.db"
    
    def simulations_dir(self) -> Path:
        """Get the simulations directory for current project."""
        sim_dir = self._ensure_project_dir() / "simulations"
        sim_dir.mkdir(exist_ok=True)
        return sim_dir
    
    def _serialize_datetime(self, dt: datetime) -> str:
        """Convert datetime to ISO string."""
        return dt.isoformat() if dt else None
    
    def _deserialize_datetime(self, s: Optional[str]) -> Optional[datetime]:
        """Parse ISO string to datetime."""
        if not s:
            return None
        # Handle timezone info
        if s.endswith('Z'):
            s = s[:-1] + '+00:00'
        return datetime.fromisoformat(s)
    
    def save_session(
        self,
        session: SessionState,
        history: Optional[HistoryManager] = None,
        reasoning: Optional[ReasoningTrace] = None,
    ) -> Path:
        """
        Save session state to project-relative JSON file.
        
        Args:
            session: Current session state
            history: Conversation history (optional)
            reasoning: Reasoning trace (optional)
            
        Returns:
            Path to saved file
        """
        filepath = self.session_file()
        
        data = {
            "version": 2,  # Bumped for project-relative paths
            "session": {
                "session_id": session.session_id,
                "project_root": session.project_root,
                "created_at": self._serialize_datetime(session.created_at),
                "last_updated": self._serialize_datetime(session.last_updated),
                "schematic": {
                    "path": session.schematic.path,
                    "relative_path": session.schematic.relative_path,
                    "hash": session.schematic.hash,
                    "component_count": session.schematic.component_count,
                    "net_count": session.schematic.net_count,
                    "last_modified": self._serialize_datetime(session.schematic.last_modified),
                    "components": session.schematic.components[:100],  # Limit for file size
                    "nets": session.schematic.nets[:50],  # Limit for file size
                    "directives": session.schematic.directives,
                },
                "simulation": {
                    "status": session.simulation.status.value,
                    "last_run_id": session.simulation.last_run_id,
                    "last_run_timestamp": self._serialize_datetime(session.simulation.last_run_timestamp),
                    "analysis_type": session.simulation.analysis_type,
                    "converged": session.simulation.converged,
                    "staleness_warning": session.simulation.staleness_warning,
                    "schematic_hash": session.simulation.schematic_hash,
                    "op_points": session.simulation.op_points[:30],
                    "signal_summaries": session.simulation.signal_summaries[:20],
                    "warnings": session.simulation.warnings[:10],
                    "errors": session.simulation.errors[:5],
                },
                "directives": session.directives.to_dict(),
                "pending_patch_plan": session.pending_patch_plan,
            },
            "history": history.export() if history else {},
            "reasoning": reasoning.export() if reasoning else {},
        }
        
        filepath.write_text(json.dumps(data, indent=2))
        return filepath
    
    def load_session(self) -> Optional[SessionState]:
        """
        Load session state from project-relative JSON file.
        
        Returns:
            SessionState if session file exists, None otherwise
        """
        filepath = self.session_file()
        if not filepath.exists():
            return None
        
        data = json.loads(filepath.read_text())
        
        # Reconstruct session state
        session_data = data.get("session", {})
        
        schematic = SchematicState(
            path=session_data.get("schematic", {}).get("path", ""),
            relative_path=session_data.get("schematic", {}).get("relative_path", ""),
            hash=session_data.get("schematic", {}).get("hash", ""),
            component_count=session_data.get("schematic", {}).get("component_count", 0),
            net_count=session_data.get("schematic", {}).get("net_count", 0),
            last_modified=self._deserialize_datetime(
                session_data.get("schematic", {}).get("last_modified")
            ),
            components=session_data.get("schematic", {}).get("components", []),
            nets=session_data.get("schematic", {}).get("nets", []),
            directives=session_data.get("schematic", {}).get("directives", []),
        )
        
        simulation = SimulationState(
            status=SimulationStatus(session_data.get("simulation", {}).get("status", "none")),
            last_run_id=session_data.get("simulation", {}).get("last_run_id"),
            last_run_timestamp=self._deserialize_datetime(
                session_data.get("simulation", {}).get("last_run_timestamp")
            ),
            analysis_type=session_data.get("simulation", {}).get("analysis_type"),
            converged=session_data.get("simulation", {}).get("converged"),
            staleness_warning=session_data.get("simulation", {}).get("staleness_warning"),
            schematic_hash=session_data.get("simulation", {}).get("schematic_hash"),
            op_points=session_data.get("simulation", {}).get("op_points", []),
            signal_summaries=session_data.get("simulation", {}).get("signal_summaries", []),
            warnings=session_data.get("simulation", {}).get("warnings", []),
            errors=session_data.get("simulation", {}).get("errors", []),
        )
        
        directives_data = session_data.get("directives", {})
        directives = UserDirectives(
            expertise_level=ExpertiseLevel(directives_data.get("expertise_level", "professional")),
            change_aggression=ChangeAggression(directives_data.get("change_aggression", "moderate")),
            explain_steps=directives_data.get("explain_steps", False),
            show_alternatives=directives_data.get("show_alternatives", False),
            verbose_reasoning=directives_data.get("verbose_reasoning", False),
            pause_before_apply=directives_data.get("pause_before_apply", True),
            target_metrics=directives_data.get("target_metrics", ["performance"]),
        )
        
        return SessionState(
            session_id=session_data.get("session_id", ""),
            project_root=session_data.get("project_root", ""),
            created_at=self._deserialize_datetime(session_data.get("created_at")),
            last_updated=self._deserialize_datetime(session_data.get("last_updated")),
            schematic=schematic,
            simulation=simulation,
            directives=directives,
            pending_patch_plan=session_data.get("pending_patch_plan"),
        )
    
    def has_session(self) -> bool:
        """Check if a session file exists for the current project."""
        return self.session_file().exists()
    
    def discover_project_root(self, schematic_path: str) -> str:
        """
        Infer project root from schematic path.
        
        Looks for:
        - Directory containing .kicad_pro file (KiCad 6+)
        - Directory containing .kicad_sch file (KiCad 5 fallback)
        - Parent directory of schematic if no project file found
        
        Args:
            schematic_path: Path to .kicad_sch file
            
        Returns:
            Inferred project root directory
        """
        sch_path = Path(schematic_path).resolve()
        parent = sch_path.parent
        
        # Look for .kicad_pro file in parent directories
        for candidate in [parent] + list(parent.parents):
            if list(candidate.glob("*.kicad_pro")):
                return str(candidate)
        
        # Fallback: use schematic's parent directory
        return str(parent)
        
    def load_history(self) -> HistoryManager:
        """Load history manager from project-relative history.db."""
        history = HistoryManager()
        # HistoryStore handles SQLite persistence internally
        # This is kept for compatibility but history is now in HistoryStore
        return history
    
    def load_reasoning(self) -> ReasoningTrace:
        """Load reasoning trace from session file."""
        filepath = self.session_file()
        if not filepath.exists():
            return ReasoningTrace()
        
        data = json.loads(filepath.read_text())
        reasoning_data = data.get("reasoning", {})
        reasoning = ReasoningTrace()
        reasoning._step_counter = reasoning_data.get("step_counter", 0)
        
        for dp_data in reasoning_data.get("decisions", []):
            dp = DecisionPoint(
                id=dp_data.get("id", ""),
                step=dp_data.get("step", 0),
                decision=dp_data.get("decision", ""),
                rationale=dp_data.get("rationale", ""),
                alternatives_rejected=dp_data.get("alternatives_rejected", []),
            )
            reasoning.decisions.append(dp)
        
        return reasoning
    
    def clear_session(self) -> bool:
        """Delete session file for current project."""
        filepath = self.session_file()
        if filepath.exists():
            filepath.unlink()
            return True
        return False