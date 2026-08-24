import { useAppState } from '@/context/AppContext'
import { useLLMProviders } from '@/hooks/useLLMProviders'

export function Settings() {
  const { llmSelection, setLLMSelection } = useAppState()
  const { data, loading, error, fetchProviders } = useLLMProviders()

  // Fetch providers on mount
  if (!data && !loading && !error) {
    fetchProviders()
  }

  if (loading) {
    return (
      <div className="settings-page">
        <h2>Settings</h2>
        <p>Loading providers...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="settings-page">
        <h2>Settings</h2>
        <p className="error">Failed to load providers: {error}</p>
      </div>
    )
  }

  if (!data) {
    return null
  }

  const currentProvider = data.providers.find(p => p.id === llmSelection.provider)
  const models = currentProvider?.models || []

  // Check if provider is usable
  const isProviderUsable = (provider: typeof data.providers[0]): boolean => {
    if (provider.requires_api_key && !provider.api_key_configured) {
      return false
    }
    if (provider.id === 'ollama' && provider.server_available === false) {
      return false
    }
    return true
  }

  const handleProviderChange = (providerId: string) => {
    const provider = data!.providers.find(p => p.id === providerId)
    if (provider && provider.models.length > 0) {
      const defaultModel = provider.models.find(m => 
        m.id === data!.defaults.model && data!.defaults.provider === providerId
      ) || provider.models[0]
      setLLMSelection({ provider: providerId, model: defaultModel.id })
    }
  }

  return (
    <div className="settings-page">
      <h2>Settings</h2>

      <section className="settings-section">
        <h3>LLM Provider</h3>
        <p className="section-description">
          Choose the AI model for schematic analysis and optimization.
        </p>

        <div className="setting-row">
          <label htmlFor="provider">Provider</label>
          <select
            id="provider"
            value={llmSelection.provider}
            onChange={(e) => handleProviderChange(e.target.value)}
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

        <div className="setting-row">
          <label htmlFor="model">Model</label>
          <select
            id="model"
            value={llmSelection.model}
            onChange={(e) => setLLMSelection({ ...llmSelection, model: e.target.value })}
            disabled={!currentProvider}
          >
            {models.map(model => (
              <option key={model.id} value={model.id}>
                {model.name}
              </option>
            ))}
          </select>
        </div>

        {/* Provider status */}
        {currentProvider && (
          <div className="provider-status">
            {currentProvider.api_key_configured === false && (
              <div className="status-warning">
                ⚠️ API key not configured. Set {currentProvider.env_var} environment variable.
              </div>
            )}
            {currentProvider.server_available === false && (
              <div className="status-warning">
                ⚠️ Ollama server not reachable at {currentProvider.base_url}
              </div>
            )}
            {isProviderUsable(currentProvider) && (
              <div className="status-ok">
                ✓ Provider ready
              </div>
            )}
          </div>
        )}

        {/* Model info */}
        {currentProvider && (
          <div className="model-info">
            <strong>Description:</strong> {models.find(m => m.id === llmSelection.model)?.description}
            <br />
            <strong>Context:</strong> {models.find(m => m.id === llmSelection.model)?.context_length?.toLocaleString()} tokens
          </div>
        )}
      </section>

      <section className="settings-section">
        <h3>About</h3>
        <p className="about-text">
          HephAIstus is an AI-assisted KiCad schematic and simulation copilot.
          It helps you design and optimize circuits by proposing validated patch-plans.
        </p>
        <p className="about-text">
          Your LLM selection is saved locally and will persist across sessions.
        </p>
      </section>
    </div>
  )
}