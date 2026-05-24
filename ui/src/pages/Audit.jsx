import { fetchApi } from '../api.js'
import { useState, useEffect } from 'react'

export default function Audit() {
  const [events, setEvents]             = useState([])
  const [total, setTotal]               = useState(0)
  const [loading, setLoading]           = useState(true)
  const [targetType, setTargetType]     = useState('')
  const [action, setAction]             = useState('')
  const [actorId, setActorId]           = useState('')
  const [dateFrom, setDateFrom]         = useState('')
  const [dateTo, setDateTo]             = useState('')
  const [q, setQ]                       = useState('')
  const [page, setPage]                 = useState(0)

  const PAGE_SIZE = 50

  const load = () => {
    setLoading(true)
    const params = new URLSearchParams()
    params.set('limit', PAGE_SIZE)
    params.set('offset', page * PAGE_SIZE)
    if (targetType) params.set('target_type', targetType)
    if (action)     params.set('action', action)
    if (actorId)    params.set('actor_id', actorId)
    if (dateFrom)   params.set('date_from', new Date(dateFrom).toISOString())
    if (dateTo)     params.set('date_to', new Date(dateTo + 'T23:59:59').toISOString())
    if (q)          params.set('q', q)

    fetchApi(`/api/governance/events?${params}`)
      .then(r => r.json())
      .then(d => { setEvents(d?.events || []); setTotal(d?.total || 0) })
      .catch(console.error)
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [targetType, action, actorId, dateFrom, dateTo, q, page])

  const TARGET_TYPES = ['', 'request', 'asset', 'exception', 'policy']

  return (
    <div>
      <div className="page-header">
        <h1>Audit Log</h1>
        <p>Immutable governance event trail – every state change recorded with actor, action, and timestamp</p>
      </div>

      <div className="filter-bar">
        <select id="filter-target-type" value={targetType} onChange={e => { setTargetType(e.target.value); setPage(0) }}>
          {TARGET_TYPES.map(t => <option key={t} value={t}>{t || 'All Types'}</option>)}
        </select>
        <input
          id="filter-action"
          placeholder="Filter by action…"
          value={action}
          onChange={e => { setAction(e.target.value); setPage(0) }}
        />
        <input
          id="filter-actor"
          placeholder="Filter by actor ID…"
          value={actorId}
          onChange={e => { setActorId(e.target.value); setPage(0) }}
        />
        <input id="filter-date-from" type="date" value={dateFrom} onChange={e => { setDateFrom(e.target.value); setPage(0) }} />
        <input id="filter-date-to" type="date" value={dateTo} onChange={e => { setDateTo(e.target.value); setPage(0) }} />
        <input
          id="filter-q"
          placeholder="Keyword search…"
          value={q}
          onChange={e => { setQ(e.target.value); setPage(0) }}
        />
        <button className="btn btn-ghost btn-sm" onClick={() => { setTargetType(''); setAction(''); setActorId(''); setDateFrom(''); setDateTo(''); setQ(''); setPage(0) }}>
          Clear
        </button>
      </div>

      <div className="panel">
        <div className="panel-header">
          <h2 className="panel-title">
            📊 Events
            <span style={{ marginLeft: '8px', fontSize: '12px', fontWeight: '400', color: 'var(--text-secondary)' }}>
              ({total} total)
            </span>
          </h2>
        </div>

        {loading && <div className="loading-center"><div className="spinner" /></div>}

        {!loading && events.length === 0 && (
          <div className="empty-state">
            <div className="empty-state-icon">📊</div>
            <h3>No events found</h3>
            <p>Adjust your filters or seed the database.</p>
          </div>
        )}

        {!loading && events.length > 0 && (
          <>
            <div className="table-wrapper">
              <table>
                <thead>
                  <tr>
                    <th>Timestamp</th>
                    <th>Target Type</th>
                    <th>Target ID</th>
                    <th>Actor</th>
                    <th>Action</th>
                    <th>Reason</th>
                  </tr>
                </thead>
                <tbody>
                  {events.map(evt => (
                    <tr key={evt.id}>
                      <td style={{ fontSize: '11px', whiteSpace: 'nowrap' }}>
                        {new Date(evt.occurred_at).toLocaleString()}
                      </td>
                      <td>
                        <span className={`badge badge-${evt.target_type}`} style={{ fontSize: '10px', padding: '2px 7px' }}>
                          {evt.target_type}
                        </span>
                      </td>
                      <td className="mono truncate">{evt.target_id.slice(0, 8)}…</td>
                      <td className="mono" style={{ fontSize: '11px' }}>{evt.actor_id}</td>
                      <td className="td-primary" style={{ fontSize: '12px', fontFamily: 'monospace' }}>
                        {evt.action}
                      </td>
                      <td style={{ fontSize: '12px', color: 'var(--text-secondary)', maxWidth: '220px' }}>
                        <span className="truncate" style={{ display: 'block' }}>{evt.reason || '—'}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '16px', paddingTop: '16px', borderTop: '1px solid var(--border-subtle)' }}>
              <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                Showing {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, total)} of {total}
              </span>
              <div className="btn-group">
                <button id="btn-audit-prev" className="btn btn-ghost btn-sm" onClick={() => setPage(p => Math.max(0, p - 1))} disabled={page === 0}>
                  ← Previous
                </button>
                <button id="btn-audit-next" className="btn btn-ghost btn-sm" onClick={() => setPage(p => p + 1)} disabled={(page + 1) * PAGE_SIZE >= total}>
                  Next →
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
