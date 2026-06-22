import { fetchApi } from '../api.js'
import { useState, useEffect } from 'react'

function RiskClassBadge({ riskClass }) {
  const map = {
    low: { bg: '#0a1a0a', color: '#44cc66', border: '#229944' },
    medium: { bg: '#1a1a00', color: '#f5c518', border: '#c9a000' },
    high: { bg: '#2d1a00', color: '#ff9944', border: '#ff7700' },
  }
  const c = map[riskClass] || map.medium
  return (
    <span style={{
      padding: '2px 10px', borderRadius: '999px', fontSize: '11px',
      fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em',
      background: c.bg, color: c.color, border: `1px solid ${c.border}`,
    }}>
      {riskClass}
    </span>
  )
}

function DriftAlert({ driftAlert, daysSince }) {
  if (!driftAlert) return (
    <span style={{ color: 'var(--green)', fontSize: '12px' }}>✓ Current</span>
  )
  return (
    <span style={{ color: 'var(--orange)', fontSize: '12px', fontWeight: 600 }}>
      ⚠ Stale {daysSince != null ? `(${daysSince}d ago)` : '(never reviewed)'}
    </span>
  )
}

function ProviderCard({ profile, onUpdate }) {
  const [expanded, setExpanded] = useState(false)
  const [editing, setEditing] = useState(false)
  const [form, setForm] = useState({ risk_class: profile.risk_class, source_notes: profile.source_notes || '' })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const saveProfile = async () => {
    setLoading(true); setError(null)
    try {
      const res = await fetchApi('/api/governance/provider-profiles', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          provider_key: profile.provider_key,
          risk_class: form.risk_class,
          source_notes: form.source_notes,
          moderation_behavior: profile.moderation_behavior,
          retention_behavior: profile.retention_behavior,
          webhook_behavior: profile.webhook_behavior,
          data_controls: profile.data_controls,
          evidence_capture_required: profile.evidence_capture_required,
        }),
      })
      if (!res.ok) throw new Error(await res.text())
      setEditing(false)
      onUpdate()
    } catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }

  return (
    <div className="panel" style={{ marginBottom: '16px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', cursor: 'pointer' }}
        onClick={() => setExpanded(e => !e)}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{ width: '40px', height: '40px', borderRadius: '10px', background: 'var(--accent-bg)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '18px' }}>
            🤖
          </div>
          <div>
            <div style={{ fontWeight: 600, fontSize: '16px' }}>{profile.provider_key}</div>
            <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '2px' }}>
              {profile.source === 'database' ? `v${profile.version} · DB Record` : 'In-memory registry'}
            </div>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <RiskClassBadge riskClass={profile.risk_class} />
          <DriftAlert driftAlert={profile.drift_alert} daysSince={profile.days_since_review} />
          <span style={{ color: 'var(--text-muted)', fontSize: '18px' }}>{expanded ? '▲' : '▼'}</span>
        </div>
      </div>

      {expanded && (
        <div style={{ marginTop: '20px', borderTop: '1px solid var(--border-default)', paddingTop: '20px' }}>
          <div className="detail-grid">
            <div className="detail-item">
              <label>Moderation Type</label>
              <div className="value">{profile.moderation_behavior?.type || '—'}</div>
            </div>
            <div className="detail-item">
              <label>Default Retention</label>
              <div className="value">{profile.retention_behavior?.default_hours != null ? `${profile.retention_behavior.default_hours}h` : '—'}</div>
            </div>
            <div className="detail-item">
              <label>Webhook Support</label>
              <div className="value">{profile.webhook_behavior?.supported ? '✓ Yes' : '✗ No'}</div>
            </div>
            <div className="detail-item">
              <label>Scoped Keys</label>
              <div className="value">{profile.data_controls?.scoped_key_support ? '✓ Yes' : '✗ No'}</div>
            </div>
            <div className="detail-item">
              <label>Evidence Capture Required</label>
              <div className="value">{profile.evidence_capture_required ? '⚠ Yes' : 'No'}</div>
            </div>
            <div className="detail-item">
              <label>Last Reviewed</label>
              <div className="value">{profile.last_reviewed_at ? new Date(profile.last_reviewed_at).toLocaleDateString() : 'Never'}</div>
            </div>
          </div>

          {profile.source_notes && (
            <div style={{ marginTop: '12px', padding: '10px', background: 'var(--bg-elevated)', borderRadius: 'var(--radius-md)', fontSize: '12px', color: 'var(--text-secondary)', fontStyle: 'italic' }}>
              {profile.source_notes}
            </div>
          )}

          {editing ? (
            <div style={{ marginTop: '16px' }}>
              <div className="form-group">
                <label>Risk Class</label>
                <select value={form.risk_class} onChange={e => setForm({ ...form, risk_class: e.target.value })}>
                  <option value="low">Low</option>
                  <option value="medium">Medium</option>
                  <option value="high">High</option>
                </select>
              </div>
              <div className="form-group">
                <label>Source Notes</label>
                <textarea value={form.source_notes} onChange={e => setForm({ ...form, source_notes: e.target.value })}
                  rows={2} style={{ width: '100%', resize: 'vertical' }} />
              </div>
              {error && <div className="alert alert-error">{error}</div>}
              <div style={{ display: 'flex', gap: '8px', marginTop: '8px' }}>
                <button className="btn btn-ghost btn-sm" onClick={() => setEditing(false)}>Cancel</button>
                <button className="btn btn-primary btn-sm" onClick={saveProfile} disabled={loading}>
                  {loading ? 'Saving…' : 'Save & Publish New Version'}
                </button>
              </div>
            </div>
          ) : (
            <div style={{ marginTop: '16px' }}>
              <button id={`btn-edit-profile-${profile.provider_key}`} className="btn btn-ghost btn-sm" onClick={() => setEditing(true)}>
                Edit Profile
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default function ProviderProfiles() {
  const [profiles, setProfiles] = useState([])
  const [loading, setLoading] = useState(true)

  const load = () => {
    setLoading(true)
    fetchApi('/api/governance/provider-profiles')
      .then(r => r.json())
      .then(d => setProfiles(Array.isArray(d) ? d : []))
      .catch(console.error)
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const driftCount = profiles.filter(p => p.drift_alert).length

  return (
    <div>
      <div className="page-header">
        <h1>Provider Policy Intelligence</h1>
        <p>Versioned policy profiles for each AI provider – moderation behavior, retention, webhook support, and drift alerts</p>
      </div>

      {driftCount > 0 && (
        <div className="alert alert-warning" style={{ marginBottom: '24px', display: 'flex', alignItems: 'center', gap: '12px' }}>
          <span style={{ fontSize: '20px' }}>⚠️</span>
          <span>
            <strong>{driftCount} provider profile{driftCount > 1 ? 's' : ''}</strong> have not been reviewed in over 30 days.
            Review and update them to prevent governance drift alerts.
          </span>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '16px', marginBottom: '24px' }}>
        {[
          { label: 'Total Providers', value: profiles.length, icon: '🤖' },
          { label: 'DB-Backed', value: profiles.filter(p => p.source === 'database').length, icon: '💾' },
          { label: 'Drift Alerts', value: driftCount, icon: '🔴' },
        ].map(m => (
          <div key={m.label} className="panel" style={{ padding: '20px', textAlign: 'center' }}>
            <div style={{ fontSize: '28px', marginBottom: '8px' }}>{m.icon}</div>
            <div style={{ fontSize: '32px', fontWeight: 700, color: 'var(--text-primary)' }}>{m.value}</div>
            <div style={{ fontSize: '13px', color: 'var(--text-muted)', marginTop: '4px' }}>{m.label}</div>
          </div>
        ))}
      </div>

      {loading && <div className="loading-center"><div className="spinner" /></div>}

      {!loading && profiles.map(p => (
        <ProviderCard key={p.provider_key} profile={p} onUpdate={load} />
      ))}
    </div>
  )
}
