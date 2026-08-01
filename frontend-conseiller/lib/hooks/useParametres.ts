"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";
import type { Parametre } from "@/lib/types";

export function useParametresListe() {
  return useQuery({
    queryKey: ["parametres", "list"],
    queryFn: () => apiFetch<Parametre[]>("/parametres"),
  });
}

export function useMajParametre() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ cle, valeur }: { cle: string; valeur: string }) =>
      apiFetch<Parametre>(`/parametres/${cle}`, {
        method: "PUT",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ valeur }),
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["parametres"] }),
  });
}

// Upload multipart : pas de content-type manuel, le navigateur pose le
// boundary lui-même (voir lib/hooks/useFactures.ts::useAnalyserFacture).
export function useUploadLogo() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (fichier: File) => {
      const formData = new FormData();
      formData.append("fichier", fichier);
      return apiFetch<Parametre>("/parametres/logo", { method: "POST", body: formData });
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["parametres"] }),
  });
}
