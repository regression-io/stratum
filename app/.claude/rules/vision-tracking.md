# Vision Tracking: Every Artifact Gets a Board Item

When you create a document (design doc, plan, spec, journal entry, discovery doc), you MUST also create a corresponding item on the Vision Surface with appropriate connections.

## The rule

After writing any file in `docs/`, immediately run `scripts/vision-track.mjs` to create the item:

```bash
node scripts/vision-track.mjs create "<title>" \
  --type <type> \
  --phase <phase> \
  --description "<one-line summary>" \
  --connects-to <parent-item-id>:<connection-type>
```

To update an existing item:
```bash
node scripts/vision-track.mjs update <id> --status complete --confidence 3
```

## Type mapping

| Doc path | Item type | Typical phase |
|----------|-----------|---------------|
| `docs/plans/` | `spec` | `planning` or `design` |
| `docs/discovery/` | `idea` | `vision` or `requirements` |
| `docs/journal/` | `artifact` | (match session's primary phase) |
| `docs/specs/` | `spec` | `requirements` or `design` |
| `docs/design/` | `decision` | `design` |
| `docs/evaluations/` | `evaluation` | (match what's being evaluated) |
| `docs/requirements/` | `spec` | `requirements` |
| `docs/decisions/` | `decision` | (match the decision's domain) |
| Open questions raised in docs | `question` | (match the doc's phase) |
| Implementation tasks identified | `task` | `planning` or `implementation` |
| Discussion threads | `thread` | (match the discussion's phase) |

## Connections

Every doc item must have at least one connection. Use `--connects-to` to link it:

- **Plan/spec informs tasks:** `--connects-to <task-id>:informs`
- **Discovery informs decisions:** `--connects-to <decision-id>:informs`
- **Journal supports the work:** `--connects-to <feature-id>:supports`
- **Evaluation informs decisions:** `--connects-to <decision-id>:informs`

If you don't know the parent item ID, search first:
```bash
node scripts/vision-track.mjs search "keyword"
node scripts/vision-track.mjs list
```

## When to skip

- Trivial edits to existing docs (typos, formatting)
- Handoff updates (`.claude/handoff.md`) — these track process, not artifacts
- Rule files (`.claude/rules/`) — these are meta-configuration

## When to update (not create)

If the doc already has a board item, update it instead of creating a duplicate:
```bash
node scripts/vision-track.mjs update <existing-id> --status complete --confidence 3
```

## Why this matters

The Vision Surface is the artifact layer. If a doc exists but isn't on the board, it's invisible to the user and disconnected from the work graph. Every artifact should be traceable.
