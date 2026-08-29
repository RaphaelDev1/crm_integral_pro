"use client";

import { useQuery, useMutation } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";
import type { FactureAnalyse, FactureAnalysePersistee } from "@/lib/types";

// Pas de header content-type manuel : le navigateur pose le boundary
// multipart lui-même à partir du FormData (voir lib/api.ts::backendFetch,
// qui passe `init` tel quel au fetch natif).
export function useAnalyserFacture() {
  return useMutation({
    mutationFn: ({ fichier, clientId, prospectId }: { fichier: File; clientId?: number; prospectId?: number }) => {
      const formData = new FormData();
      formData.append("fichier", fichier);
      if (clientId !== undefined) formData.append("client_id", String(clientId));
      if (prospectId !== undefined) formData.append("prospect_id", String(prospectId));
      return apiFetch<FactureAnalyse>("/factures/analyze", { method: "POST", body: formData });
    },
  });
}

// Analyses automatiques (à l'upload via le lien de collecte documents, voir
// backend/routers/portail_public.py) d'un prospect.
export function useProspectFacturesAnalysees(prospectId: number) {
  return useQuery({
    queryKey: ["prospects", "factures-analysees", prospectId],
    queryFn: () => apiFetch<FactureAnalysePersistee[]>(`/prospects/${prospectId}/factures-analysees`),
  });
}
