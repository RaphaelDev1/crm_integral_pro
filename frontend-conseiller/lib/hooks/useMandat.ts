"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";

export interface Mandat {
  id: number;
  client_id: number | null;
  statut: string;
  notes: string | null;
  date_creation: string | null;
  date_envoi: string | null;
  date_signature: string | null;
  pdf_url: string | null;
}

export function useMandat(dossierId: number | undefined) {
  return useQuery({
    queryKey: ["dossiers", "mandat", dossierId ?? ""],
    queryFn: () => apiFetch<Mandat | null>(`/dossiers/${dossierId}/mandat`),
    enabled: dossierId !== undefined,
  });
}

export function useEnvoyerMandat() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (dossierId: number) => apiFetch<Mandat>(`/dossiers/${dossierId}/mandat`, { method: "POST" }),
    onSuccess: (_data, dossierId) => {
      queryClient.invalidateQueries({ queryKey: ["dossiers", "mandat", dossierId] });
    },
  });
}

export function useMarquerMandatSigne() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ mandatId, signataire, dossierId }: { mandatId: number; signataire: string; dossierId: number }) =>
      apiFetch<Mandat>(`/mandats/${mandatId}/marquer-signe`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ signataire }),
      }),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["dossiers", "mandat", variables.dossierId] });
      queryClient.invalidateQueries({ queryKey: ["dossiers", "timeline", variables.dossierId] });
      queryClient.invalidateQueries({ queryKey: ["prospects"] });
      queryClient.invalidateQueries({ queryKey: ["clients"] });
    },
  });
}
