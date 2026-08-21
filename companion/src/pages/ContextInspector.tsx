import { useState } from 'react'
import { useApi } from '@/hooks/useApi'
import { ContextView } from '@/components/ContextView'
import { TokenBudgetView } from '@/components/TokenBudgetView'
import type { ContextAssemblyResult } from '@/services/context'

export function ContextInspector() {
  const [request, setRequest] = useState('')
  const [includeFullSim, setIncludeFullSim] = useState(false)
  const { data, loading, error, execute } = useApi<ContextAssemblyResult>()

  const handleAssemble = async () => {
    await execute('/api/context/assemble', {
      method: 'POST',
      body: JSON.stringify({ request, includeFullSim }),
    })
  }

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
        </div>
        
        <button onClick={handleAssemble} disabled={loading}>
          {loading ? 'Assembling...' : 'Assemble Context'}
        </button>
      </div>

      {error && (
        <div className="error-panel">
          <span className="error-icon">⚠️</span>
          <span>{error}</span>
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