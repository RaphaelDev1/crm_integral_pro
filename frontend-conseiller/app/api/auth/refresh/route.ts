import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import { ACCESS_TOKEN_COOKIE, ACCESS_TOKEN_MAX_AGE, REFRESH_TOKEN_COOKIE, cookieOptions } from "@/lib/server/backend";
import { refreshAccessToken } from "@/lib/server/refreshAccessToken";

// Appelé explicitement par AuthContext au montage (pour re-hydrater une
// session existante) — le proxy générique fait aussi son propre appel
// transparent en cas de 401, voir app/api/backend/[...path]/route.ts.
export async function POST() {
  const refreshToken = cookies().get(REFRESH_TOKEN_COOKIE)?.value;
  if (!refreshToken) {
    return NextResponse.json({ detail: "Non authentifié." }, { status: 401 });
  }

  const accessToken = await refreshAccessToken(refreshToken);
  if (!accessToken) {
    const response = NextResponse.json({ detail: "Session expirée." }, { status: 401 });
    response.cookies.delete(ACCESS_TOKEN_COOKIE);
    response.cookies.delete(REFRESH_TOKEN_COOKIE);
    return response;
  }

  const response = NextResponse.json({ message: "ok" });
  response.cookies.set(ACCESS_TOKEN_COOKIE, accessToken, cookieOptions(ACCESS_TOKEN_MAX_AGE));
  return response;
}
