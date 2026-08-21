import { useCallback } from 'react'
import { useApi } from './useApi'

export interface GenerateRequest {
  request: string
  schematic_path?: string | null
  include_full_simulation?: boolean
  provider?: 'ollama' | 'openrouter'
  model?: string | null
}

export interface GenerateResponse {
  raw_response: string
  patch_plan: any | null
  reasoning: string | null
  is_clarification: boolean
  clarification_question: string | null
  parse_error: string | null
  is_valid: boolean
}

export function useLLM() {
  const { data, loading, error, execute } = useApi<GenerateResponse>()

  const generate = useCallback(async (request: GenerateRequest) => {
    await execute('/api/llm/generate', {
      method: 'POST',
      body: JSON.stringify(request),
    })
  }, [execute])

  return { 
    data, 
    loading, 
    error, 
    generate,
    clear: () => execute('/api/llm/generate', { method: 'POST', body: JSON.stringify({ request: '' }) })
  }
}