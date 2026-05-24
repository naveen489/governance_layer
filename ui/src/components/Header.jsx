import { fetchApi } from '../api.js'
import { useLocation } from 'react-router-dom'
import { useState, useEffect } from 'react'

const PAGE_TITLES = {
  '/dashboard':  { title: 'Dashboard',     subtitle: 'Overview of governance activity' },
  '/reviews':    { title: 'Review Queue',  subtitle: 'Items requiring human review' },
  '/assets':     { title: 'Assets',        subtitle: 'Generated asset governance states and manifests' },
  '/policies':   { title: 'Policy Admin',  subtitle: 'Manage governance policy versions' },
  '/exceptions': { title: 'Exceptions',    subtitle: 'Exception requests and approvals' },
  '/audit':      { title: 'Audit Log',     subtitle: 'Immutable governance event trail' },
}

export default function Header() {
  const { pathname } = useLocation()
  const meta = PAGE_TITLES[pathname] || { title: 'Governance', subtitle: '' }
  const [healthy, setHealthy] = useState(null)

  useEffect(() => {
    fetchApi('/health')
      .then(r => r.ok ? setHealthy(true) : setHealthy(false))
      .catch(() => setHealthy(false))
  }, [])

  return (
    <header className="header">
      <div>
        <div className="header-title">{meta.title}</div>
        <div className="header-subtitle">{meta.subtitle}</div>
      </div>
      <div className="header-right">
        {healthy !== null && (
          <div className={`header-badge ${healthy ? '' : 'header-badge-error'}`}
               style={!healthy ? { background: 'var(--red-bg)', color: 'var(--red)', borderColor: 'rgba(248,113,113,0.3)' } : {}}>
            <span className="header-badge-dot"
                  style={!healthy ? { background: 'var(--red)' } : {}} />
            {healthy ? 'API Connected' : 'API Offline'}
          </div>
        )}
      </div>
    </header>
  )
}
