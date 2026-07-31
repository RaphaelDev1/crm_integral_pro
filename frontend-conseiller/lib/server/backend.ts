// Constantes partagées par les route handlers app/api/* (jamais importées
// côté client — ce fichier ne doit être utilisé que dans un contexte serveur).

export const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";

export const ACCESS_TOKEN_COOKIE = "access_token";
export const REFRESH_TOKEN_COOKIE = "refresh_token";

// Doivent suivre backend/core/config.py (access_token_expire_minutes=60,
// refresh_token_expire_days=7) : un décalage n'est pas un risque de sécurité
// (le backend reste seul juge de la validité du JWT), juste une expiration
// de cookie un peu trop tôt ou tard.
export const ACCESS_TOKEN_MAX_AGE = 60 * 60;
export const REFRESH_TOKEN_MAX_AGE = 7 * 24 * 60 * 60;

export function cookieOptions(maxAge: number) {
  return {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax" as const,
    path: "/",
    maxAge,
  };
}
