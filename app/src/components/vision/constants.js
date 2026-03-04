/**
 * Shared constants for Vision Tracker components.
 * Single source of truth for types, statuses, phases, and their colors.
 */

export const VALID_TYPES = ['feature', 'track', 'idea', 'decision', 'question', 'thread', 'artifact', 'task', 'spec', 'evaluation'];

export const TYPE_COLORS = {
  feature: '#3b82f6',     // blue — top-level container
  track: '#06b6d4',       // cyan — deliverable unit
  decision: '#22c55e',    // green
  task: '#94a3b8',        // gray
  spec: '#a78bfa',        // violet
  idea: '#fbbf24',        // amber
  question: '#f472b6',    // pink
  evaluation: '#f59e0b',  // orange
  thread: '#64748b',      // dim gray
  artifact: '#a87cb8',    // magenta
};

export const STATUS_COLORS = {
  planned: 'var(--color-text-tertiary)',
  ready: 'var(--color-primary)',
  in_progress: 'var(--color-accent)',
  review: 'var(--color-warning)',
  complete: 'var(--color-success)',
  blocked: 'var(--color-error)',
  parked: 'var(--color-text-tertiary)',
  killed: 'var(--color-text-muted)',
};

export const STATUSES = ['planned', 'ready', 'in_progress', 'review', 'complete', 'blocked', 'parked', 'killed'];

export const PHASES = ['vision', 'specification', 'planning', 'implementation', 'verification', 'release'];

export const PHASE_LABELS = {
  vision: 'Vision',
  specification: 'Specification',
  planning: 'Planning',
  implementation: 'Implementation',
  verification: 'Verification',
  release: 'Release',
};

export const CONFIDENCE_LABELS = ['Untested', 'Low', 'Moderate', 'High', 'Crystallized'];

