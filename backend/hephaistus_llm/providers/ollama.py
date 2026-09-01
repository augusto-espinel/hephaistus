"""
Ollama LLM Provider.

Provides access to local or remote Ollama servers for open-source models.
"""

import json
import time
from typing import Any, AsyncIterator, Dict, List, Optional

import urllib.request
import urllib.error

from ..base import LLMConfig, LLMResponse, Message, ModelInfo, LLMProvider


class OllamaProvider:
    """
    Ollama provider for local/remote inference.
    
    Supports Llama, Mistral, Gemma, and other open-source models
    running on an Ollama server.
    
    Docs: https://github.com/ollama/ollama/blob/main/docs/api.md
    """
    
    def __init__(self, base_url: str = "http://localhost:11434"):
        """
        Initialize Ollama provider.
        
        Args:
            base_url: Ollama server URL (default: localhost)
        """
        self.base_url = base_url.rstrip("/")
    
    @property
    def name(self) -> str:
        return "ollama"
    
    def models(self) -> List[ModelInfo]:
        """
        List models available on the Ollama server.
        
        Returns cached list; call _fetch_models() for live data.
        """
        # Common models with typical configurations
        return [
            ModelInfo(
                id="llama3.1:70b",
                name="Llama 3.1 70B",
                provider="ollama",
                context_window=131072,
                max_output_tokens=4096,
                supports_streaming=True,
                supports_tools=False,
                supports_vision=False,
                pricing_input=0.0,  # Free (local)
                pricing_output=0.0,
            ),
            ModelInfo(
                id="llama3.1:8b",
                name="Llama 3.1 8B",
                provider="ollama",
                context_window=131072,
                max_output_tokens=4096,
                supports_streaming=True,
                supports_tools=False,
                supports_vision=False,
                pricing_input=0.0,
                pricing_output=0.0,
            ),
            ModelInfo(
                id="codellama:70b",
                name="Code Llama 70B",
                provider="ollama",
                context_window=16384,
                max_output_tokens=4096,
                supports_streaming=True,
                supports_tools=False,
                supports_vision=False,
                pricing_input=0.0,
                pricing_output=0.0,
            ),
            ModelInfo(
                id="mistral:7b",
                name="Mistral 7B",
                provider="ollama",
                context_window=32768,
                max_output_tokens=4096,
                supports_streaming=True,
                supports_tools=False,
                supports_vision=False,
                pricing_input=0.0,
                pricing_output=0.0,
            ),
        ]
    
    def fetch_models(self) -> List[ModelInfo]:
        """
        Fetch live model list from Ollama server.
        
        Returns:
            List of available models with their info
        """
        url = f"{self.base_url}/api/tags"
        
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError:
            # Server not available, return defaults
            return self.models()
        
        models = []
        for model_data in data.get("models", []):
            name = model_data.get("name", "")
            # Extract parameter size from model name
            param_size = self._extract_param_size(name)
            
            models.append(ModelInfo(
                id=name,
                name=name,
                provider="ollama",
                context_window=self._estimate_context_window(param_size),
                max_output_tokens=4096,
                supports_streaming=True,
                supports_tools=False,
                supports_vision=False,
                pricing_input=0.0,
                pricing_output=0.0,
                metadata={"size": model_data.get("size"), "modified": model_data.get("modified")},
            ))
        
        return models
    
    def _extract_param_size(self, model_name: str) -> Optional[str]:
        """Extract parameter size from model name."""
        # Common patterns: llama3.1:70b, codellama:34b
        if ":" in model_name:
            tag = model_name.split(":")[-1]
            if tag.endswith("b"):
                return tag
        return None
    
    def _estimate_context_window(self, param_size: Optional[str]) -> int:
        """Estimate context window based on parameter size."""
        # Conservative defaults
        if param_size:
            try:
                size = int(param_size[:-1])
                if size >= 70:
                    return 131072  # 128K
                elif size >= 30:
                    return 32768
                else:
                    return 8192
            except ValueError:
                pass
        return 8192  # Default fallback
    
    def complete(
        self,
        messages: List[Message],
        config: LLMConfig,
    ) -> LLMResponse:
        """
        Complete a conversation using Ollama API.
        
        Args:
            messages: Conversation messages
            config: Completion configuration
            
        Returns:
            LLM response
        """
        start_time = time.time()
        
        # Build request body for Ollama
        body = {
            "model": config.model,
            "messages": [m.to_dict() for m in messages],
            "stream": False,
            "options": {
                "temperature": config.temperature,
                "num_predict": config.max_tokens,
                "top_p": config.top_p,
            },
        }
        
        if config.top_k > 0:
            body["options"]["top_k"] = config.top_k
        
        if config.stop_sequences:
            body["options"]["stop"] = config.stop_sequences
        
        # System prompt handling
        if config.system_prompt:
            # Ollama expects system as separate field
            body["system"] = config.system_prompt
        
        # Make request
        url = f"{self.base_url}/api/chat"
        headers = {"Content-Type": "application/json"}
        
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
            raise RuntimeError(f"Ollama API error {e.code}: {error_body}")
        except urllib.error.URLError as e:
            raise RuntimeError(f"Ollama connection error: {e.reason}. Is Ollama running at {self.base_url}?")
        
        # Parse response
        message = data.get("message", {})
        content = message.get("content") or ""
        
        # Ollama provides eval counts
        prompt_eval_count = data.get("prompt_eval_count", 0)
        eval_count = data.get("eval_count", 0)
        
        latency_ms = (time.time() - start_time) * 1000
        
        return LLMResponse(
            content=content,
            model=config.model,
            provider="ollama",
            usage_input_tokens=prompt_eval_count,
            usage_output_tokens=eval_count,
            finish_reason="stop",  # Ollama doesn't provide finish reason
            latency_ms=latency_ms,
            metadata={"done": data.get("done", True)},
        )
    
    async def stream(
        self,
        messages: List[Message],
        config: LLMConfig,
    ) -> AsyncIterator[str]:
        """
        Stream completion tokens from Ollama.
        
        Note: This is a synchronous implementation. For true async,
        use aiohttp or httpx with SSE.
        """
        # Build request for streaming
        body = {
            "model": config.model,
            "messages": [m.to_dict() for m in messages],
            "stream": True,
            "options": {
                "temperature": config.temperature,
                "num_predict": config.max_tokens,
                "top_p": config.top_p,
            },
        }
        
        if config.system_prompt:
            body["system"] = config.system_prompt
        
        url = f"{self.base_url}/api/chat"
        headers = {"Content-Type": "application/json"}
        
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(body).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            
            with urllib.request.urlopen(req, timeout=config.timeout_seconds) as response:
                for line in response:
                    if not line:
                        continue
                    try:
                        data = json.loads(line.decode("utf-8"))
                        message = data.get("message", {})
                        content = message.get("content") or ""
                        if content:
                            yield content
                    except json.JSONDecodeError:
                        continue
                        
        except urllib.error.URLError as e:
            raise RuntimeError(f"Ollama streaming error: {e.reason}")
    
    def count_tokens(self, text: str) -> int:
        """
        Count tokens using Ollama's tokenization.
        
        Falls back to heuristic if tokenizer unavailable.
        """
        # Try to use Ollama's tokenization endpoint
        url = f"{self.base_url}/api/tokenize"
        body = {"text": text}
        
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(body).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode("utf-8"))
                return len(data.get("tokens", []))
        except (urllib.error.URLError, urllib.error.HTTPError):
            # Fall back to heuristic
            return self._heuristic_token_count(text)
    
    def _heuristic_token_count(self, text: str) -> int:
        """Heuristic token count estimation."""
        char_count = len(text)
        # Code/JSON dense text uses fewer tokens
        code_chars = sum(text.count(c) for c in ['{', '}', '[', ']', '"', ':', '\n'])
        code_density = code_chars / max(1, char_count)
        chars_per_token = 3.0 if code_density > 0.1 else 4.0
        return int(char_count / chars_per_token + 10)
    
    def validate_config(self, config: LLMConfig) -> bool:
        """Validate configuration for Ollama."""
        if not config.model:
            return False
        if config.temperature < 0:
            return False
        if config.max_tokens < 1:
            return False
        return True
    
    def is_server_running(self) -> bool:
        """Check if Ollama server is accessible."""
        try:
            req = urllib.request.Request(f"{self.base_url}/api/version", method="GET")
            urllib.request.urlopen(req, timeout=5)
            return True
        except (urllib.error.URLError, urllib.error.HTTPError):
            return False
    
    def get_server_version(self) -> Optional[str]:
        """Get Ollama server version."""
        try:
            req = urllib.request.Request(f"{self.base_url}/api/version", method="GET")
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode("utf-8"))
                return data.get("version")
        except (urllib.error.URLError, urllib.error.HTTPError):
            return None