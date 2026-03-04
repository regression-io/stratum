/**
 * Shared guard for sensitive local endpoints.
 *
 * Usage:
 * 1) In normal dev flow, server/supervisor.js auto-generates FORGE_API_TOKEN.
 * 2) If running servers directly, set FORGE_API_TOKEN in the environment.
 * 3) Send header: x-forge-token: <FORGE_API_TOKEN>
 */
export function requireSensitiveToken(req, res, next) {
  const expected = process.env.FORGE_API_TOKEN;
  if (!expected) {
    return res.status(503).json({
      error: 'Sensitive endpoint disabled: missing FORGE_API_TOKEN (run via supervisor or set it manually)',
    });
  }

  const provided = req.get('x-forge-token');
  if (!provided || provided !== expected) {
    return res.status(401).json({ error: 'Unauthorized' });
  }

  next();
}
