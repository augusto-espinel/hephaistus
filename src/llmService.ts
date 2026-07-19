// llmService.ts

import { createLlmClient, createOptimizeLlmClient } from './llmClientFactory';
import { loadLlmConfig } from './llmConfig';

export interface LlmBudget {
  iterations: number;
  timeoutSeconds: number;
}

export interface LlmResponse {
  success: boolean;
  result?: string;
  error?: string;
  modelUsed?: string;
}

/**
 * Generate content using sync-optimized model (local/cheap)
 */
export async function llmGenerateSync(prompt: string, context: Record<string, unknown>): Promise<LlmResponse> {
  try {
    const cfg = loadLlmConfig();
    const client = createLlmClient(cfg);
    const budget: LlmBudget = { iterations: 2, timeoutSeconds: 15 };
    const res = await client.generate(prompt, context, budget);
    return res;
  } catch (error) {
    return { success: false, error: (error as Error).message };
  }
}

/**
 * Generate content using optimization model (frontier/cloud)
 */
export async function llmGenerateOptimize(prompt: string, context: Record<string, unknown>): Promise<LlmResponse> {
  try {
    const cfg = loadLlmConfig();
    const client = createOptimizeLlmClient(cfg);
    const budget: LlmBudget = { iterations: 3, timeoutSeconds: 20 };
    const res = await client.generate(prompt, context, budget);
    return res;
  } catch (error) {
    return { success: false, error: (error as Error).message };
  }
}
