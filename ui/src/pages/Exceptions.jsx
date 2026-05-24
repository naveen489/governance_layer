import { fetchApi } from '../api.js'
import { useState, useEffect } from 'react'

function formatExpiry(dateStr) {
  if (!dateStr) return '—'
  const diff = new Date(dateStr).getTime() - Date.now()
  if (diff < 0) return 'Expired'
  const h = Math.floor(diff / 3600000)
  if (h > 24) return `in ${Math.floor(h / 24)}d`
  if (h > 0)  return `in ${h}h`
  return `in ${Math.floor(diff / 60000)}m`
}

function StateBadge({ state }) {
  return (
    <span className={`badge badge-${state}`}>
      <span className="badge-dot" />
      {state?.replace(/_/g, ' ')}
    </span>
  )
}

const TABS = ['All', 'Pending', 'Approved', 'Rejected', 'Expired']

function DecideModal({ exc, onClose, onDone }) {
  const [decision, setDecision] = useState('approve')
  const [reason, setReason]     = useState('')
  const [expiry, setExpiry]     = useState('')
  const [loading, setLoading]   = useState(false)
  const [error, setError]       = useState(null)

  const submit = async () => {
    setLoading(true)
    setError(null)
    try {
      const body = { decision, reason }
      if (decision === 'approve' && expiry) body.expiry_at = new Date(expiry).toISOString()
      const res = await fetchApi(`/api/governance/exceptions/${exc.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', 'X-User-Id': 'exc_reviewer_01' },
        body: JSON.stringify(body),
      })
      if (!res.ok) throw new Error(await res.text())
      onDone()
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal">
        <h2 className="modal-title">Exception Decision</h2>
        <div style={{ marginBottom: '16px', padding: '12px', background: 'var(--bg-elevated)', borderRadius: 'var(--radius-md)' }}>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '4px' }}>Business Reason</div>
          <div style={{ fontSize: '13px', color: 'var(--text-secondary)', fontStyle: 'italic' }}>"{exc.business_reason}"</div>
        </div>
        <div className="detail-grid" style={{ marginBottom: '16px' }}>
          <div className="detail-item">
            <label>Target Type</label>
            <div className="value">{exc.target_type}</div>
          </div>
          <div className="detail-item">
            <label>Requested By</label>
            <div className="value mono">{exc.requested_by}</div>
          </div>
        </div>
        <div className="form-group">
          <label htmlFor="exc-decision">Decision</label>
          <select id="exc-decision" value={decision} onChange={e => setDecision(e.target.value)}>
            <option value="approve">Approve</option>
            <option value="reject">Reject</option>
          </select>
        </div>
        {decision === 'approve' && (
          <div className="form-group">
            <label htmlFor="exc-expiry">Expiry Date (optional)</label>
            <input id="exc-expiry" type="date" value={expiry} onChange={e => setExpiry(e.target.value)} />
          </div>
        )}
        <div className="form-group">
          <label htmlFor="exc-reason">Reviewer Notes</label>
          <textarea id="exc-reason" value={reason} onChange={e => setReason(e.target.value)} placeholder="Add reviewer notes..." />
        </div>
        {error && <div className="alert alert-error">{error}</div>}
        <div className="modal-actions">
          <button className="btn btn-ghost" onClick={onClose} disabled={loading}>Cancel</button>
          <button
            id="btn-submit-exc-decision"
            className={`btn ${decision === 'approve' ? 'btn-success' : 'btn-danger'}`}
            onClick={submit}
            disabled={loading}
          >
            {loading ? 'Submitting…' : decision === 'approve' ? 'Approve Exception' : 'Reject Exception'}
          </button>
        </div>
      </div>
    </div>
  )
}

export default function Exceptions() {
  const [exceptions, setExceptions] = useState([])
  const [loading, setLoading]       = useState(true)
  const [activeTab, setActiveTab]   = useState('All')
  const [selected, setSelected]     = useState(null)
  const [success, setSuccess]       = useState(null)

  const load = (tab = activeTab) => {
    setLoading(true)
    const statusMap = { Pending: 'pending', Approved: 'approved', Rejected: 'rejected', Expired: 'expired' }
    const statusParam = statusMap[tab] ? `&status=${statusMap[tab]}` : ''
    fetchApi(`/api/governance/exceptions?limit=100${statusParam}`)
      .then(r => r.json())
      .then(d => setExceptions(d?.exceptions || []))
      .catch(console.error)
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [activeTab])

  const handleDone = () => {
    setSelected(null)
    setSuccess('Exception decision submitted and audit event recorded.')
    load()
    setTimeout(() => setSuccess(null), 4000)
  }

  return (
    <div>
      <div className="page-header">
        <h1>Exception Dashboard</h1>
        <p>Manage exception requests – pending, approved, rejected, and expiring</p>
      </div>

      {success && <div className="alert alert-success">✓ {success}</div>}

      <div className="tabs">
        {TABS.map(tab => (
          <button
            key={tab}
            id={`tab-exceptions-${tab.toLowerCase()}`}
            className={`tab ${activeTab === tab ? 'active' : ''}`}
            onClick={() => { setActiveTab(tab); load(tab) }}
          >
            {tab}
          </button>
        ))}
      </div>

      <div className="panel">
        <div className="panel-header">
          <h2 className="panel-title">⚡ Exception Requests ({exceptions.length})</h2>
        </div>

        {loading && <div className="loading-center"><div className="spinner" /></div>}
        {!loading && exceptions.length === 0 && (
          <div className="empty-state">
            <div className="empty-state-icon">⚡</div>
            <h3>No exceptions</h3>
            <p>No exception requests match this filter.</p>
          </div>
        )}
        {!loading && exceptions.length > 0 && (
          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>Target Type</th>
                  <th>Target ID</th>
                  <th>Status</th>
                  <th>Business Reason</th>
                  <th>Requested By</th>
                  <th>Expires</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {exceptions.map(exc => (
                  <tr key={exc.id}>
                    <td style={{ textTransform: 'capitalize' }}>{exc.target_type}</td>
                    <td className="mono truncate">{exc.target_id.slice(0, 8)}…</td>
                    <td><StateBadge state={exc.status} /></td>
                    <td style={{ fontSize: '12px', maxWidth: '200px' }}>
                      <span className="truncate" style={{ display: 'block' }}>{exc.business_reason}</span>
                    </td>
                    <td className="mono" style={{ fontSize: '11px' }}>{exc.requested_by}</td>
                    <td style={{ fontSize: '12px' }}>
                      {formatExpiry(exc.expiry_at)}
                    </td>
                    <td>
                      {exc.status === 'pending' ? (
                        <button
                          id={`btn-decide-exc-${exc.id}`}
                          className="btn btn-primary btn-sm"
                          onClick={() => setSelected(exc)}
                        >
                          Decide
                        </button>
                      ) : (
                        <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                          {exc.approved_by || '—'}
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {selected && <DecideModal exc={selected} onClose={() => setSelected(null)} onDone={handleDone} />}
    </div>
  )
}
