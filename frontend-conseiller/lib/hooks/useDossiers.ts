"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";
import { createResourceHooks } from "@/lib/hooks/useResource";
import type { Dossier, EtapeTimeline } from "@/lib/types";

// Ressource générique (list/one) — la création passe par useCreerDossier
// ci-dessous (dépend du client_id), la mise à jour de champs simples n'est
// pas exposée par l'UI pour l'instant (voir plan Phase 5).
export const dossiersResource = createResourceHooks<Dossier>("dossiers", "/dossiers");

export function useDossiersClient(clientId: number | undefined) {
  return useQuery({
    queryKey: ["dossiers", "list", { client_id: clientId ?? "" }],
    queryFn: () => apiFetch<Dossier[]>(`/dossiers?client_id=${clientId}`),
    enabled: clientId !== undefined,
  });
}

export function useDossiersStagnants() {
  return useQuery({
    queryKey: ["dossiers", "stagnants"],
    queryFn: () => apiFetch<Dossier[]>("/dossiers/stagnants"),
  });
}

export function useDossierTimeline(dossierId: number | undefined) {
  return useQuery({
    queryKey: ["dossiers", "timeline", dossierId ?? ""],
    queryFn: () => apiFetch<EtapeTimeline[]>(`/dossiers/${dossierId}/timeline`),
    enabled: dossierId !== undefined,
  });
}

export function useTransitionDossier() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, nouveau_statut, commentaire }: { id: number; nouveau_statut: string; commentaire?: string }) =>
      apiFetch<Dossier>(`/dossiers/${id}/transition`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ nouveau_statut, commentaire }),
      }),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: dossiersResource.keys.lists() });
      queryClient.invalidateQueries({ queryKey: dossiersResource.keys.detail(variables.id) });
      queryClient.invalidateQueries({ queryKey: ["dossiers", "timeline", variables.id] });
      queryClient.invalidateQueries({ queryKey: ["dossiers", "stagnants"] });
    },
  });
}

export function useAjouterNoteDossier() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, texte }: { id: number; texte: string }) =>
      apiFetch<Dossier>(`/dossiers/${id}/notes`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ texte }),
      }),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: dossiersResource.keys.detail(variables.id) });
    },
  });
}

// Crée un nouveau dossier de souscription pour un client — c'est ce qui
// déclenche concrètement la préparation d'une offre/devis (pas de concept de
// "devis" séparé côté backend, voir backend/routers/dossiers.py).
export function useCreerDossier() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (values: {
      client_id: number;
      univers: string;
      fournisseur_cible?: string;
      offre_cible_id?: number;
      economie_annuelle_estimee?: number;
      frais_annexes_cible?: number;
      // false par défaut (fiche client déjà établie) — true quand le dossier est
      // créé depuis le diagnostic pour un prospect pas encore converti (client
      // "miroir", voir EtapeRecommandations.tsx) : allège les documents requis
      // tant que le mandat n'est pas signé (dossier_engine.documents_requis_pour_univers).
      est_prospect?: boolean;
    }) =>
      apiFetch<Dossier>("/dossiers", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ ...values, est_prospect: values.est_prospect ?? false }),
      }),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["dossiers", "list", { client_id: variables.client_id }] });
      queryClient.invalidateQueries({ queryKey: dossiersResource.keys.lists() });
    },
  });
}

interface LienClientResult {
  token: string;
  url: string;
  expire_le: string;
  message_sms_suggere: string;
}

export function useGenererLienClientDossier() {
  return useMutation({
    mutationFn: (dossierId: number) =>
      apiFetch<LienClientResult>(`/dossiers/${dossierId}/token-client`, { method: "POST" }),
  });
}

interface EnvoiLienResult {
  token: string;
  url: string;
  expire_le: string;
  sms_envoye: boolean;
  email_envoye: boolean;
}

export function useEnvoyerLienClientDossier() {
  return useMutation({
    mutationFn: ({ dossierId, canal }: { dossierId: number; canal: "sms" | "email" }) =>
      apiFetch<EnvoiLienResult>(`/dossiers/${dossierId}/envoyer-lien-client`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ canal }),
      }),
  });
}
