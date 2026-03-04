#!/usr/bin/env node
/**
 * stratum-ui serve — serves built @stratum/ui assets.
 * Does NOT start stratum-mcp serve. Expects the API to already be running.
 *
 * Usage:
 *   stratum-ui serve [--port 7820] [--api-base http://localhost:7821]
 */
import { createServer } from 'http'
import { readFileSync, existsSync } from 'fs'
import { resolve, extname, dirname } from 'path'
import { fileURLToPath } from 'url'

const __dirname = dirname(fileURLToPath(import.meta.url))

const args = process.argv.slice(2)
const portIdx = args.indexOf('--port')
const PORT = portIdx >= 0 ? parseInt(args[portIdx + 1]) : 7820
const apiBaseIdx = args.indexOf('--api-base')
const API_BASE = apiBaseIdx >= 0 ? args[apiBaseIdx + 1] : 'http://localhost:7821'

const DIST = resolve(__dirname, '../dist/app')

if (!existsSync(DIST)) {
  console.error('Error: dist/app not found. Build the standalone app first:')
  console.error('  npm run build:app')
  process.exit(1)
}

const MIME = {
  '.html': 'text/html',
  '.js':   'application/javascript',
  '.css':  'text/css',
  '.svg':  'image/svg+xml',
  '.json': 'application/json',
}

const API_BASE_INJECTION = `<script>window.__STRATUM_API_BASE__=${JSON.stringify(API_BASE)}</script>`

const server = createServer((req, res) => {
  let filePath = resolve(DIST, req.url === '/' ? 'index.html' : req.url.slice(1))
  if (!existsSync(filePath)) filePath = resolve(DIST, 'index.html') // SPA fallback
  try {
    let data = readFileSync(filePath)
    const ext = extname(filePath)
    // Inject API base into HTML so the app knows where the API lives
    if (ext === '.html' || filePath.endsWith('index.html')) {
      data = Buffer.from(data.toString().replace('</head>', `${API_BASE_INJECTION}</head>`))
    }
    res.writeHead(200, { 'Content-Type': MIME[ext] || 'application/octet-stream' })
    res.end(data)
  } catch {
    res.writeHead(404)
    res.end('Not found')
  }
})

server.listen(PORT, '127.0.0.1', () => {
  console.log(`stratum-ui serving on http://localhost:${PORT}`)
  console.log(`API base: ${API_BASE}`)
  console.log('(Run stratum-mcp serve separately for the API)')
})
