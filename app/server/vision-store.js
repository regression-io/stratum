/**
 * Vision Store — JSON-file-backed storage for vision surface items and connections.
 * Loads from disk on startup, saves after every mutation.
 */

import { v4 as uuidv4 } from 'uuid';
import fs from 'node:fs';
import path from 'node:path';

export const VALID_TYPES = ['feature', 'track', 'idea', 'decision', 'question', 'thread', 'artifact', 'task', 'spec', 'evaluation'];
export const VALID_STATUSES = ['planned', 'ready', 'in_progress', 'review', 'complete', 'blocked', 'parked', 'killed'];
export const VALID_CONNECTION_TYPES = ['informs', 'blocks', 'supports', 'contradicts', 'implements'];
export const VALID_PHASES = ['vision', 'specification', 'planning', 'implementation', 'verification', 'release'];

const DATA_DIR = path.resolve(import.meta.dirname, '..', 'data');
const DATA_FILE = path.join(DATA_DIR, 'vision-state.json');

function slugify(title) {
  return title.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
}

export class VisionStore {
  constructor() {
    this.items = new Map();
    this.connections = new Map();
    this._load();
  }

  /** Load state from disk */
  _load() {
    try {
      const raw = fs.readFileSync(DATA_FILE, 'utf-8');
      const data = JSON.parse(raw);
      if (Array.isArray(data.items)) {
        for (const item of data.items) {
          if (!item.slug && item.title) item.slug = slugify(item.title);
          if (!item.files) item.files = [];
          this.items.set(item.id, item);
        }
      }
      if (Array.isArray(data.connections)) {
        for (const conn of data.connections) this.connections.set(conn.id, conn);
      }
      console.log(`[vision] Loaded ${this.items.size} items, ${this.connections.size} connections from ${DATA_FILE}`);
    } catch (err) {
      if (err.code === 'ENOENT') {
        console.log('[vision] No saved state found, starting fresh');
      } else {
        console.error('[vision] Failed to load state, starting fresh:', err.message);
      }
    }
  }

  /** Save state to disk */
  _save() {
    try {
      fs.mkdirSync(DATA_DIR, { recursive: true });
      const data = JSON.stringify(this.getState(), null, 2);
      fs.writeFileSync(DATA_FILE, data, 'utf-8');
    } catch (err) {
      console.error('[vision] Failed to save state:', err.message);
    }
  }

  /** Get full state snapshot */
  getState() {
    return {
      items: Array.from(this.items.values()),
      connections: Array.from(this.connections.values()),
    };
  }

  /** Create a new vision item */
  createItem({ type, title, description = '', confidence = 0, status = 'planned', phase, position, parentId, files }) {
    if (!VALID_TYPES.includes(type)) throw new Error(`Invalid type: ${type}`);
    if (!title) throw new Error('title required');
    if (!VALID_STATUSES.includes(status)) throw new Error(`Invalid status: ${status}`);
    if (confidence < 0 || confidence > 4) throw new Error('confidence must be 0-4');
    if (phase && !VALID_PHASES.includes(phase)) throw new Error(`Invalid phase: ${phase}`);
    if (parentId && !this.items.has(parentId)) throw new Error(`Parent not found: ${parentId}`);

    const now = new Date().toISOString();
    const item = {
      id: uuidv4(),
      type,
      title,
      description,
      confidence,
      status,
      phase: phase || null,
      parentId: parentId || null,
      files: Array.isArray(files) ? files : [],
      slug: slugify(title),
      position: position || { x: 100 + Math.random() * 400, y: 100 + Math.random() * 300 },
      createdAt: now,
      updatedAt: now,
    };

    this.items.set(item.id, item);
    this._save();
    return item;
  }

  /** Update an existing item (partial) */
  updateItem(id, updates) {
    const item = this.items.get(id);
    if (!item) throw new Error(`Item not found: ${id}`);

    if (updates.type !== undefined && !VALID_TYPES.includes(updates.type)) {
      throw new Error(`Invalid type: ${updates.type}`);
    }
    if (updates.status !== undefined && !VALID_STATUSES.includes(updates.status)) {
      throw new Error(`Invalid status: ${updates.status}`);
    }
    if (updates.confidence !== undefined && (updates.confidence < 0 || updates.confidence > 4)) {
      throw new Error('confidence must be 0-4');
    }
    if (updates.phase !== undefined && updates.phase !== null && !VALID_PHASES.includes(updates.phase)) {
      throw new Error(`Invalid phase: ${updates.phase}`);
    }

    const allowed = ['type', 'title', 'description', 'confidence', 'status', 'phase', 'position', 'parentId', 'summary', 'files', 'speckitKey', 'stratumFlowId', 'evidence'];
    for (const key of allowed) {
      if (updates[key] !== undefined) {
        item[key] = updates[key];
      }
    }
    // Regenerate slug when title changes
    if (updates.title !== undefined) {
      item.slug = slugify(updates.title);
    }
    // Ensure files is always an array
    if (updates.files !== undefined) {
      item.files = Array.isArray(updates.files) ? updates.files : [];
    }
    item.updatedAt = new Date().toISOString();

    this.items.set(id, item);
    this._save();
    return item;
  }

  /** Delete an item and all its connections */
  deleteItem(id) {
    if (!this.items.has(id)) throw new Error(`Item not found: ${id}`);
    this.items.delete(id);

    // Remove connections referencing this item
    for (const [connId, conn] of this.connections) {
      if (conn.fromId === id || conn.toId === id) {
        this.connections.delete(connId);
      }
    }
    this._save();
    return { ok: true };
  }

  /** Create a connection between two items */
  createConnection({ fromId, toId, type }) {
    if (!this.items.has(fromId)) throw new Error(`Item not found: ${fromId}`);
    if (!this.items.has(toId)) throw new Error(`Item not found: ${toId}`);
    if (!VALID_CONNECTION_TYPES.includes(type)) throw new Error(`Invalid connection type: ${type}`);

    const conn = {
      id: uuidv4(),
      fromId,
      toId,
      type,
      createdAt: new Date().toISOString(),
    };

    this.connections.set(conn.id, conn);
    this._save();
    return conn;
  }

  /** Delete a connection */
  deleteConnection(id) {
    if (!this.connections.has(id)) throw new Error(`Connection not found: ${id}`);
    this.connections.delete(id);
    this._save();
    return { ok: true };
  }
}
