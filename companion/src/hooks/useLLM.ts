import { useCallback } from 'react'
import { useApi } from './useApi'

export interface GenerateRequest {
  request: string
  schematic_path?: string | null
  include_full_simulation?: boolean
  provider?: 'ollama' | 'openrouter'
  model?: string | null
  timeout_seconds?: number  // Override default 120s timeout for complex requests
}

export interface GenerateResponse {
  raw_response: string
  patch_plan: any | null
  reasoning: string | null
  is_clarification: boolean
  clarification_question: string | null
  parse_error: string | null
  is_valid: boolean
  // Thinking/reasoning blocks extracted from response (DeepSeek-R1, etc.)
  thinking_content: string | null
  // Display-friendly response with thinking blocks condensed
  display_response: string | null
}

export function useLLM() {
  const { data, loading, error, execute } = useApi<GenerateResponse>()

  const generate = useCallback(async (request: GenerateRequest) => {
    const result = await execute('/api/llm/generate', {
      method: 'POST',
      body: JSON.stringify(request),
    })
    return result
  }, [execute])

  return { 
    data, 
    loading, 
    error, 
    generate,
    clear: () => execute('/api/llm/generate', { method: 'POST', body: JSON.stringify({ request: '' }) })
  }
}