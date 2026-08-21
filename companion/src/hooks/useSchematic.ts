import { useCallback } from 'react'
import { useApi } from './useApi'

export interface LoadSchematicResponse {
  status: 'loaded' | 'error'
  path: string
  project_root: string
  relative_path: string
  components: number
  nets: number
  session_file: string
}

export function useSchematic() {
  const { data, loading, error, execute } = useApi<LoadSchematicResponse>()

  const load = useCallback(async (schematicPath: string) => {
    await execute(`/api/schematic/load?path=${encodeURIComponent(schematicPath)}`)
  }, [execute])

  return {
    data,
    loading,
    error,
    load,
  }
}