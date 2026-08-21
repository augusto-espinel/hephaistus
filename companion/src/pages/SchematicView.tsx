import { useFetch } from '@/hooks/useFetch'
import type { SchematicState } from '@/services/schematic'

export function SchematicView() {
  const { data, loading, error } = useFetch<SchematicState>('/api/schematic/state')

  return (
    <div className="schematic-view">
      <div className="page-header">
        <h1>Schematic</h1>
        <p className="page-description">
          Current schematic state and components.
        </p>
      </div>

      {loading && <div className="loading">Loading...</div>}

      {error && (
        <div className="error-panel">
          <span className="error-icon">⚠️</span>
          <span>{error}</span>
        </div>
      )}

      {data && (
        <div className="schematic-info">
          <div className="info-card">
            <h3>File</h3>
            <span className="file-path">{data.path || '(none loaded)'}</span>
          </div>

          <div className="info-card">
            <h3>Components ({data.component_count})</h3>
            <ul className="component-list">
              {data.components?.slice(0, 10).map((c) => (
                <li key={c.reference}>
                  <span className="ref">{c.reference}</span>
                  <span className="value">{c.value}</span>
                </li>
              ))}
              {data.component_count > 10 && (
                <li className="more">+{data.component_count - 10} more</li>
              )}
            </ul>
          </div>

          <div className="info-card">
            <h3>Nets ({data.net_count})</h3>
            <ul className="net-list">
              {data.nets?.slice(0, 5).map((n) => (
                <li key={n.name}>{n.name} ({n.pins?.length || 0} pins)</li>
              ))}
            </ul>
          </div>

          <div className="info-card">
            <h3>Simulation Directives</h3>
            <ul className="directive-list">
              {data.directives?.map((d, i) => (
                <li key={i}><code>{d.text}</code></li>
              ))}
              {(!data.directives || data.directives.length === 0) && (
                <li className="none">No simulation directives</li>
              )}
            </ul>
          </div>
        </div>
      )}
    </div>
  )
}