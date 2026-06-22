import { fetchApi } from '../api.js'
import { useState } from 'react'

const GOLDEN_SCENARIOS_HINT = [
  { scenario_id: 'safe_request', scope: 'request', payload: { risk_class: 'low', provider_status: 'approved', provider_key: 'openai' } },
  { scenario_id: 'high_risk_block', scope: 'request', payload: { risk_class: 'high', provider_status: 'approved', provider_key: 'openai' } },
  { scenario_id: 'unknown_provider_review', scope: 'request', payload: { risk_class: 'low', provider_status: 'unknown', provider_key: 'unknown_provider' } },
  { scenario_id: 'medium_risk_warn', scope: 'request', payload: { risk_class: 'medium', provider_status: 'approved', provider_key: 'openai' } },
]

function ActionBadge({ action }) {
  const map = {
    pass: 'badge-governance_passed',
    warn: 'badge-changes_requested',
    review_required: 'badge-review_required',
    block: 'badge-blocked',
  }
  return (
    <span className={`badge ${map[action] || 'badge-draft'}`}>
      <span className="badge-dot" />
      {action}
    </span>
  )
}

function ResultRow({ result }) {
  const passed = result.result === 'pass'
  return (
    <tr>
      <td>
        <span style={{ fontSize: '16px', marginRight: '6px' }}>{passed ? '✅' : '❌'}</span>
        {result.scenario_id}
      </td>
      <td style={{ fontSize: '12px', color: 'var(--text-muted)' }}>{result.scope}</td>
      <td>
        {result.expected_action
          ? <ActionBadge action={result.expected_action} />
          : <span style={{ color: 'var(--text-muted)' }}>—</span>
        }
      </td>
      <td><ActionBadge action={result.actual_action} /></td>
      <td style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
        {result.reason_codes.length > 0 ? result.reason_codes.join(', ') : result.reasons.filter(Boolean).join(', ') || '—'}
      </td>
      <td style={{ fontSize: '12px', color: 'var(--text-muted)' }}>{result.next_action || '—'}</td>
    </tr>
  )
}

export default function PolicySimulation() {
  const [mode, setMode] = useState('golden')  // golden | custom_payload | custom_policy
  const [loading, setLoading] = useState(false)
  const [results, setResults] = useState(null)
  const [error, setError] = useState(null)

  // Custom payload mode
  const [payloadScope, setPayloadScope] = useState('request')
  const [payloadJson, setPayloadJson] = useState(JSON.stringify(GOLDEN_SCENARIOS_HINT[0].payload, null, 2))
  const [policyPreviewJson, setPolicyPreviewJson] = useState(JSON.stringify({
    rules: [
      { rule_id: 'high_risk_block', when: { risk_class: 'high' }, then: { action: 'block', reason: 'High risk content', reason_code: 'HIGH_RISK' } },
      { rule_id: 'unknown_provider_review', when: { provider_status: 'unknown' }, then: { action: 'review_required', reason: 'Unknown provider', reason_code: 'UNKNOWN_PROVIDER' } },
    ]
  }, null, 2))

  const runGolden = async () => {
    setLoading(true); setError(null); setResults(null)
    try {
      const res = await fetchApi('/api/governance/simulate/scenarios/run', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({}) })
      if (!res.ok) throw new Error(await res.text())
      setResults(await res.json())
    } catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }

  const runCustomPayload = async () => {
    setLoading(true); setError(null); setResults(null)
    try {
      const payload = JSON.parse(payloadJson)
      const body = { scenarios: [{ scenario_id: 'custom', scope: payloadScope, payload }] }
      const res = await fetchApi('/api/governance/simulate/scenarios/run', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
      if (!res.ok) throw new Error(await res.text())
      setResults(await res.json())
    } catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }

  const runPolicyPreview = async () => {
    setLoading(true); setError(null); setResults(null)
    try {
      const policy_json = JSON.parse(policyPreviewJson)
      const test_payloads = GOLDEN_SCENARIOS_HINT.map(s => s.payload)
      const body = { policy_json, scope: payloadScope, test_payloads }
      const res = await fetchApi('/api/governance/simulate/policy/preview', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
      if (!res.ok) throw new Error(await res.text())
      const data = await res.json()
      // Normalize for display
      setResults({
        total: data.test_payloads_count,
        passed: data.results.filter(r => r.action === 'pass').length,
        failed: 0,
        coverage_pct: 100,
        run_at: new Date().toISOString(),
        results: data.results.map((r, i) => ({
          scenario_id: `payload_${i}`,
          scope: data.scope,
          expected_action: null,
          actual_action: r.action,
          severity: r.severity,
          reasons: r.reasons,
          reason_codes: r.reason_codes,
          result: 'pass',
          next_action: '—',
        })),
      })
    } catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }

  const passedCount = results?.results?.filter(r => r.result === 'pass').length || 0
  const failedCount = results?.results?.filter(r => r.result === 'fail').length || 0

  return (
    <div>
      <div className="page-header">
        <h1>Policy Simulation</h1>
        <p>Preview how your active policies behave against golden scenarios or custom payloads before pushing changes to production.</p>
      </div>

      {/* Mode selector */}
      <div className="panel" style={{ marginBottom: '24px' }}>
        <div className="panel-header">
          <h2 className="panel-title">⚗️ Simulation Mode</h2>
        </div>
        <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
          {[
            { key: 'golden', label: '🏅 Golden Scenarios', desc: 'Run the built-in test suite against the active policy' },
            { key: 'custom_payload', label: '📝 Custom Payload', desc: 'Test how the active policy evaluates your own payload' },
            { key: 'custom_policy', label: '🔧 Policy Preview', desc: 'Dry-run a custom policy JSON before activating it' },
          ].map(m => (
            <div
              key={m.key}
              onClick={() => { setMode(m.key); setResults(null); setError(null) }}
              style={{
                flex: 1, minWidth: '200px', padding: '16px', borderRadius: 'var(--radius-lg)',
                border: `2px solid ${mode === m.key ? 'var(--accent-primary)' : 'var(--border-default)'}`,
                background: mode === m.key ? 'var(--accent-bg)' : 'var(--bg-elevated)',
                cursor: 'pointer', transition: 'all 0.2s',
              }}
            >
              <div style={{ fontWeight: 600, marginBottom: '4px' }}>{m.label}</div>
              <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>{m.desc}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Controls */}
      <div className="panel" style={{ marginBottom: '24px' }}>
        <div className="panel-header">
          <h2 className="panel-title">⚙️ Configuration</h2>
        </div>

        {mode === 'golden' && (
          <div>
            <p style={{ color: 'var(--text-secondary)', marginBottom: '16px' }}>
              Runs {GOLDEN_SCENARIOS_HINT.length} built-in golden scenarios (safe_request, high_risk_block, unknown_provider_review, medium_risk_warn, missing_rights_block, standard_asset_pass) against your active policy.
            </p>
            <button id="btn-run-golden" className="btn btn-primary" onClick={runGolden} disabled={loading}>
              {loading ? '⏳ Running…' : '▶ Run Golden Scenarios'}
            </button>
          </div>
        )}

        {mode === 'custom_payload' && (
          <div>
            <div className="form-group">
              <label>Policy Scope</label>
              <select value={payloadScope} onChange={e => setPayloadScope(e.target.value)}>
                {['request', 'asset', 'publish', 'retention', 'exception'].map(s => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
            <div className="form-group">
              <label>Payload JSON</label>
              <textarea value={payloadJson} onChange={e => setPayloadJson(e.target.value)}
                rows={8} style={{ width: '100%', fontFamily: 'monospace', fontSize: '12px', resize: 'vertical' }} />
            </div>
            <button id="btn-run-custom" className="btn btn-primary" onClick={runCustomPayload} disabled={loading}>
              {loading ? '⏳ Evaluating…' : '▶ Evaluate Payload'}
            </button>
          </div>
        )}

        {mode === 'custom_policy' && (
          <div>
            <div className="form-group">
              <label>Policy Scope</label>
              <select value={payloadScope} onChange={e => setPayloadScope(e.target.value)}>
                {['request', 'asset', 'publish', 'retention', 'exception'].map(s => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
            <div className="form-group">
              <label>Policy JSON (proposed rules)</label>
              <textarea value={policyPreviewJson} onChange={e => setPolicyPreviewJson(e.target.value)}
                rows={12} style={{ width: '100%', fontFamily: 'monospace', fontSize: '12px', resize: 'vertical' }} />
            </div>
            <button id="btn-run-preview" className="btn btn-primary" onClick={runPolicyPreview} disabled={loading}>
              {loading ? '⏳ Previewing…' : '▶ Preview Policy'}
            </button>
          </div>
        )}
      </div>

      {error && <div className="alert alert-error" style={{ marginBottom: '24px' }}>{error}</div>}

      {/* Results */}
      {results && (
        <div className="panel">
          <div className="panel-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h2 className="panel-title">📊 Results</h2>
            <div style={{ display: 'flex', gap: '16px', fontSize: '13px' }}>
              <span>Run: {new Date(results.run_at).toLocaleTimeString()}</span>
              <span style={{ color: 'var(--green)' }}>✅ {passedCount} passed</span>
              {failedCount > 0 && <span style={{ color: 'var(--red)' }}>❌ {failedCount} failed</span>}
              <span>Coverage: {results.coverage_pct}%</span>
            </div>
          </div>

          {/* Coverage bar */}
          <div style={{ marginBottom: '20px' }}>
            <div style={{ height: '8px', background: 'var(--bg-elevated)', borderRadius: '4px', overflow: 'hidden' }}>
              <div style={{ height: '100%', width: `${results.coverage_pct}%`, background: failedCount > 0 ? 'var(--orange)' : 'var(--green)', borderRadius: '4px', transition: 'width 0.6s ease' }} />
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '6px', fontSize: '12px', color: 'var(--text-muted)' }}>
              <span>0%</span><span>{results.coverage_pct}% coverage</span><span>100%</span>
            </div>
          </div>

          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>Scenario</th>
                  <th>Scope</th>
                  <th>Expected</th>
                  <th>Actual</th>
                  <th>Reason Codes</th>
                  <th>Next Action</th>
                </tr>
              </thead>
              <tbody>
                {results.results.map((r, i) => <ResultRow key={i} result={r} />)}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
