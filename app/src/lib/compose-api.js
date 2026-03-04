export const COMPOSE_API_TOKEN = import.meta.env.VITE_COMPOSE_API_TOKEN || '';

export function withComposeToken(headers = {}) {
  if (!COMPOSE_API_TOKEN) return headers;
  return { ...headers, 'x-compose-token': COMPOSE_API_TOKEN };
}
