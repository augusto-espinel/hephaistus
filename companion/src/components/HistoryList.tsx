import type { HistoryEntry } from '@/services/history'

interface HistoryListProps {
  entries: HistoryEntry[]
}

export function HistoryList({ entries }: HistoryListProps) {
  if (entries.length === 0) {
    return <div className="empty-state">No history entries found</div>
  }

  return (
    <div className="history-list">
      {entries.map((entry) => (
        <div key={entry.id} className="history-entry">
          <div className="entry-header">
            <span className="entry-id">[{entry.id}]</span>
            <span className="entry-time">{formatTime(entry.timestamp)}</span>
            <ActionBadge action={entry.user_action} />
          </div>
          <div className="entry-request">{entry.user_request}</div>
          {entry.reasoning_summary && (
            <div className="entry-reasoning">{entry.reasoning_summary}</div>
          )}
          <div className="entry-meta">
            <span className="meta-tokens">
              {entry.context_tokens} ctx + {entry.response_tokens} resp
            </span>
          </div>
        </div>
      ))}
    </div>
  )
}

function ActionBadge({ action }: { action: string | null }) {
  if (!action) return null

  const color = action === 'accepted' ? '#4caf50' : action === 'rejected' ? '#f44336' : '#888'

  return (
    <span className="action-badge" style={{ backgroundColor: color }}>
      {action}
    </span>
  )
}

function formatTime(timestamp: string): string {
  const date = new Date(timestamp)
  return date.toLocaleString()
}