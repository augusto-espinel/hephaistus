import { useState } from 'react'
import { useApi } from '@/hooks/useApi'
import type { SchematicState, SimulationState } from '@/services/schematic'
import { SessionStatus } from '@/components/SessionStatus'

export function Chat() {
  const [request, setRequest] = useState('')
  const { data: schematicData, loading: schematicLoading } = useApi<SchematicState>('/api/schematic/state')
  const { data: simData, loading: simLoading } = useApi<SimulationState>('/api/simulation/state')
  const { data, loading, error, execute } = useApi<{ response: string }>()
  
  // Pre-prompt guard status
  const schematicSaved = !schematicData?.has_unsaved_changes
  const simulationCurrent = simData?.status === 'current'
  const canPrompt = schematicSaved
  
  const handleSubmit = async () => {
    if (!canPrompt) {
      return
    }
    await execute('/api/llm/generate', {
      method: 'POST',
      body: JSON.stringify({ request }),
    })
    setRequest('')
  }

  return (
    <div className="chat-page">
      <div className="page-header">
        <h1>HephAIstus</h1>
        <p className="page-description">
          Describe what you want to change, and I'll propose a patch-plan.
        </p>
      </div>

      <SessionStatus 
        schematic={schematicData} 
        simulation={simData}
        loading={schematicLoading || simLoading}
      />

      {!canPrompt && (
        <div className="guard-panel">
          <div className="guard-warning">
            <span className="guard-icon">⚠️</span>
            <div className="guard-message">
              <strong>Save required before prompting</strong>
              <p>
                {schematicSaved ? '' : 'Save your schematic in KiCad first. '}
                {simulationCurrent ? '' : 'Run simulation for fresh context (optional but recommended).'}
              </p>
              <div className="guard-actions">
                {!schematicSaved && (
                  <span className="guard-item">
                    <span className="guard-status stale">●</span> Schematic has unsaved changes
                  </span>
                )}
                {!simulationCurrent && simData?.status !== 'none' && (
                  <span className="guard-item">
                    <span className="guard-status stale">●</span> Simulation is stale
                  </span>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      <div className="chat-container">
        <div className="chat-messages">
          {data?.response && (
            <div className="message assistant">
              <div className="message-content">
                {data.response}
              </div>
            </div>
          )}
          {!data && !loading && (
            <div className="empty-state">
              <p>No conversation yet. Describe a change you'd like to make.</p>
            </div>
          )}
        </div>

        <div className="chat-input">
          <textarea
            value={request}
            onChange={(e) => setRequest(e.target.value)}
            placeholder="e.g., Add a snubber circuit across D1 to suppress voltage spikes"
            rows={3}
            disabled={!canPrompt}
          />
          <button 
            onClick={handleSubmit} 
            disabled={!canPrompt || loading || !request.trim()}
          >
            {loading ? 'Thinking...' : 'Send'}
          </button>
        </div>
      </div>

      {error && (
        <div className="error-panel">
          <span className="error-icon">⚠️</span>
          <span>{error}</span>
        </div>
      )}
    </div>
  )
}