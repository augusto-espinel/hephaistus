export interface SchematicState {
  path: string | null
  hash: string | null
  component_count: number
  net_count: number
  components: Component[]
  nets: Net[]
  directives: Directive[]
  last_modified: string | null
  has_unsaved_changes: boolean
}

export interface SimulationState {
  status: 'current' | 'stale' | 'none'
  last_run_id: string | null
  last_run_timestamp: string | null
  analysis_type: string | null
  converged: boolean | null
  staleness_warning: string | null
}

// Re-export from hooks for backward compatibility
export type { SpiceLibraryInfo, SchematicInfo, SessionStatusResponse } from '@/hooks/useSessionStatus'
export type { SimulationImportRequest, SimulationImportResponse } from '@/hooks/useSimulation'

export interface Component {
  reference: string
  lib_id: string
  value?: string
  footprint?: string
  pins: Pin[]
}

export interface Pin {
  number: string
  name: string
  net: string
}

export interface Net {
  name: string
  pins: string[]
}

export interface Directive {
  directive_type: string
  text: string
}