"use client";

import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";

export interface AdresseResultat {
  label: string | null;
  rue: string | null;
  code_postal: string | null;
  ville: string | null;
  lat: number | null;
  lng: number | null;
}

// Auto-complétion d'adresse (AnswerInput type "adresse" des trames IA
// Conseil) — passe par /api/backend/geo/adresses (BFF), la CSP interdit un
// appel direct depuis le navigateur vers api-adresse.data.gouv.fr (même
// contrainte que useCommunesParCodePostal, voir lib/hooks/useGeo.ts).
export function useAdresseAutocomplete(recherche: string) {
  const actif = recherche.trim().length >= 3;
  return useQuery({
    queryKey: ["geo", "adresses", recherche],
    queryFn: () => apiFetch<{ resultats: AdresseResultat[] }>(`/geo/adresses?q=${encodeURIComponent(recherche)}`),
    enabled: actif,
    staleTime: 60 * 1000,
  });
}
