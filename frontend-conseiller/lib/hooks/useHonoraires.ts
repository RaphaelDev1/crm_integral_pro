"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch, downloadBackendFile } from "@/lib/api";
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

// Taux par défaut réglable par l'admin (panneau Admin > Paramètres > Réglages,
// clé "taux_honoraires_defaut") — voir backend/routers/honoraires.py.
export function useTauxHonorairesDefaut() {
  return useQuery({
    queryKey: ["honoraires", "taux-defaut"],
    queryFn: () => apiFetch<{ taux: number }>("/honoraires/taux-defaut"),
    staleTime: 5 * 60 * 1000,
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

export function useTelechargerMandatHonoraires() {
  return useMutation({
    mutationFn: (dossierId: number) =>
      downloadBackendFile(`/dossiers/${dossierId}/mandat-honoraires/pdf`, `mandat_honoraires_dossier_${dossierId}.pdf`),
  });
}

interface EnvoiMandatHonorairesResultat {
  email_envoye: boolean;
  sms_envoye: boolean;
}

export function useEnvoyerMandatHonoraires() {
  return useMutation({
    mutationFn: ({ dossierId, canal }: { dossierId: number; canal: "email" | "sms" }) =>
      apiFetch<EnvoiMandatHonorairesResultat>(`/dossiers/${dossierId}/mandat-honoraires/envoyer`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ canal }),
      }),
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
