import { cookies } from "next/headers";
import { NextRequest } from "next/server";
import WebSocket from "ws";

import { ACCESS_TOKEN_COOKIE, BACKEND_URL } from "@/lib/server/backend";

// Relais SSE <-> WebSocket pour le flux temps réel d'une session de trame IA
// Conseil (backend WS `/api/v1/sessions/{id}/live`, voir
// backend/routers/ia_conseil_sessions.py). Le navigateur ne parle jamais
// directement au backend (voir .env.example/lib/api.ts) : ce serveur
// maintient la connexion WS côté Node avec le JWT lu depuis le cookie
// httpOnly, et retransmet chaque message au client via Server-Sent Events
// (EventSource, même origine, cookies envoyés automatiquement — pas besoin
// de ticket). SSE suffit : le canal est à sens unique (les réponses du
// conseiller partent déjà en POST /answer via useRepondre), pas besoin d'un
// WebSocket bidirectionnel côté client.
export async function GET(_request: NextRequest, { params }: { params: { sessionId: string } }) {
  const accessToken = cookies().get(ACCESS_TOKEN_COOKIE)?.value;
  if (!accessToken) {
    return new Response("Unauthorized", { status: 401 });
  }

  const wsUrl = `${BACKEND_URL.replace(/^http/, "ws")}/api/v1/sessions/${params.sessionId}/live?token=${encodeURIComponent(accessToken)}`;
  const encoder = new TextEncoder();
  let socket: WebSocket | undefined;
  let heartbeat: ReturnType<typeof setInterval> | undefined;

  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      const envoyer = (evenement: string, donnee: string) => {
        try {
          controller.enqueue(encoder.encode(`event: ${evenement}\ndata: ${donnee}\n\n`));
        } catch {
          // Contrôleur déjà fermé (client déconnecté) — rien à faire.
        }
      };

      socket = new WebSocket(wsUrl);
      socket.on("open", () => envoyer("open", "{}"));
      socket.on("message", (data) => envoyer("message", data.toString()));
      socket.on("close", () => {
        envoyer("close", "{}");
        try {
          controller.close();
        } catch {
          /* déjà fermé */
        }
      });
      socket.on("error", () => {
        envoyer("error", '{"detail":"Connexion temps réel indisponible."}');
        try {
          controller.close();
        } catch {
          /* déjà fermé */
        }
      });

      // Ping périodique (commentaire SSE, ignoré par EventSource) pour éviter
      // qu'un proxy intermédiaire ne coupe la connexion pour inactivité.
      heartbeat = setInterval(() => {
        try {
          controller.enqueue(encoder.encode(`: ping\n\n`));
        } catch {
          clearInterval(heartbeat);
        }
      }, 25000);
    },
    cancel() {
      clearInterval(heartbeat);
      socket?.close();
    },
  });

  return new Response(stream, {
    headers: {
      "content-type": "text/event-stream",
      "cache-control": "no-cache, no-transform",
      connection: "keep-alive",
    },
  });
}
