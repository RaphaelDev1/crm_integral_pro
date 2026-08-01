"use client";

import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";
import { createResourceHooks } from "@/lib/hooks/useResource";
import type { ContratCreateInput, ContratUpdateInput } from "@/lib/schemas/contrat";
import type { Contrat } from "@/lib/types";

export const contratsResource = createResourceHooks<Contrat, ContratCreateInput, ContratUpdateInput>(
  "contrats",
  "/contrats"
);

export function useContratsClient(clientId: number | undefined) {
  return useQuery({
    queryKey: ["contrats", "list", { client_id: clientId ?? "" }],
    queryFn: () => apiFetch<Contrat[]>(`/contrats?client_id=${clientId}`),
    enabled: clientId !== undefined,
  });
}
