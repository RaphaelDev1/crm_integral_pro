import { BACKEND_URL } from "./backend";

// Utilisé à la fois par app/api/auth/refresh/route.ts (appel explicite depuis
// AuthContext) et par le proxy générique app/api/backend/[...path]/route.ts
// (rafraîchissement transparent sur 401). Retourne null si le refresh token
// est absent, expiré ou révoqué — l'appelant décide alors de déconnecter.
export async function refreshAccessToken(refreshToken: string): Promise<string | null> {
  let res: Response;
  try {
    res = await fetch(`${BACKEND_URL}/auth/refresh`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
      cache: "no-store",
    });
  } catch {
    return null;
  }
  if (!res.ok) return null;
  const data = await res.json().catch(() => null);
  return data?.access_token ?? null;
}
