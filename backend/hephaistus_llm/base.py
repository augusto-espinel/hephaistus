"""
Base LLM provider interface and data classes.

Defines the protocol that all LLM providers must implement.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncIterator, Dict, List, Optional, Protocol, runtime_checkable


class MessageRole(str, Enum):
    """Role of a message in the conversation."""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


@dataclass
class Message:
    """A single message in a conversation."""
    role: MessageRole
    content: str
    
    def to_dict(self) -> dict:
        return {"role": self.role.value, "content": self.content}


@dataclass
class ModelInfo:
    """Information about an available model."""
    id: str
    name: str
    provider: str
    context_window: int
    max_output_tokens: int = 4096
    supports_streaming: bool = True
    supports_tools: bool = False
    supports_vision: bool = False
    pricing_input: float = 0.0  # Per 1M tokens in USD
    pricing_output: float = 0.0  # Per 1M tokens in USD
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "provider": self.provider,
            "context_window": self.context_window,
            "max_output_tokens": self.max_output_tokens,
            "supports_streaming": self.supports_streaming,
            "supports_tools": self.supports_tools,
            "supports_vision": self.supports_vision,
            "pricing_input": self.pricing_input,
            "pricing_output": self.pricing_output,
        }


@dataclass
class LLMConfig:
    """Configuration for an LLM completion request."""
    model: str
    temperature: float = 0.7
    max_tokens: int = 4096
    top_p: float = 1.0
    top_k: int = 0
    stop_sequences: List[str] = field(default_factory=list)
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    timeout_seconds: float = 120.0
    
    # For models that support system prompts
    system_prompt: Optional[str] = None
    
    # For tool/function calling
    tools: List[Dict[str, Any]] = field(default_factory=list)
    tool_choice: Optional[str] = None
    
    # Provider-specific options
    provider_options: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        result = {
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "top_p": self.top_p,
        }
        if self.system_prompt:
            result["system_prompt"] = self.system_prompt
        if self.stop_sequences:
            result["stop"] = self.stop_sequences
        if self.tools:
            result["tools"] = self.tools
        return result


@dataclass
class LLMResponse:
    """Response from an LLM completion."""
    content: str
    model: str
    provider: str
    usage_input_tokens: int = 0
    usage_output_tokens: int = 0
    finish_reason: str = "stop"
    latency_ms: float = 0.0
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    # Reasoning content from models that return it separately (DeepSeek, etc.)
    reasoning_content: Optional[str] = None
    
    @property
    def total_tokens(self) -> int:
        return self.usage_input_tokens + self.usage_output_tokens
    
    def to_dict(self) -> dict:
        result = {
            "content": self.content,
            "model": self.model,
            "provider": self.provider,
            "usage_input_tokens": self.usage_input_tokens,
            "usage_output_tokens": self.usage_output_tokens,
            "finish_reason": self.finish_reason,
            "latency_ms": self.latency_ms,
            "tool_calls": self.tool_calls,
        }
        if self.reasoning_content:
            result["reasoning_content"] = self.reasoning_content
        return result


@runtime_checkable
class LLMProvider(Protocol):
    """
    Protocol for LLM providers.
    
    All providers must implement these methods for unified access.
    """
    
    @property
    def name(self) -> str:
        """Provider name (e.g., 'openrouter', 'ollama')."""
        ...
    
    def models(self) -> List[ModelInfo]:
        """List available models."""
        ...
    
    def complete(
        self, 
        messages: List[Message], 
        config: LLMConfig
    ) -> LLMResponse:
        """
        Complete a conversation.
        
        Args:
            messages: Conversation messages
            config: Completion configuration
            
        Returns:
            LLM response
        """
        ...
    
    def stream(
        self, 
        messages: List[Message], 
        config: LLMConfig
    ) -> AsyncIterator[str]:
        """
        Stream completion tokens.
        
        Args:
            messages: Conversation messages
            config: Completion configuration
            
        Yields:
            Content chunks as they arrive
        """
        ...
    
    def count_tokens(self, text: str) -> int:
        """
        Count tokens in text.
        
        Uses provider-specific tokenizer if available,
        otherwise falls back to heuristic estimation.
        """
        ...
    
    def validate_config(self, config: LLMConfig) -> bool:
        """Validate that configuration is compatible with this provider."""
        ...