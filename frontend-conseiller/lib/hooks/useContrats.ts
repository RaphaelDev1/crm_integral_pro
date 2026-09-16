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

interface RattachementEntite {
  clientId?: number;
  prospectId?: number;
}

// Un contrat est rattaché soit à un client, soit à un prospect non converti
// (voir backend/routers/contrats.py) — l'un des deux est toujours fourni.
export function useContrats({ clientId, prospectId }: RattachementEntite) {
  return useQuery({
    queryKey: ["contrats", "list", { client_id: clientId ?? "", prospect_id: prospectId ?? "" }],
    queryFn: () =>
      apiFetch<Contrat[]>(
        clientId != null ? `/contrats?client_id=${clientId}` : `/contrats?prospect_id=${prospectId}`
      ),
    enabled: clientId !== undefined || prospectId !== undefined,
  });
}

export interface LigneEstimationContrat {
  categorie: string;
  cout_actuel_mensuel: number;
  notre_moyenne_mensuel: number;
  economie_mensuelle_basse: number;
  economie_mensuelle_haute: number;
  economie_annuelle_typique: number;
  source: string;
  echantillon: number;
  tranche_age_utilisee: string | null;
}

interface EstimationContrat {
  lignes: LigneEstimationContrat[];
  economie_annuelle_totale_basse: number;
  economie_annuelle_totale_haute: number;
  economie_annuelle_totale_typique: number;
  calculee_le: string;
}

// Fourchette d'économie annuelle (basse/haute/typique), calculée par le même
// moteur que la landing publique /economiser (backend/services/estimation_publique.py)
// à partir des contrats "Actuel" (situation avant nous) de l'entité.
export function useContratsEstimation({ clientId, prospectId }: RattachementEntite) {
  return useQuery({
    queryKey: ["contrats", "estimation", { client_id: clientId ?? "", prospect_id: prospectId ?? "" }],
    queryFn: () =>
      apiFetch<EstimationContrat>(
        clientId != null ? `/contrats/estimation?client_id=${clientId}` : `/contrats/estimation?prospect_id=${prospectId}`
      ),
    enabled: clientId !== undefined || prospectId !== undefined,
  });
}
