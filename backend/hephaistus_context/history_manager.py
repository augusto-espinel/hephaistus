"""
Conversation history management for HephAIstus.

Provides windowed history with summarization of older exchanges.
"""

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class HistoryEntry:
    """A single exchange in the conversation history."""
    
    id: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    # User input
    user_request: str = ""
    user_context: Optional[str] = None  # Any additional context user provided
    
    # LLM output
    llm_response: str = ""
    reasoning_summary: str = ""
    patch_plan: Optional[Dict[str, Any]] = None
    
    # Validation
    validation_result: Optional[str] = None  # "passed", "failed", None
    validation_details: Optional[Dict[str, Any]] = None
    
    # User action
    user_action: Optional[str] = None  # "accepted", "rejected", "modified", None
    user_feedback: Optional[str] = None
    
    # Token tracking
    context_tokens_used: int = 0
    response_tokens_used: int = 0
    
    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())[:12]
    
    def to_dict(self) -> dict:
        """Serialize entry."""
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "user_request": self.user_request,
            "llm_response_summary": self.llm_response[:200] if self.llm_response else "",
            "reasoning_summary": self.reasoning_summary,
            "has_patch_plan": self.patch_plan is not None,
            "validation_result": self.validation_result,
            "user_action": self.user_action,
        }
    
    def compact(self) -> dict:
        """Generate compact representation for context."""
        result = {
            "id": self.id,
            "request": self.user_request[:100],
            "action": self.user_action,
        }
        if self.reasoning_summary:
            result["reasoning"] = self.reasoning_summary[:150]
        if self.patch_plan:
            result["intent"] = self.patch_plan.get("intent", "")[:100]
        return result


@dataclass
class HistorySummary:
    """Summarized version of older history entries."""
    
    period_start: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    period_end: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    entry_count: int = 0
    summary_text: str = ""
    key_decisions: List[str] = field(default_factory=list)
    rejected_approaches: List[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "period": f"{self.period_start.isoformat()} to {self.period_end.isoformat()}",
            "entries": self.entry_count,
            "summary": self.summary_text,
            "key_decisions": self.key_decisions,
            "rejected": self.rejected_approaches,
        }


class HistoryManager:
    """
    Manages conversation history with windowed access.
    
    Recent exchanges are kept in full detail.
    Older exchanges are summarized to save tokens.
    """
    
    def __init__(self, max_window: int = 10):
        self.entries: List[HistoryEntry] = []
        self.summaries: List[HistorySummary] = []
        self.max_window = max_window
    
    def add_entry(self, entry: HistoryEntry) -> None:
        """Add a new exchange to history."""
        self.entries.append(entry)
        
        # If we exceed window, summarize oldest entries
        while len(self.entries) > self.max_window:
            self._summarize_oldest()
    
    def _summarize_oldest(self) -> None:
        """Summarize the oldest batch of entries."""
        if not self.entries:
            return
        
        # Take oldest entries (batch of min_window)
        batch_size = min(3, len(self.entries))
        batch = self.entries[:batch_size]
        
        # Build summary
        decisions = []
        rejected = []
        
        for entry in batch:
            if entry.user_action == "accepted" and entry.reasoning_summary:
                decisions.append(f"Step: {entry.user_request[:80]} → {entry.reasoning_summary[:80]}")
            elif entry.user_action == "rejected":
                rejected.append(f"{entry.user_request[:80]}")
        
        summary = HistorySummary(
            period_start=batch[0].timestamp,
            period_end=batch[-1].timestamp,
            entry_count=len(batch),
            summary_text=f"{len(batch)} exchanges: " + "; ".join(
                e.user_request[:50] for e in batch
            ),
            key_decisions=decisions,
            rejected_approaches=rejected,
        )
        
        self.summaries.append(summary)
        self.entries = self.entries[batch_size:]
    
    def get_recent(self, count: Optional[int] = None) -> List[HistoryEntry]:
        """Get recent entries in full detail."""
        if count is None:
            return self.entries
        return self.entries[-count:]
    
    def get_summaries(self) -> List[HistorySummary]:
        """Get summaries of older entries."""
        return self.summaries
    
    def format_for_context(self, include_summaries: bool = True) -> str:
        """
        Format history for LLM context.
        
        Args:
            include_summaries: Whether to include summaries of older exchanges
            
        Returns:
            Formatted history string
        """
        lines = []
        
        # Older summaries
        if include_summaries and self.summaries:
            lines.append("### Previous Session Summary")
            for summary in self.summaries:
                lines.append(f"- {summary.summary_text}")
                for decision in summary.key_decisions:
                    lines.append(f"  Decision: {decision}")
                for rejected in summary.rejected_approaches:
                    lines.append(f"  Rejected: {rejected}")
            lines.append("")
        
        # Recent entries (full detail)
        if self.entries:
            lines.append("### Recent Exchanges")
            for entry in self.entries:
                lines.append(f"**[{entry.id}]** User: {entry.user_request}")
                if entry.reasoning_summary:
                    lines.append(f"  Reasoning: {entry.reasoning_summary}")
                if entry.patch_plan:
                    intent = entry.patch_plan.get("intent", "")
                    if intent:
                        lines.append(f"  Proposed: {intent}")
                if entry.validation_result:
                    lines.append(f"  Validation: {entry.validation_result}")
                if entry.user_action:
                    lines.append(f"  User action: {entry.user_action}")
                lines.append("")
        
        return "\n".join(lines)
    
    def clear(self) -> None:
        """Clear all history."""
        self.entries = []
        self.summaries = []
    
    def export(self) -> dict:
        """Export all history for persistence."""
        return {
            "entries": [e.to_dict() for e in self.entries],
            "summaries": [s.to_dict() for s in self.summaries],
            "max_window": self.max_window,
        }
    
    def search(self, query: str, limit: int = 5) -> List[HistoryEntry]:
        """Search history by keyword."""
        query_lower = query.lower()
        results = []
        for entry in reversed(self.entries):
            if (query_lower in entry.user_request.lower() or
                query_lower in entry.llm_response.lower() or
                query_lower in entry.reasoning_summary.lower()):
                results.append(entry)
                if len(results) >= limit:
                    break
        return results
