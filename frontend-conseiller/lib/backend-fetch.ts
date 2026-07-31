// Wrapper fetch pour les Client Components : passe toujours par le proxy
// same-origin (jamais le backend FastAPI directement, jamais le JWT ici).
const PROXY_PREFIX = "/api/backend";

export function backendFetch(path: string, init?: RequestInit): Promise<Response> {
  const url = path.startsWith("/") ? `${PROXY_PREFIX}${path}` : `${PROXY_PREFIX}/${path}`;
  return fetch(url, { ...init, cache: "no-store" });
}
