import type { SchematicState, SimulationState } from '@/services/schematic'

interface SessionStatusProps {
  schematic: SchematicState | null
  simulation: SimulationState | null
  loading?: boolean
}

export function SessionStatus({ schematic, simulation, loading }: SessionStatusProps) {
  if (loading) {
    return (
      <div className="session-status loading">
        <span className="status-dot pulse" />
        <span>Loading session status...</span>
      </div>
    )
  }

  const schematicStatus = schematic?.has_unsaved_changes ? 'stale' : 'current'
  const simulationStatus = simulation?.status || 'none'
  const fileSaved = schematicStatus === 'current'
  const simFresh = simulationStatus === 'current'

  return (
    <div className="session-status">
      <div className="status-section">
        <h4>Schematic</h4>
        <div className="status-row">
          <span className={`status-dot ${fileSaved ? 'current' : 'stale'}`} />
          <span className="status-label">
            {schematic?.path?.split('/').pop() || '(none loaded)'}
          </span>
          <span className={`status-badge ${fileSaved ? 'saved' : 'unsaved'}`}>
            {fileSaved ? 'saved' : 'unsaved'}
          </span>
        </div>
        {schematic && (
          <div className="status-details">
            <span>{schematic.component_count} components</span>
            <span>{schematic.net_count} nets</span>
          </div>
        )}
      </div>

      <div className="status-section">
        <h4>Simulation</h4>
        <div className="status-row">
          <span className={`status-dot ${simFresh ? 'current' : simulationStatus === 'stale' ? 'stale' : 'none'}`} />
          <span className="status-label">
            {simulationStatus === 'current' ? 'Current' : 
             simulationStatus === 'stale' ? 'Stale' : 'No simulation'}
          </span>
          {simulation?.analysis_type && (
            <span className="status-badge info">{simulation.analysis_type}</span>
          )}
        </div>
        {simulation?.staleness_warning && (
          <div className="status-warning">
            {simulation.staleness_warning}
          </div>
        )}
      </div>

      <div className="status-section workflow">
        <h4>Workflow</h4>
        <ol className="workflow-steps">
          <li className={fileSaved ? 'complete' : ''}>
            Save in KiCad
          </li>
          <li className={simFresh ? 'complete' : ''}>
            Run simulation (optional)
          </li>
          <li className={fileSaved ? 'active' : ''}>
            Prompt companion
          </li>
        </ol>
      </div>
    </div>
  )
}