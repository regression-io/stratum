import { useState, useEffect } from 'react'

const DEFAULT_API = 'http://localhost:7821'

const blankPhase = () => ({ name: '', capability: '', policy: '' })

export default function PipelineEditor({ onChange, onSave, apiBase = DEFAULT_API }) {
  const [draft, setDraft] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetch(`${apiBase}/api/pipeline-draft`)
      .then(res => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        return res.json()
      })
      .then(setDraft)
      .catch(e => setError(e.message))
  }, [apiBase])

  const update = (newDraft) => {
    setDraft(newDraft)
    onChange?.(newDraft)
  }

  const updatePhase = (index, field, value) => {
    const phases = [...draft.phases]
    phases[index] = { ...phases[index], [field]: value }
    update({ ...draft, phases })
  }

  const addPhase = () => {
    update({ ...draft, phases: [...(draft.phases || []), blankPhase()] })
  }

  const deletePhase = (index) => {
    const phases = draft.phases.filter((_, i) => i !== index)
    update({ ...draft, phases })
  }

  const save = async () => {
    await fetch(`${apiBase}/api/pipeline-draft`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(draft),
    })
    onSave?.()
  }

  if (error) return <div className="stratum-error">Error loading draft: {error}</div>
  if (!draft) return <div className="stratum-loading">Loading draft...</div>

  return (
    <div className="stratum-pipeline-editor">
      <div style={{ marginBottom: 12 }}>
        <label>
          Pipeline name:{' '}
          <input
            value={draft.name || ''}
            onChange={e => update({ ...draft, name: e.target.value })}
          />
        </label>
      </div>
      {(draft.phases || []).map((phase, i) => (
        <div key={i} style={{ padding: '8px 0', borderBottom: '1px solid #eee' }}>
          <input
            placeholder="Phase name"
            value={phase.name}
            onChange={e => updatePhase(i, 'name', e.target.value)}
            style={{ marginRight: 8 }}
          />
          <input
            placeholder="Capability"
            value={phase.capability}
            onChange={e => updatePhase(i, 'capability', e.target.value)}
            style={{ marginRight: 8 }}
          />
          <input
            placeholder="Policy"
            value={phase.policy}
            onChange={e => updatePhase(i, 'policy', e.target.value)}
            style={{ marginRight: 8 }}
          />
          <button onClick={() => deletePhase(i)}>Delete</button>
        </div>
      ))}
      <div style={{ marginTop: 8 }}>
        <button onClick={addPhase} style={{ marginRight: 8 }}>Add phase</button>
        <button onClick={save}>Save</button>
      </div>
    </div>
  )
}
