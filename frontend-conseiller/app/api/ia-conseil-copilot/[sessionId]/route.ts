import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";

import { ACCESS_TOKEN_COOKIE, BACKEND_URL } from "@/lib/server/backend";

// Relais SSE en streaming vers le copilote IA Conseil (backend POST
// /api/v1/sessions/{id}/copilot, voir backend/services/copilot_engine.py).
// Pas via le proxy générique app/api/backend/[...path] (celui-ci bufferise
// toute la réponse avec arrayBuffer() avant de répondre — inutilisable pour
// un flux streamé), même raison d'être qu'app/api/ia-conseil-live pour le
// flux WS. Ici la source est déjà un flux HTTP SSE côté backend (pas un
// WebSocket) : `backendRes.body` est retransmis tel quel.
export async function POST(request: NextRequest, { params }: { params: { sessionId: string } }) {
  const accessToken = cookies().get(ACCESS_TOKEN_COOKIE)?.value;
  if (!accessToken) {
    return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
  }

  const body = await request.text();
  let backendRes: Response;
  try {
    backendRes = await fetch(`${BACKEND_URL}/api/v1/sessions/${params.sessionId}/copilot`, {
      method: "POST",
      headers: { "content-type": "application/json", authorization: `Bearer ${accessToken}` },
      body,
      cache: "no-store",
    });
  } catch {
    return NextResponse.json({ detail: "Backend indisponible." }, { status: 502 });
  }

  if (!backendRes.ok || !backendRes.body) {
    const detail = await backendRes.text().catch(() => "Erreur copilote.");
    return NextResponse.json({ detail: detail || "Erreur copilote." }, { status: backendRes.status || 502 });
  }

  return new NextResponse(backendRes.body, {
    status: 200,
    headers: {
      "content-type": "text/event-stream",
      "cache-control": "no-cache, no-transform",
      connection: "keep-alive",
    },
  });
}
