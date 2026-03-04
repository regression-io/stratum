export const FORGE_API_TOKEN = import.meta.env.VITE_FORGE_API_TOKEN || '';

export function withForgeToken(headers = {}) {
  if (!FORGE_API_TOKEN) return headers;
  return { ...headers, 'x-forge-token': FORGE_API_TOKEN };
}
