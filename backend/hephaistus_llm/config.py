"""
LLM Provider configuration.

Defines configuration for each supported provider.
"""

import os
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class ProviderConfig:
    """
    Configuration for a specific LLM provider.
    
    Supports OpenRouter, Ollama (local/remote), and OpenAI.
    """
    
    # Provider type
    provider: str  # "openrouter" | "ollama" | "openai"
    
    # Model selection
    model: str
    
    # Provider-specific settings
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    
    # Generation parameters
    temperature: float = 0.7
    max_tokens: int = 4096
    top_p: float = 1.0
    
    # Request settings
    timeout_seconds: float = 120.0
    
    # Additional options
    extra_options: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Resolve environment variables."""
        if self.api_key and self.api_key.startswith("${") and self.api_key.endswith("}"):
            env_var = self.api_key[2:-1]
            self.api_key = os.environ.get(env_var)
    
    @classmethod
    def openrouter(
        cls,
        model: str = "anthropic/claude-3.5-sonnet",
        api_key: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        timeout_seconds: Optional[float] = None,
        **kwargs
    ) -> "ProviderConfig":
        """Create OpenRouter configuration."""
        return cls(
            provider="openrouter",
            model=model,
            api_key=api_key or os.environ.get("OPENROUTER_API_KEY"),
            temperature=temperature,
            max_tokens=max_tokens,
            timeout_seconds=timeout_seconds if timeout_seconds is not None else 120.0,
            extra_options=kwargs,
        )
    
    @classmethod
    def ollama(
        cls,
        model: str = "gemma4:e4b",
        base_url: str = "http://localhost:11434",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        timeout_seconds: Optional[float] = None,
        **kwargs
    ) -> "ProviderConfig":
        """Create Ollama configuration."""
        return cls(
            provider="ollama",
            model=model,
            base_url=base_url,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout_seconds=timeout_seconds if timeout_seconds is not None else 120.0,
            extra_options=kwargs,
        )
    
    @classmethod
    def openai(
        cls,
        model: str = "gpt-4o",
        api_key: Optional[str] = None,
        organization: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs
    ) -> "ProviderConfig":
        """Create OpenAI configuration."""
        return cls(
            provider="openai",
            model=model,
            api_key=api_key or os.environ.get("OPENAI_API_KEY"),
            extra_options={"organization": organization, **kwargs} if organization else kwargs,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProviderConfig":
        """Create configuration from dictionary."""
        return cls(
            provider=data.get("provider", "openrouter"),
            model=data.get("model", "claude-3.5-sonnet"),
            api_key=data.get("api_key"),
            base_url=data.get("base_url"),
            temperature=data.get("temperature", 0.7),
            max_tokens=data.get("max_tokens", 4096),
            top_p=data.get("top_p", 1.0),
            timeout_seconds=data.get("timeout_seconds", 120.0),
            extra_options=data.get("extra_options", {}),
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize configuration."""
        return {
            "provider": self.provider,
            "model": self.model,
            "base_url": self.base_url,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "top_p": self.top_p,
            "timeout_seconds": self.timeout_seconds,
            **self.extra_options,
        }


# Default configurations for common use cases
DEFAULT_CONFIGS = {
    "openrouter_claude": ProviderConfig.openrouter(
        model="anthropic/claude-3.5-sonnet",
        temperature=0.7,
    ),
    "openrouter_gemini": ProviderConfig.openrouter(
        model="google/gemini-pro-1.5",
        temperature=0.7,
    ),
    "ollama_local": ProviderConfig.ollama(
        model="gemma4:e4b",
        base_url="http://localhost:11434",
    ),
    "ollama_remote": ProviderConfig.ollama(
        model="gemma4:e4b",
        base_url="${OLLAMA_HOST}",
    ),
    "openai_gpt4": ProviderConfig.openai(
        model="gpt-4o",
        temperature=0.7,
    ),
}