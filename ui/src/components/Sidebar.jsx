import { fetchApi } from '../api.js'
import { NavLink } from 'react-router-dom'
import { useState, useEffect } from 'react'

const NAV_ITEMS_CORE = [
  { to: '/dashboard',  icon: '⬡',  label: 'Dashboard' },
  { to: '/reviews',    icon: '⏳',  label: 'Review Queue',    queueKey: true },
  { to: '/assets',     icon: '🎬',  label: 'Assets' },
  { to: '/policies',   icon: '📋',  label: 'Policies' },
  { to: '/exceptions', icon: '⚡',  label: 'Exceptions' },
  { to: '/audit',      icon: '📊',  label: 'Audit Log' },
]

const NAV_ITEMS_V2 = [
  { to: '/incidents',         icon: '🚨',  label: 'Incidents',          incidentKey: true },
  { to: '/provider-profiles', icon: '🤖',  label: 'Provider Profiles' },
  { to: '/simulate',          icon: '⚗️',  label: 'Policy Simulation' },
]

export default function Sidebar() {
  const [queueCount, setQueueCount] = useState(null)
  const [incidentCount, setIncidentCount] = useState(null)

  useEffect(() => {
    fetchApi('/api/governance/reviews')
      .then(r => r.json())
      .then(d => setQueueCount(Array.isArray(d) ? d.length : 0))
      .catch(() => setQueueCount(0))

    fetchApi('/api/governance/incidents?status=open&limit=100')
      .then(r => r.json())
      .then(d => setIncidentCount(d.total || 0))
      .catch(() => setIncidentCount(0))
  }, [])

  const renderLink = (item) => (
    <NavLink
      key={item.to}
      to={item.to}
      id={`nav-${item.to.replace(/\//g, '').replace(/-/g, '')}`}
      className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}
    >
      <span className="nav-icon">{item.icon}</span>
      {item.label}
      {item.queueKey && queueCount > 0 && (
        <span className="sidebar-badge">{queueCount}</span>
      )}
      {item.incidentKey && incidentCount > 0 && (
        <span className="sidebar-badge" style={{ background: 'var(--red)' }}>{incidentCount}</span>
      )}
    </NavLink>
  )

  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        <div className="sidebar-logo-title">IncuBrix</div>
        <div className="sidebar-logo-sub">Governance Layer v2</div>
      </div>

      <nav className="sidebar-nav">
        <div className="nav-section-label">Control Plane</div>
        {NAV_ITEMS_CORE.map(renderLink)}

        <div className="nav-section-label" style={{ marginTop: '16px' }}>Intelligence v2</div>
        {NAV_ITEMS_V2.map(renderLink)}
      </nav>

      <div className="sidebar-footer">
        v2.0.0 · Internal Alpha<br />
        Feature flag: governance_layer_v2
      </div>
    </aside>
  )
}
