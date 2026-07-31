import { NextResponse } from "next/server";

import { ACCESS_TOKEN_COOKIE, REFRESH_TOKEN_COOKIE } from "@/lib/server/backend";

// Le backend n'expose pas d'endpoint de révocation de token (cf.
// backend/routers/auth.py) : se déconnecter se limite à effacer les cookies
// côté BFF, comme le ferait un client qui jette ses tokens.
export async function POST() {
  const response = NextResponse.json({ message: "Déconnecté." });
  response.cookies.delete(ACCESS_TOKEN_COOKIE);
  response.cookies.delete(REFRESH_TOKEN_COOKIE);
  return response;
}
