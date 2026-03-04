import { RunList, GateQueue } from '@stratum/ui'
import { useState } from 'react'

export default function Home() {
  const [selectedRunId, setSelectedRunId] = useState(null)

  return (
    <main style={{ fontFamily: 'sans-serif', padding: '2rem', maxWidth: '960px', margin: '0 auto' }}>
      <h1>Stratum Dashboard</h1>
      <p style={{ color: '#666' }}>
        Requires <code>stratum-mcp serve</code> running on port 7821.
      </p>

      <section>
        <h2>Pending Gates</h2>
        <GateQueue
          onApprove={(runId, phase) => console.log('approved', runId, phase)}
          onReject={(runId, phase) => console.log('rejected', runId, phase)}
        />
      </section>

      <section>
        <h2>Pipeline Runs</h2>
        <RunList onSelect={setSelectedRunId} />
        {selectedRunId && (
          <p>Selected: {selectedRunId}</p>
        )}
      </section>
    </main>
  )
}
