# custom-tracker

Minimal MCP server that exposes a project tracker over stdio — the same pattern used by compose-mcp.

Shows how to build a read-only project context tool for Claude Code agents.

## Setup

```bash
node server/tracker-mcp.js  # run directly (for testing)
```

Register with Claude Code by adding to `.mcp.json`:
```json
{
  "mcpServers": {
    "tracker": {
      "command": "node",
      "args": ["/path/to/custom-tracker/server/tracker-mcp.js"]
    }
  }
}
```

## Tools exposed

- `get_items` — list all tracker items, optionally filtered by status or type
- `update_item` — update an item's status

## Extending

- Replace `tracker.json` with any data source (database, API, files)
- Add more tools following the same pattern
- See `compose-mcp.js` in the compose project for a full production example
