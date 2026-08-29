"use client";

import { useCallback, useRef, useState } from "react";

import type { CopilotMode } from "@/lib/types-ia-conseil";

interface CopilotState {
  streaming: boolean;
  texte: string;
  erreur: string | null;
}

const ETAT_INITIAL: CopilotState = { streaming: false, texte: "", erreur: null };

// Consomme le relais SSE app/api/ia-conseil-copilot/[sessionId] en streaming
// via fetch + ReadableStream — EventSource ne supporte pas les requêtes
// POST, indispensable ici pour envoyer {mode, message} (voir ce fichier côté
// serveur pour le pourquoi d'un relais dédié plutôt que le proxy générique).
export function useCopilot(sessionId: string) {
  const [state, setState] = useState<CopilotState>(ETAT_INITIAL);
  const controllerRef = useRef<AbortController | null>(null);

  const demander = useCallback(
    async (mode: CopilotMode, message?: string) => {
      controllerRef.current?.abort();
      const controller = new AbortController();
      controllerRef.current = controller;

      setState({ streaming: true, texte: "", erreur: null });

      try {
        const res = await fetch(`/api/ia-conseil-copilot/${sessionId}`, {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ mode, message }),
          signal: controller.signal,
        });

        if (!res.ok || !res.body) {
          const corps = await res.json().catch(() => null);
          setState({ streaming: false, texte: "", erreur: (corps as { detail?: string } | null)?.detail ?? "Copilote indisponible." });
          return;
        }

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        for (;;) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });

          // Découpage sur les blocs SSE ("\n\n") ; le dernier fragment
          // incomplet reste dans buffer pour la prochaine itération.
          const blocs = buffer.split("\n\n");
          buffer = blocs.pop() ?? "";

          for (const bloc of blocs) {
            const lignes = bloc.split("\n");
            const ligneEvent = lignes.find((l) => l.startsWith("event: "));
            const ligneData = lignes.find((l) => l.startsWith("data: "));
            if (!ligneEvent || !ligneData) continue;

            const evenement = ligneEvent.slice("event: ".length);
            let donnee: { text?: string; detail?: string };
            try {
              donnee = JSON.parse(ligneData.slice("data: ".length));
            } catch {
              continue;
            }

            if (evenement === "delta") {
              setState((s) => ({ ...s, texte: s.texte + (donnee.text ?? "") }));
            } else if (evenement === "error") {
              setState((s) => ({ ...s, erreur: donnee.detail ?? "Erreur copilote." }));
            }
          }
        }
      } catch (err) {
        if ((err as Error).name !== "AbortError") {
          setState((s) => ({ ...s, erreur: "Connexion copilote interrompue." }));
        }
      } finally {
        setState((s) => ({ ...s, streaming: false }));
      }
    },
    [sessionId]
  );

  return { ...state, demander };
}
