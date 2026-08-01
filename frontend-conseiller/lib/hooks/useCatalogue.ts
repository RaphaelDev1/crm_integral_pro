"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";
import { createResourceHooks } from "@/lib/hooks/useResource";
import type { CatalogueSourceCreateInput, CatalogueSourceUpdateInput } from "@/lib/schemas/catalogue";
import type { CatalogueSource, IngestionResume, OffreStaging } from "@/lib/types";

export const sourcesCatalogueResource = createResourceHooks<
  CatalogueSource,
  CatalogueSourceCreateInput,
  CatalogueSourceUpdateInput
>("catalogue-sources", "/catalogue/sources");

export function useIngererSourceCatalogue() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (sourceId: number) => apiFetch<IngestionResume>(`/catalogue/sources/${sourceId}/ingerer`, { method: "POST" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["catalogue-sources"] });
      queryClient.invalidateQueries({ queryKey: ["catalogue-offres-staging"] });
    },
  });
}

export function useOffresStaging(statut: string = "en_attente") {
  return useQuery({
    queryKey: ["catalogue-offres-staging", "list", { statut }],
    queryFn: () => apiFetch<OffreStaging[]>(`/catalogue/offres-staging?statut=${statut}`),
  });
}

export function useValiderOffreStaging() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => apiFetch(`/catalogue/offres-staging/${id}/valider`, { method: "POST" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["catalogue-offres-staging"] }),
  });
}

export function useRejeterOffreStaging() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => apiFetch(`/catalogue/offres-staging/${id}/rejeter`, { method: "POST" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["catalogue-offres-staging"] }),
  });
}
