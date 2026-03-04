#!/usr/bin/env node
/**
 * vision-track — Agent bridge to the Vision Surface.
 *
 * Full CLI for creating, reading, updating, deleting, connecting,
 * and querying vision board items from the embedded terminal.
 */

import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));

// Import validation constants from the server (single source of truth)
const { VALID_TYPES, VALID_STATUSES, VALID_CONNECTION_TYPES, VALID_PHASES } = await import(
  resolve(__dirname, '..', 'server', 'vision-store.js')
);

const API = process.env.VISION_API || 'http://localhost:3001/api/vision';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function apiCall(path, method = 'GET', body) {
  const opts = { method, headers: { 'Content-Type': 'application/json' } };
  if (body) opts.body = JSON.stringify(body);

  let res;
  try {
    res = await fetch(`${API}${path}`, opts);
  } catch (err) {
    console.error(`Failed to reach server at ${API}. Is it running?`);
    process.exit(1);
  }

  const data = await res.json();
  if (!res.ok) {
    console.error(`API error ${res.status}: ${data.error || JSON.stringify(data)}`);
    process.exit(1);
  }
  return data;
}

function parseArgs(args) {
  const result = { positional: [], flags: {}, connections: [] };
  let i = 0;
  while (i < args.length) {
    if (args[i] === '--connects-to') {
      result.connections.push(args[++i]);
      i++;
    } else if (args[i].startsWith('--')) {
      const key = args[i].slice(2);
      result.flags[key] = args[++i];
      i++;
    } else {
      result.positional.push(args[i]);
      i++;
    }
  }
  return result;
}

function formatItem(i) {
  return `${i.id}  ${(i.status || '').padEnd(12)}  ${(i.type || '').padEnd(10)}  ${(i.phase || '-').padEnd(15)}  ${i.title}`;
}

// ---------------------------------------------------------------------------
// Commands
// ---------------------------------------------------------------------------

async function createItem(parsed) {
  const title = parsed.positional[0];
  if (!title) {
    console.error('Usage: vision-track create <title> [options]');
    process.exit(1);
  }

  const type = parsed.flags.type || 'artifact';
  const status = parsed.flags.status || 'planned';
  const confidence = parseInt(parsed.flags.confidence || '0', 10);
  const phase = parsed.flags.phase || undefined;
  const description = parsed.flags.description || '';
  const parentId = parsed.flags['parent-id'] || undefined;

  // Validate before sending
  if (!VALID_TYPES.includes(type)) {
    console.error(`Invalid type: ${type}. Valid: ${VALID_TYPES.join(', ')}`);
    process.exit(1);
  }
  if (!VALID_STATUSES.includes(status)) {
    console.error(`Invalid status: ${status}. Valid: ${VALID_STATUSES.join(', ')}`);
    process.exit(1);
  }
  if (phase && !VALID_PHASES.includes(phase)) {
    console.error(`Invalid phase: ${phase}. Valid: ${VALID_PHASES.join(', ')}`);
    process.exit(1);
  }
  if (confidence < 0 || confidence > 4) {
    console.error('Confidence must be 0-4');
    process.exit(1);
  }

  const body = { type, title, status, confidence, description };
  if (phase) body.phase = phase;
  if (parentId) body.parentId = parentId;
  if (parsed.flags.files !== undefined) {
    body.files = parsed.flags.files ? parsed.flags.files.split(',').map(f => f.trim()) : [];
  }

  const item = await apiCall('/items', 'POST', body);
  console.error(`Created: ${item.id} (${title})`);

  // Create connections
  for (const conn of parsed.connections) {
    const sepIdx = conn.lastIndexOf(':');
    if (sepIdx === -1) {
      console.error(`Invalid connection format: ${conn} (expected ID:TYPE)`);
      continue;
    }
    const targetId = conn.slice(0, sepIdx);
    const connType = conn.slice(sepIdx + 1);

    if (!VALID_CONNECTION_TYPES.includes(connType)) {
      console.error(`Invalid connection type: ${connType}. Valid: ${VALID_CONNECTION_TYPES.join(', ')}`);
      continue;
    }

    await apiCall('/connections', 'POST', {
      fromId: item.id,
      toId: targetId,
      type: connType,
    });
    console.error(`  Connected: ${item.id} --[${connType}]--> ${targetId}`);
  }

  // Machine-readable output on stdout
  process.stdout.write(item.id + '\n');
}

async function updateItem(parsed) {
  const id = parsed.positional[0];
  if (!id) {
    console.error('Usage: vision-track update <id> [options]');
    process.exit(1);
  }

  const updates = {};
  if (parsed.flags.status) {
    if (!VALID_STATUSES.includes(parsed.flags.status)) {
      console.error(`Invalid status: ${parsed.flags.status}. Valid: ${VALID_STATUSES.join(', ')}`);
      process.exit(1);
    }
    updates.status = parsed.flags.status;
  }
  if (parsed.flags.confidence !== undefined) {
    updates.confidence = parseInt(parsed.flags.confidence, 10);
  }
  if (parsed.flags.phase) {
    if (!VALID_PHASES.includes(parsed.flags.phase)) {
      console.error(`Invalid phase: ${parsed.flags.phase}. Valid: ${VALID_PHASES.join(', ')}`);
      process.exit(1);
    }
    updates.phase = parsed.flags.phase;
  }
  if (parsed.flags.title) updates.title = parsed.flags.title;
  if (parsed.flags.description) updates.description = parsed.flags.description;
  if (parsed.flags.files !== undefined) {
    updates.files = parsed.flags.files ? parsed.flags.files.split(',').map(f => f.trim()) : [];
  }
  if (parsed.flags['add-files']) {
    const current = await apiCall(`/items/${id}`);
    const existing = current.files || [];
    const adding = parsed.flags['add-files'].split(',').map(f => f.trim());
    updates.files = [...new Set([...existing, ...adding])];
  }

  if (Object.keys(updates).length === 0) {
    console.error('No updates specified');
    process.exit(1);
  }

  const item = await apiCall(`/items/${id}`, 'PATCH', updates);
  console.error(`Updated: ${item.id} (${item.title})`);
  process.stdout.write(item.id + '\n');
}

async function getItem(parsed) {
  const id = parsed.positional[0];
  if (!id) {
    console.error('Usage: vision-track get <id>');
    process.exit(1);
  }

  // Try the single-item endpoint first; fall back to fetching all and filtering
  let item, connections;
  try {
    const result = await apiCall(`/items/${id}`);
    // If the endpoint returns item+connections (new server), use directly
    if (result.id) {
      connections = result.connections || [];
      item = result;
    } else {
      throw new Error('fallback');
    }
  } catch {
    // Fallback: fetch all items and filter client-side
    const state = await apiCall('/items');
    const allItems = state.items || [];
    item = allItems.find(i => i.id === id);
    if (!item) {
      console.error(`Item not found: ${id}`);
      process.exit(1);
    }
    connections = (state.connections || []).filter(
      c => c.fromId === id || c.toId === id
    );
  }

  console.log(`ID:          ${item.id}`);
  console.log(`Title:       ${item.title}`);
  console.log(`Type:        ${item.type}`);
  console.log(`Status:      ${item.status}`);
  console.log(`Phase:       ${item.phase || '-'}`);
  console.log(`Confidence:  ${item.confidence}`);
  console.log(`Description: ${item.description || '-'}`);
  console.log(`Parent:      ${item.parentId || '-'}`);
  console.log(`Created:     ${item.createdAt}`);
  console.log(`Updated:     ${item.updatedAt}`);
  if (item.files && item.files.length > 0) {
    console.log(`Files:       ${item.files.join(', ')}`);
  }

  if (connections.length > 0) {
    console.log(`\nConnections (${connections.length}):`);
    for (const c of connections) {
      const direction = c.fromId === item.id ? '-->' : '<--';
      const otherId = c.fromId === item.id ? c.toId : c.fromId;
      console.log(`  ${c.id}  ${direction} [${c.type}] ${otherId}`);
    }
  }
}

async function deleteItem(parsed) {
  const id = parsed.positional[0];
  if (!id) {
    console.error('Usage: vision-track delete <id>');
    process.exit(1);
  }

  await apiCall(`/items/${id}`, 'DELETE');
  console.error(`Deleted: ${id}`);
}

async function connectItems(parsed) {
  const fromId = parsed.positional[0];
  const toId = parsed.positional[1];
  const connType = parsed.flags.type;

  if (!fromId || !toId) {
    console.error('Usage: vision-track connect <fromId> <toId> --type <type>');
    process.exit(1);
  }
  if (!connType) {
    console.error(`Connection type required. Use --type <type>. Valid: ${VALID_CONNECTION_TYPES.join(', ')}`);
    process.exit(1);
  }
  if (!VALID_CONNECTION_TYPES.includes(connType)) {
    console.error(`Invalid connection type: ${connType}. Valid: ${VALID_CONNECTION_TYPES.join(', ')}`);
    process.exit(1);
  }

  const conn = await apiCall('/connections', 'POST', { fromId, toId, type: connType });
  console.error(`Connected: ${fromId} --[${connType}]--> ${toId}`);
  process.stdout.write(conn.id + '\n');
}

async function disconnectItems(parsed) {
  const connectionId = parsed.positional[0];
  if (!connectionId) {
    console.error('Usage: vision-track disconnect <connectionId>');
    process.exit(1);
  }

  await apiCall(`/connections/${connectionId}`, 'DELETE');
  console.error(`Disconnected: ${connectionId}`);
}

async function showStatus() {
  // Compute summary client-side from /items — works with or without /summary endpoint
  const state = await apiCall('/items');
  const items = state.items || [];
  const connections = state.connections || [];

  const byPhase = {};
  const byStatus = {};
  const byType = {};
  let totalConfidence = 0;
  let confidenceCount = 0;
  let openQuestions = 0;
  let blockedItems = 0;

  for (const item of items) {
    const phase = item.phase || 'unassigned';
    byPhase[phase] = (byPhase[phase] || 0) + 1;

    const status = item.status || 'planned';
    byStatus[status] = (byStatus[status] || 0) + 1;

    const type = item.type || 'artifact';
    byType[type] = (byType[type] || 0) + 1;

    if (typeof item.confidence === 'number') {
      totalConfidence += item.confidence;
      confidenceCount++;
    }

    if (item.type === 'question' && item.status !== 'complete' && item.status !== 'killed') {
      openQuestions++;
    }

    if (item.status === 'blocked') {
      blockedItems++;
    }
  }

  const avgConfidence = confidenceCount > 0
    ? Math.round((totalConfidence / confidenceCount) * 100) / 100
    : 0;

  console.log(`=== Vision Surface Summary ===`);
  console.log(`Total items: ${items.length}   Connections: ${connections.length}   Avg confidence: ${avgConfidence}`);
  console.log(`Open questions: ${openQuestions}   Blocked: ${blockedItems}`);

  if (Object.keys(byPhase).length > 0) {
    console.log(`\nBy phase:`);
    for (const [phase, count] of Object.entries(byPhase).sort((a, b) => b[1] - a[1])) {
      console.log(`  ${phase.padEnd(18)} ${count}`);
    }
  }

  if (Object.keys(byStatus).length > 0) {
    console.log(`\nBy status:`);
    for (const [status, count] of Object.entries(byStatus).sort((a, b) => b[1] - a[1])) {
      console.log(`  ${status.padEnd(18)} ${count}`);
    }
  }

  if (Object.keys(byType).length > 0) {
    console.log(`\nBy type:`);
    for (const [type, count] of Object.entries(byType).sort((a, b) => b[1] - a[1])) {
      console.log(`  ${type.padEnd(18)} ${count}`);
    }
  }
}

async function showReady() {
  const state = await apiCall('/items');
  const items = state.items || [];
  const connections = state.connections || [];

  // Build set of items that are blocked by non-complete items
  const blockedIds = new Set();
  for (const conn of connections) {
    if (conn.type === 'blocks') {
      const blocker = items.find(i => i.id === conn.fromId);
      if (blocker && blocker.status !== 'complete' && blocker.status !== 'killed') {
        blockedIds.add(conn.toId);
      }
    }
  }

  // Ready = planned or ready status, not blocked
  const ready = items.filter(i =>
    (i.status === 'planned' || i.status === 'ready') &&
    !blockedIds.has(i.id)
  );

  if (ready.length === 0) {
    console.log('No ready items found.');
  } else {
    for (const i of ready) {
      console.log(formatItem(i));
    }
  }
  console.error(`${ready.length} ready item${ready.length !== 1 ? 's' : ''}`);
}

async function searchItems(parsed) {
  const query = (parsed.positional[0] || '').toLowerCase();
  const state = await apiCall('/items');
  const items = state.items || [];

  const matches = query
    ? items.filter(i =>
        i.title.toLowerCase().includes(query) ||
        (i.description || '').toLowerCase().includes(query) ||
        i.type.includes(query) ||
        (i.phase || '').includes(query)
      )
    : items;

  for (const i of matches) {
    console.log(formatItem(i));
  }
  console.error(`${matches.length} item${matches.length !== 1 ? 's' : ''} found`);
}

async function listItems() {
  const state = await apiCall('/items');
  const items = state.items || [];
  for (const i of items) {
    console.log(formatItem(i));
  }
  console.error(`${items.length} item${items.length !== 1 ? 's' : ''} total`);
}

function showHelp() {
  console.log(`vision-track — Agent bridge to the Vision Surface

COMMANDS

  Items:
    create <title> [options]    Create a new item
    get <id>                    Get item details + connections
    update <id> [options]       Update an item
    delete <id>                 Delete an item and its connections
    list                        List all items
    search [query]              Search items by title/description/type/phase

  Connections:
    connect <fromId> <toId> --type <type>   Create a connection
    disconnect <connectionId>               Delete a connection

  Queries:
    status                      Board summary (counts by phase/status/type)
    ready                       Items ready to work on (not blocked)
    help                        Show this help

CREATE OPTIONS
    --type TYPE           ${VALID_TYPES.join(', ')}
    --phase PHASE         ${VALID_PHASES.join(', ')}
    --status STATUS       ${VALID_STATUSES.join(', ')}
    --confidence N        0-4 (default: 0)
    --description DESC    Item description
    --parent-id ID        Parent item ID
    --files <paths>       Comma-separated file paths
    --connects-to ID:TYPE Connection (repeatable)

UPDATE OPTIONS
    --status STATUS       New status
    --confidence N        New confidence (0-4)
    --phase PHASE         New phase
    --title TITLE         New title
    --description DESC    New description
    --files <paths>       Comma-separated file paths (replaces existing)
    --add-files <paths>   Comma-separated file paths (merges with existing)

CONNECTION TYPES
    ${VALID_CONNECTION_TYPES.join(', ')}

EXAMPLES
    # Create a spec in design phase
    vision-track create "Auth flow spec" --type spec --phase design

    # Create and connect to parent
    vision-track create "Login UI" --type task --phase implementation \\
      --connects-to abc123:supports

    # Get item details
    vision-track get abc123

    # Update status and confidence
    vision-track update abc123 --status complete --confidence 3

    # Connect two existing items
    vision-track connect item1 item2 --type informs

    # Board overview
    vision-track status

    # What's ready to work on?
    vision-track ready

    # Delete an item
    vision-track delete abc123

OUTPUT
    stdout: machine-readable (IDs). stderr: human-readable messages.
    Pipe-friendly: \`id=$(vision-track create "title" --type task)\``);
}

// ---------------------------------------------------------------------------
// Snapshot
// ---------------------------------------------------------------------------

async function takeSnapshot(parsed) {
  const BASE = (process.env.VISION_API || 'http://localhost:3001/api/vision').replace('/api/vision', '');
  const timeout = parsed.flags.timeout || '3000';
  const noDom = parsed.flags['no-dom'] !== undefined;

  let res;
  try {
    res = await fetch(`${BASE}/api/snapshot?timeout=${timeout}`);
  } catch (err) {
    console.error(`Failed to connect: ${err.message}`);
    process.exit(1);
  }

  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    console.error(`Snapshot failed (${res.status}): ${data.error || res.statusText}`);
    process.exit(1);
  }

  const snapshot = await res.json();

  // Optionally strip DOM tree for compact output
  if (noDom) delete snapshot.dom;

  console.log(JSON.stringify(snapshot, null, 2));
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

const args = process.argv.slice(2);
const command = args[0];
const rest = args.slice(1);

if (!command || command === '--help' || command === '-h' || command === 'help') {
  showHelp();
  process.exit(0);
}

const parsed = parseArgs(rest);

switch (command) {
  case 'create':     await createItem(parsed); break;
  case 'get':        await getItem(parsed); break;
  case 'update':     await updateItem(parsed); break;
  case 'delete':     await deleteItem(parsed); break;
  case 'connect':    await connectItems(parsed); break;
  case 'disconnect': await disconnectItems(parsed); break;
  case 'status':     await showStatus(); break;
  case 'ready':      await showReady(); break;
  case 'search':     await searchItems(parsed); break;
  case 'list':       await listItems(); break;
  case 'snapshot':   await takeSnapshot(parsed); break;
  default:
    console.error(`Unknown command: ${command}. Run 'vision-track help' for usage.`);
    process.exit(1);
}
