import { createContext, useContext, useState, useCallback, useEffect, ReactNode } from 'react'
import { useApi } from '@/hooks/useApi'
import type { ContextAssemblyResult } from '@/services/context'

interface LLMResponse {
  raw_response: string
  patch_plan: any | null
  provider: string
  model: string
}

interface AppState {
  // Last LLM response (persists across tab switches)
  lastResponse: LLMResponse | null
  setLastResponse: (response: LLMResponse | null) => void
  
  // Last assembled context (persists across tab switches)
  lastContext: ContextAssemblyResult | null
  setLastContext: (context: ContextAssemblyResult | null) => void
  
  // Fetch last prompt from server (for Context Inspector)
  fetchLastPrompt: () => Promise<void>
}

const AppContext = createContext<AppState | null>(null)

export function AppProvider({ children }: { children: ReactNode }) {
  const [lastResponse, setLastResponse] = useState<LLMResponse | null>(null)
  const [lastContext, setLastContext] = useState<ContextAssemblyResult | null>(null)
  const { execute } = useApi<any>()

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

  // Load last prompt on mount (in case page was refreshed)
  useEffect(() => {
    if (!lastContext) {
      fetchLastPrompt()
    }
  }, [])

  return (
    <AppContext.Provider value={{
      lastResponse,
      setLastResponse,
      lastContext,
      setLastContext,
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
