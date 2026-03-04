#!/usr/bin/env node
import { readFileSync } from 'fs';
const d = JSON.parse(readFileSync('data/vision-state.json', 'utf8'));

// Show type x phase distribution
const dist = {};
for (const i of d.items) {
  if (!dist[i.type]) dist[i.type] = {};
  dist[i.type][i.phase] = (dist[i.type][i.phase] || 0) + 1;
}
console.log('=== TYPE x PHASE ===');
for (const [type, phases] of Object.entries(dist).sort()) {
  console.log(type + ':');
  for (const [p, c] of Object.entries(phases).sort()) {
    console.log('  ' + p.padEnd(18) + c);
  }
}

// Items that are likely vision-phase
console.log('\n=== LIKELY VISION PHASE ===');
const visionTypes = new Set(['idea', 'thread', 'question']);
for (const i of d.items) {
  if (i.phase === 'vision') continue;
  const t = i.title.toLowerCase();
  let reason = '';
  if (visionTypes.has(i.type)) reason = `type=${i.type}`;
  else if (t.includes('vision') && i.type !== 'track' && i.type !== 'task') reason = 'title:vision';
  else if (t.includes('discovery') && i.type !== 'track') reason = 'title:discovery';
  else if (t.includes('brainstorm')) reason = 'title:brainstorm';
  if (reason) {
    console.log(`${i.id.slice(0,8)}  ${i.phase.padEnd(16)} ${i.type.padEnd(12)} ${reason.padEnd(16)} ${i.title}`);
  }
}
