"""
Layer 3: Reasoning trace context for HephAIstus.

Condensed decision points with rationale for audit trail.
"""

from typing import Optional

from ..reasoning_trace import ReasoningTrace


class ReasoningLayer:
    """
    Layer 3: Reasoning trace context.
    
    Key decisions with rationale, not full chain-of-thought.
    Enables engineers to understand WHY certain approaches were chosen.
    """
    
    def __init__(self, trace: ReasoningTrace, max_entries: Optional[int] = None):
        self.trace = trace
        self.max_entries = max_entries
    
    def generate(self) -> str:
        """
        Generate the reasoning trace context string.
        
        Returns:
            Formatted reasoning trace for LLM prompt
        """
        return self.trace.format_for_context(max_entries=self.max_entries)
