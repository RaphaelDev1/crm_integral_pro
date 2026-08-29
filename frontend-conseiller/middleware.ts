import { NextRequest, NextResponse } from "next/server";

import { ACCESS_TOKEN_COOKIE } from "@/lib/server/backend";

// Garde d'auth minimale : redirige vers /login si le cookie access_token est
// absent. Ne vérifie PAS la signature (pas de secret JWT partagé côté edge
// runtime) — le backend reste seul juge de la validité, exactement comme
// peut_modifier()/est_admin() dans src/app.py sont des aides d'affichage et
// non une frontière de sécurité. Le proxy backend/[...path] gère le cas d'un
// cookie présent mais expiré (refresh transparent, puis 401 si besoin).
export function middleware(request: NextRequest) {
  const hasAccessToken = Boolean(request.cookies.get(ACCESS_TOKEN_COOKIE)?.value);
  if (!hasAccessToken) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("next", request.nextUrl.pathname);
    return NextResponse.redirect(loginUrl);
  }
  return NextResponse.next();
}

// /api/backend/* est volontairement exclu : c'est une route JSON, pas une
// page. La rediriger vers /login casserait les appels fetch (le client
// suivrait la redirection et recevrait du HTML là où il attend du JSON) —
// le proxy applique déjà l'auth lui-même et répond 401 en JSON quand le
// cookie est absent ou expiré (voir app/api/backend/[...path]/route.ts).
//
// /ia-conseil-partage/* est également exclu : lien lecture-seule envoyé au
// CLIENT (pas au conseiller), protégé par son propre jeton `session_view`
// en query param plutôt que par le cookie access_token (§1.5.1) — voir
// backend/routers/ia_conseil_sessions.py::obtenir_session_publique.
export const config = {
  matcher: ["/((?!login|api|ia-conseil-partage|_next/static|_next/image|favicon.ico).*)"],
};
