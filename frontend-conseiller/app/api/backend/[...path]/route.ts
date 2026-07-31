import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";

import {
  ACCESS_TOKEN_COOKIE,
  ACCESS_TOKEN_MAX_AGE,
  BACKEND_URL,
  REFRESH_TOKEN_COOKIE,
  cookieOptions,
} from "@/lib/server/backend";
import { refreshAccessToken } from "@/lib/server/refreshAccessToken";

// Proxy authentifié générique : tout appel du frontend vers l'API passe par
// ici (voir lib/backend-fetch.ts), qui ajoute `Authorization: Bearer` à
// partir du cookie httpOnly — le navigateur ne voit jamais le JWT. Sur 401,
// tente un refresh une fois avant de relayer l'échec au client.
function forwardToBackend(
  request: NextRequest,
  path: string[],
  token: string | undefined,
  body: ArrayBuffer | undefined
) {
  const targetUrl = `${BACKEND_URL}/${path.join("/")}${request.nextUrl.search}`;
  const headers = new Headers();
  const contentType = request.headers.get("content-type");
  if (contentType) headers.set("content-type", contentType);
  if (token) headers.set("authorization", `Bearer ${token}`);

  return fetch(targetUrl, {
    method: request.method,
    headers,
    body,
    cache: "no-store",
  });
}

async function toNextResponse(backendRes: Response) {
  const body = await backendRes.arrayBuffer();
  const headers = new Headers();
  const contentType = backendRes.headers.get("content-type");
  if (contentType) headers.set("content-type", contentType);
  return new NextResponse(body, { status: backendRes.status, headers });
}

async function handler(request: NextRequest, { params }: { params: { path: string[] } }) {
  const cookieStore = cookies();
  const accessToken = cookieStore.get(ACCESS_TOKEN_COOKIE)?.value;
  // Lu une seule fois : le corps de la requête ne peut être consommé qu'une
  // fois, il doit donc être bufferisé avant un éventuel retry post-refresh.
  const body = ["GET", "HEAD"].includes(request.method) ? undefined : await request.arrayBuffer();

  let backendRes: Response;
  try {
    backendRes = await forwardToBackend(request, params.path, accessToken, body);
  } catch {
    return NextResponse.json({ detail: "Backend indisponible." }, { status: 502 });
  }

  if (backendRes.status !== 401) {
    return toNextResponse(backendRes);
  }

  const refreshToken = cookieStore.get(REFRESH_TOKEN_COOKIE)?.value;
  const newAccessToken = refreshToken ? await refreshAccessToken(refreshToken) : null;

  if (!newAccessToken) {
    const response = await toNextResponse(backendRes);
    response.cookies.delete(ACCESS_TOKEN_COOKIE);
    response.cookies.delete(REFRESH_TOKEN_COOKIE);
    return response;
  }

  let retryRes: Response;
  try {
    retryRes = await forwardToBackend(request, params.path, newAccessToken, body);
  } catch {
    return NextResponse.json({ detail: "Backend indisponible." }, { status: 502 });
  }

  const response = await toNextResponse(retryRes);
  response.cookies.set(ACCESS_TOKEN_COOKIE, newAccessToken, cookieOptions(ACCESS_TOKEN_MAX_AGE));
  return response;
}

export { handler as GET, handler as POST, handler as PUT, handler as PATCH, handler as DELETE };
