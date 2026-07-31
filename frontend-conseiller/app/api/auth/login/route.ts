import { NextRequest, NextResponse } from "next/server";

import {
  ACCESS_TOKEN_COOKIE,
  ACCESS_TOKEN_MAX_AGE,
  BACKEND_URL,
  REFRESH_TOKEN_COOKIE,
  REFRESH_TOKEN_MAX_AGE,
  cookieOptions,
} from "@/lib/server/backend";

// Seul point d'entrée qui voit les tokens en clair : les pose en cookies
// httpOnly puis ne renvoie que `{ user }` au navigateur.
export async function POST(request: NextRequest) {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ detail: "Requête invalide." }, { status: 400 });
  }

  let backendRes: Response;
  try {
    backendRes = await fetch(`${BACKEND_URL}/auth/login`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
      cache: "no-store",
    });
  } catch {
    return NextResponse.json({ detail: "Backend indisponible." }, { status: 502 });
  }

  const data = await backendRes.json().catch(() => null);
  if (!backendRes.ok || !data) {
    return NextResponse.json(
      data ?? { detail: "Identifiant ou mot de passe incorrect." },
      { status: backendRes.status || 401 }
    );
  }

  const response = NextResponse.json({ user: data.user });
  response.cookies.set(ACCESS_TOKEN_COOKIE, data.access_token, cookieOptions(ACCESS_TOKEN_MAX_AGE));
  response.cookies.set(REFRESH_TOKEN_COOKIE, data.refresh_token, cookieOptions(REFRESH_TOKEN_MAX_AGE));
  return response;
}
