import { readFileSync } from 'fs';
const d = JSON.parse(readFileSync('./data/vision-state.json', 'utf8'));
const items = d.items, conns = d.connections;

const childIds = new Set();
for (const c of conns) {
  if (c.type === 'implements' || c.type === 'supports') childIds.add(c.fromId);
}
for (const i of items) {
  if (i.parentId) childIds.add(i.id);
}

const containers = items.filter(i => i.type === 'feature' || i.type === 'track');
const cids = new Set(containers.map(c => c.id));
const orphans = items.filter(i => !cids.has(i.id) && !childIds.has(i.id));

console.log('=== CONTAINERS ===');
for (const c of containers) {
  const kids = conns.filter(cn => cn.toId === c.id && (cn.type === 'implements' || cn.type === 'supports')).length;
  console.log(`${c.id.slice(0,8)}  ${c.type.padEnd(8)}  ${c.title}  (${kids} children)`);
}
console.log('');
console.log(`=== ORPHANS (${orphans.length}) ===`);
for (const o of orphans) {
  console.log(`${o.id.slice(0,8)}  ${o.type.padEnd(10)}  ${o.phase.padEnd(15)}  ${o.title}`);
}
