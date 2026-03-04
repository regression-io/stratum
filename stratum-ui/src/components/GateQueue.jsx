import { useState, useEffect, useCallback } from 'react'

const DEFAULT_API = 'http://localhost:7821'

export default function GateQueue({ onApprove, onReject, apiBase = DEFAULT_API }) {
  const [gates, setGates] = useState(null)
  const [error, setError] = useState(null)

  const fetchGates = useCallback(() => {
    fetch(`${apiBase}/api/gates`)
      .then(res => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        return res.json()
      })
      .then(setGates)
      .catch(e => setError(e.message))
  }, [apiBase])

  useEffect(() => { fetchGates() }, [fetchGates])

  const handleApprove = async (runId, phase) => {
    await fetch(`${apiBase}/api/gates/${runId}/${phase}/approve`, { method: 'POST' })
    onApprove?.(runId, phase)
    fetchGates()
  }

  const handleReject = async (runId, phase) => {
    await fetch(`${apiBase}/api/gates/${runId}/${phase}/reject`, { method: 'POST' })
    onReject?.(runId, phase)
    fetchGates()
  }

  if (error) return <div className="stratum-error">Error loading gates: {error}</div>
  if (!gates) return <div className="stratum-loading">Loading gates...</div>
  if (gates.length === 0) return <div className="stratum-empty">No pending gates</div>

  return (
    <div className="stratum-gate-queue">
      {gates.map((gate, i) => (
        <div key={i} style={{ padding: '8px 0', borderBottom: '1px solid #eee' }}>
          <div>
            <strong>{gate.pipeline}</strong> &mdash; {gate.phase}
          </div>
          <div style={{ opacity: 0.6, fontSize: '0.85em' }}>{gate.run_id}</div>
          <div style={{ marginTop: 4 }}>
            <button onClick={() => handleApprove(gate.run_id, gate.phase)} style={{ marginRight: 8 }}>
              Approve
            </button>
            <button onClick={() => handleReject(gate.run_id, gate.phase)}>
              Reject
            </button>
          </div>
        </div>
      ))}
    </div>
  )
}
