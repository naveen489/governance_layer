import { fetchApi } from '../api.js'
import { NavLink } from 'react-router-dom'
import { useState, useEffect } from 'react'

const NAV_ITEMS = [
  { to: '/dashboard',  icon: '⬡',  label: 'Dashboard' },
  { to: '/reviews',    icon: '⏳',  label: 'Review Queue',    queueKey: true },
  { to: '/assets',     icon: '🎬',  label: 'Assets' },
  { to: '/policies',   icon: '📋',  label: 'Policies' },
  { to: '/exceptions', icon: '⚡',  label: 'Exceptions' },
  { to: '/audit',      icon: '📊',  label: 'Audit Log' },
]

export default function Sidebar() {
  const [queueCount, setQueueCount] = useState(null)

  useEffect(() => {
    fetchApi('/api/governance/reviews')
      .then(r => r.json())
      .then(d => setQueueCount(Array.isArray(d) ? d.length : 0))
      .catch(() => setQueueCount(0))
  }, [])

  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        <div className="sidebar-logo-title">IncuBrix</div>
        <div className="sidebar-logo-sub">Governance Layer</div>
      </div>

      <nav className="sidebar-nav">
        <div className="nav-section-label">Control Plane</div>
        {NAV_ITEMS.map(item => (
          <NavLink
            key={item.to}
            to={item.to}
            id={`nav-${item.to.replace('/', '')}`}
            className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}
          >
            <span className="nav-icon">{item.icon}</span>
            {item.label}
            {item.queueKey && queueCount > 0 && (
              <span className="sidebar-badge">{queueCount}</span>
            )}
          </NavLink>
        ))}
      </nav>

      <div className="sidebar-footer">
        v1.0.0 · Internal Alpha<br />
        Feature flag: governance_layer
      </div>
    </aside>
  )
}
