"""
Token budget management for LLM context assembly.

Enforces hard limits on context size with priority-based truncation.
"""

import re
from dataclasses import dataclass, field
from enum import IntEnum
from typing import List, Tuple


class LayerPriority(IntEnum):
    """Priority ordering for context layers (higher = more important)."""
    SYSTEM = 100       # Layer 0: Never truncated
    SESSION = 90       # Layer 1: Rarely truncated
    HISTORY = 70       # Layer 2: Windowed, can summarize older
    REASONING = 50     # Layer 3: Can condense
    SIMULATION = 30    # Layer 4: Summary only by default
    DEEP_HISTORY = 10  # Layer 5: Not in context by default


@dataclass
class TokenBudgetConfig:
    """Configuration for token budget management."""
    
    # Model limits
    model_context_window: int = 200000      # Claude's context window
    response_budget: int = 8192             # Tokens reserved for response
    
    # Layer budgets (max tokens per layer)
    system_max: int = 2500
    session_max: int = 2000
    history_max: int = 5000
    reasoning_max: int = 1500
    simulation_max: int = 1000
    simulation_full_max: int = 10000       # When full data requested
    
    # History configuration
    history_window_default: int = 10       # Exchanges to keep
    history_min_window: int = 3            # Minimum before summarization
    
    @property
    def total_context_budget(self) -> int:
        """Maximum tokens available for context."""
        return self.model_context_window - self.response_budget
    
    @property
    def default_layer_budget(self) -> int:
        """Sum of all layer budgets with default settings."""
        return (
            self.system_max + 
            self.session_max + 
            self.history_max + 
            self.reasoning_max + 
            self.simulation_max
        )


@dataclass
class LayerUsage:
    """Token usage for a single layer."""
    layer: str
    tokens: int
    max_tokens: int
    priority: LayerPriority
    truncated: bool = False
    truncation_note: str = ""
    
    @property
    def utilization(self) -> float:
        """Percentage of max tokens used."""
        if self.max_tokens == 0:
            return 0.0
        return min(1.0, self.tokens / self.max_tokens)
    
    @property
    def remaining(self) -> int:
        """Tokens remaining before hitting limit."""
        return max(0, self.max_tokens - self.tokens)


@dataclass
class TokenBudget:
    """Manages token budget across all context layers."""
    
    config: TokenBudgetConfig = field(default_factory=TokenBudgetConfig)
    layers: List[LayerUsage] = field(default_factory=list)
    
    def reset(self) -> None:
        """Reset all layer tracking."""
        self.layers = []
    
    def count_tokens(self, text: str) -> int:
        """
        Estimate token count for text.
        
        Uses a simple heuristic: ~4 characters per token for English text.
        This is accurate enough for budget management without requiring
        model-specific tokenizers.
        
        For production use, consider integrating tiktoken for exact counts.
        """
        if not text:
            return 0
        
        # Count words and adjust for code/JSON which compress differently
        # Approximation: 1 token ≈ 4 chars for prose, 3 chars for code
        char_count = len(text)
        
        # Detect if mostly code/structured data
        code_indicators = ['{', '}', '[', ']', '"', ':', '\\n', '\\t']
        code_density = sum(text.count(c) for c in code_indicators) / max(1, char_count)
        
        # Adjust ratio based on content type
        chars_per_token = 3.0 if code_density > 0.1 else 4.0
        
        # Add small buffer for safety
        return int(char_count / chars_per_token + 5)
    
    def track_layer(
        self, 
        layer: str, 
        content: str, 
        priority: LayerPriority,
        max_tokens: int,
        allow_truncation: bool = True
    ) -> Tuple[str, LayerUsage]:
        """
        Track and optionally truncate a layer's content.
        
        Returns (possibly truncated content, usage record).
        """
        original_tokens = self.count_tokens(content)
        
        if original_tokens <= max_tokens or not allow_truncation:
            # Content fits or truncation not allowed
            final_content = content
            final_tokens = original_tokens
            truncated = False
            truncation_note = ""
        else:
            # Need to truncate
            final_content = self._truncate_content(content, max_tokens)
            final_tokens = self.count_tokens(final_content)
            truncated = True
            truncation_note = f"Truncated from {original_tokens} to {final_tokens} tokens"
        
        usage = LayerUsage(
            layer=layer,
            tokens=final_tokens,
            max_tokens=max_tokens,
            priority=priority,
            truncated=truncated,
            truncation_note=truncation_note
        )
        
        self.layers.append(usage)
        return final_content, usage
    
    def _truncate_content(self, content: str, max_tokens: int) -> str:
        """
        Truncate content to fit within token budget.
        
        Attempts to truncate at natural boundaries (paragraphs, sentences).
        """
        target_chars = max_tokens * 3.5  # Conservative estimate
        
        if len(content) <= target_chars:
            return content
        
        # Try to truncate at paragraph boundary
        paragraphs = content.split('\n\n')
        result = []
        current_len = 0
        
        for para in paragraphs:
            if current_len + len(para) + 2 <= target_chars:
                result.append(para)
                current_len += len(para) + 2
            else:
                break
        
        if result:
            truncated = '\n\n'.join(result)
            truncated += '\n\n[Content truncated due to token budget...]'
            return truncated
        
        # Fall back to hard truncation at sentence boundary
        sentences = re.split(r'(?<=[.!?])\s+', content)
        result = []
        current_len = 0
        
        for sentence in sentences:
            if current_len + len(sentence) + 1 <= target_chars:
                result.append(sentence)
                current_len += len(sentence) + 1
            else:
                break
        
        if result:
            truncated = ' '.join(result)
            truncated += ' [truncated...]'
            return truncated
        
        # Last resort: hard truncation
        return content[:int(target_chars)] + ' [truncated...]'
    
    @property
    def total_tokens(self) -> int:
        """Total tokens used across all layers."""
        return sum(layer.tokens for layer in self.layers)
    
    @property
    def remaining_budget(self) -> int:
        """Tokens remaining in total budget."""
        return self.config.total_context_budget - self.total_tokens
    
    def summary(self) -> dict:
        """Generate summary of token usage."""
        return {
            "total_tokens": self.total_tokens,
            "total_budget": self.config.total_context_budget,
            "remaining_budget": self.remaining_budget,
            "utilization": self.total_tokens / self.config.total_context_budget,
            "layers": [
                {
                    "layer": layer.layer,
                    "tokens": layer.tokens,
                    "max_tokens": layer.max_tokens,
                    "priority": layer.priority.name,
                    "truncated": layer.truncated,
                    "truncation_note": layer.truncation_note if layer.truncated else None
                }
                for layer in self.layers
            ]
        }
