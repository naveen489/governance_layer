import { useState, useEffect } from 'react'

function StateBadge({ state }) {
  return (
    <span className={`badge badge-${state}`}>
      <span className="badge-dot" />
      {state?.replace(/_/g, ' ')}
    </span>
  )
}

function AssetDetailModal({ asset, onClose }) {
  const prov = asset.provenance_json || {}
  const manifest = asset.rights_manifest_json || {}

  const downloadManifest = () => {
    const blob = new Blob([JSON.stringify(manifest, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `manifest_${asset.id}.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="modal-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal" style={{ maxWidth: '680px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '24px' }}>
          <h2 className="modal-title" style={{ marginBottom: 0 }}>Asset Detail</h2>
          <StateBadge state={asset.governance_state} />
        </div>

        <div className="tabs" id="asset-detail-tabs">
          {/* Simple tab state via CSS class toggling – using a lightweight pattern */}
        </div>

        <div className="detail-grid" style={{ marginBottom: '20px' }}>
          <div className="detail-item">
            <label>Asset ID</label>
            <div className="value mono" style={{ fontSize: '11px' }}>{asset.id}</div>
          </div>
          <div className="detail-item">
            <label>Request ID</label>
            <div className="value mono" style={{ fontSize: '11px' }}>{asset.request_id}</div>
          </div>
          <div className="detail-item">
            <label>Provider</label>
            <div className="value">{asset.provider_key}</div>
          </div>
          <div className="detail-item">
            <label>Model</label>
            <div className="value">{asset.model_key}</div>
          </div>
          <div className="detail-item">
            <label>Retention Class</label>
            <div className="value">{asset.retention_class}</div>
          </div>
          <div className="detail-item">
            <label>Retention Expires</label>
            <div className="value">{asset.retention_expires_at ? new Date(asset.retention_expires_at).toLocaleDateString() : '—'}</div>
          </div>
          <div className="detail-item">
            <label>Legal Hold</label>
            <div className="value">{asset.legal_hold ? '🔒 Yes' : 'No'}</div>
          </div>
          <div className="detail-item">
            <label>Incident Hold</label>
            <div className="value">{asset.incident_hold ? '⚠️ Yes' : 'No'}</div>
          </div>
        </div>

        {prov.input_prompt && (
          <div style={{ marginBottom: '16px' }}>
            <label>Source Prompt</label>
            <div style={{ marginTop: '6px', padding: '10px', background: 'var(--bg-elevated)', borderRadius: 'var(--radius-md)', fontSize: '12px', color: 'var(--text-secondary)', fontStyle: 'italic' }}>
              "{prov.input_prompt}"
            </div>
          </div>
        )}

        <div style={{ marginBottom: '16px' }}>
          <label>Rights Manifest Summary</label>
          <div style={{ marginTop: '6px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
            <div className="detail-item">
              <label style={{ fontSize: '10px' }}>License Class</label>
              <div className="value">{manifest.license_class || '—'}</div>
            </div>
            <div className="detail-item">
              <label style={{ fontSize: '10px' }}>Attribution Required</label>
              <div className="value">{manifest.attribution_required ? 'Yes' : 'No'}</div>
            </div>
            <div className="detail-item" style={{ gridColumn: '1/-1' }}>
              <label style={{ fontSize: '10px' }}>Restrictions</label>
              <div style={{ marginTop: '4px', display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                {(manifest.restrictions || []).map((r, i) => <span key={i} className="reason-pill">{r}</span>)}
              </div>
            </div>
          </div>
        </div>

        <div className="modal-actions">
          <button className="btn btn-ghost" onClick={onClose}>Close</button>
          <button id={`btn-download-manifest-${asset.id}`} className="btn btn-primary btn-sm" onClick={downloadManifest}>
            ⬇ Download Manifest
          </button>
        </div>
      </div>
    </div>
  )
}

export default function Assets() {
  const [assets, setAssets]         = useState([])
  const [loading, setLoading]       = useState(true)
  const [stateFilter, setStateFilter] = useState('')
  const [selected, setSelected]     = useState(null)

  useEffect(() => {
    const url = stateFilter
      ? `/api/governance/assets?limit=100&governance_state=${stateFilter}`
      : '/api/governance/assets?limit=100'
    setLoading(true)
    fetch(url)
      .then(r => r.json())
      .then(d => setAssets(Array.isArray(d) ? d : []))
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [stateFilter])

  const states = ['', 'governance_passed', 'review_required', 'blocked', 'asset_registered', 'expired', 'deleted']

  return (
    <div>
      <div className="page-header">
        <h1>Asset Governance</h1>
        <p>Governance states, provenance records, and rights manifests for every generated asset</p>
      </div>

      <div className="filter-bar">
        <select id="filter-asset-state" value={stateFilter} onChange={e => setStateFilter(e.target.value)}>
          {states.map(s => (
            <option key={s} value={s}>{s || 'All States'}</option>
          ))}
        </select>
      </div>

      <div className="panel">
        <div className="panel-header">
          <h2 className="panel-title">🎬 Assets ({assets.length})</h2>
        </div>

        {loading && <div className="loading-center"><div className="spinner" /></div>}

        {!loading && assets.length === 0 && (
          <div className="empty-state">
            <div className="empty-state-icon">🎬</div>
            <h3>No assets found</h3>
            <p>Seed the database or evaluate an asset via the API.</p>
          </div>
        )}

        {!loading && assets.length > 0 && (
          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>Asset ID</th>
                  <th>Provider</th>
                  <th>Model</th>
                  <th>State</th>
                  <th>Retention</th>
                  <th>Expires</th>
                  <th>Holds</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {assets.map(a => (
                  <tr key={a.id}>
                    <td className="td-primary mono truncate" title={a.id}>{a.id.slice(0, 8)}…</td>
                    <td>{a.provider_key}</td>
                    <td className="truncate" style={{ maxWidth: '130px', fontSize: '12px' }}>{a.model_key}</td>
                    <td><StateBadge state={a.governance_state} /></td>
                    <td>
                      <span className="badge" style={{ background: 'var(--accent-bg)', color: 'var(--accent-light)', borderColor: 'var(--border-accent)', borderStyle: 'solid', borderWidth: '1px' }}>
                        {a.retention_class}
                      </span>
                    </td>
                    <td style={{ fontSize: '12px' }}>
                      {a.retention_expires_at ? new Date(a.retention_expires_at).toLocaleDateString() : '—'}
                    </td>
                    <td style={{ fontSize: '11px' }}>
                      {a.legal_hold && <span title="Legal Hold" style={{ color: 'var(--yellow)' }}>🔒</span>}
                      {a.incident_hold && <span title="Incident Hold" style={{ color: 'var(--orange)' }}>⚠️</span>}
                      {!a.legal_hold && !a.incident_hold && <span style={{ color: 'var(--text-muted)' }}>—</span>}
                    </td>
                    <td>
                      <button
                        id={`btn-asset-detail-${a.id}`}
                        className="btn btn-ghost btn-sm"
                        onClick={() => setSelected(a)}
                      >
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

      {selected && <AssetDetailModal asset={selected} onClose={() => setSelected(null)} />}
    </div>
  )
}
