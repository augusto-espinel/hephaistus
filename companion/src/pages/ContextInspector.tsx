import { useState, useEffect, useCallback } from 'react'
import { useApi } from '@/hooks/useApi'
import { ContextView } from '@/components/ContextView'
import { TokenBudgetView } from '@/components/TokenBudgetView'
import { on, Events } from '@/events'
import type { ContextAssemblyResult } from '@/services/context'

export function ContextInspector() {
  const [request, setRequest] = useState('')
  const [includeFullSim, setIncludeFullSim] = useState(false)
  const [autoRefresh, setAutoRefresh] = useState(true)
  const [lastEventSource, setLastEventSource] = useState<string | null>(null)
  const { data, loading, error, execute } = useApi<ContextAssemblyResult>()

  const handleAssemble = useCallback(async (source?: string) => {
    await execute('/api/context/assemble', {
      method: 'POST',
      body: JSON.stringify({ request, includeFullSim }),
    })
    if (source) {
      setLastEventSource(source)
    }
  }, [execute, request, includeFullSim])

  // Manual assemble button
  const handleManualAssemble = () => {
    setLastEventSource(null)
    handleAssemble()
  }

  // Auto-refresh on events from other components
  useEffect(() => {
    if (!autoRefresh) return

    const unsubPrompt = on(Events.PROMPT_SENT, () => {
      handleAssemble('after prompt sent')
    })
    const unsubSchematic = on(Events.SCHEMATIC_LOADED, () => {
      handleAssemble('after schematic loaded')
    })
    const unsubSim = on(Events.SIMULATION_IMPORTED, () => {
      handleAssemble('after simulation imported')
    })

    return () => {
      unsubPrompt()
      unsubSchematic()
      unsubSim()
    }
  }, [autoRefresh, handleAssemble])

  return (
    <div className="context-inspector">
      <div className="page-header">
        <h1>Context Inspector</h1>
        <p className="page-description">
          Debug view of assembled LLM context. See what the AI sees before each request.
        </p>
      </div>

      <div className="request-panel">
        <div className="input-group">
          <label htmlFor="request">User Request</label>
          <textarea
            id="request"
            value={request}
            onChange={(e) => setRequest(e.target.value)}
            placeholder="Enter a request to see how context is assembled..."
            rows={3}
          />
        </div>
        
        <div className="checkbox-group">
          <label>
            <input
              type="checkbox"
              checked={includeFullSim}
              onChange={(e) => setIncludeFullSim(e.target.checked)}
            />
            Include full simulation data
          </label>
          <label>
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
            />
            Auto-refresh on chat events
          </label>
        </div>
        
        <button onClick={handleManualAssemble} disabled={loading}>
          {loading ? 'Assembling...' : 'Assemble Context'}
        </button>
      </div>

      {error && (
        <div className="error-panel">
          <span className="error-icon">⚠️</span>
          <span>{error}</span>
        </div>
      )}

      {lastEventSource && (
        <div className="refresh-indicator">
          <span className="refresh-icon">🔄</span>
          <span>Auto-refreshed {lastEventSource}</span>
        </div>
      )}

      {data && (
        <div className="result-panel">
          <TokenBudgetView budget={data.budget_summary} totalTokens={data.total_tokens} />
          <ContextView layers={data.layers} />
        </div>
      )}
    </div>
  )
}