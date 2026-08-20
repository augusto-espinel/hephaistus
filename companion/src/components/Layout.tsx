import { Outlet, NavLink } from 'react-router-dom'
import './Layout.css'

export function Layout() {
  return (
    <div className="layout">
      <header className="header">
        <div className="logo">
          <span className="logo-icon">🔧</span>
          <span className="logo-text">HephAIstus</span>
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
        </nav>
        <div className="status">
          <span className="status-dot connected" />
          <span className="status-text">Connected</span>
        </div>
      </header>
      <main className="main">
        <Outlet />
      </main>
    </div>
  )
}