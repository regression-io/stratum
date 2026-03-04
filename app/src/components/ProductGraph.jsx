import React from 'react';
import GraphRenderer from './GraphRenderer.jsx';

/**
 * ProductGraph — the Forge product ontology rendered via GraphRenderer.
 * Colors mapped from constants.js TYPE_COLORS.
 * Includes the 6-phase development pipeline as a grouped row.
 */

// Entity colors — match TYPE_COLORS in vision/constants.js
const COLORS = {
  discovery: '#a78bfa',   // violet-400 (orthogonal process)
  feature: '#3b82f6',     // blue — top-level container
  track: '#06b6d4',       // cyan — deliverable unit
  task: '#94a3b8',        // gray
  spec: '#a78bfa',        // violet
  idea: '#fbbf24',        // amber
  question: '#f472b6',    // pink
  evaluation: '#f59e0b',  // orange
  thread: '#64748b',      // dim gray
  decision: '#22c55e',    // green
  artifact: '#a87cb8',    // magenta
  // Edge-specific
  informs: '#64748b',     // slate-500
  structural: '#475569',  // slate-600
  // Pipeline
  pipeline: '#6366f1',    // indigo-500
};

const nodes = [
  // Discovery (orthogonal process)
  { id: 'discovery', label: 'Discovery', sublabel: 'orthogonal process', color: COLORS.discovery, shape: 'diamond' },

  // Phase pipeline (compound group)
  { id: 'pipeline', label: 'Feature Development Pipeline', color: COLORS.pipeline },
  { id: 'p-vision', label: 'Vision', parent: 'pipeline', color: COLORS.pipeline },
  { id: 'p-specification', label: 'Specification', parent: 'pipeline', color: COLORS.pipeline },
  { id: 'p-planning', label: 'Planning', parent: 'pipeline', color: COLORS.pipeline },
  { id: 'p-implementation', label: 'Implementation', parent: 'pipeline', color: COLORS.pipeline },
  { id: 'p-verification', label: 'Verification', parent: 'pipeline', color: COLORS.pipeline },
  { id: 'p-release', label: 'Release', parent: 'pipeline', color: COLORS.pipeline },

  // Execution
  { id: 'feature', label: 'Feature', sublabel: 'strategic container', color: COLORS.feature },
  { id: 'track', label: 'Track', sublabel: 'deliverable unit', color: COLORS.track },
  { id: 'task', label: 'Task', sublabel: 'planned → doing → done', color: COLORS.task },

  // Specification
  { id: 'spec', label: 'Spec', sublabel: 'behavioral specification', color: COLORS.spec },
  { id: 'evaluation', label: 'Evaluation', sublabel: 'assessment / gap analysis', color: COLORS.evaluation },

  // Thinking
  { id: 'idea', label: 'Idea', sublabel: 'can float free', color: COLORS.idea },
  { id: 'thread', label: 'Thread', sublabel: 'deliberation', color: COLORS.thread },
  { id: 'decision', label: 'Decision', sublabel: 'resolved choice', color: COLORS.decision },
  { id: 'question', label: 'Question', sublabel: 'may block progress', color: COLORS.question },

  // Captured output
  { id: 'artifact', label: 'Artifact', sublabel: 'journal / doc / output', color: COLORS.artifact },
];

const edges = [
  // Pipeline flow (sequential)
  { from: 'p-vision', to: 'p-specification', color: COLORS.pipeline },
  { from: 'p-specification', to: 'p-planning', color: COLORS.pipeline },
  { from: 'p-planning', to: 'p-implementation', color: COLORS.pipeline },
  { from: 'p-implementation', to: 'p-verification', color: COLORS.pipeline },
  { from: 'p-verification', to: 'p-release', color: COLORS.pipeline },

  // Entity → primary phase (dotted, shows where types live)
  { from: 'idea', to: 'p-vision', label: 'lives in', color: COLORS.idea, style: 'dotted' },
  { from: 'spec', to: 'p-specification', label: 'lives in', color: COLORS.spec, style: 'dotted' },
  { from: 'task', to: 'p-implementation', label: 'lives in', color: COLORS.task, style: 'dotted' },
  { from: 'evaluation', to: 'p-verification', label: 'lives in', color: COLORS.evaluation, style: 'dotted' },

  // Discovery produces anything
  { from: 'discovery', to: 'feature', label: 'produces', color: COLORS.discovery, style: 'dashed' },
  { from: 'discovery', to: 'idea', label: 'produces', color: COLORS.discovery, style: 'dashed' },
  { from: 'discovery', to: 'thread', label: 'produces', color: COLORS.discovery, style: 'dashed' },
  { from: 'discovery', to: 'decision', label: 'produces', color: COLORS.discovery, style: 'dashed' },
  { from: 'discovery', to: 'question', label: 'produces', color: COLORS.discovery, style: 'dashed' },
  { from: 'discovery', to: 'spec', label: 'produces', color: COLORS.discovery, style: 'dashed' },

  // Implements (structural hierarchy)
  { from: 'track', to: 'feature', label: 'implements', color: COLORS.track },
  { from: 'task', to: 'feature', label: 'implements', color: COLORS.task },
  { from: 'spec', to: 'feature', label: 'implements', color: COLORS.spec },

  // Blocks
  { from: 'feature', to: 'feature', label: 'blocks', color: COLORS.question, id: 'feat-blocks' },

  // Informs (thinking → execution)
  { from: 'idea', to: 'feature', label: 'informs', color: COLORS.informs, style: 'dashed' },
  { from: 'thread', to: 'decision', label: 'informs', color: COLORS.informs, style: 'dashed' },
  { from: 'evaluation', to: 'decision', label: 'informs', color: COLORS.informs, style: 'dashed' },

  // Supports
  { from: 'artifact', to: 'feature', label: 'supports', color: COLORS.artifact },

  // Contradicts (pressure test)
  { from: 'question', to: 'decision', label: 'contradicts', color: COLORS.question },

  // Feature traverses the pipeline
  { from: 'feature', to: 'p-vision', label: 'enters', color: COLORS.feature, style: 'dashed' },
];

export default function ProductGraph() {
  return (
    <GraphRenderer
      graphKey="product"
      nodes={nodes}
      edges={edges}
      title="Forge Product Ontology"
      subtitle="10 entity types · 6 phases · 5 edge types · Discovery orthogonal"
    />
  );
}
