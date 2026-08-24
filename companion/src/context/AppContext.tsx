import { createContext, useContext, useState, useCallback, useEffect, ReactNode } from 'react'
import { useApi } from '@/hooks/useApi'
import type { ContextAssemblyResult } from '@/services/context'

const STORAGE_KEY_LLM = 'hephaistus_llm_selection'

interface LLMSelection {
  provider: string
  model: string
}

interface HistoryEntry {
  id: string
  session_id: string
  timestamp: string
  user_request: string
  llm_response?: string
  reasoning_summary?: string
  patch_plan_json?: string
}

interface LLMResponse {
  raw_response: string
  patch_plan: any | null
  provider: string
  model: string
}

interface AppState {
  // LLM selection (persisted to localStorage)
  llmSelection: LLMSelection
  setLLMSelection: (selection: LLMSelection) => void
  
  // Last LLM response (persists across tab switches)
  lastResponse: LLMResponse | null
  setLastResponse: (response: LLMResponse | null) => void
  
  // Last assembled context (persists across tab switches)
  lastContext: ContextAssemblyResult | null
  setLastContext: (context: ContextAssemblyResult | null) => void
  
  // Chat history navigation
  historyEntries: HistoryEntry[]
  historyIndex: number
  setHistoryIndex: (index: number) => void
  historyLoading: boolean
  fetchHistory: () => Promise<void>
  navigateHistory: (direction: 'prev' | 'next') => void
  canNavigateHistory: { prev: boolean; next: boolean }
  
  // Fetch last prompt from server (for Context Inspector)
  fetchLastPrompt: () => Promise<void>
}

const AppContext = createContext<AppState | null>(null)

export function AppProvider({ children }: { children: ReactNode }) {
  const [llmSelection, setLLMSelectionState] = useState<LLMSelection>(() => {
    // Load from localStorage on init
    try {
      const stored = localStorage.getItem(STORAGE_KEY_LLM)
      if (stored) {
        return JSON.parse(stored)
      }
    } catch {}
    return { provider: 'ollama', model: 'gemma4:e4b' }
  })
  
  const [lastResponse, setLastResponse] = useState<LLMResponse | null>(null)
  const [lastContext, setLastContext] = useState<ContextAssemblyResult | null>(null)
  const [historyEntries, setHistoryEntries] = useState<HistoryEntry[]>([])
  const [historyIndex, setHistoryIndex] = useState<number>(-1) // -1 means current/none selected
  const [historyLoading, setHistoryLoading] = useState(false)
  
  const { execute } = useApi<any>()

  // Persist LLM selection to localStorage
  const setLLMSelection = useCallback((selection: LLMSelection) => {
    setLLMSelectionState(selection)
    try {
      localStorage.setItem(STORAGE_KEY_LLM, JSON.stringify(selection))
    } catch {}
  }, [])

  const fetchLastPrompt = useCallback(async () => {
    try {
      const result = await execute('/api/debug/last-prompt')
      if (result && result.layer_contents) {
        setLastContext({
          total_tokens: result.total_tokens || 0,
          budget_summary: result.budget_summary,
          layers: result.layers || result.layer_contents,
          prompt: result.assembled_context || '',
        })
      }
    } catch (err) {
      console.error('Failed to fetch last prompt:', err)
    }
  }, [execute])

  const fetchHistory = useCallback(async () => {
    setHistoryLoading(true)
    try {
      const result = await execute('/api/history/recent?limit=50')
      if (result && result.entries) {
        setHistoryEntries(result.entries)
        setHistoryIndex(-1) // Reset to current
      }
    } catch (err) {
      console.error('Failed to fetch history:', err)
    } finally {
      setHistoryLoading(false)
    }
  }, [execute])

  const navigateHistory = useCallback((direction: 'prev' | 'next') => {
    if (direction === 'prev' && historyIndex < historyEntries.length - 1) {
      setHistoryIndex(historyIndex + 1)
    } else if (direction === 'next' && historyIndex > -1) {
      setHistoryIndex(historyIndex - 1)
    }
  }, [historyIndex, historyEntries.length])

  const canNavigateHistory = {
    prev: historyIndex < historyEntries.length - 1,
    next: historyIndex > -1,
  }

  // Load last prompt on mount (in case page was refreshed)
  useEffect(() => {
    if (!lastContext) {
      fetchLastPrompt()
    }
  }, [])

  // Fetch history on mount
  useEffect(() => {
    fetchHistory()
  }, [fetchHistory])

  return (
    <AppContext.Provider value={{
      llmSelection,
      setLLMSelection,
      lastResponse,
      setLastResponse,
      lastContext,
      setLastContext,
      historyEntries,
      historyIndex,
      setHistoryIndex,
      historyLoading,
      fetchHistory,
      navigateHistory,
      canNavigateHistory,
      fetchLastPrompt,
    }}>
      {children}
    </AppContext.Provider>
  )
}

export function useAppState() {
  const context = useContext(AppContext)
  if (!context) {
    throw new Error('useAppState must be used within AppProvider')
  }
  return context
}