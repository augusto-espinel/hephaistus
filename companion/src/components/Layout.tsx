import { Outlet, NavLink } from 'react-router-dom'
import { useSessionStatus } from '@/hooks/useSessionStatus'
import './Layout.css'

interface LayoutProps {
  onLoadSchematic?: () => void
  onClearHistory?: () => void
  clearLoading?: boolean
}

export function Layout({ onLoadSchematic, onClearHistory, clearLoading }: LayoutProps) {
  const { data: sessionData } = useSessionStatus()
  
  const hasSession = sessionData?.has_session ?? false
  const schematicName = sessionData?.schematic?.relative_path || 'No schematic'

  return (
    <div className="layout">
      <header className="header">
        <div className="logo">
          <span className="logo-icon">🔧</span>
          <span className="logo-text">HephAIstus</span>
        </div>
        
        {/* Session actions bar */}
        <div className="session-bar">
          <span className="schematic-name" title={sessionData?.schematic?.path || undefined}>
            {hasSession ? schematicName : 'No schematic loaded'}
          </span>
          {onLoadSchematic && (
            <button className="header-btn load" onClick={onLoadSchematic}>
              📁 Load
            </button>
          )}
          {hasSession && onClearHistory && (
            <button 
              className="header-btn clear" 
              onClick={onClearHistory}
              disabled={clearLoading}
            >
              🗑️ Clear
            </button>
          )}
        </div>
        
        <nav className="nav">
          <NavLink to="/" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
            Chat
          </NavLink>
          <NavLink to="/context" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
            Context
          </NavLink>
          <NavLink to="/diff" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
            Diff
          </NavLink>
          <NavLink to="/history" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
            History
          </NavLink>
          <NavLink to="/settings" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'} title="Settings">
            ⚙️
          </NavLink>
        </nav>
      </header>
      <main className="main">
        <Outlet />
      </main>
    </div>
  )
}