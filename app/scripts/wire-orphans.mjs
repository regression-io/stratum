#!/usr/bin/env node

/**
 * Wire 66 orphaned vision tracker items into the feature/track hierarchy
 * by creating `implements` connections (fromId=item, toId=track).
 */

import { readFileSync, writeFileSync } from 'fs';
import { v4 as uuidv4 } from 'uuid';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const dataPath = resolve(__dirname, '..', 'data', 'vision-state.json');

// The 66 orphaned items mapped to their tracks (item semanticId -> track semanticId)
const MAPPINGS = [
  ['FORGE-DEC-1',   'FORGE-TRK-1'],
  ['FORGE-DEC-2',   'FORGE-TRK-5'],
  ['FORGE-DEC-5',   'FORGE-TRK-5'],
  ['FORGE-DEC-6',   'FORGE-TRK-5'],
  ['FORGE-DEC-4',   'FORGE-TRK-5'],
  ['FORGE-DEC-3',   'FORGE-TRK-5'],
  ['FORGE-DEC-7',   'FORGE-TRK-3'],
  ['FORGE-DEC-8',   'FORGE-TRK-10'],
  ['FORGE-DEC-9',   'FORGE-TRK-1'],
  ['FORGE-IDEA-8',  'FORGE-TRK-5'],
  ['FORGE-IDEA-9',  'FORGE-TRK-13'],
  ['FORGE-IDEA-2',  'FORGE-TRK-14'],
  ['FORGE-IDEA-3',  'FORGE-TRK-5'],
  ['FORGE-IDEA-1',  'FORGE-TRK-1'],
  ['FORGE-IDEA-4',  'FORGE-TRK-5'],
  ['FORGE-Q-3',     'FORGE-TRK-5'],
  ['FORGE-Q-4',     'FORGE-TRK-1'],
  ['FORGE-Q-5',     'FORGE-TRK-5'],
  ['FORGE-Q-1',     'FORGE-TRK-5'],
  ['FORGE-THR-3',   'FORGE-TRK-1'],
  ['FORGE-THR-1',   'FORGE-TRK-5'],
  ['FORGE-THR-2',   'FORGE-TRK-5'],
  ['FORGE-THR-4',   'FORGE-TRK-5'],
  ['FORGE-ART-1',   'FORGE-TRK-3'],
  ['FORGE-DEC-10',  'FORGE-TRK-1'],
  ['FORGE-DEC-11',  'FORGE-TRK-5'],
  ['FORGE-DEC-12',  'FORGE-TRK-3'],
  ['FORGE-DEC-13',  'FORGE-TRK-3'],
  ['FORGE-IDEA-5',  'FORGE-TRK-8'],
  ['FORGE-IDEA-6',  'FORGE-TRK-9'],
  ['FORGE-IDEA-7',  'FORGE-TRK-11'],
  ['FORGE-IDEA-10', 'FORGE-TRK-14'],
  ['FORGE-THR-5',   'FORGE-TRK-1'],
  ['FORGE-Q-2',     'FORGE-TRK-11'],
  ['FORGE-SPEC-1',  'FORGE-TRK-3'],
  ['FORGE-SPEC-2',  'FORGE-TRK-3'],
  ['FORGE-SPEC-3',  'FORGE-TRK-3'],
  ['FORGE-SPEC-4',  'FORGE-TRK-3'],
  ['FORGE-TASK-1',  'FORGE-TRK-3'],
  ['FORGE-TASK-2',  'FORGE-TRK-3'],
  ['FORGE-TASK-3',  'FORGE-TRK-14'],
  ['FORGE-TASK-4',  'FORGE-TRK-6'],
  ['FORGE-TASK-5',  'FORGE-TRK-14'],
  ['FORGE-TASK-6',  'FORGE-TRK-3'],
  ['FORGE-DEC-14',  'FORGE-TRK-5'],
  ['FORGE-DEC-15',  'FORGE-TRK-5'],
  ['FORGE-DEC-16',  'FORGE-TRK-5'],
  ['FORGE-ART-2',   'FORGE-TRK-5'],
  ['FORGE-ART-3',   'FORGE-TRK-1'],
  ['FORGE-DEC-17',  'FORGE-TRK-12'],
  ['FORGE-DEC-18',  'FORGE-TRK-13'],
  ['FORGE-SPEC-5',  'FORGE-TRK-6'],
  ['FORGE-SPEC-6',  'FORGE-TRK-6'],
  ['FORGE-DEC-19',  'FORGE-TRK-6'],
  ['FORGE-DEC-20',  'FORGE-TRK-6'],
  ['FORGE-DEC-21',  'FORGE-TRK-5'],
  ['FORGE-DEC-22',  'FORGE-TRK-5'],
  ['FORGE-DEC-23',  'FORGE-TRK-13'],
  ['FORGE-DEC-24',  'FORGE-TRK-6'],
  ['FORGE-DEC-25',  'FORGE-TRK-6'],
  ['FORGE-DEC-26',  'FORGE-TRK-6'],
  ['FORGE-DEC-27',  'FORGE-TRK-6'],
  ['FORGE-IDEA-11', 'FORGE-TRK-7'],
  ['FORGE-SPEC-7',  'FORGE-TRK-7'],
  ['FORGE-DEC-28',  'FORGE-TRK-13'],
  ['FORGE-DEC-29',  'FORGE-TRK-13'],
];

// Read the state file
const state = JSON.parse(readFileSync(dataPath, 'utf-8'));

// Build a lookup: semanticId -> item UUID
const semanticToId = new Map();
for (const item of state.items) {
  if (item.semanticId) {
    semanticToId.set(item.semanticId, item.id);
  }
}

// Build a set of existing connections for dedup: "fromId->toId->type"
const existingConnections = new Set();
for (const conn of state.connections) {
  existingConnections.add(`${conn.fromId}->${conn.toId}->${conn.type}`);
}

let created = 0;
let skippedDuplicate = 0;
let skippedMissing = 0;
const summary = { byTrack: {} };

for (const [itemSemantic, trackSemantic] of MAPPINGS) {
  const fromId = semanticToId.get(itemSemantic);
  const toId = semanticToId.get(trackSemantic);

  if (!fromId) {
    console.warn(`  SKIP: item ${itemSemantic} not found in vision-state.json`);
    skippedMissing++;
    continue;
  }
  if (!toId) {
    console.warn(`  SKIP: track ${trackSemantic} not found in vision-state.json`);
    skippedMissing++;
    continue;
  }

  const key = `${fromId}->${toId}->implements`;
  if (existingConnections.has(key)) {
    skippedDuplicate++;
    continue;
  }

  const connection = {
    id: uuidv4(),
    fromId,
    toId,
    type: 'implements',
    createdAt: new Date().toISOString(),
  };

  state.connections.push(connection);
  existingConnections.add(key);
  created++;

  // Track summary
  if (!summary.byTrack[trackSemantic]) {
    summary.byTrack[trackSemantic] = [];
  }
  summary.byTrack[trackSemantic].push(itemSemantic);
}

// Save
writeFileSync(dataPath, JSON.stringify(state, null, 2) + '\n', 'utf-8');

// Print summary
console.log(`\n=== Wire Orphans Summary ===`);
console.log(`Total mappings:     ${MAPPINGS.length}`);
console.log(`Connections created: ${created}`);
console.log(`Skipped (duplicate): ${skippedDuplicate}`);
console.log(`Skipped (missing):   ${skippedMissing}`);
console.log(`\nBy track:`);

for (const [track, items] of Object.entries(summary.byTrack).sort()) {
  console.log(`  ${track} (${items.length} items):`);
  for (const item of items) {
    console.log(`    - ${item}`);
  }
}
