"""
Reasoning trace management for HephAIstus.

Tracks key decisions and rationale as a condensed audit trail.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class DecisionPoint:
    """A key decision made during the session."""
    
    id: str = ""
    step: int = 0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    # The decision
    decision: str = ""
    rationale: str = ""
    
    # Alternatives considered
    alternatives_considered: List[str] = field(default_factory=list)
    alternatives_rejected: List[str] = field(default_factory=list)
    rejection_reasons: List[str] = field(default_factory=list)
    
    # Context
    user_constraint: Optional[str] = None
    triggered_by: Optional[str] = None  # What prompted this decision
    
    # Outcome
    outcome: Optional[str] = None  # "successful", "revised", "abandoned"
    outcome_note: Optional[str] = None
    
    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())[:12]
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "step": self.step,
            "decision": self.decision,
            "rationale": self.rationale,
            "alternatives_rejected": self.alternatives_rejected,
            "outcome": self.outcome,
        }
    
    def compact(self) -> str:
        """Generate compact single-line representation."""
        parts = [f"[Step {self.step}] {self.decision}"]
        if self.rationale:
            parts.append(f"Reason: {self.rationale[:80]}")
        if self.alternatives_rejected:
            parts.append(f"Rejected: {', '.join(self.alternatives_rejected[:3])}")
        return " | ".join(parts)


class ReasoningTrace:
    """
    Manages the condensed reasoning trace for context Layer 3.
    
    Unlike full conversation history, this tracks only key decisions
    with their rationale, enabling engineers to understand WHY
    certain approaches were chosen.
    """
    
    def __init__(self, max_entries: int = 20):
        self.decisions: List[DecisionPoint] = []
        self.max_entries = max_entries
        self._step_counter = 0
    
    def add_decision(
        self,
        decision: str,
        rationale: str,
        alternatives_considered: Optional[List[str]] = None,
        alternatives_rejected: Optional[List[str]] = None,
        rejection_reasons: Optional[List[str]] = None,
        user_constraint: Optional[str] = None,
        triggered_by: Optional[str] = None,
    ) -> DecisionPoint:
        """
        Record a key decision point.
        
        Args:
            decision: What was decided
            rationale: Why it was decided this way
            alternatives_considered: Other options evaluated
            alternatives_rejected: Options explicitly rejected
            rejection_reasons: Why alternatives were rejected
            user_constraint: Any user-imposed constraint
            triggered_by: What prompted this decision
            
        Returns:
            The created DecisionPoint
        """
        self._step_counter += 1
        
        dp = DecisionPoint(
            step=self._step_counter,
            decision=decision,
            rationale=rationale,
            alternatives_considered=alternatives_considered or [],
            alternatives_rejected=alternatives_rejected or [],
            rejection_reasons=rejection_reasons or [],
            user_constraint=user_constraint,
            triggered_by=triggered_by,
        )
        
        self.decisions.append(dp)
        
        # Enforce max entries
        while len(self.decisions) > self.max_entries:
            self.decisions.pop(0)
            # Renumber steps
            for i, d in enumerate(self.decisions):
                d.step = i + 1
        
        return dp
    
    def mark_outcome(self, decision_id: str, outcome: str, note: str = "") -> bool:
        """
        Mark the outcome of a decision.
        
        Args:
            decision_id: ID of the decision
            outcome: "successful", "revised", "abandoned"
            note: Additional outcome note
            
        Returns:
            True if decision was found and updated
        """
        for dp in self.decisions:
            if dp.id == decision_id:
                dp.outcome = outcome
                dp.outcome_note = note
                return True
        return False
    
    def get_recent(self, count: int = 5) -> List[DecisionPoint]:
        """Get the most recent decisions."""
        return self.decisions[-count:]
    
    def format_for_context(self, max_entries: Optional[int] = None) -> str:
        """
        Format reasoning trace for LLM context.
        
        Args:
            max_entries: Maximum entries to include (default: all)
            
        Returns:
            Formatted reasoning string
        """
        entries = self.decisions
        if max_entries:
            entries = entries[-max_entries:]
        
        if not entries:
            return "No decisions recorded yet."
        
        lines = ["### Decision Trace"]
        
        for dp in entries:
            lines.append(f"**Step {dp.step}:** {dp.decision}")
            lines.append(f"  Rationale: {dp.rationale}")
            
            if dp.alternatives_rejected:
                lines.append(f"  Rejected: {', '.join(dp.alternatives_rejected[:3])}")
                if dp.rejection_reasons:
                    for reason in dp.rejection_reasons[:2]:
                        lines.append(f"    - {reason}")
            
            if dp.user_constraint:
                lines.append(f"  Constraint: {dp.user_constraint}")
            
            if dp.outcome:
                lines.append(f"  Outcome: {dp.outcome}")
                if dp.outcome_note:
                    lines.append(f"    {dp.outcome_note}")
            
            lines.append("")
        
        return "\n".join(lines)
    
    def search(self, query: str) -> List[DecisionPoint]:
        """Search decisions by keyword."""
        query_lower = query.lower()
        results = []
        for dp in reversed(self.decisions):
            if (query_lower in dp.decision.lower() or
                query_lower in dp.rationale.lower()):
                results.append(dp)
        return results
    
    def export(self) -> dict:
        """Export all decisions for persistence."""
        return {
            "decisions": [d.to_dict() for d in self.decisions],
            "step_counter": self._step_counter,
        }
    
    def clear(self) -> None:
        """Clear all decisions."""
        self.decisions = []
        self._step_counter = 0
