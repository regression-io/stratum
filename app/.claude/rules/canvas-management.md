# Canvas Management Rule

The canvas (right panel) is the shared document surface. Use it proactively.

## Opening docs

When entering a discussion or working on a topic, **immediately open the relevant doc(s) in the canvas** using:

```bash
curl -s -X POST http://localhost:3001/api/canvas/open \
  -H 'Content-Type: application/json' \
  -d '{"path": "docs/path/to/file.md"}'
```

To scroll to a specific section, add `"anchor": "heading-slug"` (GitHub-style slugified heading).

## When to open

- **Starting a discussion:** Open the discovery doc, spec, or plan being discussed
- **Resuming from handoff:** Open the docs listed in the handoff's "key docs" section
- **Writing/editing a doc:** Open it in the canvas so the human sees changes live
- **Referencing prior work:** Open the artifact being referenced

## Closing docs

Close tabs that are no longer relevant to the current discussion:

```bash
# Close a specific tab
curl -s -X POST http://localhost:3001/api/canvas/close \
  -H 'Content-Type: application/json' \
  -d '{"path": "docs/path/to/file.md"}'

# Close all tabs
curl -s -X POST http://localhost:3001/api/canvas/close \
  -H 'Content-Type: application/json' -d '{}'
```

When the topic shifts, close irrelevant tabs and open relevant ones. Keep the canvas focused on what we're actually discussing.

## The canvas reflects the conversation

If we're talking about it, it should be visible. If we're not talking about it anymore, don't force it into view. The canvas is the artifact layer of the conversation — terminal is process, canvas is understanding.
