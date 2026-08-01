"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";
import type { Demarche, DemarchesDossier } from "@/lib/types";

export function useDemarchesDossier(dossierId: number | undefined) {
  return useQuery({
    queryKey: ["demarches", "dossier", dossierId ?? ""],
    queryFn: () => apiFetch<DemarchesDossier>(`/dossiers/${dossierId}/demarches`),
    enabled: dossierId !== undefined,
  });
}

export function useCreerDemarche() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ dossierId, type_demarche }: { dossierId: number; type_demarche: string }) =>
      apiFetch<Demarche>(`/dossiers/${dossierId}/demarches`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ type_demarche }),
      }),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["demarches", "dossier", variables.dossierId] });
    },
  });
}

export function useGenererDemarche() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ demarcheId }: { demarcheId: number; dossierId: number }) =>
      apiFetch<Demarche>(`/demarches/${demarcheId}/generer`, { method: "POST" }),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["demarches", "dossier", variables.dossierId] });
    },
  });
}

export function useEnvoyerDemarche() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ demarcheId }: { demarcheId: number; dossierId: number }) =>
      apiFetch<Demarche>(`/demarches/${demarcheId}/envoyer`, { method: "POST" }),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["demarches", "dossier", variables.dossierId] });
    },
  });
}

export function useRenseignerChampsDemarche() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      demarcheId,
      valeurs,
    }: {
      demarcheId: number;
      dossierId: number;
      valeurs: Record<string, string>;
    }) =>
      apiFetch<Demarche>(`/demarches/${demarcheId}/champs`, {
        method: "PATCH",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ valeurs }),
      }),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["demarches", "dossier", variables.dossierId] });
    },
  });
}
