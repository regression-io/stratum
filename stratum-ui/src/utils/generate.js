/**
 * Simple generators that produce pipeline definitions in various formats.
 * These mirror the Python generators in stratum-ui's original server.
 */

export function generateToml(draft) {
  const lines = [`[pipeline]`, `name = "${draft.name || 'unnamed'}"`]
  for (const phase of draft.phases || []) {
    lines.push('')
    lines.push(`[[pipeline.phases]]`)
    lines.push(`name = "${phase.name || ''}"`)
    if (phase.capability) lines.push(`capability = "${phase.capability}"`)
    if (phase.policy) lines.push(`policy = "${phase.policy}"`)
  }
  return lines.join('\n') + '\n'
}

export function generatePython(draft) {
  const name = draft.name || 'unnamed'
  const className = name.replace(/[^a-zA-Z0-9]/g, '_').replace(/^(\d)/, '_$1') || 'Pipeline'
  const lines = [
    `from stratum import pipeline, phase`,
    ``,
    `@pipeline`,
    `class ${className}:`,
    `    """${name} pipeline."""`,
  ]
  for (const phase of draft.phases || []) {
    const fnName = (phase.name || 'step').replace(/[^a-zA-Z0-9]/g, '_').toLowerCase()
    const decoratorArgs = []
    if (phase.capability) decoratorArgs.push(`capability="${phase.capability}"`)
    if (phase.policy) decoratorArgs.push(`policy="${phase.policy}"`)
    const decoratorStr = decoratorArgs.length ? `@phase(${decoratorArgs.join(', ')})` : '@phase'
    lines.push(``)
    lines.push(`    ${decoratorStr}`)
    lines.push(`    def ${fnName}(self):`)
    lines.push(`        ...`)
  }
  if (!draft.phases?.length) {
    lines.push(`    pass`)
  }
  return lines.join('\n') + '\n'
}

export function generateYaml(draft) {
  const lines = [`pipeline:`, `  name: "${draft.name || 'unnamed'}"`, `  phases:`]
  for (const phase of draft.phases || []) {
    lines.push(`    - name: "${phase.name || ''}"`)
    if (phase.capability) lines.push(`      capability: "${phase.capability}"`)
    if (phase.policy) lines.push(`      policy: "${phase.policy}"`)
  }
  if (!draft.phases?.length) lines.push(`    []`)
  return lines.join('\n') + '\n'
}
