import { useState } from 'react'
import type { SessionStatusResponse } from '@/hooks/useSessionStatus'

interface SessionStatusProps {
  data: SessionStatusResponse | null
  loading?: boolean
  onLoadSchematic?: () => void
  onImportSimulation?: () => void
}

export function SessionStatus({ data, loading, onLoadSchematic, onImportSimulation }: SessionStatusProps) {
  const [showLibraries, setShowLibraries] = useState(false)

  if (loading) {
    return (
      <div className="session-status loading">
        <span className="status-dot pulse" />
        <span>Loading session status...</span>
      </div>
    )
  }

  if (!data || !data.has_session) {
    return (
      <div className="session-status empty">
        <p>No schematic loaded</p>
        <p className="hint">Open a KiCad schematic to begin</p>
        {onLoadSchematic && (
          <button className="load-button" onClick={onLoadSchematic}>
            Load Schematic
          </button>
        )}
      </div>
    )
  }

  const { schematic, simulation, spice_libraries } = data
  const simStatus = simulation.status
  const hasLibraries = spice_libraries && spice_libraries.length > 0

  return (
    <div className="session-status">
      {/* Schematic Section */}
      <div className="status-section">
        <h4>Schematic</h4>
        <div className="status-row">
          <span className="status-dot current" />
          <span className="status-label">
            {schematic.relative_path || 'unknown'}
          </span>
          <span className="status-badge saved">loaded</span>
        </div>
        <div className="status-details">
          <span>{schematic.component_count} components</span>
          <span>{schematic.net_count} nets</span>
        </div>
      </div>

      {/* Simulation Section */}
      <div className="status-section">
        <h4>Simulation</h4>
        <div className="status-row">
          <span className={`status-dot ${simStatus}`} />
          <span className="status-label">
            {simStatus === 'current' ? 'Current' : 
             simStatus === 'stale' ? 'Stale' : 'None'}
          </span>
          {simulation.analysis_type && (
            <span className="status-badge info">{simulation.analysis_type}</span>
          )}
        </div>
        
        {simulation.last_run_timestamp && (
          <div className="status-details">
            <span>Last run: {new Date(simulation.last_run_timestamp).toLocaleString()}</span>
          </div>
        )}

        {simulation.staleness_warning && (
          <div className="status-warning">
            {simulation.staleness_warning}
          </div>
        )}

        {(simStatus === 'none' || simStatus === 'stale') && onImportSimulation && (
          <button 
            className="import-button"
            onClick={onImportSimulation}
          >
            Import Simulation
          </button>
        )}
      </div>

      {/* SPICE Libraries Section */}
      {hasLibraries && (
        <div className="status-section">
          <h4>
            <button 
              className="expand-header"
              onClick={() => setShowLibraries(!showLibraries)}
            >
              <span>SPICE Libraries</span>
              <span className="expand-icon">{showLibraries ? '▼' : '▶'}</span>
              <span className="status-badge count">{spice_libraries.length}</span>
            </button>
          </h4>
          
          {showLibraries && (
            <div className="library-list">
              {spice_libraries.map((lib, idx) => (
                <div key={idx} className="library-item">
                  <span className="library-name">{lib.name}</span>
                  <div className="library-details">
                    {lib.models.length > 0 && (
                      <span className="library-models">
                        Models: {lib.models.join(', ')}
                      </span>
                    )}
                    {lib.subcircuits.length > 0 && (
                      <span className="library-subcircuits">
                        Subckts: {lib.subcircuits.join(', ')}
                      </span>
                    )}
                    <span className="library-tokens">
                      ~{lib.token_estimate} tokens
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Workflow Section */}
      <div className="status-section workflow">
        <h4>Workflow</h4>
        <ol className="workflow-steps">
          <li className="complete">Open schematic in KiCad</li>
          <li className={simStatus === 'current' ? 'complete' : ''}>
            Run simulation (optional)
          </li>
          <li className="active">
            Describe changes in chat
          </li>
        </ol>
      </div>
    </div>
  )
}