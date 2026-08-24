import { useCallback } from 'react'
import { useApi } from './useApi'

interface SummaryResponse {
  status: string
  prompt: string
  history_stats?: {
    total_entries: number
    sessions: string[]
  }
}

interface ClearResponse {
  status: string
  message: string
}

interface StalenessInfo {
  stale: boolean
  reason: string
  path?: string
}

export function useSession() {
  const clearApi = useApi<ClearResponse>()
  const summaryApi = useApi<SummaryResponse>()
  const staleApi = useApi<StalenessInfo>()

  const clearHistory = useCallback(async () => {
    const result = await clearApi.execute('/api/history', { method: 'DELETE' })
    return result
  }, [clearApi.execute])

  const generateSummary = useCallback(async () => {
    const result = await summaryApi.execute('/api/summary/generate', { method: 'POST' })
    return result
  }, [summaryApi.execute])

  const checkStale = useCallback(async () => {
    const result = await staleApi.execute('/api/schematic/check-stale')
    return result
  }, [staleApi.execute])

  return {
    clearHistory,
    generateSummary,
    checkStale,
    clearLoading: clearApi.loading,
    clearError: clearApi.error,
    summaryLoading: summaryApi.loading,
    summaryError: summaryApi.error,
  }
}