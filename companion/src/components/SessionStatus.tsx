import { useState, useEffect } from 'react'
import { useApi } from '@/hooks/useApi'
import type { SessionStatusResponse } from '@/hooks/useSessionStatus'

interface SessionStatusProps {
  data: SessionStatusResponse | null
  loading?: boolean
  onLoadSchematic?: () => void
  onImportSimulation?: () => void
  onReloadSchematic?: () => void
}

interface StalenessInfo {
  stale: boolean
  reason: string
  path?: string
  stored_hash?: string
  current_hash?: string
}

export function SessionStatus({ 
  data, 
  loading, 
  onLoadSchematic, 
  onImportSimulation,
  onReloadSchematic 
}: SessionStatusProps) {
  const [showLibraries, setShowLibraries] = useState(false)
  const [staleness, setStaleness] = useState<StalenessInfo | null>(null)
  const { execute } = useApi<StalenessInfo>()

  // Check for schematic staleness periodically
  useEffect(() => {
    if (!data?.has_session) {
      setStaleness(null)
      return
    }

    const checkStaleness = async () => {
      try {
        const result = await execute('/api/schematic/check-stale')
        setStaleness(result)
      } catch (err) {
        console.error('Failed to check staleness:', err)
      }
    }

    // Check immediately
    checkStaleness()

    // Check every 5 seconds
    const interval = setInterval(checkStaleness, 5000)
    return () => clearInterval(interval)
  }, [data?.has_session])

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
  const isStale = staleness?.stale && staleness.reason === 'modified_externally'

  return (
    <div className="session-status">
      {/* Schematic Section */}
      <div className="status-section">
        <h4>Schematic</h4>
        <div className="status-row">
          <span className={`status-dot ${isStale ? 'stale' : 'current'}`} />
          <span className="status-label">
            {schematic.relative_path || 'unknown'}
          </span>
          <span className={`status-badge ${isStale ? 'warning' : 'saved'}`}>
            {isStale ? 'modified' : 'loaded'}
          </span>
          {onReloadSchematic && (
            <button 
              className="reload-mini-btn"
              onClick={onReloadSchematic}
              title="Reload schematic"
            >
              ↻
            </button>
          )}
        </div>
        <div className="status-details">
          <span>{schematic.component_count} components</span>
          <span>{schematic.net_count} nets</span>
        </div>
        
        {/* Staleness Warning */}
        {isStale && (
          <div className="status-warning stale">
            <span className="warning-icon">⚠️</span>
            <span>Schematic modified in KiCad</span>
          </div>
        )}
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

        {/* Always allow importing new simulation */}
        {onImportSimulation && (
          <button 
            className="import-button"
            onClick={onImportSimulation}
          >
            {simStatus === 'none' ? 'Import Simulation' : 'Replace Simulation'}
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