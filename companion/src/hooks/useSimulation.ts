import { useEffect, useCallback } from 'react'
import { useApi } from './useApi'

export interface SimulationStateResponse {
  status: 'current' | 'stale' | 'none'
  last_run_id: string | null
  last_run_timestamp: string | null
  analysis_type: string | null
  converged: boolean | null
  staleness_warning: string | null
}

export interface SimulationImportRequest {
  csv_path?: string | null
  console_text?: string | null
}

export interface SimulationImportResponse {
  status: 'imported' | 'error'
  run_id: string
  analysis_type: string
  converged: boolean
  warnings: string[]
  errors: string[]
  op_point_count: number
  signal_count: number
  sample_count: number
}

export function useSimulationState() {
  const { data, loading, error, execute } = useApi<SimulationStateResponse>()

  const fetch = useCallback(() => {
    execute('/api/simulation/state')
  }, [execute])

  useEffect(() => {
    fetch()
  }, [fetch])

  return { 
    data, 
    loading, 
    error, 
    refresh: fetch 
  }
}

export function useSimulationImport() {
  const { data, loading, error, execute } = useApi<SimulationImportResponse>()

  const importSimulation = useCallback(async (request: SimulationImportRequest) => {
    await execute('/api/simulation/import', {
      method: 'POST',
      body: JSON.stringify(request),
    })
  }, [execute])

  return { 
    data, 
    loading, 
    error, 
    importSimulation,
    reset: () => execute('/api/simulation/state') // Reset to just fetch state
  }
}