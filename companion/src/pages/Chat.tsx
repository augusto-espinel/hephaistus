import { useState, useEffect } from 'react'
import { useSessionStatus } from '@/hooks/useSessionStatus'
import { useSimulationState, useSimulationImport } from '@/hooks/useSimulation'
import { useLLM } from '@/hooks/useLLM'
import { useSchematic } from '@/hooks/useSchematic'
import { useSession } from '@/hooks/useSession'
import { useAppState } from '@/context/AppContext'
import { SessionStatus } from '@/components/SessionStatus'
import { ImportSimulationDialog } from '@/components/ImportSimulationDialog'
import { LoadSchematicDialog } from '@/components/LoadSchematicDialog'
import { MarkdownRenderer } from '@/components/MarkdownRenderer'
import { PatchApprovalCard } from '@/components/PatchApprovalCard'
import { emit, Events } from '@/events'

interface ChatProps {
  showLoadDialog?: boolean
  onLoadDialogClose?: () => void
  showClearDialog?: boolean
  onClearDialogClose?: (confirmed: boolean) => void
}

export function Chat({ 
  showLoadDialog = false, 
  onLoadDialogClose,
  showClearDialog = false,
  onClearDialogClose 
}: ChatProps) {
  const [request, setRequest] = useState('')
  const [internalShowLoad, setInternalShowLoad] = useState(false)
  const [internalShowImport, setInternalShowImport] = useState(false)
  
  // Use external or internal dialog state
  const showLoad = showLoadDialog || internalShowLoad
  const setShowLoad = onLoadDialogClose 
    ? (show: boolean) => { if (!show) onLoadDialogClose() } 
    : setInternalShowLoad
  
  // Shared app state (persists across tab switches)
  const { 
    lastResponse, 
    setLastResponse,
    llmSelection,
    historyEntries,
    historyIndex,
    setHistoryIndex,
    historyLoading,
    fetchHistory,
    navigateHistory,
    canNavigateHistory,
  } = useAppState()
  
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
  
  // Schematic load
  const {
    loading: loadLoading,
    error: loadError,
    load: loadSchematic
  } = useSchematic()

  // Session management
  const {
    generateSummary,
  } = useSession()

  // Pre-prompt guard status
  const hasSession = sessionData?.has_session ?? false
  const canPrompt = hasSession

  // Refresh history after session loads
  useEffect(() => {
    if (hasSession) {
      fetchHistory()
    }
  }, [hasSession, fetchHistory])

  // Handle clear dialog confirmation
  useEffect(() => {
    if (showClearDialog && onClearDialogClose) {
      // Dialog is shown externally, wait for result
    }
  }, [showClearDialog, onClearDialogClose])

  const handleSubmit = async () => {
    if (!canPrompt || !request.trim()) return

    const result = await generate({
      request: request.trim(),
      provider: llmSelection.provider as 'ollama' | 'openrouter',
      model: llmSelection.model,
      // OpenRouter needs longer timeout for large models (network + inference)
      timeout_seconds: llmSelection.provider === 'openrouter' ? 300 : undefined,
    })
    
    // Persist response to shared state so it survives tab switches
    if (result) {
      setLastResponse({
        raw_response: result.raw_response || '',
        patch_plan: result.patch_plan || null,
        provider: llmSelection.provider,
        model: llmSelection.model,
        thinking_content: result.thinking_content || '',
        display_response: result.display_response || '',
      })
      setRequest('') // Clear input after successful submission
      // Refresh history to include new entry
      fetchHistory()
    }
    
    // Signal Context Inspector to refresh
    emit(Events.PROMPT_SENT)
  }

  const handleGenerateSummary = async () => {
    if (!canPrompt) return

    try {
      const result = await generateSummary()
      if (result && result.prompt) {
        // Send the summary prompt to the LLM
        const llmResult = await generate({
          request: result.prompt,
          provider: llmSelection.provider as 'ollama' | 'openrouter',
          model: llmSelection.model,
          // OpenRouter needs longer timeout for large models (network + inference)
          timeout_seconds: llmSelection.provider === 'openrouter' ? 300 : undefined,
        })
        
        if (llmResult) {
          setLastResponse({
            raw_response: llmResult.raw_response || '',
            patch_plan: llmResult.patch_plan || null,
            provider: llmSelection.provider,
            model: llmSelection.model,
            thinking_content: llmResult.thinking_content || '',
            display_response: llmResult.display_response || '',
          })
          fetchHistory()
        }
      }
    } catch (err) {
      console.error('Failed to generate summary:', err)
    }
  }

  const handleImportSimulation = async (csvPath: string | null, consoleText: string | null) => {
    await importSimulation({
      csv_path: csvPath,
      console_text: consoleText,
    })
    // Refresh both session and simulation state
    refreshSession()
    refreshSimState()
    emit(Events.SIMULATION_IMPORTED)
  }

  const handleLoadSchematic = async (path: string) => {
    await loadSchematic(path)
    // Schematic loaded successfully - caller will close dialog
    // Clear state immediately
    setLastResponse(null)
    setHistoryIndex(-1)
    // Delay refresh to allow dialog close animation to complete
    // 300ms is enough for CSS transitions
    setTimeout(() => {
      refreshSession()
      fetchHistory()
      emit(Events.SCHEMATIC_LOADED)
    }, 300)
  }

  const handleReloadSchematic = async () => {
    if (!sessionData?.schematic?.path) return
    await loadSchematic(sessionData.schematic.path)
    refreshSession()
    fetchHistory() // Refresh history after reload
  }

  // Get current display based on history navigation
  const getCurrentEntry = () => {
    if (historyIndex === -1 || historyIndex >= historyEntries.length) {
      return null // Show current/none
    }
    return historyEntries[historyIndex]
  }

  const currentEntry = getCurrentEntry()
  
  // Determine what to display: history entry or last response
  const displayResponse = currentEntry 
    ? {
        raw_response: currentEntry.llm_response || '',
        patch_plan: currentEntry.patch_plan_json ? JSON.parse(currentEntry.patch_plan_json) : null,
        is_history: true as const,
        timestamp: currentEntry.timestamp,
        request: currentEntry.user_request,
        thinking_content: '',
        display_response: '',
      }
    : lastResponse

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
        onLoadSchematic={() => setInternalShowLoad(true)}
        onImportSimulation={() => setInternalShowImport(true)}
        onReloadSchematic={handleReloadSchematic}
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

      {/* History Navigation */}
      {hasSession && historyEntries.length > 0 && (
        <div className="history-nav">
          <span className="history-label">Design Iterations</span>
          <div className="history-controls">
            <button 
              className="history-btn"
              onClick={() => navigateHistory('prev')}
              disabled={!canNavigateHistory.prev || historyLoading}
              title="Previous iteration"
            >
              ← Older
            </button>
            <span className="history-position">
              {historyIndex === -1 
                ? 'Current' 
                : `${historyEntries.length - historyIndex} / ${historyEntries.length}`}
            </span>
            <button 
              className="history-btn"
              onClick={() => navigateHistory('next')}
              disabled={!canNavigateHistory.next || historyLoading}
              title="Next iteration"
            >
              Newer →
            </button>
          </div>
          {currentEntry && (
            <div className="history-timestamp">
              {new Date(currentEntry.timestamp).toLocaleString()}
            </div>
          )}
        </div>
      )}

      {/* Response Display */}
      <div className="chat-container">
        <div className="chat-messages">
          {displayResponse?.raw_response && (
            <div className={`message assistant ${currentEntry ? 'history-entry' : ''}`}>
              {currentEntry && (
                <div className="history-request">
                  <strong>Request:</strong> {currentEntry.user_request}
                </div>
              )}
              {/* Collapsible thinking/reasoning block */}
              {displayResponse.thinking_content && (
                <details className="thinking-block">
                  <summary>🧠 Reasoning ({displayResponse.thinking_content.length} chars)</summary>
                  <div className="thinking-content">
                    <MarkdownRenderer content={displayResponse.thinking_content} />
                  </div>
                </details>
              )}
              {/* Main response content (uses display_response with thinking removed) */}
              <div className="message-content">
                <MarkdownRenderer content={displayResponse.display_response || displayResponse.raw_response} />
              </div>
              {displayResponse.patch_plan && (
                <PatchApprovalCard
                  patchPlan={displayResponse.patch_plan}
                  onApplied={() => {
                    setLastResponse(null)
                    refreshSession()
                    fetchHistory()
                  }}
                />
              )}
            </div>
          )}
          {!displayResponse && !llmLoading && hasSession && (
            <div className="empty-state">
              <p>No conversation yet. Describe a change you'd like to make.</p>
              <p className="hint">
                Example: "Add a snubber circuit across D1 to suppress voltage spikes"
              </p>
            </div>
          )}
        </div>

        {/* Input area */}
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
          <div className="input-actions">
            <button 
              className="secondary-btn"
              onClick={handleGenerateSummary}
              disabled={!canPrompt || llmLoading}
              title="Generate a summary of this design session"
            >
              📋 Summary
            </button>
            <button 
              onClick={handleSubmit} 
              disabled={!canPrompt || llmLoading || !request.trim()}
            >
              {llmLoading ? 'Thinking...' : 'Send'}
            </button>
          </div>
        </div>

        {llmError && (
          <div className="error-panel">
            <span className="error-icon">⚠️</span>
            <span>{llmError}</span>
          </div>
        )}
      </div>

      <ImportSimulationDialog
        isOpen={internalShowImport}
        onClose={() => setInternalShowImport(false)}
        onImport={handleImportSimulation}
        loading={importLoading}
        error={importError}
      />

      <LoadSchematicDialog
        isOpen={showLoad}
        onClose={() => setShowLoad(false)}
        onLoad={handleLoadSchematic}
        loading={loadLoading}
        error={loadError}
      />
    </div>
  )
}