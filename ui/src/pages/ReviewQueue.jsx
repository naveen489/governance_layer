import { useState, useEffect, useCallback } from 'react'

function StateBadge({ state }) {
  return (
    <span className={`badge badge-${state}`}>
      <span className="badge-dot" />
      {state?.replace(/_/g, ' ')}
    </span>
  )
}

function timeAgo(dateStr) {
  const diff = Date.now() - new Date(dateStr).getTime()
  const h = Math.floor(diff / 3600000)
  const m = Math.floor(diff / 60000)
  if (h > 24) return `${Math.floor(h / 24)}d ago`
  if (h > 0)  return `${h}h ago`
  return `${m}m ago`
}

function DecisionModal({ item, onClose, onDone }) {
  const [decision, setDecision]   = useState('approve')
  const [reason, setReason]       = useState('')
  const [loading, setLoading]     = useState(false)
  const [error, setError]         = useState(null)

  const submit = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`/api/governance/reviews/${item.item_id}/decision`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-User-Id': 'reviewer_01' },
        body: JSON.stringify({ decision, reason }),
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
        <h2 className="modal-title">Submit Review Decision</h2>

        <div className="detail-grid" style={{ marginBottom: '20px' }}>
          <div className="detail-item">
            <label>Item Type</label>
            <div className="value">{item.item_type}</div>
          </div>
          <div className="detail-item">
            <label>Current State</label>
            <div className="value"><StateBadge state={item.governance_state} /></div>
          </div>
          <div className="detail-item" style={{ gridColumn: '1/-1' }}>
            <label>Item ID</label>
            <div className="value mono truncate" style={{ maxWidth: '100%' }}>{item.item_id}</div>
          </div>
        </div>

        {item.policy_reasons?.length > 0 && (
          <div style={{ marginBottom: '16px' }}>
            <label>Policy Reasons</label>
            <div style={{ marginTop: '6px', display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
              {item.policy_reasons.map((r, i) => <span key={i} className="reason-pill">{r}</span>)}
            </div>
          </div>
        )}

        <div className="form-group">
          <label htmlFor="decision-select">Decision</label>
          <select id="decision-select" value={decision} onChange={e => setDecision(e.target.value)}>
            <option value="approve">Approve</option>
            <option value="reject">Reject</option>
            <option value="escalate">Escalate</option>
            <option value="request_changes">Request Changes</option>
          </select>
        </div>

        <div className="form-group">
          <label htmlFor="decision-reason">Reason (optional)</label>
          <textarea
            id="decision-reason"
            value={reason}
            onChange={e => setReason(e.target.value)}
            placeholder="Enter rationale for this decision..."
          />
        </div>

        {error && <div className="alert alert-error">{error}</div>}

        <div className="modal-actions">
          <button className="btn btn-ghost" onClick={onClose} disabled={loading}>Cancel</button>
          <button
            id="btn-submit-decision"
            className={`btn ${decision === 'approve' ? 'btn-success' : decision === 'reject' ? 'btn-danger' : 'btn-primary'}`}
            onClick={submit}
            disabled={loading}
          >
            {loading ? 'Submitting…' : `Submit ${decision}`}
          </button>
        </div>
      </div>
    </div>
  )
}

export default function ReviewQueue() {
  const [items, setItems]       = useState([])
  const [loading, setLoading]   = useState(true)
  const [selected, setSelected] = useState(null)
  const [success, setSuccess]   = useState(null)

  const load = useCallback(() => {
    setLoading(true)
    fetch('/api/governance/reviews')
      .then(r => r.json())
      .then(d => setItems(Array.isArray(d) ? d : []))
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { load() }, [load])

  const handleDone = () => {
    setSelected(null)
    setSuccess('Decision submitted successfully. Audit event recorded.')
    load()
    setTimeout(() => setSuccess(null), 4000)
  }

  return (
    <div>
      <div className="page-header">
        <h1>Review Queue</h1>
        <p>Items requiring human review before proceeding through governance workflow</p>
      </div>

      {success && <div className="alert alert-success">✓ {success}</div>}

      <div className="panel">
        <div className="panel-header">
          <h2 className="panel-title">⏳ Pending Reviews
            <span style={{ marginLeft: '8px', fontSize: '12px', fontWeight: '400', color: 'var(--text-secondary)' }}>
              ({items.length} items)
            </span>
          </h2>
          <button id="btn-refresh-queue" className="btn btn-ghost btn-sm" onClick={load}>↻ Refresh</button>
        </div>

        {loading && <div className="loading-center"><div className="spinner" /></div>}

        {!loading && items.length === 0 && (
          <div className="empty-state">
            <div className="empty-state-icon">✅</div>
            <h3>Queue is empty</h3>
            <p>All items have been reviewed or no reviews are pending.</p>
          </div>
        )}

        {!loading && items.length > 0 && (
          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>Type</th>
                  <th>Item ID</th>
                  <th>State</th>
                  <th>Policy Reasons</th>
                  <th>Age</th>
                  <th>Requester</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {items.map(item => (
                  <tr key={item.item_id}>
                    <td>
                      <span className="badge badge-draft" style={{ textTransform: 'capitalize' }}>
                        {item.item_type}
                      </span>
                    </td>
                    <td className="td-primary mono truncate">{item.item_id}</td>
                    <td><StateBadge state={item.governance_state} /></td>
                    <td>
                      {(item.policy_reasons || []).slice(0, 2).map((r, i) => (
                        <span key={i} className="reason-pill">{r}</span>
                      ))}
                      {(item.policy_reasons || []).length > 2 && (
                        <span className="reason-pill">+{item.policy_reasons.length - 2} more</span>
                      )}
                    </td>
                    <td>{timeAgo(item.created_at)}</td>
                    <td className="mono" style={{ fontSize: '11px' }}>{item.created_by || '—'}</td>
                    <td>
                      <div className="btn-group">
                        <button
                          id={`btn-review-${item.item_id}`}
                          className="btn btn-primary btn-sm"
                          onClick={() => setSelected(item)}
                        >
                          Review
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {selected && (
        <DecisionModal
          item={selected}
          onClose={() => setSelected(null)}
          onDone={handleDone}
        />
      )}
    </div>
  )
}
