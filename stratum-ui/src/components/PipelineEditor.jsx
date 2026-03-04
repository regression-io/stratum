import { useState, useEffect, useRef } from 'react'

const DEFAULT_API = 'http://localhost:7821'

const blankPhase = () => ({ name: '', capability: '', policy: '' })

export default function PipelineEditor({ onChange, onSave, apiBase = DEFAULT_API }) {
  const [draft, setDraft] = useState(null)
  const [error, setError] = useState(null)
  const [templates, setTemplates] = useState([])
  const lastEtagRef = useRef(null)

  // Fetch draft once, then poll every 2s for agent-pushed updates
  const fetchDraft = async (force = false) => {
    try {
      const res = await fetch(`${apiBase}/api/pipeline-draft`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const etag = res.headers.get('etag') || null
      if (!force && etag && etag === lastEtagRef.current) return  // unchanged
      lastEtagRef.current = etag
      const data = await res.json()
      setDraft(data)
      setError(null)
    } catch (e) {
      setError(e.message)
    }
  }

  useEffect(() => {
    fetchDraft(true)
    const id = setInterval(() => fetchDraft(false), 2000)
    return () => clearInterval(id)
  }, [apiBase])

  // Fetch template list once
  useEffect(() => {
    fetch(`${apiBase}/api/templates`)
      .then(res => res.ok ? res.json() : [])
      .then(setTemplates)
      .catch(() => {})
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

  const loadTemplate = async (name) => {
    if (!name) return
    try {
      const res = await fetch(`${apiBase}/api/templates/${name}`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const tmpl = await res.json()
      update(tmpl)
    } catch (e) {
      setError(`Failed to load template: ${e.message}`)
    }
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
      <div style={{ display: 'flex', gap: 8, marginBottom: 12, alignItems: 'center' }}>
        <label style={{ flex: 1 }}>
          Pipeline name:{' '}
          <input
            value={draft.name || ''}
            onChange={e => update({ ...draft, name: e.target.value })}
          />
        </label>
        {templates.length > 0 && (
          <select
            defaultValue=""
            onChange={e => { loadTemplate(e.target.value); e.target.value = '' }}
            style={{ fontSize: '0.85em' }}
          >
            <option value="" disabled>Load template…</option>
            {templates.map(t => (
              <option key={t.name} value={t.name} title={t.description}>{t.name}</option>
            ))}
          </select>
        )}
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
