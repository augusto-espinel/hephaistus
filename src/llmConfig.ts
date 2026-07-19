// llmConfig.ts
// Lightweight configuration loader for LLM backends used by the orchestrator.
// Supports Ollama (local) and OpenRouter (cloud).

import { getHephaistusConfig, ModelConfig } from './configService';

export type LlmBackend = 'ollama' | 'openrouter';

export interface LlmConfig {
  // Backend used for synchronization/inference
  syncBackend: LlmBackend;
  // Backend used for optimization steps
  optimizeBackend: LlmBackend;
  // Optional: endpoints/credentials for providers
  credentials?: {
    ollama?: string;
    openrouter?: string;
  };
}

export const defaultLlmConfig: LlmConfig = {
  syncBackend: 'ollama',
  optimizeBackend: 'openrouter',
  credentials: {
    ollama: '',
    openrouter: ''
  }
};

/**
 * Get LLM configuration from VS Code settings.
 * This is the primary configuration loader.
 */
export function loadLlmConfig(): LlmConfig {
  const config = getHephaistusConfig();
  
  return {
    syncBackend: config.models.sync.provider as LlmBackend,
    optimizeBackend: config.models.optimization.provider as LlmBackend,
    credentials: {
      ollama: config.models.sync.endpoint,
      openrouter: config.models.optimization.apiKey
    }
  };
}

/**
 * Get model configuration for a specific task type.
 */
export function getModelConfigForTask(taskType: 'sync' | 'optimization'): ModelConfig {
  const config = getHephaistusConfig();
  return config.models[taskType];
}

// Legacy export for backwards compatibility
export { loadLlmConfig as _loadLlmConfigDeprecated };
