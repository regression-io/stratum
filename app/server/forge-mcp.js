#!/usr/bin/env node
/**
 * Forge MCP Server — stdio transport
 *
 * Exposes Forge tracker state as MCP tools for Claude Code agents running
 * inside this project. Claude Code launches this process on-demand and
 * communicates via stdin/stdout JSON-RPC. No port, no supervisor entry.
 *
 * Register in .mcp.json:
 *   { "mcpServers": { "forge": { "command": "node", "args": ["server/forge-mcp.js"] } } }
 *
 * Tools:
 *   get_vision_items     — query items by phase/status/type/keyword
 *   get_item_detail      — single item with its connections
 *   get_current_session  — active session: tool count, items touched, summaries
 *   get_phase_summary    — status distribution for a given phase
 *   get_blocked_items    — items blocked by non-complete dependencies
 *
 * Token budget (per docs/features/mcp-connector/design.md Decision 6):
 *   Baseline (2026-02-24): ~519 tokens for all 5 tool definitions combined
 *   Soft cap: 2,000 tokens. Add typed tools for new operations; avoid proliferation.
 *   Per-tool: get_vision_items 235, get_phase_summary 104,
 *   get_item_detail 72, get_current_session 62, get_blocked_items 44
 */

import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { CallToolRequestSchema, ListToolsRequestSchema } from '@modelcontextprotocol/sdk/types.js';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = path.resolve(__dirname, '..');
const VISION_FILE = path.join(PROJECT_ROOT, 'data', 'vision-state.json');
const SESSIONS_FILE = path.join(PROJECT_ROOT, 'data', 'sessions.json');

// ---------------------------------------------------------------------------
// Data access — read directly from disk (no HTTP, no daemon dependency)
// ---------------------------------------------------------------------------

function loadVisionState() {
  try {
    const raw = fs.readFileSync(VISION_FILE, 'utf-8');
    return JSON.parse(raw);
  } catch {
    return { items: [], connections: [] };
  }
}

function loadSessions() {
  try {
    const raw = fs.readFileSync(SESSIONS_FILE, 'utf-8');
    const sessions = JSON.parse(raw);
    return Array.isArray(sessions) ? sessions : [];
  } catch {
    return [];
  }
}

// ---------------------------------------------------------------------------
// Tool implementations
// ---------------------------------------------------------------------------

function toolGetVisionItems({ phase, status, type, keyword, limit = 30 }) {
  const { items } = loadVisionState();

  let results = items;

  if (phase) {
    results = results.filter(i => i.phase === phase);
  }
  if (status) {
    const statuses = status.split(',').map(s => s.trim());
    results = results.filter(i => statuses.includes(i.status));
  }
  if (type) {
    results = results.filter(i => i.type === type);
  }
  if (keyword) {
    const kw = keyword.toLowerCase();
    results = results.filter(i =>
      i.title?.toLowerCase().includes(kw) ||
      i.description?.toLowerCase().includes(kw)
    );
  }

  const sliced = results.slice(0, limit);

  return {
    count: results.length,
    returned: sliced.length,
    items: sliced.map(i => ({
      id: i.id,
      title: i.title,
      type: i.type,
      phase: i.phase,
      status: i.status,
      confidence: i.confidence ?? null,
      description: i.description ?? null,
    })),
  };
}

function toolGetItemDetail({ id }) {
  const { items, connections } = loadVisionState();

  const item = items.find(i => i.id === id || i.semanticId === id || i.slug === id);
  if (!item) return { error: `Item not found: ${id}` };

  const related = connections.filter(c => c.fromId === id || c.toId === id);
  const connectionDetails = related.map(c => {
    const other = items.find(i => i.id === (c.fromId === id ? c.toId : c.fromId));
    return {
      direction: c.fromId === id ? 'outgoing' : 'incoming',
      type: c.type,
      otherId: other?.id,
      otherTitle: other?.title ?? '(unknown)',
      otherStatus: other?.status,
    };
  });

  return { ...item, connections: connectionDetails };
}

function toolGetPhasesSummary({ phase }) {
  const { items } = loadVisionState();

  const scoped = phase ? items.filter(i => i.phase === phase) : items;

  const byStatus = {};
  const byType = {};
  for (const item of scoped) {
    const s = item.status || 'unknown';
    byStatus[s] = (byStatus[s] || 0) + 1;
    const t = item.type || 'unknown';
    byType[t] = (byType[t] || 0) + 1;
  }

  const confidences = scoped
    .map(i => i.confidence)
    .filter(c => typeof c === 'number');
  const avgConfidence = confidences.length
    ? Math.round((confidences.reduce((a, b) => a + b, 0) / confidences.length) * 100) / 100
    : null;

  return {
    phase: phase || 'all',
    total: scoped.length,
    byStatus,
    byType,
    avgConfidence,
  };
}

function toolGetBlockedItems() {
  const { items, connections } = loadVisionState();
  const itemMap = new Map(items.map(i => [i.id, i]));

  const blocked = [];
  for (const conn of connections) {
    if (conn.type === 'blocks') {
      const blocker = itemMap.get(conn.fromId);
      const target = itemMap.get(conn.toId);
      if (
        blocker && target &&
        blocker.status !== 'complete' &&
        blocker.status !== 'killed'
      ) {
        blocked.push({
          item: { id: target.id, title: target.title, status: target.status, phase: target.phase },
          blockedBy: { id: blocker.id, title: blocker.title, status: blocker.status },
        });
      }
    }
  }

  return { count: blocked.length, blocked };
}

function toolGetCurrentSession() {
  const sessions = loadSessions();
  if (sessions.length === 0) return { session: null };

  // Most recent session
  const last = sessions[sessions.length - 1];

  // Flatten summaries across all items
  const allSummaries = [];
  for (const [, acc] of Object.entries(last.items || {})) {
    for (const s of acc.summaries || []) {
      if (s) allSummaries.push(typeof s === 'string' ? { summary: s } : s);
    }
  }

  return {
    session: {
      id: last.id,
      startedAt: last.startedAt,
      endedAt: last.endedAt ?? null,
      source: last.source,
      toolCount: last.toolCount,
      blockCount: (last.blocks || []).length,
      errorCount: (last.errors || []).length,
      itemCount: Object.keys(last.items || {}).length,
      recentSummaries: allSummaries.slice(-5),
    },
  };
}

// ---------------------------------------------------------------------------
// Tool definitions
// ---------------------------------------------------------------------------

const TOOLS = [
  {
    name: 'get_vision_items',
    description: 'Query Forge tracker items. Filter by phase, status, type, or keyword. Returns id, title, type, phase, status, confidence, description.',
    inputSchema: {
      type: 'object',
      properties: {
        phase: {
          type: 'string',
          description: 'Filter by phase: vision, requirements, design, planning, implementation, verification, release',
        },
        status: {
          type: 'string',
          description: 'Filter by status (comma-separated for multiple): planned, in_progress, complete, blocked, parked, killed',
        },
        type: {
          type: 'string',
          description: 'Filter by type: task, decision, evaluation, idea, spec, thread, artifact, question, feature, track',
        },
        keyword: {
          type: 'string',
          description: 'Search keyword matched against title and description',
        },
        limit: {
          type: 'number',
          description: 'Max results to return (default 30)',
        },
      },
    },
  },
  {
    name: 'get_item_detail',
    description: 'Get full detail for a single tracker item including all its connections.',
    inputSchema: {
      type: 'object',
      properties: {
        id: {
          type: 'string',
          description: 'Item ID (UUID) or semanticId/slug',
        },
      },
      required: ['id'],
    },
  },
  {
    name: 'get_phase_summary',
    description: 'Get status and type distribution for a phase (or all phases). Useful for understanding overall project health.',
    inputSchema: {
      type: 'object',
      properties: {
        phase: {
          type: 'string',
          description: 'Phase to summarize: vision, requirements, design, planning, implementation, verification, release. Omit for all phases.',
        },
      },
    },
  },
  {
    name: 'get_blocked_items',
    description: 'List all tracker items that are blocked by non-complete items.',
    inputSchema: {
      type: 'object',
      properties: {},
    },
  },
  {
    name: 'get_current_session',
    description: 'Get the most recent session: tool count, items touched, error count, and recent Haiku summaries of what was accomplished.',
    inputSchema: {
      type: 'object',
      properties: {},
    },
  },
];

// ---------------------------------------------------------------------------
// MCP Server setup
// ---------------------------------------------------------------------------

const server = new Server(
  { name: 'forge', version: '1.0.0' },
  { capabilities: { tools: {} } }
);

server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: TOOLS,
}));

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args = {} } = request.params;

  try {
    let result;

    switch (name) {
      case 'get_vision_items':    result = toolGetVisionItems(args); break;
      case 'get_item_detail':     result = toolGetItemDetail(args); break;
      case 'get_phase_summary':   result = toolGetPhasesSummary(args); break;
      case 'get_blocked_items':   result = toolGetBlockedItems(); break;
      case 'get_current_session': result = toolGetCurrentSession(); break;
      default:
        return {
          content: [{ type: 'text', text: `Unknown tool: ${name}` }],
          isError: true,
        };
    }

    return {
      content: [{ type: 'text', text: JSON.stringify(result, null, 2) }],
    };
  } catch (err) {
    return {
      content: [{ type: 'text', text: `Error: ${err.message}` }],
      isError: true,
    };
  }
});

// ---------------------------------------------------------------------------
// Start
// ---------------------------------------------------------------------------

const transport = new StdioServerTransport();
await server.connect(transport);
// Server runs until stdin closes — no explicit exit needed
