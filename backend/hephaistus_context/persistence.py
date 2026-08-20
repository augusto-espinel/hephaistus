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
    
    Session files store:
    - Session metadata (id, timestamps)
    - Schematic state and hash
    - Simulation state
    - User directives
    - Conversation history
    - Reasoning trace
    """
    
    def __init__(self, save_dir: str = ".hephaistus/sessions"):
        self.save_dir = Path(save_dir)
        self.save_dir.mkdir(parents=True, exist_ok=True)
    
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
        history: HistoryManager,
        reasoning: ReasoningTrace,
        filename: Optional[str] = None,
    ) -> Path:
        """
        Save session state to JSON file.
        
        Args:
            session: Current session state
            history: Conversation history
            reasoning: Reasoning trace
            filename: Optional filename (defaults to session_id.json)
            
        Returns:
            Path to saved file
        """
        if filename is None:
            filename = f"{session.session_id}.json"
        
        filepath = self.save_dir / filename
        
        data = {
            "version": 1,
            "session": {
                "session_id": session.session_id,
                "created_at": self._serialize_datetime(session.created_at),
                "last_updated": self._serialize_datetime(session.last_updated),
                "schematic": {
                    "path": session.schematic.path,
                    "hash": session.schematic.hash,
                    "component_count": session.schematic.component_count,
                    "net_count": session.schematic.net_count,
                    "last_modified": self._serialize_datetime(session.schematic.last_modified),
                },
                "simulation": {
                    "status": session.simulation.status.value,
                    "last_run_id": session.simulation.last_run_id,
                    "last_run_timestamp": self._serialize_datetime(session.simulation.last_run_timestamp),
                    "analysis_type": session.simulation.analysis_type,
                    "converged": session.simulation.converged,
                    "staleness_warning": session.simulation.staleness_warning,
                },
                "directives": session.directives.to_dict(),
                "pending_patch_plan": session.pending_patch_plan,
            },
            "history": history.export(),
            "reasoning": reasoning.export(),
        }
        
        filepath.write_text(json.dumps(data, indent=2))
        return filepath
    
    def load_session(
        self,
        filename: str,
    ) -> tuple[SessionState, HistoryManager, ReasoningTrace]:
        """
        Load session state from JSON file.
        
        Args:
            filename: Session filename
            
        Returns:
            Tuple of (SessionState, HistoryManager, ReasoningTrace)
        """
        filepath = self.save_dir / filename
        data = json.loads(filepath.read_text())
        
        # Reconstruct session state
        session_data = data.get("session", {})
        
        schematic = SchematicState(
            path=session_data.get("schematic", {}).get("path", ""),
            hash=session_data.get("schematic", {}).get("hash", ""),
            component_count=session_data.get("schematic", {}).get("component_count", 0),
            net_count=session_data.get("schematic", {}).get("net_count", 0),
            last_modified=self._deserialize_datetime(
                session_data.get("schematic", {}).get("last_modified")
            ),
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
        
        session = SessionState(
            session_id=session_data.get("session_id", ""),
            created_at=self._deserialize_datetime(session_data.get("created_at")),
            last_updated=self._deserialize_datetime(session_data.get("last_updated")),
            schematic=schematic,
            simulation=simulation,
            directives=directives,
            pending_patch_plan=session_data.get("pending_patch_plan"),
        )
        
        # Reconstruct history
        history_data = data.get("history", {})
        history = HistoryManager(max_window=history_data.get("max_window", 10))
        
        # Note: Full history entries would need more detailed deserialization
        # For now, we just set the summaries
        for summary_data in history_data.get("summaries", []):
            summary = HistorySummary(
                period_start=self._deserialize_datetime(summary_data.get("period_start")),
                period_end=self._deserialize_datetime(summary_data.get("period_end")),
                entry_count=summary_data.get("entry_count", 0),
                summary_text=summary_data.get("summary", ""),
                key_decisions=summary_data.get("key_decisions", []),
                rejected_approaches=summary_data.get("rejected", []),
            )
            history.summaries.append(summary)
        
        # Reconstruct reasoning trace
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
        
        return session, history, reasoning
    
    def list_sessions(self) -> list[Dict[str, Any]]:
        """List all saved sessions."""
        sessions = []
        for filepath in sorted(self.save_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                data = json.loads(filepath.read_text())
                session_data = data.get("session", {})
                sessions.append({
                    "filename": filepath.name,
                    "session_id": session_data.get("session_id", "?"),
                    "schematic": session_data.get("schematic", {}).get("path", "(none)"),
                    "last_updated": session_data.get("last_updated", "?"),
                })
            except (json.JSONDecodeError, KeyError):
                continue
        return sessions
    
    def delete_session(self, filename: str) -> bool:
        """Delete a saved session file."""
        filepath = self.save_dir / filename
        if filepath.exists():
            filepath.unlink()
            return True
        return False