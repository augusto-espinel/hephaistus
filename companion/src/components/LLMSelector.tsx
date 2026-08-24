import { useState, useEffect } from 'react'
import { useLLMProviders, Provider } from '@/hooks/useLLMProviders'

interface LLMSelectorProps {
  value: { provider: string; model: string }
  onChange: (value: { provider: string; model: string }) => void
  disabled?: boolean
}

export function LLMSelector({ value, onChange, disabled }: LLMSelectorProps) {
  const { data, loading, error, fetchProviders } = useLLMProviders()
  const [selectedProvider, setSelectedProvider] = useState<string>(value.provider)
  const [selectedModel, setSelectedModel] = useState<string>(value.model)

  // Fetch providers on mount
  useEffect(() => {
    fetchProviders()
  }, [])

  // Update parent when selection changes
  useEffect(() => {
    onChange({ provider: selectedProvider, model: selectedModel })
  }, [selectedProvider, selectedModel])

  // Set defaults when data loads
  useEffect(() => {
    if (data?.defaults && !selectedProvider) {
      setSelectedProvider(data.defaults.provider)
      setSelectedModel(data.defaults.model)
    }
  }, [data])

  if (loading) {
    return <div className="llm-selector loading">Loading models...</div>
  }

  if (error) {
    return <div className="llm-selector error">Failed to load providers</div>
  }

  if (!data) {
    return null
  }

  const currentProvider = data.providers.find(p => p.id === selectedProvider)
  const models = currentProvider?.models || []

  // Check if provider is usable
  const isProviderUsable = (provider: Provider): boolean => {
    if (provider.requires_api_key && !provider.api_key_configured) {
      return false
    }
    if (provider.id === 'ollama' && provider.server_available === false) {
      return false
    }
    return true
  }

  const handleProviderChange = (providerId: string) => {
    const provider = data.providers.find(p => p.id === providerId)
    if (provider && provider.models.length > 0) {
      setSelectedProvider(providerId)
      // Auto-select first model or default
      const defaultModel = provider.models.find(m => 
        m.id === data.defaults.model && data.defaults.provider === providerId
      ) || provider.models[0]
      setSelectedModel(defaultModel.id)
    }
  }

  return (
    <div className="llm-selector">
      <div className="selector-row">
        <div className="selector-group">
          <label htmlFor="provider">Provider</label>
          <select
            id="provider"
            value={selectedProvider}
            onChange={(e) => handleProviderChange(e.target.value)}
            disabled={disabled}
          >
            {data.providers.map(provider => (
              <option 
                key={provider.id} 
                value={provider.id}
                disabled={!isProviderUsable(provider)}
              >
                {provider.name}
                {!isProviderUsable(provider) && ' (unavailable)'}
              </option>
            ))}
          </select>
        </div>

        <div className="selector-group">
          <label htmlFor="model">Model</label>
          <select
            id="model"
            value={selectedModel}
            onChange={(e) => setSelectedModel(e.target.value)}
            disabled={disabled || !currentProvider}
          >
            {models.map(model => (
              <option key={model.id} value={model.id}>
                {model.name}
                {model.recommended_for?.includes('complex') && ' ⚡'}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Status indicators */}
      {currentProvider && (
        <div className="provider-status">
          {currentProvider.api_key_configured === false && (
            <span className="status warning">
              ⚠️ API key not configured
            </span>
          )}
          {currentProvider.server_available === false && (
            <span className="status warning">
              ⚠️ Server not reachable
            </span>
          )}
          {isProviderUsable(currentProvider) && (
            <span className="status ok">
              ✓ Ready
            </span>
          )}
        </div>
      )}

      {/* Model description */}
      {currentProvider && (
        <div className="model-info">
          {models.find(m => m.id === selectedModel)?.description}
        </div>
      )}
    </div>
  )
}