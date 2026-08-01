"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";
import type { MandatHonoraires } from "@/lib/types";

export function useMandatHonoraires(dossierId: number | undefined) {
  return useQuery({
    queryKey: ["honoraires", "detail", dossierId ?? ""],
    queryFn: () => apiFetch<MandatHonoraires | null>(`/dossiers/${dossierId}/mandat-honoraires`),
    enabled: dossierId !== undefined,
  });
}

export function useMandatsHonorairesListe() {
  return useQuery({
    queryKey: ["honoraires", "list"],
    queryFn: () => apiFetch<MandatHonoraires[]>("/honoraires"),
  });
}

export function useCreerMandatHonoraires() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ dossierId, montant, taux }: { dossierId: number; montant: number; taux: number }) =>
      apiFetch<MandatHonoraires>(`/dossiers/${dossierId}/mandat-honoraires`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ montant, taux }),
      }),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["honoraires", "detail", variables.dossierId] });
      queryClient.invalidateQueries({ queryKey: ["honoraires", "list"] });
    },
  });
}

export function useMarquerSigneHonoraires() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ dossierId, signataire }: { dossierId: number; signataire: string }) =>
      apiFetch<MandatHonoraires>(`/dossiers/${dossierId}/mandat-honoraires/marquer-signe`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ signataire }),
      }),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["honoraires", "detail", variables.dossierId] });
      queryClient.invalidateQueries({ queryKey: ["honoraires", "list"] });
    },
  });
}
