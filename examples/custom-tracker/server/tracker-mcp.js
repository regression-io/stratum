#!/usr/bin/env node
/**
 * custom-tracker MCP server
 *
 * Minimal stdio MCP server exposing a JSON tracker file as Claude Code tools.
 * Pattern: read data file → expose as MCP tools → Claude Code calls them.
 *
 * Register in .mcp.json:
 *   { "mcpServers": { "tracker": { "command": "node", "args": ["server/tracker-mcp.js"] } } }
 */
import { Server } from '@modelcontextprotocol/sdk/server/index.js'
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js'
import { CallToolRequestSchema, ListToolsRequestSchema } from '@modelcontextprotocol/sdk/types.js'
import { readFileSync, writeFileSync } from 'fs'
import { resolve, dirname } from 'path'
import { fileURLToPath } from 'url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const TRACKER_FILE = resolve(__dirname, '../tracker.json')

function loadItems() {
  try {
    return JSON.parse(readFileSync(TRACKER_FILE, 'utf-8'))
  } catch {
    return []
  }
}

function saveItems(items) {
  writeFileSync(TRACKER_FILE, JSON.stringify(items, null, 2))
}

const server = new Server(
  { name: 'custom-tracker', version: '0.1.0' },
  { capabilities: { tools: {} } }
)

server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    {
      name: 'get_items',
      description: 'List tracker items. Optionally filter by status or type.',
      inputSchema: {
        type: 'object',
        properties: {
          status: { type: 'string', enum: ['planned', 'in_progress', 'complete'], description: 'Filter by status' },
          type:   { type: 'string', enum: ['task', 'bug', 'feature'], description: 'Filter by type' },
        },
      },
    },
    {
      name: 'update_item',
      description: 'Update an item status by ID.',
      inputSchema: {
        type: 'object',
        required: ['id', 'status'],
        properties: {
          id:     { type: 'string', description: 'Item ID, e.g. ITEM-1' },
          status: { type: 'string', enum: ['planned', 'in_progress', 'complete'] },
        },
      },
    },
  ],
}))

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params

  if (name === 'get_items') {
    let items = loadItems()
    if (args?.status) items = items.filter(i => i.status === args.status)
    if (args?.type)   items = items.filter(i => i.type === args.type)
    return { content: [{ type: 'text', text: JSON.stringify(items, null, 2) }] }
  }

  if (name === 'update_item') {
    const items = loadItems()
    const item = items.find(i => i.id === args.id)
    if (!item) {
      return { content: [{ type: 'text', text: `Item ${args.id} not found` }], isError: true }
    }
    item.status = args.status
    saveItems(items)
    return { content: [{ type: 'text', text: JSON.stringify(item) }] }
  }

  throw new Error(`Unknown tool: ${name}`)
})

const transport = new StdioServerTransport()
await server.connect(transport)
