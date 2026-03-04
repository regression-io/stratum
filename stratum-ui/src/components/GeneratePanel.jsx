import { useState, useEffect } from 'react'
import { generateToml, generatePython, generateYaml } from '../utils/generate.js'

const DEFAULT_API = 'http://localhost:7821'

const generators = {
  toml: generateToml,
  python: generatePython,
  yaml: generateYaml,
}

export default function GeneratePanel({ formats = ['toml', 'python', 'yaml'], apiBase = DEFAULT_API }) {
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

  const copyToClipboard = (text) => {
    navigator.clipboard?.writeText(text)
  }

  if (error) return <div className="stratum-error">Error loading draft: {error}</div>
  if (!draft) return <div className="stratum-loading">Loading draft...</div>

  return (
    <div className="stratum-generate-panel">
      {formats.map(fmt => {
        const gen = generators[fmt]
        if (!gen) return null
        const output = gen(draft)
        return (
          <div key={fmt} style={{ marginBottom: 16 }}>
            <div style={{ display: 'flex', alignItems: 'center', marginBottom: 4 }}>
              <strong>{fmt.toUpperCase()}</strong>
              <button onClick={() => copyToClipboard(output)} style={{ marginLeft: 8, fontSize: '0.8em' }}>
                Copy
              </button>
            </div>
            <pre style={{ background: '#f5f5f5', padding: 12, borderRadius: 4, overflow: 'auto', fontSize: '0.85em' }}>
              {output}
            </pre>
          </div>
        )
      })}
    </div>
  )
}
