"""
Context Service — Main orchestrator for HephAIstus context assembly.

Assembles layered LLM context from all components with token budget enforcement.
"""

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

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
from .history_manager import HistoryManager, HistoryEntry
from .reasoning_trace import ReasoningTrace, DecisionPoint
from .layers.system_layer import SystemLayer
from .layers.session_layer import SessionLayer
from .layers.history_layer import HistoryLayer
from .layers.reasoning_layer import ReasoningLayer
from .layers.simulation_layer import SimulationLayer


@dataclass
class ContextAssemblyResult:
    """Result of context assembly operation."""
    
    # The assembled prompt
    prompt: str = ""
    
    # Token usage breakdown
    budget: Optional[TokenBudget] = None
    
    # Metadata
    session_id: str = ""
    assembled_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    total_tokens: int = 0
    
    # Layer contents (for debugging/inspection)
    layer_contents: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        """Serialize result for debugging/inspection."""
        return {
            "session_id": self.session_id,
            "assembled_at": self.assembled_at.isoformat(),
            "total_tokens": self.total_tokens,
            "budget_summary": self.budget.summary() if self.budget else None,
            "layers": {
                name: {
                    "content_length": len(content),
                    "preview": content[:200] + "..." if len(content) > 200 else content,
                }
                for name, content in self.layer_contents.items()
            },
        }


class ContextService:
    """
    Main context assembly orchestrator for HephAIstus.
    
    Manages the complete lifecycle of LLM context:
    1. Refresh session state from schematic
    2. Assemble context layers in priority order
    3. Enforce token budgets with priority-based truncation
    4. Return structured prompt for LLM consumption
    """
    
    def __init__(
        self,
        budget_config: Optional[TokenBudgetConfig] = None,
        history_window: int = 10,
        include_schema: bool = True,
    ):
        self.budget_config = budget_config or TokenBudgetConfig()
        self.include_schema = include_schema
        
        # Core components
        self.session = SessionState(session_id=str(uuid.uuid4())[:12])
        self.history = HistoryManager(max_window=history_window)
        self.reasoning = ReasoningTrace()
        self.budget = TokenBudget(config=self.budget_config)
        
        # Layer generators
        self._system_layer = SystemLayer(include_schema=include_schema)
    
    def initialize_session(
        self,
        schematic_path: Optional[str] = None,
        parsed_state: Optional[Dict] = None,
        expertise_level: str = "professional",
        change_aggression: str = "moderate",
        explain_steps: bool = False,
    ) -> SessionState:
        """Initialize or reset the session state."""
        self.session = SessionState(session_id=str(uuid.uuid4())[:12])
        self.history.clear()
        self.reasoning.clear()
        self.budget.reset()
        
        self.session.directives = UserDirectives(
            expertise_level=ExpertiseLevel(expertise_level),
            change_aggression=ChangeAggression(change_aggression),
            explain_steps=explain_steps,
        )
        
        if schematic_path:
            self.session.refresh_schematic(schematic_path, parsed_state)
        
        return self.session
    
    def refresh_schematic(self, schematic_path: str, parsed_state: Optional[Dict] = None) -> None:
        """Refresh schematic state from file."""
        self.session.refresh_schematic(schematic_path, parsed_state)
    
    def update_simulation(
        self,
        analysis_type: Optional[str] = None,
        converged: Optional[bool] = None,
        op_points: Optional[List[Dict]] = None,
        signal_summaries: Optional[List[Dict]] = None,
        warnings: Optional[List[str]] = None,
        errors: Optional[List[str]] = None,
    ) -> None:
        """Update simulation state with new results."""
        self.session.simulation.status = SimulationStatus.CURRENT
        self.session.simulation.staleness_warning = None
        self.session.simulation.analysis_type = analysis_type
        self.session.simulation.converged = converged
        
        if op_points is not None:
            self.session.simulation.op_points = op_points
        if signal_summaries is not None:
            self.session.simulation.signal_summaries = signal_summaries
        if warnings is not None:
            self.session.simulation.warnings = warnings
        if errors is not None:
            self.session.simulation.errors = errors
        
        self.session.last_updated = datetime.now(timezone.utc)
    
    def record_exchange(
        self,
        user_request: str,
        llm_response: str,
        reasoning_summary: str = "",
        patch_plan: Optional[Dict] = None,
        validation_result: Optional[str] = None,
        user_action: Optional[str] = None,
        context_tokens: int = 0,
        response_tokens: int = 0,
    ) -> HistoryEntry:
        """Record a conversation exchange."""
        entry = HistoryEntry(
            user_request=user_request,
            llm_response=llm_response,
            reasoning_summary=reasoning_summary,
            patch_plan=patch_plan,
            validation_result=validation_result,
            user_action=user_action,
            context_tokens_used=context_tokens,
            response_tokens_used=response_tokens,
        )
        self.history.add_entry(entry)
        return entry
    
    def record_decision(
        self,
        decision: str,
        rationale: str,
        alternatives_rejected: Optional[List[str]] = None,
        user_constraint: Optional[str] = None,
    ) -> DecisionPoint:
        """Record a key decision point."""
        return self.reasoning.add_decision(
            decision=decision,
            rationale=rationale,
            alternatives_rejected=alternatives_rejected or [],
            user_constraint=user_constraint,
        )
    
    def assemble(
        self,
        user_request: str = "",
        include_full_simulation: bool = False,
    ) -> ContextAssemblyResult:
        """
        Assemble the complete LLM context.
        
        Args:
            user_request: The current user request (prepended to context)
            include_full_simulation: Include full waveform data
            
        Returns:
            ContextAssemblyResult with prompt and metadata
        """
        self.budget.reset()
        layer_contents = {}
        
        # === Layer 0: System (never truncated) ===
        system_content = self._system_layer.generate()
        system_content, system_usage = self.budget.track_layer(
            layer="system",
            content=system_content,
            priority=LayerPriority.SYSTEM,
            max_tokens=self.budget_config.system_max,
            allow_truncation=False,
        )
        layer_contents["system"] = system_content
        
        # === Layer 1: Session State (rarely truncated) ===
        session_layer = SessionLayer(self.session)
        session_content = session_layer.generate()
        session_content, session_usage = self.budget.track_layer(
            layer="session",
            content=session_content,
            priority=LayerPriority.SESSION,
            max_tokens=self.budget_config.session_max,
            allow_truncation=True,
        )
        layer_contents["session"] = session_content
        
        # === Layer 2: History (windowed) ===
        history_layer = HistoryLayer(self.history, include_summaries=True)
        history_content = history_layer.generate()
        history_content, history_usage = self.budget.track_layer(
            layer="history",
            content=history_content,
            priority=LayerPriority.HISTORY,
            max_tokens=self.budget_config.history_max,
            allow_truncation=True,
        )
        layer_contents["history"] = history_content
        
        # === Layer 3: Reasoning ===
        reasoning_layer = ReasoningLayer(self.reasoning)
        reasoning_content = reasoning_layer.generate()
        reasoning_content, reasoning_usage = self.budget.track_layer(
            layer="reasoning",
            content=reasoning_content,
            priority=LayerPriority.REASONING,
            max_tokens=self.budget_config.reasoning_max,
            allow_truncation=True,
        )
        layer_contents["reasoning"] = reasoning_content
        
        # === Layer 4: Simulation ===
        sim_max = (
            self.budget_config.simulation_full_max 
            if include_full_simulation 
            else self.budget_config.simulation_max
        )
        simulation_layer = SimulationLayer(
            self.session.simulation,
            include_full_data=include_full_simulation,
        )
        simulation_content = simulation_layer.generate()
        simulation_content, simulation_usage = self.budget.track_layer(
            layer="simulation",
            content=simulation_content,
            priority=LayerPriority.SIMULATION,
            max_tokens=sim_max,
            allow_truncation=True,
        )
        layer_contents["simulation"] = simulation_content
        
        # === Assemble final prompt ===
        sections = []
        
        if user_request:
            sections.append(f"## Current Request\n{user_request}")
        
        sections.append(system_content)
        sections.append(session_content)
        sections.append(history_content)
        sections.append(reasoning_content)
        sections.append(simulation_content)
        
        prompt = "\n\n---\n\n".join(sections)
        
        return ContextAssemblyResult(
            prompt=prompt,
            budget=self.budget,
            session_id=self.session.session_id,
            total_tokens=self.budget.total_tokens,
            layer_contents=layer_contents,
        )
    
    def get_debug_view(self) -> dict:
        """
        Get detailed debug view of current context state.
        
        Returns comprehensive view for the Context Inspector UI feature.
        """
        return {
            "session": self.session.to_dict(),
            "history": {
                "recent_count": len(self.history.entries),
                "summary_count": len(self.history.summaries),
                "max_window": self.history.max_window,
            },
            "reasoning": {
                "decision_count": len(self.reasoning.decisions),
                "recent_decisions": [d.to_dict() for d in self.reasoning.get_recent(3)],
            },
            "budget": self.budget.summary(),
        }
