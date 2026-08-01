"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";
import { createResourceHooks } from "@/lib/hooks/useResource";
import type { SourceVeilleCreateInput, SourceVeilleUpdateInput } from "@/lib/schemas/veille";
import type { SourceVeille, VeilleAlerte, VeilleHistoriquePrix } from "@/lib/types";

export const sourcesVeilleResource = createResourceHooks<SourceVeille, SourceVeilleCreateInput, SourceVeilleUpdateInput>(
  "veille-sources",
  "/veille/sources"
);

export function useVeilleHistorique(sourceId: number | undefined) {
  return useQuery({
    queryKey: ["veille-sources", "historique", sourceId ?? ""],
    queryFn: () => apiFetch<VeilleHistoriquePrix[]>(`/veille/sources/${sourceId}/historique`),
    enabled: sourceId !== undefined,
  });
}

export function useVeilleAlertes(statut: string = "en_attente") {
  return useQuery({
    queryKey: ["veille-alertes", "list", { statut }],
    queryFn: () => apiFetch<VeilleAlerte[]>(`/veille/alertes?statut=${statut}`),
  });
}

export function useValiderAlerteVeille() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => apiFetch(`/veille/alertes/${id}/valider`, { method: "POST" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["veille-alertes"] }),
  });
}

export function useRejeterAlerteVeille() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => apiFetch(`/veille/alertes/${id}/rejeter`, { method: "POST" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["veille-alertes"] }),
  });
}

export function useLancerVeilleManuelle() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => apiFetch<unknown[]>("/veille/lancer", { method: "POST" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["veille-sources"] });
      queryClient.invalidateQueries({ queryKey: ["veille-alertes"] });
    },
  });
}
