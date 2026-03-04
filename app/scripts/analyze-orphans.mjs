import fs from 'node:fs';
const d = JSON.parse(fs.readFileSync('data/vision-state.json', 'utf8'));

const features = d.items.filter(i => i.type === 'feature');
const reachable = new Set(features.map(f => f.id));

let changed = true;
while (changed) {
  changed = false;
  for (const conn of d.connections) {
    if (conn.type === 'implements' && reachable.has(conn.toId)) {
      if (!reachable.has(conn.fromId)) {
        reachable.add(conn.fromId);
        changed = true;
      }
    }
  }
  for (const item of d.items) {
    if (item.parentId && reachable.has(item.parentId)) {
      if (!reachable.has(item.id)) {
        reachable.add(item.id);
        changed = true;
      }
    }
  }
}

const orphans = d.items.filter(i => !reachable.has(i.id));
console.log(`Reachable: ${reachable.size} | Orphaned: ${orphans.length}`);
console.log('');

const tracks = d.items.filter(i => i.type === 'track');
console.log('=== TRACKS ===');
tracks.forEach(t => console.log(`  ${t.semanticId}  ${t.title}`));
console.log('');

console.log('=== ORPHANS ===');
for (const o of orphans) {
  const conns = d.connections.filter(c => c.fromId === o.id || c.toId === o.id);
  const targets = conns.map(c => {
    const otherId = c.fromId === o.id ? c.toId : c.fromId;
    const other = d.items.find(i => i.id === otherId);
    const dir = c.fromId === o.id ? '>' : '<';
    return `${dir}${c.type}:${other?.semanticId || other?.title?.slice(0, 25) || otherId.slice(0, 8)}`;
  }).join(' | ');
  const sid = (o.semanticId || o.id.slice(0, 8)).padEnd(15);
  const typ = o.type.padEnd(10);
  const tit = o.title.slice(0, 45).padEnd(47);
  console.log(`  ${sid} ${typ} ${tit} ${targets}`);
}
