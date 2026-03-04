/**
 * Shared guard for sensitive local endpoints.
 *
 * Usage:
 * 1) In normal dev flow, server/supervisor.js auto-generates COMPOSE_API_TOKEN.
 * 2) If running servers directly, set COMPOSE_API_TOKEN in the environment.
 * 3) Send header: x-compose-token: <COMPOSE_API_TOKEN>
 */
export function requireSensitiveToken(req, res, next) {
  const expected = process.env.COMPOSE_API_TOKEN;
  if (!expected) {
    return res.status(503).json({
      error: 'Sensitive endpoint disabled: missing COMPOSE_API_TOKEN (run via supervisor or set it manually)',
    });
  }

  const provided = req.get('x-compose-token');
  if (!provided || provided !== expected) {
    return res.status(401).json({ error: 'Unauthorized' });
  }

  next();
}
