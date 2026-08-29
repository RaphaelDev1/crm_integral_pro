"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";
import type { CampagneCout, DashboardAttribution, DashboardUtm, DashboardUtmInscrits } from "@/lib/types";

function periodeQuery(debut?: string, fin?: string): string {
  const params = new URLSearchParams();
  if (debut) params.set("debut", debut);
  if (fin) params.set("fin", fin);
  const query = params.toString();
  return query ? `?${query}` : "";
}

export function useDashboardUtm(debut?: string, fin?: string) {
  return useQuery({
    queryKey: ["dashboard", "utm-tunnel", { debut, fin }],
    queryFn: () => apiFetch<DashboardUtm>(`/dashboard/utm-tunnel${periodeQuery(debut, fin)}`),
  });
}

export function useDashboardAttribution(debut?: string, fin?: string) {
  return useQuery({
    queryKey: ["dashboard", "attribution", { debut, fin }],
    queryFn: () => apiFetch<DashboardAttribution>(`/dashboard/attribution${periodeQuery(debut, fin)}`),
  });
}

export function useDashboardUtmInscrits(debut?: string, fin?: string) {
  return useQuery({
    queryKey: ["dashboard", "utm-inscrits", { debut, fin }],
    queryFn: () => apiFetch<DashboardUtmInscrits>(`/dashboard/utm-inscrits${periodeQuery(debut, fin)}`),
  });
}

export function useCampagnesCouts() {
  return useQuery({
    queryKey: ["dashboard", "couts-campagne"],
    queryFn: () => apiFetch<CampagneCout[]>("/dashboard/couts-campagne"),
  });
}

interface EnregistrerCoutCampagneInput {
  utm_source: string;
  utm_campaign?: string;
  mois: string;
  cout: number;
  notes?: string;
}

// Upsert par (utm_source, utm_campaign, mois) — sert pour la création comme
// pour l'édition d'une dépense publicitaire. Invalide couts-campagne (liste
// affichée) et utm-tunnel (le CAC dépend du coût saisi ici).
export function useEnregistrerCoutCampagne() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: EnregistrerCoutCampagneInput) =>
      apiFetch<CampagneCout>("/dashboard/couts-campagne", {
        method: "PUT",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(input),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["dashboard", "couts-campagne"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard", "utm-tunnel"] });
    },
  });
}

export function useSupprimerCoutCampagne() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => apiFetch<void>(`/dashboard/couts-campagne/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["dashboard", "couts-campagne"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard", "utm-tunnel"] });
    },
  });
}
