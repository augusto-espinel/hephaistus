"""
Layer 2: Conversation history context for HephAIstus.

Windowed history of exchanges with summarization of older entries.
"""

from typing import Optional

from ..history_manager import HistoryManager, HistoryEntry


class HistoryLayer:
    """
    Layer 2: Conversation history context.
    
    Recent exchanges in full detail, older exchanges summarized.
    Configurable window size.
    """
    
    def __init__(self, history: HistoryManager, include_summaries: bool = True):
        self.history = history
        self.include_summaries = include_summaries
    
    def generate(self) -> str:
        """
        Generate the history context string.
        
        Returns:
            Formatted history for LLM prompt
        """
        if not self.history.entries and not self.history.summaries:
            return "## Conversation History\n(No previous exchanges in this session)"
        
        return self.history.format_for_context(
            include_summaries=self.include_summaries
        )
