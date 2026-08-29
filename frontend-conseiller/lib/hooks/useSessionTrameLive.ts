"use client";

import { useEffect, useRef } from "react";

import type { SessionTrameLiveMessage } from "@/lib/types-ia-conseil";

// Consomme le relais SSE app/api/ia-conseil-live/[sessionId] (voir ce fichier
// pour le pourquoi SSE plutôt que WebSocket direct). `onMessage` est gardé
// dans une ref pour ne réouvrir la connexion que si `sessionId` change, pas à
// chaque rendu du composant appelant.
export function useSessionTrameLive(sessionId: string | undefined, onMessage: (message: SessionTrameLiveMessage) => void) {
  const onMessageRef = useRef(onMessage);
  onMessageRef.current = onMessage;

  useEffect(() => {
    if (!sessionId) return;

    const source = new EventSource(`/api/ia-conseil-live/${sessionId}`);
    source.addEventListener("message", (event) => {
      try {
        onMessageRef.current(JSON.parse(event.data) as SessionTrameLiveMessage);
      } catch {
        // Message non-JSON (ne devrait pas arriver) — ignoré silencieusement.
      }
    });

    return () => source.close();
  }, [sessionId]);
}
