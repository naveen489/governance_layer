import { useState, useEffect } from 'react'

function StatCard({ icon, value, label, color }) {
  return (
    <div className="stat-card" style={{ '--accent-gradient': color }}>
      <div className="stat-card-icon">{icon}</div>
      <div className="stat-card-value">{value ?? '—'}</div>
      <div className="stat-card-label">{label}</div>
    </div>
  )
}

function StateBadge({ state }) {
  return (
    <span className={`badge badge-${state}`}>
      <span className="badge-dot" />
      {state?.replace(/_/g, ' ')}
    </span>
  )
}

export default function Dashboard() {
  const [requests, setRequests]   = useState([])
  const [assets, setAssets]       = useState([])
  const [events, setEvents]       = useState([])
  const [exceptions, setExceptions] = useState([])
  const [loading, setLoading]     = useState(true)

  const load = useCallback(() => {
    setLoading(true)
    Promise.all([
      fetchApi('/api/governance/requests?limit=100').then(r => r.json()),
      fetchApi('/api/governance/assets?limit=100').then(r => r.json()),
      fetchApi('/api/governance/events?limit=20').then(r => r.json()),
      fetchApi('/api/governance/exceptions?limit=100').then(r => r.json()),
    ])
      .then(([reqs, ast, evts, excs]) => {
        setRequests(Array.isArray(reqs) ? reqs : [])
        setAssets(Array.isArray(ast) ? ast : [])
        setEvents(evts?.events || [])
        setExceptions(excs?.exceptions || [])
      })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="loading-center"><div className="spinner" /></div>

  const pendingReviews = [
    ...requests.filter(r => r.governance_state === 'review_required'),
    ...assets.filter(a => a.governance_state === 'review_required'),
  ].length

  const activeExceptions = exceptions.filter(e => e.status === 'pending').length
  const expiredAssets    = assets.filter(a => a.governance_state === 'expired').length
  const passedAssets     = assets.filter(a => a.governance_state === 'governance_passed').length
  const blockedRequests  = requests.filter(r => r.governance_state === 'blocked').length

  const stateDistrib = requests.reduce((acc, r) => {
    acc[r.governance_state] = (acc[r.governance_state] || 0) + 1
    return acc
  }, {})

  return (
    <div>
      <div className="page-header">
        <h1>Governance Overview</h1>
        <p>Real-time view of requests, assets, approvals, and compliance posture</p>
      </div>

      <div className="stat-grid">
        <StatCard icon="📨" value={requests.length}   label="Total Requests"   color="linear-gradient(90deg, #6366f1, #818cf8)" />
        <StatCard icon="⏳" value={pendingReviews}    label="Pending Reviews"  color="linear-gradient(90deg, #60a5fa, #818cf8)" />
        <StatCard icon="✅" value={passedAssets}      label="Assets Passed"    color="linear-gradient(90deg, #34d399, #6ee7b7)" />
        <StatCard icon="🚫" value={blockedRequests}   label="Blocked Requests" color="linear-gradient(90deg, #f87171, #fca5a5)" />
        <StatCard icon="⚡" value={activeExceptions}  label="Pending Exceptions" color="linear-gradient(90deg, #fb923c, #fbbf24)" />
        <StatCard icon="🗂️" value={expiredAssets}    label="Expired Assets"   color="linear-gradient(90deg, #64748b, #94a3b8)" />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px' }}>
        {/* Request State Distribution */}
        <div className="panel">
          <div className="panel-header">
            <h2 className="panel-title">📊 Request State Distribution</h2>
          </div>
          {Object.entries(stateDistrib).map(([state, count]) => (
            <div key={state} style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '10px' }}>
              <StateBadge state={state} />
              <div style={{ flex: 1, background: 'var(--bg-elevated)', borderRadius: '99px', height: '6px', overflow: 'hidden' }}>
                <div style={{
                  width: `${(count / requests.length) * 100}%`,
                  height: '100%',
                  background: 'var(--accent)',
                  borderRadius: '99px',
                  transition: 'width 0.8s ease',
                }} />
              </div>
              <span style={{ fontSize: '13px', fontWeight: '700', color: 'var(--text-primary)', minWidth: '24px', textAlign: 'right' }}>{count}</span>
            </div>
          ))}
        </div>

        {/* Recent Audit Events */}
        <div className="panel">
          <div className="panel-header">
            <h2 className="panel-title">📋 Recent Audit Events</h2>
          </div>
          {events.length === 0 && <p style={{ color: 'var(--text-muted)', fontSize: '13px' }}>No events recorded yet.</p>}
          {events.slice(0, 8).map(evt => (
            <div key={evt.id} style={{
              padding: '10px 0',
              borderBottom: '1px solid var(--border-subtle)',
              display: 'flex',
              flexDirection: 'column',
              gap: '3px'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span style={{ fontSize: '12px', fontWeight: '600', color: 'var(--text-primary)' }}>
                  {evt.action?.replace(/_/g, ' ')}
                </span>
                <span className={`badge badge-${evt.target_type}`} style={{ fontSize: '10px', padding: '2px 7px' }}>
                  {evt.target_type}
                </span>
              </div>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                Actor: {evt.actor_id} · {new Date(evt.occurred_at).toLocaleString()}
              </div>
              {evt.reason && (
                <div style={{ fontSize: '11px', color: 'var(--text-secondary)', fontStyle: 'italic' }}>
                  "{evt.reason?.slice(0, 70)}{evt.reason?.length > 70 ? '…' : ''}"
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
