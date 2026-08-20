"""
HephAIstus Context Management Service.

Assembles layered LLM context from schematic state, simulation results,
conversation history, and user directives.
"""

from .context_service import ContextService, ContextAssemblyResult
from .token_budget import (
    TokenBudget,
    TokenBudgetConfig,
    LayerPriority,
    LayerUsage,
)
from .session_state import (
    SessionState,
    UserDirectives,
    SchematicState,
    SimulationState,
    ExpertiseLevel,
    ChangeAggression,
    SimulationStatus,
)
from .history_manager import HistoryManager, HistoryEntry, HistorySummary
from .reasoning_trace import ReasoningTrace, DecisionPoint
from .persistence import SessionPersistence
from .history_store import HistoryStore, HistoryEntryRecord, SearchResult

__all__ = [
    # Core service
    "ContextService",
    "ContextAssemblyResult",
    # Token budget
    "TokenBudget",
    "TokenBudgetConfig",
    "LayerPriority",
    "LayerUsage",
    # Session state
    "SessionState",
    "UserDirectives",
    "SchematicState",
    "SimulationState",
    "ExpertiseLevel",
    "ChangeAggression",
    "SimulationStatus",
    # History
    "HistoryManager",
    "HistoryEntry",
    "HistorySummary",
    # Reasoning
    "ReasoningTrace",
    "DecisionPoint",
    # Persistence
    "SessionPersistence",
    # History Store
    "HistoryStore",
    "HistoryEntryRecord",
    "SearchResult",
]
