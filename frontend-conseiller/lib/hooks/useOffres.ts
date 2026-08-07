"use client";

import { useMutation, useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";
import type { ComparaisonOffre, OffreComparee, OffreCompareeItem, Recommandations } from "@/lib/types";

interface ComparerOffresPayload {
  univers: string;
  categorie: string;
  cout_actuel_mensuel: number;
  fournisseurs_autorises?: string[] | null;
  fournisseur_exclu?: string | null;
  data_go_min?: number | null;
}

// Compare les offres actives d'un (univers, catégorie) donné à un coût actuel
// — utilisé pour Énergie/Abonnements à l'étape 4 (backend/routers/offres.py::comparer).
// C'est un POST côté backend (payload complexe) mais un GET côté sémantique
// (aucun effet de bord) : on le consomme via useQuery pour bénéficier du
// cache/refetch automatique de React Query plutôt que de le redéclencher à la main.
export function useOffresComparees(payload: ComparerOffresPayload, enabled = true) {
  return useQuery({
    queryKey: ["offres", "comparer", payload],
    queryFn: () =>
      apiFetch<OffreComparee[]>("/offres/comparer", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(payload),
      }),
    enabled,
  });
}

interface RecommandationsPayload {
  service_principal: string;
  cout_tel: number;
  fournisseurs_autorises?: string[] | null;
  fournisseur_exclu?: string | null;
  data_go_min?: number | null;
}

// Bloc principal + cross-sell Télécom (mobile/box/pack/multi-lignes) — même
// logique que src/offres_engine.py::construire_recommandations, portée dans
// backend/routers/offres.py::recommandations.
export function useRecommandationsTelecom(payload: RecommandationsPayload, enabled = true) {
  return useQuery({
    queryKey: ["offres", "recommandations", payload],
    queryFn: () =>
      apiFetch<Recommandations>("/offres/recommandations", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(payload),
      }),
    enabled,
  });
}

interface CreerComparaisonPayload {
  client_id: number;
  univers: string;
  categorie: string;
  cout_actuel_mensuel: number;
  offre_recommandee_id: number | null;
  offres_comparees: OffreCompareeItem[];
  economie_mensuelle_estimee: number;
  economie_annuelle_estimee: number;
  contexte?: string;
}

// Liste les comparaisons enregistrées pour un client (ou un prospect) — la
// plus récente (id desc, voir backend/routers/comparaisons_offres.py) sert à
// afficher la meilleure offre trouvée sous "Économies estimées" sur la fiche
// client (clients/[id]/page.tsx).
export function useComparaisonsOffres(params: { client_id?: number; prospect_id?: number }, enabled = true) {
  const query = new URLSearchParams();
  if (params.client_id != null) query.set("client_id", String(params.client_id));
  if (params.prospect_id != null) query.set("prospect_id", String(params.prospect_id));
  return useQuery({
    queryKey: ["comparaisons-offres", "list", params],
    queryFn: () => apiFetch<ComparaisonOffre[]>(`/comparaisons-offres?${query.toString()}`),
    enabled,
  });
}

// Dernière comparaison d'offres du même univers que ce dossier — sert à
// proposer de choisir une autre offre parmi celles comparées lors du
// diagnostic (backend/routers/dossiers.py::obtenir_comparaison_dossier).
export function useComparaisonDossier(dossierId: number | undefined) {
  return useQuery({
    queryKey: ["dossiers", "comparaison", dossierId ?? ""],
    queryFn: () => apiFetch<ComparaisonOffre | null>(`/dossiers/${dossierId}/comparaison`),
    enabled: dossierId !== undefined,
  });
}

// Persiste le résultat d'une comparaison (backend/routers/comparaisons_offres.py)
// — nécessaire avant de générer un PDF de restitution : GET /dossiers/{id}/pdf-restitution
// lit toujours la dernière ComparaisonOffre du client.
export function useCreerComparaisonOffre() {
  return useMutation({
    mutationFn: (payload: CreerComparaisonPayload) =>
      apiFetch<ComparaisonOffre>("/comparaisons-offres", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(payload),
      }),
  });
}
