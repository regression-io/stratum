import React, { useState } from 'react'
import { createRoot } from 'react-dom/client'
import { RunList, RunDetail, GateQueue, PipelineEditor, GeneratePanel } from '../index.jsx'

const TABS = ['Runs', 'Gates', 'Editor', 'Generate']
const API_BASE = window.__STRATUM_API_BASE__ || 'http://localhost:7821'

function App() {
  const [tab, setTab] = useState('Runs')
  const [selectedRun, setSelectedRun] = useState(null)

  return (
    <div style={{ fontFamily: 'system-ui, sans-serif', maxWidth: 800, margin: '0 auto', padding: 20 }}>
      <h1 style={{ fontSize: '1.4em', marginBottom: 16 }}>Stratum UI</h1>
      <nav style={{ display: 'flex', gap: 4, marginBottom: 20 }}>
        {TABS.map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            style={{
              padding: '6px 16px',
              border: '1px solid #ccc',
              borderBottom: tab === t ? '2px solid #333' : '1px solid #ccc',
              background: tab === t ? '#f8f8f8' : '#fff',
              cursor: 'pointer',
            }}
          >
            {t}
          </button>
        ))}
      </nav>

      {tab === 'Runs' && (
        <div style={{ display: 'flex', gap: 20 }}>
          <div style={{ flex: 1 }}>
            <RunList onSelect={setSelectedRun} apiBase={API_BASE} />
          </div>
          <div style={{ flex: 2 }}>
            <RunDetail runId={selectedRun} apiBase={API_BASE} />
          </div>
        </div>
      )}
      {tab === 'Gates' && <GateQueue apiBase={API_BASE} />}
      {tab === 'Editor' && <PipelineEditor apiBase={API_BASE} />}
      {tab === 'Generate' && <GeneratePanel apiBase={API_BASE} />}
    </div>
  )
}

createRoot(document.getElementById('root')).render(<App />)
