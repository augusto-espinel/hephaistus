import { useApi } from './useApi'

export interface Model {
  id: string
  name: string
  description: string
  context_length: number
  recommended_for: string[]
}

export interface Provider {
  id: string
  name: string
  description: string
  requires_api_key: boolean
  base_url?: string
  env_var?: string
  api_key_configured: boolean
  server_available?: boolean  // For Ollama
  models: Model[]
}

export interface ProvidersConfig {
  providers: Provider[]
  defaults: {
    provider: string
    model: string
  }
}

export function useLLMProviders() {
  const { data, loading, error, execute } = useApi<ProvidersConfig>()

  const fetchProviders = async () => {
    const result = await execute('/api/llm/providers')
    return result
  }

  return {
    data,
    loading,
    error,
    fetchProviders,
  }
}