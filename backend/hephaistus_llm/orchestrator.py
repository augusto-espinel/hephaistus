"""
LLM Orchestrator — Wires ContextService to LLM providers.

Provides a unified interface for generating patch-plans using
the assembled context from HephAIstus.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from hephaistus_context import (
    ContextService,
    ContextAssemblyResult,
    TokenBudgetConfig,
)
from hephaistus_context.session_state import UserDirectives, ExpertiseLevel
from .base import LLMConfig, LLMResponse, Message, MessageRole
from .config import ProviderConfig
from .providers.openrouter import OpenRouterProvider
from .providers.ollama import OllamaProvider


# Default system prompt for HephAIstus
HEPHAISTUS_SYSTEM_PROMPT = """You are HephAIstus, an AI assistant specialized in KiCad schematic design and SPICE simulation.

You help engineers design and optimize electronic circuits by proposing changes through a deterministic patch-plan system.

## Your Role

1. **Analyze** the schematic state and simulation results provided in context
2. **Propose** changes using the patch-plan schema (never modify files directly)
3. **Explain** your reasoning in terms of circuit behavior and design trade-offs
4. **Wait** for user approval before any changes are applied

## Key Principles

- Geometry (positions, wire routing) is the engineer's domain — you only propose connectivity changes
- All changes must pass validation before the user sees them
- Simulation results may be stale — always check the staleness indicator
- When uncertain, ask clarifying questions rather than guessing

## Response Format

If you have a proposed change, output exactly ONE JSON patch-plan block:

```json
{
  "schema": "hephaistus/patch-plan/v1",
  "intent": "Brief description of what this change accomplishes",
  "operations": [
    { "type": "component.add", ... },
    { "type": "net.split", ... }
  ],
  "rationale": "Why these specific values/connections"
}
```

If you need clarification, ask a direct question. Do not propose changes you are uncertain about.

## Choosing Between Alternatives

When multiple approaches could work, recommend ONE best option and explain your choice in the rationale.
Do NOT output multiple patch-plan JSON blocks. Mention alternatives briefly in your reasoning text if
they're worth considering, but only one patch-plan block per response.

Factors to consider when choosing:
- Computational efficiency (faster simulation)
- Accuracy (capturing essential behavior)
- Simplicity (easier to understand/modify)
- Robustness (convergence reliability)

State your recommendation clearly and commit to one plan.

## Output Discipline

**DO NOT output your internal reasoning process.** Start directly with your answer.

- Do NOT write "Let me think..." or "We need to analyze..." or similar preamble
- Do NOT output your step-by-step analysis as text before the answer
- Start immediately with either: the patch-plan JSON, or a brief clarifying question
- Keep any explanatory text SHORT (2-3 sentences max before the JSON)

Your response should be structured as:
1. Optional: 1-2 sentences of context (only if absolutely necessary)
2. The patch-plan JSON block (your primary output)
3. Optional: Brief rationale paragraph after the JSON

DO NOT spend tokens on lengthy preamble. Every token spent on "Let me think" is a token not available for your answer.
"""


# Thinking block patterns for models that reason in-band (DeepSeek-R1, etc.)
# These are compiled at module level for efficiency
_THINK_TAG_OPEN = "<think>"
_THINK_TAG_CLOSE = "</think>"
_THINKING_TAG_OPEN = "<thinking>"
_THINKING_TAG_CLOSE = "</thinking>"


@dataclass
class PatchPlanProposal:
    """A proposed patch-plan from the LLM."""
    
    raw_response: str
    patch_plan: Optional[Dict[str, Any]] = None
    reasoning: str = ""
    is_clarification: bool = False
    clarification_question: str = ""
    parse_error: Optional[str] = None
    # Thinking/reasoning blocks extracted from response (for models like DeepSeek-R1)
    thinking_content: str = ""
    # Display-friendly response (raw_response with thinking blocks condensed)
    display_response: str = ""
    
    def is_valid(self) -> bool:
        """Check if proposal contains a valid patch-plan."""
        return self.patch_plan is not None and self.parse_error is None


def _extract_thinking_blocks(content: str) -> tuple:
    """
    Extract thinking/reasoning blocks from LLM response.
    
    Supports models that output structured reasoning tags:
    - DeepSeek-R1: <think>...</think>
    - Some models: <thinking>...</thinking>
    
    Returns:
        (thinking_content, display_content) tuple where:
        - thinking_content: extracted reasoning text (empty string if none found)
        - display_content: content with thinking blocks replaced by collapsible marker
    """
    import re
    
    thinking_parts = []
    display_content = content
    
    # Pattern 1: <think>...</think> (DeepSeek-R1, some reasoning models)
    think_pattern = re.escape(_THINK_TAG_OPEN) + r'(.*?)' + re.escape(_THINK_TAG_CLOSE)
    matches = re.findall(think_pattern, content, re.DOTALL)
    if matches:
        thinking_parts.extend(matches)
        display_content = re.sub(think_pattern, '[reasoning...]', display_content, flags=re.DOTALL)
    
    # Pattern 2: <thinking>...</thinking> (some providers)
    thinking_pattern = re.escape(_THINKING_TAG_OPEN) + r'(.*?)' + re.escape(_THINKING_TAG_CLOSE)
    matches = re.findall(thinking_pattern, content, re.DOTALL)
    if matches:
        thinking_parts.extend(matches)
        display_content = re.sub(thinking_pattern, '[reasoning...]', display_content, flags=re.DOTALL)
    
    thinking_content = '\n'.join(thinking_parts).strip() if thinking_parts else ""
    
    return thinking_content, display_content


class LLMOrchestrator:
    """
    Orchestrates LLM interactions for HephAIstus.
    
    Manages:
    - Context assembly (ContextService)
    - LLM provider selection
    - Response parsing and validation
    - Token budget management
    """
    
    def __init__(
        self,
        provider_config: Optional[ProviderConfig] = None,
        budget_config: Optional[TokenBudgetConfig] = None,
        system_prompt: str = HEPHAISTUS_SYSTEM_PROMPT,
        context_service: Optional[ContextService] = None,
    ):
        """
        Initialize orchestrator.
        
        Args:
            provider_config: LLM provider configuration
            budget_config: Token budget configuration
            system_prompt: System prompt for the LLM
            context_service: Shared context service (if None, creates new instance)
        """
        self.provider_config = provider_config or ProviderConfig.openrouter()
        self.budget_config = budget_config or TokenBudgetConfig()
        self.system_prompt = system_prompt
        
        # Use shared context service if provided, otherwise create new
        self.context_service = context_service or ContextService(budget_config=self.budget_config)
        
        # Initialize provider
        self._provider = self._create_provider()
    
    def _save_last_prompt(self, context_result, messages, user_request):
        """
        Save last prompt+context to file for debugging.
        
        Written to <project>/.hephaistus/last_prompt.json, overwritten each call.
        """
        import json
        from pathlib import Path
        
        # Get project root from context service
        project_root = getattr(self.context_service.session, 'project_root', None)
        if not project_root:
            return  # No project loaded, skip
        
        debug_file = Path(project_root) / '.hephaistus' / 'last_prompt.json'
        debug_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Build debug payload
        payload = {
            'timestamp': context_result.assembled_at.isoformat() if context_result.assembled_at else None,
            'user_request': user_request,
            'total_tokens': context_result.total_tokens,
            'budget_summary': context_result.budget.summary() if context_result.budget else None,
            'messages': [
                {'role': m.role.value, 'content': m.content}
                for m in messages
            ],
            'assembled_context': context_result.prompt,
            'layers': context_result.layer_contents,
        }
        
        with open(debug_file, 'w') as f:
            json.dump(payload, f, indent=2)
    
    def _create_provider(self):
        """Create the appropriate LLM provider."""
        provider_type = self.provider_config.provider
        
        if provider_type == "openrouter":
            return OpenRouterProvider(api_key=self.provider_config.api_key)
        elif provider_type == "ollama":
            return OllamaProvider(base_url=self.provider_config.base_url or "http://localhost:11434")
        else:
            raise ValueError(f"Unsupported provider: {provider_type}")
    
    def set_provider(self, config: ProviderConfig) -> None:
        """Switch to a different LLM provider."""
        self.provider_config = config
        self._provider = self._create_provider()
    
    def assemble_context(
        self,
        user_request: str,
        include_full_simulation: bool = False,
    ) -> ContextAssemblyResult:
        """
        Assemble context for LLM prompt.
        
        Args:
            user_request: The user's request
            include_full_simulation: Include full simulation data
            
        Returns:
            ContextAssemblyResult with prompt and metadata
        """
        return self.context_service.assemble(
            user_request=user_request,
            include_full_simulation=include_full_simulation,
        )
    
    def generate(
        self,
        user_request: str,
        include_full_simulation: bool = False,
    ) -> PatchPlanProposal:
        """
        Generate a patch-plan proposal for the user request.
        
        This is the main entry point for LLM-powered schematic modifications.
        
        Args:
            user_request: The user's request in natural language
            include_full_simulation: Include full simulation data in context
            
        Returns:
            PatchPlanProposal with parsed patch-plan or clarification
        """
        # Assemble context
        context_result = self.assemble_context(user_request, include_full_simulation)
        
        # Build messages
        messages = [
            Message(role=MessageRole.SYSTEM, content=self.system_prompt),
            Message(role=MessageRole.USER, content=context_result.prompt),
        ]
        
        # Debug: write last prompt to file for inspection
        self._save_last_prompt(context_result, messages, user_request)
        
        # Build LLM config
        llm_config = LLMConfig(
            model=self.provider_config.model,
            temperature=self.provider_config.temperature,
            max_tokens=self.provider_config.max_tokens,
            system_prompt=None,  # Already in messages
        )
        
        # Call LLM
        response = self._provider.complete(messages, llm_config)
        
        # Parse response
        return self._parse_response(response.content)
    
    def _parse_response(self, content: str) -> PatchPlanProposal:
        """
        Parse LLM response to extract patch-plan or clarification.
        
        Handles models that output think-tag reasoning blocks
        (like DeepSeek-R1) by extracting them separately.
        
        Args:
            content: Raw LLM response content
            
        Returns:
            PatchPlanProposal with parsed content
        """
        import json
        import re
        
        # Handle None or empty content (e.g., tool_calls-only responses)
        content = content or ""
        
        # Guard: empty response after stripping indicates LLM failure
        if not content.strip():
            raise RuntimeError(
                "LLM returned empty response. This usually indicates a timeout, "
                "rate limit, or server error. Please check your provider status "
                "and try again. Consider increasing timeout_seconds if using a "
                "local model."
            )
        
        proposal = PatchPlanProposal(raw_response=content)
        
        # Extract thinking/reasoning blocks (for models like DeepSeek-R1)
        thinking_content, display_content = _extract_thinking_blocks(content)
        proposal.thinking_content = thinking_content
        proposal.display_response = display_content
        
        # Use display_content for further parsing (thinking blocks removed)
        parse_content = display_content
        
        # Check for clarification
        clarification_markers = [
            "could you clarify",
            "what is",
            "can you tell me more",
            "I need more information",
            "could you provide more details",
        ]
        content_lower = parse_content.lower()
        
        if any(marker in content_lower for marker in clarification_markers):
            proposal.is_clarification = True
            proposal.clarification_question = parse_content.strip()
            return proposal
        
        # Try to extract JSON patch-plan
        json_pattern = r'```json\s*([\s\S]*?)\s*```'
        matches = re.findall(json_pattern, parse_content)
        
        for match in matches:
            try:
                patch_plan = json.loads(match)
                
                # Validate schema
                if patch_plan.get("schema") == "hephaistus/patch-plan/v1":
                    proposal.patch_plan = patch_plan
                    proposal.reasoning = patch_plan.get("rationale", "")
                    return proposal
            except json.JSONDecodeError:
                continue
        
        # Try direct JSON
        try:
            # Find JSON object in content
            json_start = parse_content.find("{")
            json_end = parse_content.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                potential_json = parse_content[json_start:json_end]
                patch_plan = json.loads(potential_json)
                
                if patch_plan.get("schema") == "hephaistus/patch-plan/v1":
                    proposal.patch_plan = patch_plan
                    proposal.reasoning = patch_plan.get("rationale", "")
                    return proposal
        except (json.JSONDecodeError, ValueError):
            pass
        
        # No valid patch-plan found
        proposal.parse_error = "No valid patch-plan found in response"
        
        # Extract reasoning from response
        reasoning_pattern = r'(?:rationale|reasoning|explanation)[:\s]*([^\n]+(?:\n[^\n]+)*)'
        reasoning_match = re.search(reasoning_pattern, parse_content, re.IGNORECASE)
        if reasoning_match:
            proposal.reasoning = reasoning_match.group(1).strip()
        
        return proposal
    
    def get_available_models(self) -> List[Dict[str, Any]]:
        """Get list of available models from current provider."""
        models = self._provider.models()
        return [m.to_dict() for m in models]
    
    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for text."""
        return self._provider.count_tokens(text)
    
    def update_session(
        self,
        schematic_path: Optional[str] = None,
        parsed_state: Optional[Dict] = None,
        expertise_level: str = "professional",
        change_aggression: str = "moderate",
    ) -> None:
        """Update session state."""
        self.context_service.initialize_session(
            schematic_path=schematic_path,
            parsed_state=parsed_state,
            expertise_level=expertise_level,
            change_aggression=change_aggression,
        )
    
    def record_exchange(
        self,
        user_request: str,
        response: str,
        patch_plan: Optional[Dict] = None,
        user_action: Optional[str] = None,
    ) -> None:
        """Record an exchange in history."""
        self.context_service.record_exchange(
            user_request=user_request,
            llm_response=response,
            patch_plan=patch_plan,
            user_action=user_action,
        )
