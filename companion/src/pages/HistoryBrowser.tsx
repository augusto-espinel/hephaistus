import { useState } from 'react'
import { useApi } from '@/hooks/useApi'
import { HistoryList } from '@/components/HistoryList'
import type { HistoryEntry } from '@/services/history'

export function HistoryBrowser() {
  const [query, setQuery] = useState('')
  const [sessionId, setSessionId] = useState('')
  const { data, loading, error, execute } = useApi<{ entries: HistoryEntry[] }>()

  const handleSearch = async () => {
    const params = new URLSearchParams()
    if (query) params.set('q', query)
    if (sessionId) params.set('session', sessionId)
    await execute(`/api/history/search?${params.toString()}`)
  }

  const handleRecent = async () => {
    const params = new URLSearchParams()
    params.set('limit', '20')
    if (sessionId) params.set('session', sessionId)
    await execute(`/api/history/recent?${params.toString()}`)
  }

  return (
    <div className="history-browser">
      <div className="page-header">
        <h1>History Browser</h1>
        <p className="page-description">
          Search and explore past decisions and conversations.
        </p>
      </div>

      <div className="search-panel">
        <div className="input-row">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search history..."
            className="search-input"
          />
          <input
            type="text"
            value={sessionId}
            onChange={(e) => setSessionId(e.target.value)}
            placeholder="Session ID (optional)"
            className="session-input"
          />
        </div>
        <div className="button-row">
          <button onClick={handleSearch} disabled={loading}>Search</button>
          <button onClick={handleRecent} disabled={loading}>Recent</button>
        </div>
      </div>

      {error && (
        <div className="error-panel">
          <span className="error-icon">⚠️</span>
          <span>{error}</span>
        </div>
      )}

      {data && <HistoryList entries={data.entries} />}
    </div>
  )
}