import { fetchApi } from '../api.js'
import { useState, useEffect } from 'react'

const SEVERITY_ORDER = ['critical', 'high', 'medium', 'low']

function SeverityBadge({ severity }) {
  const colors = {
    critical: { bg: '#3d0a0a', color: '#ff5555', border: '#ff2222' },
    high: { bg: '#2d1a00', color: '#ff9944', border: '#ff7700' },
    medium: { bg: '#1a1a00', color: '#f5c518', border: '#c9a000' },
    low: { bg: '#0a1a0a', color: '#44cc66', border: '#229944' },
  }
  const c = colors[severity] || colors.medium
  return (
    <span style={{
      padding: '2px 10px', borderRadius: '999px', fontSize: '11px',
      fontWeight: 600, letterSpacing: '0.05em', textTransform: 'uppercase',
      background: c.bg, color: c.color, border: `1px solid ${c.border}`,
    }}>
      {severity}
    </span>
  )
}

function StatusBadge({ status }) {
  const map = {
    open: 'badge-review_required',
    triaged: 'badge-changes_requested',
    investigating: 'badge-escalated',
    remediation_pending: 'badge-escalated',
    resolved: 'badge-governance_passed',
    closed: 'badge-deleted',
  }
  return (
    <span className={`badge ${map[status] || 'badge-draft'}`}>
      <span className="badge-dot" />
      {status?.replace(/_/g, ' ')}
    </span>
  )
}

function CreateIncidentModal({ onClose, onCreated }) {
  const [form, setForm] = useState({ severity: 'medium', summary: '', trigger_event_id: '' })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const submit = async () => {
    if (!form.summary.trim()) { setError('Summary is required.'); return }
    setLoading(true); setError(null)
    try {
      const res = await fetchApi('/api/governance/incidents', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...form, trigger_event_id: form.trigger_event_id || undefined }),
      })
      if (!res.ok) throw new Error(await res.text())
      onCreated()
      onClose()
    } catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }

  return (
    <div className="modal-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal" style={{ maxWidth: '520px' }}>
        <h2 className="modal-title">Open Incident</h2>
        <div className="form-group">
          <label>Severity</label>
          <select value={form.severity} onChange={e => setForm({ ...form, severity: e.target.value })}>
            {SEVERITY_ORDER.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
        <div className="form-group">
          <label>Summary</label>
          <textarea value={form.summary} onChange={e => setForm({ ...form, summary: e.target.value })}
            placeholder="Describe the incident..." rows={3} style={{ width: '100%', resize: 'vertical' }} />
        </div>
        <div className="form-group">
          <label>Trigger Event ID <span style={{ color: 'var(--text-muted)' }}>(optional)</span></label>
          <input value={form.trigger_event_id} onChange={e => setForm({ ...form, trigger_event_id: e.target.value })}
            placeholder="event-uuid..." />
        </div>
        {error && <div className="alert alert-error">{error}</div>}
        <div className="modal-actions">
          <button className="btn btn-ghost" onClick={onClose} disabled={loading}>Cancel</button>
          <button className="btn btn-primary" onClick={submit} disabled={loading}>
            {loading ? 'Opening…' : 'Open Incident'}
          </button>
        </div>
      </div>
    </div>
  )
}

function IncidentDetailModal({ incident, onClose, onRefresh }) {
  const [form, setForm] = useState({ status: incident.status, notes: incident.notes || '', closure_reason: '' })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const update = async () => {
    setLoading(true); setError(null)
    try {
      const res = await fetchApi(`/api/governance/incidents/${incident.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      })
      if (!res.ok) throw new Error(await res.text())
      onRefresh(); onClose()
    } catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }

  const STATUS_OPTIONS = ['open', 'triaged', 'investigating', 'remediation_pending', 'resolved', 'closed']

  return (
    <div className="modal-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal" style={{ maxWidth: '600px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '24px' }}>
          <h2 className="modal-title" style={{ marginBottom: 0 }}>Incident Detail</h2>
          <SeverityBadge severity={incident.severity} />
        </div>

        <div className="detail-grid" style={{ marginBottom: '20px' }}>
          <div className="detail-item">
            <label>Incident ID</label>
            <div className="value mono" style={{ fontSize: '11px' }}>{incident.id}</div>
          </div>
          <div className="detail-item">
            <label>Status</label>
            <StatusBadge status={incident.status} />
          </div>
          <div className="detail-item" style={{ gridColumn: '1/-1' }}>
            <label>Summary</label>
            <div className="value">{incident.summary}</div>
          </div>
          {incident.trigger_event_id && (
            <div className="detail-item" style={{ gridColumn: '1/-1' }}>
              <label>Trigger Event</label>
              <div className="value mono" style={{ fontSize: '11px' }}>{incident.trigger_event_id}</div>
            </div>
          )}
          {incident.linked_targets && (
            <div className="detail-item" style={{ gridColumn: '1/-1' }}>
              <label>Linked Targets</label>
              <div className="value mono" style={{ fontSize: '11px' }}>{JSON.stringify(incident.linked_targets)}</div>
            </div>
          )}
          <div className="detail-item">
            <label>Opened</label>
            <div className="value">{new Date(incident.created_at).toLocaleString()}</div>
          </div>
          {incident.closed_at && (
            <div className="detail-item">
              <label>Closed</label>
              <div className="value">{new Date(incident.closed_at).toLocaleString()}</div>
            </div>
          )}
        </div>

        <hr style={{ borderColor: 'var(--border-default)', margin: '16px 0' }} />
        <h3 style={{ fontSize: '14px', marginBottom: '12px', color: 'var(--text-secondary)' }}>Update Incident</h3>

        <div className="form-group">
          <label>Status</label>
          <select value={form.status} onChange={e => setForm({ ...form, status: e.target.value })}>
            {STATUS_OPTIONS.map(s => <option key={s} value={s}>{s.replace(/_/g, ' ')}</option>)}
          </select>
        </div>
        <div className="form-group">
          <label>Notes</label>
          <textarea value={form.notes} onChange={e => setForm({ ...form, notes: e.target.value })}
            rows={2} style={{ width: '100%', resize: 'vertical' }} />
        </div>
        {(form.status === 'resolved' || form.status === 'closed') && (
          <div className="form-group">
            <label>Closure Reason</label>
            <textarea value={form.closure_reason} onChange={e => setForm({ ...form, closure_reason: e.target.value })}
              rows={2} style={{ width: '100%', resize: 'vertical' }} />
          </div>
        )}

        {error && <div className="alert alert-error">{error}</div>}
        <div className="modal-actions">
          <button className="btn btn-ghost" onClick={onClose} disabled={loading}>Close</button>
          <button className="btn btn-primary" onClick={update} disabled={loading}>
            {loading ? 'Saving…' : 'Save Changes'}
          </button>
        </div>
      </div>
    </div>
  )
}

export default function Incidents() {
  const [incidents, setIncidents] = useState([])
  const [loading, setLoading] = useState(true)
  const [statusFilter, setStatusFilter] = useState('')
  const [severityFilter, setSeverityFilter] = useState('')
  const [selected, setSelected] = useState(null)
  const [showCreate, setShowCreate] = useState(false)

  const load = () => {
    let url = '/api/governance/incidents?limit=100'
    if (statusFilter) url += `&status=${statusFilter}`
    if (severityFilter) url += `&severity=${severityFilter}`
    setLoading(true)
    fetchApi(url).then(r => r.json()).then(d => setIncidents(d.incidents || [])).catch(console.error).finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [statusFilter, severityFilter])

  const openCount = incidents.filter(i => ['open', 'triaged', 'investigating'].includes(i.status)).length
  const criticalCount = incidents.filter(i => i.severity === 'critical').length

  return (
    <div>
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <h1>Incident Management</h1>
          <p>Compliance cases, policy violations, and governance incidents</p>
        </div>
        <button id="btn-create-incident" className="btn btn-primary" onClick={() => setShowCreate(true)}>
          + Open Incident
        </button>
      </div>

      {/* Metrics */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '16px', marginBottom: '24px' }}>
        {[
          { label: 'Total Incidents', value: incidents.length, icon: '🚨' },
          { label: 'Open / Active', value: openCount, icon: '🔴' },
          { label: 'Critical', value: criticalCount, icon: '⚡' },
        ].map(m => (
          <div key={m.label} className="panel" style={{ padding: '20px', textAlign: 'center' }}>
            <div style={{ fontSize: '28px', marginBottom: '8px' }}>{m.icon}</div>
            <div style={{ fontSize: '32px', fontWeight: 700, color: 'var(--text-primary)' }}>{m.value}</div>
            <div style={{ fontSize: '13px', color: 'var(--text-muted)', marginTop: '4px' }}>{m.label}</div>
          </div>
        ))}
      </div>

      <div className="filter-bar">
        <select id="filter-incident-status" value={statusFilter} onChange={e => setStatusFilter(e.target.value)}>
          <option value="">All Statuses</option>
          {['open', 'triaged', 'investigating', 'remediation_pending', 'resolved', 'closed'].map(s => (
            <option key={s} value={s}>{s.replace(/_/g, ' ')}</option>
          ))}
        </select>
        <select id="filter-incident-severity" value={severityFilter} onChange={e => setSeverityFilter(e.target.value)}>
          <option value="">All Severities</option>
          {SEVERITY_ORDER.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>

      <div className="panel">
        <div className="panel-header">
          <h2 className="panel-title">🚨 Incidents ({incidents.length})</h2>
        </div>

        {loading && <div className="loading-center"><div className="spinner" /></div>}

        {!loading && incidents.length === 0 && (
          <div className="empty-state">
            <div className="empty-state-icon">✅</div>
            <h3>No incidents found</h3>
            <p>No governance incidents match the current filters.</p>
          </div>
        )}

        {!loading && incidents.length > 0 && (
          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>Severity</th>
                  <th>Status</th>
                  <th>Summary</th>
                  <th>Owner</th>
                  <th>Opened</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {incidents.map(i => (
                  <tr key={i.id}>
                    <td><SeverityBadge severity={i.severity} /></td>
                    <td><StatusBadge status={i.status} /></td>
                    <td className="truncate" style={{ maxWidth: '280px' }}>{i.summary}</td>
                    <td style={{ fontSize: '12px', color: 'var(--text-muted)' }}>{i.owner_id || '—'}</td>
                    <td style={{ fontSize: '12px' }}>{new Date(i.created_at).toLocaleDateString()}</td>
                    <td>
                      <button id={`btn-incident-detail-${i.id}`} className="btn btn-ghost btn-sm" onClick={() => setSelected(i)}>
                        Detail
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {showCreate && <CreateIncidentModal onClose={() => setShowCreate(false)} onCreated={load} />}
      {selected && <IncidentDetailModal incident={selected} onClose={() => setSelected(null)} onRefresh={load} />}
    </div>
  )
}
