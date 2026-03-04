import { useState, useEffect } from 'react'

const DEFAULT_API = 'http://localhost:7821'

export default function RunDetail({ runId, apiBase = DEFAULT_API }) {
  const [run, setRun] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!runId) return
    setRun(null)
    setError(null)
    fetch(`${apiBase}/api/runs/${runId}`)
      .then(res => {
        if (res.status === 404) throw new Error('not_found')
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        return res.json()
      })
      .then(setRun)
      .catch(e => setError(e.message))
  }, [runId, apiBase])

  if (!runId) return <div className="stratum-empty">Select a run</div>
  if (error === 'not_found') return <div className="stratum-empty">Run not found</div>
  if (error) return <div className="stratum-error">Error: {error}</div>
  if (!run) return <div className="stratum-loading">Loading run...</div>

  return (
    <div className="stratum-run-detail">
      <h2>{run.pipeline}</h2>
      <div style={{ opacity: 0.6, fontSize: '0.85em', marginBottom: 12 }}>{run.run_id}</div>
      {Object.entries(run.phases || {}).map(([name, phase]) => (
        <div key={name} style={{ padding: '8px 0', borderBottom: '1px solid #eee' }}>
          <div>
            <strong>{name}</strong>
            <span style={{ marginLeft: 8 }} data-status={phase.status}>
              {phase.status}
            </span>
          </div>
          {phase.stratumViolations?.length > 0 && (
            <div style={{ color: '#c00', fontSize: '0.85em', marginTop: 4 }}>
              {phase.stratumViolations.map((v, j) => (
                <div key={j}>Violation: {v}</div>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
