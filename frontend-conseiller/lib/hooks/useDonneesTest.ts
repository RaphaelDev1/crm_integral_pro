"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";

interface PurgeDonneesTestResultat {
  clients_supprimes: number;
  prospects_supprimes: number;
  fichiers_supprimes: number;
}

// Purge totale des prospects/clients de test (et tout ce qui en dépend :
// dossiers, mandats, documents, factures...), fichiers de stockage inclus —
// voir backend/routers/admin.py::purger_donnees_test. Réservé Admin, bloqué
// en production côté backend.
export function usePurgerDonneesTest() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => apiFetch<PurgeDonneesTestResultat>("/admin/donnees-test", { method: "DELETE" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["clients"] });
      queryClient.invalidateQueries({ queryKey: ["prospects"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}
