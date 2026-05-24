import { fetchApi } from '../api.js'
import { useState, useEffect } from 'react'

const DEFAULT_POLICY = JSON.stringify({
  policy_id: "new_policy_v1",
  rules: [
    { rule_id: "example_rule", when: { risk_class: "high" }, then: { action: "block", reason: "High risk" } }
  ]
}, null, 2)

function PolicyModal({ onClose, onDone }) {
  const [scope, setScope]       = useState('request')
  const [version, setVersion]   = useState(1)
  const [policyJson, setPolicyJson] = useState(DEFAULT_POLICY)
  const [isActive, setIsActive] = useState(true)
  const [loading, setLoading]   = useState(false)
  const [error, setError]       = useState(null)

  const submit = async () => {
    setLoading(true)
    setError(null)
    let parsed
    try {
      parsed = JSON.parse(policyJson)
    } catch {
      setError('Invalid JSON in policy rules.')
      setLoading(false)
      return
    }
    try {
      const res = await fetchApi('/api/governance/policies', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ workspace_id: 'default', policy_scope: scope, version, policy_json: parsed, is_active: isActive }),
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
      <div className="modal" style={{ maxWidth: '600px' }}>
        <h2 className="modal-title">New Policy Version</h2>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
          <div className="form-group">
            <label htmlFor="policy-scope">Scope</label>
            <select id="policy-scope" value={scope} onChange={e => setScope(e.target.value)}>
              <option value="request">Request</option>
              <option value="asset">Asset</option>
              <option value="publish">Publish</option>
              <option value="retention">Retention</option>
            </select>
          </div>
          <div className="form-group">
            <label htmlFor="policy-version">Version</label>
            <input id="policy-version" type="number" min="1" value={version} onChange={e => setVersion(+e.target.value)} />
          </div>
        </div>

        <div className="form-group">
          <label htmlFor="policy-json">Policy Rules (JSON)</label>
          <textarea
            id="policy-json"
            value={policyJson}
            onChange={e => setPolicyJson(e.target.value)}
            rows={10}
            style={{ fontFamily: 'monospace', fontSize: '12px' }}
          />
        </div>

        <div className="form-group" style={{ flexDirection: 'row', alignItems: 'center', gap: '10px' }}>
          <input id="policy-active" type="checkbox" checked={isActive} onChange={e => setIsActive(e.target.checked)} style={{ width: 'auto' }} />
          <label htmlFor="policy-active" style={{ marginBottom: 0, textTransform: 'none', letterSpacing: 0, fontSize: '13px', cursor: 'pointer' }}>
            Set as Active
          </label>
        </div>

        {error && <div className="alert alert-error">{error}</div>}

        <div className="modal-actions">
          <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button id="btn-submit-policy" className="btn btn-primary" onClick={submit} disabled={loading}>
            {loading ? 'Publishing…' : 'Publish Policy'}
          </button>
        </div>
      </div>
    </div>
  )
}

export default function Policies() {
  const [policies, setPolicies]   = useState([])
  const [loading, setLoading]     = useState(true)
  const [showModal, setShowModal] = useState(false)
  const [success, setSuccess]     = useState(null)
  const [scopeFilter, setScopeFilter] = useState('')

  const load = () => {
    setLoading(true)
    const url = scopeFilter ? `/api/governance/policies?policy_scope=${scopeFilter}` : '/api/governance/policies'
    fetchApi(url)
      .then(r => r.json())
      .then(d => setPolicies(d?.policies || []))
      .catch(console.error)
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [scopeFilter])

  const toggleActive = async (policy) => {
    await fetchApi(`/api/governance/policies/${policy.id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ is_active: !policy.is_active }),
    })
    load()
  }

  const handleDone = () => {
    setShowModal(false)
    setSuccess('Policy published successfully.')
    load()
    setTimeout(() => setSuccess(null), 4000)
  }

  return (
    <div>
      <div className="page-header">
        <h1>Policy Admin</h1>
        <p>Manage governance policy versions – add, edit, disable, and publish</p>
      </div>

      {success && <div className="alert alert-success">✓ {success}</div>}

      <div className="panel">
        <div className="panel-header">
          <h2 className="panel-title">📋 Policy Registry</h2>
          <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
            <select id="filter-policy-scope" value={scopeFilter} onChange={e => setScopeFilter(e.target.value)} style={{ width: 'auto' }}>
              <option value="">All Scopes</option>
              <option value="request">Request</option>
              <option value="asset">Asset</option>
              <option value="publish">Publish</option>
              <option value="retention">Retention</option>
            </select>
            <button id="btn-new-policy" className="btn btn-primary btn-sm" onClick={() => setShowModal(true)}>
              + New Version
            </button>
          </div>
        </div>

        {loading && <div className="loading-center"><div className="spinner" /></div>}
        {!loading && policies.length === 0 && (
          <div className="empty-state">
            <div className="empty-state-icon">📋</div>
            <h3>No policies found</h3>
            <p>Seed the database or create a new policy version.</p>
          </div>
        )}
        {!loading && policies.length > 0 && (
          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>Scope</th>
                  <th>Version</th>
                  <th>Rules</th>
                  <th>Status</th>
                  <th>Effective From</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {policies.map(pol => (
                  <tr key={pol.id}>
                    <td className="td-primary" style={{ textTransform: 'capitalize' }}>{pol.policy_scope}</td>
                    <td>v{pol.version}</td>
                    <td style={{ fontSize: '12px' }}>{pol.policy_json?.rules?.length ?? 0} rules</td>
                    <td>
                      <span className={`badge ${pol.is_active ? 'badge-governance_passed' : 'badge-expired'}`}>
                        <span className="badge-dot" />
                        {pol.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </td>
                    <td style={{ fontSize: '12px' }}>
                      {new Date(pol.effective_from).toLocaleDateString()}
                    </td>
                    <td>
                      <button
                        id={`btn-toggle-policy-${pol.id}`}
                        className={`btn btn-sm ${pol.is_active ? 'btn-danger' : 'btn-success'}`}
                        onClick={() => toggleActive(pol)}
                      >
                        {pol.is_active ? 'Disable' : 'Enable'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {showModal && <PolicyModal onClose={() => setShowModal(false)} onDone={handleDone} />}
    </div>
  )
}
