import { useState, useEffect } from 'react'

const DEFAULT_API = 'http://localhost:7821'

export default function RunList({ apiBase = DEFAULT_API, onSelect }) {
  const [runs, setRuns] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetch(`${apiBase}/api/runs`)
      .then(res => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        return res.json()
      })
      .then(setRuns)
      .catch(e => setError(e.message))
  }, [apiBase])

  if (error) return <div className="stratum-error">Error loading runs: {error}</div>
  if (!runs) return <div className="stratum-loading">Loading runs...</div>
  if (runs.length === 0) return <div className="stratum-empty">No runs yet</div>

  return (
    <div className="stratum-run-list">
      {runs.map(run => (
        <div
          key={run.run_id}
          className="stratum-run-item"
          onClick={() => onSelect?.(run.run_id)}
          style={{ cursor: 'pointer', padding: '8px', borderBottom: '1px solid #eee' }}
        >
          <strong>{run.pipeline}</strong>
          <span style={{ marginLeft: 8, opacity: 0.6, fontSize: '0.85em' }}>{run.run_id}</span>
          <div style={{ fontSize: '0.85em', marginTop: 4 }}>
            Phases complete: {run.phases_complete ?? 0} | Gates pending: {run.gates_pending ?? 0}
          </div>
        </div>
      ))}
    </div>
  )
}
