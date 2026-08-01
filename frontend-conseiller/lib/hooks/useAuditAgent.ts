"use client";

import { useMutation } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";
import type { AbonnementSituationAudit, AuditResult } from "@/lib/types";

interface SituationAuditPayload {
  service_principal?: string;
  cout_mensuel_actuel?: number;
  ville?: string;
  operateur_actuel?: string;
  satisfaction_reseau?: string;
  veut_rester?: string;
  cout_elec?: number;
  cout_gaz?: number;
  fournisseur_energie?: string;
  abonnements?: AbonnementSituationAudit[];
  data_go_min?: number;
}

interface AuditRequestPayload {
  situation: SituationAuditPayload;
}

// Agent d'audit autonome (backend/services/audit_agent.py, Claude tool-use) —
// invoqué depuis l'étape 4 du wizard Diagnostic pour pré-remplir le panier
// automatiquement à partir de la situation déjà collectée.
export function useLancerAudit() {
  return useMutation({
    mutationFn: (payload: AuditRequestPayload) =>
      apiFetch<AuditResult>("/audit/lancer", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(payload),
      }),
  });
}
