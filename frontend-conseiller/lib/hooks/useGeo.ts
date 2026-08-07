"use client";

import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";

interface CommunesResult {
  villes: string[];
}

// Auto-complétion ville à partir du code postal (étape Identité du diagnostic)
// — passe par /api/backend/geo/communes (BFF), la CSP interdit un appel
// direct depuis le navigateur vers geo.api.gouv.fr.
export function useCommunesParCodePostal(codePostal: string) {
  const actif = /^\d{5}$/.test(codePostal);
  return useQuery({
    queryKey: ["geo", "communes", codePostal],
    queryFn: () => apiFetch<CommunesResult>(`/geo/communes?code_postal=${codePostal}`),
    enabled: actif,
    staleTime: 10 * 60 * 1000,
  });
}
