import { useEffect, useCallback } from 'react'
import { useApi } from './useApi'

export interface SpiceLibraryInfo {
  name: string
  path: string
  models: string[]
  subcircuits: string[]
  token_estimate: number
}

export interface SchematicInfo {
  path: string | null
  relative_path: string | null
  hash: string | null
  component_count: number
  net_count: number
}

export interface SimulationInfo {
  status: 'current' | 'stale' | 'none'
  last_run_id: string | null
  last_run_timestamp: string | null
  analysis_type?: string | null
  converged?: boolean | null
  staleness_warning?: string | null
}

export interface SessionStatusResponse {
  has_session: boolean
  session_id: string | null
  project_root: string | null
  schematic: SchematicInfo
  simulation: SimulationInfo
  spice_libraries: SpiceLibraryInfo[]
  last_updated: string | null
}

export function useSessionStatus() {
  const { data, loading, error, execute } = useApi<SessionStatusResponse>()

  const fetch = useCallback(() => {
    execute('/api/session/status')
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