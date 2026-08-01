"use client";

import { useMutation } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";
import type { FactureAnalyse } from "@/lib/types";

// Pas de header content-type manuel : le navigateur pose le boundary
// multipart lui-même à partir du FormData (voir lib/api.ts::backendFetch,
// qui passe `init` tel quel au fetch natif).
export function useAnalyserFacture() {
  return useMutation({
    mutationFn: ({ fichier, clientId }: { fichier: File; clientId?: number }) => {
      const formData = new FormData();
      formData.append("fichier", fichier);
      if (clientId !== undefined) formData.append("client_id", String(clientId));
      return apiFetch<FactureAnalyse>("/factures/analyze", { method: "POST", body: formData });
    },
  });
}
