"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";
import type { AlerteOffre } from "@/lib/types";

export function useAlertesOffresListe(statut: string = "en_attente") {
  return useQuery({
    queryKey: ["alertes-offres", "list", { statut }],
    queryFn: () => apiFetch<AlerteOffre[]>(`/alertes-offres?statut=${statut}`),
  });
}

export function useValiderAlerteOffre() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => apiFetch(`/alertes-offres/${id}/valider`, { method: "POST" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["alertes-offres"] }),
  });
}

export function useRejeterAlerteOffre() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => apiFetch(`/alertes-offres/${id}/rejeter`, { method: "POST" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["alertes-offres"] }),
  });
}
