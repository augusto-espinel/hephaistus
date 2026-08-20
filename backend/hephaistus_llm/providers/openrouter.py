"""
OpenRouter LLM Provider.

Provides access to Claude, GPT, Gemini, and other models via OpenRouter API.
"""

import json
import time
from typing import Any, AsyncIterator, Dict, List, Optional

import urllib.request
import urllib.error

from ..base import LLMConfig, LLMResponse, Message, ModelInfo, LLMProvider


class OpenRouterProvider:
    """
    OpenRouter API provider.
    
    Supports Claude, GPT, Gemini, Llama, and other models through
    a unified API with standardized pricing and routing.
    
    API Docs: https://openrouter.ai/docs
    """
    
    BASE_URL = "https://openrouter.ai/api/v1"
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize OpenRouter provider.
        
        Args:
            api_key: OpenRouter API key (defaults to OPENROUTER_API_KEY env var)
        """
        import os
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY")
        if not self.api_key:
            raise ValueError("OpenRouter API key required (set OPENROUTER_API_KEY or pass api_key)")
    
    @property
    def name(self) -> str:
        return "openrouter"
    
    def models(self) -> List[ModelInfo]:
        """
        List available models from OpenRouter.
        
        Returns cached list; call _fetch_models() for live data.
        """
        # Common models with known capabilities
        return [
            ModelInfo(
                id="anthropic/claude-3.5-sonnet",
                name="Claude 3.5 Sonnet",
                provider="openrouter",
                context_window=200000,
                max_output_tokens=8192,
                supports_streaming=True,
                supports_tools=True,
                supports_vision=True,
                pricing_input=3.0,
                pricing_output=15.0,
            ),
            ModelInfo(
                id="anthropic/claude-3-opus",
                name="Claude 3 Opus",
                provider="openrouter",
                context_window=200000,
                max_output_tokens=4096,
                supports_streaming=True,
                supports_tools=True,
                supports_vision=True,
                pricing_input=15.0,
                pricing_output=75.0,
            ),
            ModelInfo(
                id="openai/gpt-4o",
                name="GPT-4o",
                provider="openrouter",
                context_window=128000,
                max_output_tokens=4096,
                supports_streaming=True,
                supports_tools=True,
                supports_vision=True,
                pricing_input=5.0,
                pricing_output=15.0,
            ),
            ModelInfo(
                id="google/gemini-pro-1.5",
                name="Gemini Pro 1.5",
                provider="openrouter",
                context_window=1000000,
                max_output_tokens=8192,
                supports_streaming=True,
                supports_tools=True,
                supports_vision=True,
                pricing_input=2.5,
                pricing_output=10.0,
            ),
            ModelInfo(
                id="meta-llama/llama-3.1-70b-instruct",
                name="Llama 3.1 70B",
                provider="openrouter",
                context_window=131072,
                max_output_tokens=4096,
                supports_streaming=True,
                supports_tools=False,
                supports_vision=False,
                pricing_input=0.52,
                pricing_output=0.75,
            ),
        ]
    
    def complete(
        self,
        messages: List[Message],
        config: LLMConfig,
    ) -> LLMResponse:
        """
        Complete a conversation using OpenRouter API.
        
        Args:
            messages: Conversation messages
            config: Completion configuration
            
        Returns:
            LLM response
        """
        start_time = time.time()
        
        # Build request body
        body = {
            "model": config.model,
            "messages": [m.to_dict() for m in messages],
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
            "top_p": config.top_p,
        }
        
        if config.stop_sequences:
            body["stop"] = config.stop_sequences
        
        if config.system_prompt:
            body["system"] = config.system_prompt
        
        if config.tools:
            body["tools"] = config.tools
            if config.tool_choice:
                body["tool_choice"] = config.tool_choice
        
        # Provider-specific options
        if config.provider_options:
            body.update(config.provider_options)
        
        # Make request
        url = f"{self.BASE_URL}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://hephaistus.dev",  # Optional, for rankings
            "X-Title": "HephAIstus",  # Optional, for rankings
        }
        
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(body).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            
            with urllib.request.urlopen(req, timeout=config.timeout_seconds) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8") if e.fp else ""
            raise RuntimeError(f"OpenRouter API error {e.code}: {error_body}")
        except urllib.error.URLError as e:
            raise RuntimeError(f"OpenRouter connection error: {e.reason}")
        
        # Parse response
        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})
        usage = data.get("usage", {})
        
        content = message.get("content", "")
        tool_calls = message.get("tool_calls", [])
        
        latency_ms = (time.time() - start_time) * 1000
        
        return LLMResponse(
            content=content,
            model=config.model,
            provider="openrouter",
            usage_input_tokens=usage.get("prompt_tokens", 0),
            usage_output_tokens=usage.get("completion_tokens", 0),
            finish_reason=choice.get("finish_reason", "stop"),
            latency_ms=latency_ms,
            tool_calls=tool_calls,
            metadata={"response_id": data.get("id")},
        )
    
    async def stream(
        self,
        messages: List[Message],
        config: LLMConfig,
    ) -> AsyncIterator[str]:
        """
        Stream completion tokens.
        
        Note: This is a synchronous implementation using urllib.
        For true async, use aiohttp or httpx.
        """
        # For now, fall back to complete
        # TODO: Implement SSE streaming
        response = self.complete(messages, config)
        yield response.content
    
    def count_tokens(self, text: str) -> int:
        """
        Estimate token count.
        
        OpenRouter doesn't provide a tokenization API, so we use
        a heuristic estimate.
        """
        # Rough estimate: ~4 characters per token for English
        # Adjust for code/JSON which compress differently
        char_count = len(text)
        
        # Detect code density
        code_chars = sum(text.count(c) for c in ['{', '}', '[', ']', '"', ':', '\n'])
        code_density = code_chars / max(1, char_count)
        
        chars_per_token = 3.0 if code_density > 0.1 else 4.0
        return int(char_count / chars_per_token + 10)  # Buffer for safety
    
    def validate_config(self, config: LLMConfig) -> bool:
        """Validate configuration for OpenRouter."""
        if not config.model:
            return False
        if config.temperature < 0 or config.temperature > 2:
            return False
        if config.max_tokens < 1:
            return False
        return True