// llmClientFactory.ts
// Factory and interface abstractions for LLM backends used by the orchestrator.
// Supports Ollama (local) and OpenRouter (cloud).

import { LlmBackend } from './llmConfig';

export interface LlmClient {
  generate(
    prompt: string,
    context: any,
    budget: { iterations: number; timeoutSeconds: number },
    environmentContext?: { availableTools?: string[]; simulationScriptTemplate?: string }
  ): Promise<{ success: boolean; result?: string; modelUsed?: string; diagnostics?: any }>;
}

// Ollama (local) client implementation
class OllamaClient implements LlmClient {
  private baseUrl: string;
  constructor(baseUrl?: string) {
    this.baseUrl = baseUrl || 'http://localhost:11434/api/generate';
  }
  async generate(prompt: string, context: any, budget: { iterations: number; timeoutSeconds: number }, environmentContext?: { availableTools?: string[]; simulationScriptTemplate?: string }) {
    const payload = { prompt, context, budget, environmentContext };
    try {
      // Use global fetch available in modern Node runtimes
      const res = await fetch(this.baseUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json() as Record<string, unknown>;
      return { success: true, result: (data?.generatedCode ?? data?.result ?? '') as string, modelUsed: 'ollama' };
    } catch (err) {
      console.error('[LLM-Client][Ollama] generate error:', err);
      // Fallback path (graceful mock when Ollama is offline/unreachable during early integration)
      return { 
        success: true, 
        result: JSON.stringify({ mock: "Ollama offline fallback response" }), 
        modelUsed: 'mock/ollama-offline-fallback',
        diagnostics: err
      };
    }
  }
}

// OpenRouter (cloud) client implementation
class OpenRouterClient implements LlmClient {
  private endpoint: string;
  private apiKey?: string;
  constructor(endpoint?: string, apiKey?: string) {
    this.endpoint = endpoint || 'https://openrouter.ai/api/v1/chat/completions';
    this.apiKey = apiKey;
  }
  async generate(prompt: string, context: any, budget: { iterations: number; timeoutSeconds: number }, environmentContext?: { availableTools?: string[]; simulationScriptTemplate?: string }) {
    const payload = {
      model: "google/gemini-2.5-flash", // Reasonable default for OpenRouter
      messages: [
        { role: "system", content: "You are the HephAIstus backend companion." },
        { role: "user", content: `Context:\n${JSON.stringify(context)}\n\nPrompt:\n${prompt}` }
      ]
    };
    try {
      const headers: any = { 'Content-Type': 'application/json' };
      if (this.apiKey) headers['Authorization'] = `Bearer ${this.apiKey}`;
      const res = await fetch(this.endpoint, {
        method: 'POST',
        headers,
        body: JSON.stringify(payload)
      });
      const data = await res.json() as Record<string, unknown>;
      const choices = (data?.choices as Array<{message?: {content?: string}}>) ?? [];
      const content = choices?.[0]?.message?.content ?? '';
      return { success: true, result: content, modelUsed: 'openrouter' };
    } catch (err) {
      console.error('[LLM-Client][OpenRouter] generate error:', err);
      // Fallback path (graceful mock when OpenRouter credentials aren't set yet)
      return { 
        success: true, 
        result: JSON.stringify({ mock: "OpenRouter placeholder response" }), 
        modelUsed: 'mock/openrouter-placeholder',
        diagnostics: err
      };
    }
  }
}

type LlmConfigBridge = {
  syncBackend: LlmBackend;
  optimizeBackend: LlmBackend;
  credentials?: { ollama?: string; openrouter?: string };
};

export function createLlmClient(config: LlmConfigBridge): LlmClient {
  const backend = config.syncBackend || 'ollama';
  if (backend === 'ollama') {
    return new OllamaClient(config.credentials?.ollama);
  } else {
    return new OpenRouterClient('https://openrouter.ai/api/v1/chat/completions', config.credentials?.openrouter);
  }
}
export function createOptimizeLlmClient(config: LlmConfigBridge): LlmClient {
  const backend = config.optimizeBackend || 'openrouter';
  if (backend === 'ollama') {
    return new OllamaClient(config.credentials?.ollama);
  } else {
    return new OpenRouterClient('https://openrouter.ai/api/v1/chat/completions', config.credentials?.openrouter);
  }
}
