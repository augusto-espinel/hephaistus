import { useState } from 'react'
import { useSessionStatus } from '@/hooks/useSessionStatus'
import { useSimulationState, useSimulationImport } from '@/hooks/useSimulation'
import { useLLM } from '@/hooks/useLLM'
import { SessionStatus } from '@/components/SessionStatus'
import { ImportSimulationDialog } from '@/components/ImportSimulationDialog'

export function Chat() {
  const [request, setRequest] = useState('')
  const [showImportDialog, setShowImportDialog] = useState(false)
  
  // Session status (includes schematic + SPICE libraries)
  const { 
    data: sessionData, 
    loading: sessionLoading, 
    error: sessionError,
    refresh: refreshSession 
  } = useSessionStatus()
  
  // Simulation state (for import button visibility)
  const { refresh: refreshSimState } = useSimulationState()
  
  // LLM generation
  const { 
    data: llmData, 
    loading: llmLoading, 
    error: llmError, 
    generate 
  } = useLLM()
  
  // Simulation import
  const { 
    loading: importLoading, 
    error: importError, 
    importSimulation 
  } = useSimulationImport()

  // Pre-prompt guard status
  const hasSession = sessionData?.has_session ?? false
  const canPrompt = hasSession

  const handleSubmit = async () => {
    if (!canPrompt || !request.trim()) return

    await generate({
      request: request.trim(),
      provider: 'ollama', // Default to local
    })
  }

  const handleImportSimulation = async (csvPath: string | null, consoleText: string | null) => {
    await importSimulation({
      csv_path: csvPath,
      console_text: consoleText,
    })
    // Refresh both session and simulation state
    refreshSession()
    refreshSimState()
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
        data={sessionData}
        loading={sessionLoading}
        onImportSimulation={() => setShowImportDialog(true)}
      />

      {sessionError && (
        <div className="error-banner">
          <span className="error-icon">⚠️</span>
          <span>Session error: {sessionError}</span>
        </div>
      )}

      {!hasSession && !sessionLoading && (
        <div className="guard-panel">
          <div className="guard-warning">
            <span className="guard-icon">📋</span>
            <div className="guard-message">
              <strong>No schematic loaded</strong>
              <p>
                Open a KiCad schematic to begin. Save it in KiCad to make it available.
              </p>
            </div>
          </div>
        </div>
      )}

      <div className="chat-container">
        <div className="chat-messages">
          {llmData?.raw_response && (
            <div className="message assistant">
              <div className="message-content">
                {llmData.raw_response}
              </div>
              {llmData.patch_plan && (
                <div className="patch-plan-preview">
                  <h4>Proposed Changes:</h4>
                  <pre>{JSON.stringify(llmData.patch_plan, null, 2)}</pre>
                </div>
              )}
            </div>
          )}
          {!llmData && !llmLoading && hasSession && (
            <div className="empty-state">
              <p>No conversation yet. Describe a change you'd like to make.</p>
              <p className="hint">
                Example: "Add a snubber circuit across D1 to suppress voltage spikes"
              </p>
            </div>
          )}
        </div>

        <div className="chat-input">
          <textarea
            value={request}
            onChange={(e) => setRequest(e.target.value)}
            placeholder={
              hasSession 
                ? "e.g., Add a snubber circuit across D1 to suppress voltage spikes"
                : "Open a schematic first..."
            }
            rows={3}
            disabled={!canPrompt}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
                handleSubmit()
              }
            }}
          />
          <button 
            onClick={handleSubmit} 
            disabled={!canPrompt || llmLoading || !request.trim()}
          >
            {llmLoading ? 'Thinking...' : 'Send'}
          </button>
        </div>

        {llmError && (
          <div className="error-panel">
            <span className="error-icon">⚠️</span>
            <span>{llmError}</span>
          </div>
        )}
      </div>

      <ImportSimulationDialog
        isOpen={showImportDialog}
        onClose={() => setShowImportDialog(false)}
        onImport={handleImportSimulation}
        loading={importLoading}
        error={importError}
      />
    </div>
  )
}