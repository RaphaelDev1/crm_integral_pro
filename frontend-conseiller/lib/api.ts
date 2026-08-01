// Wrapper fetch unique pour tout le code client : passe toujours par le
// proxy same-origin app/api/backend/[...path] (jamais le backend FastAPI
// directement, jamais le JWT ici — voir lib/server/backend.ts côté serveur).
const PROXY_PREFIX = "/api/backend";

export function backendFetch(path: string, init?: RequestInit): Promise<Response> {
  const url = path.startsWith("/") ? `${PROXY_PREFIX}${path}` : `${PROXY_PREFIX}/${path}`;
  return fetch(url, { ...init, cache: "no-store" });
}

export interface ApiFieldError {
  field: string;
  message: string;
}

// Levée par apiFetch sur toute réponse non-2xx. Portée par React Query
// jusqu'aux hooks (`error instanceof ApiError`) et jusqu'au toast global
// (voir app/providers.tsx) : le message affiché à l'utilisateur est celui
// renvoyé par le backend (`{"detail": "..."}`, convention FastAPI).
// `fieldErrors` est peuplé quand `detail` est le tableau d'erreurs de
// validation Pydantic (`[{loc, msg, type}]`, réponses 422) — consommé par
// components/forms/AppForm.tsx pour mapper les erreurs champ par champ.
export class ApiError extends Error {
  status: number;
  detail: string;
  fieldErrors: ApiFieldError[];

  constructor(status: number, detail: string, fieldErrors: ApiFieldError[] = []) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
    this.fieldErrors = fieldErrors;
  }
}

function parseErrorBody(status: number, path: string, body: unknown): { detail: string; fieldErrors: ApiFieldError[] } {
  const rawDetail = (body as { detail?: unknown } | null)?.detail;

  if (typeof rawDetail === "string") {
    return { detail: rawDetail, fieldErrors: [] };
  }

  if (Array.isArray(rawDetail)) {
    const fieldErrors = rawDetail
      .filter(
        (item): item is { loc: (string | number)[]; msg: string } =>
          Array.isArray(item?.loc) && typeof item?.msg === "string"
      )
      .map((item) => ({ field: String(item.loc[item.loc.length - 1]), message: item.msg }));
    const detail = fieldErrors.map((e) => e.message).join(" ") || `Erreur ${status} lors de l'appel à ${path}.`;
    return { detail, fieldErrors };
  }

  return { detail: `Erreur ${status} lors de l'appel à ${path}.`, fieldErrors: [] };
}

// A utiliser comme queryFn/mutationFn React Query. Parse le JSON de réponse
// et lève une ApiError normalisée en cas d'échec, pour que le cache
// d'erreurs de React Query (et le toast global) aient toujours un message
// exploitable, même quand le backend ne renvoie pas de JSON.
export async function apiFetch<T = unknown>(path: string, init?: RequestInit): Promise<T> {
  const res = await backendFetch(path, init);

  if (!res.ok) {
    const body = await res.json().catch(() => null);
    const { detail, fieldErrors } = parseErrorBody(res.status, path, body);
    throw new ApiError(res.status, detail, fieldErrors);
  }

  if (res.status === 204) {
    return undefined as T;
  }

  return res.json() as Promise<T>;
}

// Téléchargement d'une réponse binaire (PDF de restitution) via le même
// proxy BFF que apiFetch — déclenche un <a download> côté navigateur, pas de
// fetch(BACKEND_URL) direct (voir convention Phase 0/Annexe A).
export async function downloadBackendFile(path: string, filename: string): Promise<void> {
  const res = await backendFetch(path);

  if (!res.ok) {
    const body = await res.json().catch(() => null);
    const { detail, fieldErrors } = parseErrorBody(res.status, path, body);
    throw new ApiError(res.status, detail, fieldErrors);
  }

  const blob = await res.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
}
