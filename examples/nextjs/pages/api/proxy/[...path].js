/**
 * Optional API proxy — avoids CORS issues when stratum-mcp serve
 * is on a different port or host.
 *
 * Usage: set STRATUM_API_BASE in @stratum/ui components to /api/proxy
 */
export default async function handler(req, res) {
  const STRATUM_URL = process.env.STRATUM_API_URL || 'http://localhost:7821'
  const path = req.query.path.join('/')
  const url = `${STRATUM_URL}/api/${path}`

  const fetchRes = await fetch(url, {
    method: req.method,
    headers: { 'Content-Type': 'application/json' },
    body: ['POST', 'PUT', 'PATCH'].includes(req.method)
      ? JSON.stringify(req.body)
      : undefined,
  })

  const body = await fetchRes.text()
  res.status(fetchRes.status)
  res.setHeader('Content-Type', fetchRes.headers.get('content-type') || 'application/json')
  res.end(body)
}
