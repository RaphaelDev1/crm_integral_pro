"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";
import { createResourceHooks } from "@/lib/hooks/useResource";
import type { ProspectCreateInput, ProspectUpdateInput } from "@/lib/schemas/prospect";
import type {
  Client,
  DocumentProspect,
  HistoriqueAction,
  Prospect,
  ScoreProspect,
} from "@/lib/types";

export const prospectsResource = createResourceHooks<Prospect, ProspectCreateInput, ProspectUpdateInput>(
  "prospects",
  "/prospects"
);

export function useProspectScore(prospectId: number | undefined) {
  return useQuery({
    queryKey: ["prospects", "score", prospectId ?? ""],
    queryFn: () => apiFetch<ScoreProspect>(`/prospects/${prospectId}/score`),
    enabled: prospectId !== undefined,
  });
}

export function useProspectDocuments(prospectId: number | undefined) {
  return useQuery({
    queryKey: ["prospects", "documents", prospectId ?? ""],
    queryFn: () => apiFetch<DocumentProspect[]>(`/prospects/${prospectId}/documents`),
    enabled: prospectId !== undefined,
  });
}

export function useSupprimerDocumentProspect(prospectId: number | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (documentId: number) =>
      apiFetch<void>(`/prospects/${prospectId}/documents/${documentId}`, { method: "DELETE" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["prospects", "documents", prospectId ?? ""] });
    },
  });
}

export function useProspectHistorique(prospectId: number | undefined) {
  return useQuery({
    queryKey: ["prospects", "historique", prospectId ?? ""],
    queryFn: () => apiFetch<HistoriqueAction[]>(`/prospects/${prospectId}/historique`),
    enabled: prospectId !== undefined,
  });
}

export function useConvertirProspect() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (prospectId: number) => apiFetch<Client>(`/prospects/${prospectId}/convertir`, { method: "POST" }),
    onSuccess: (_data, prospectId) => {
      queryClient.invalidateQueries({ queryKey: prospectsResource.keys.lists() });
      queryClient.invalidateQueries({ queryKey: prospectsResource.keys.detail(prospectId) });
      queryClient.invalidateQueries({ queryKey: ["clients", "list"] });
    },
  });
}

// Crée (ou réutilise) le client "miroir" du prospect sans finaliser la
// conversion — utilisé par le diagnostic pour créer un dossier avant la
// signature du mandat, qui déclenchera la vraie conversion (voir
// EtapeRecommandations.tsx).
export function useClientMiroirProspect() {
  return useMutation({
    mutationFn: (prospectId: number) => apiFetch<Client>(`/prospects/${prospectId}/client-miroir`, { method: "POST" }),
  });
}

// Crée (ou réutilise) le ClientConseil IA Conseil rattaché à ce prospect —
// voir backend/services/ia_conseil_bridge.py. Utilisé par l'étape "Trame" du
// diagnostic pour pouvoir lancer des sessions de trame adaptative.
export function useIaConseilClientProspect() {
  return useMutation({
    mutationFn: (prospectId: number) =>
      apiFetch<{ id: string }>(`/prospects/${prospectId}/ia-conseil-client`, { method: "POST" }),
  });
}

interface LienDocumentsResult {
  token: string;
  url: string;
  expire_le: string;
  message_sms_suggere: string;
}

export function useGenererLienDocumentsProspect() {
  return useMutation({
    mutationFn: ({ prospectId, remplissageAutonome }: { prospectId: number; remplissageAutonome?: boolean }) =>
      apiFetch<LienDocumentsResult>(
        `/prospects/${prospectId}/token-documents?remplissage_autonome=${remplissageAutonome ?? true}`,
        { method: "POST" }
      ),
  });
}

interface EnvoiLienResult {
  token: string;
  url: string;
  expire_le: string;
  sms_envoye: boolean;
  email_envoye: boolean;
}

export function useEnvoyerLienDocumentsProspect() {
  return useMutation({
    mutationFn: ({
      prospectId,
      canal,
      remplissageAutonome = true,
    }: {
      prospectId: number;
      canal: "sms" | "email";
      remplissageAutonome?: boolean;
    }) =>
      apiFetch<EnvoiLienResult>(`/prospects/${prospectId}/envoyer-lien-documents`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ canal, remplissage_autonome: remplissageAutonome }),
      }),
  });
}

// Marque la relance du jour comme faite : journalise l'action (source du
// "dernier contact" affiché) et programme la prochaine relance à +7 jours —
// voir backend/routers/prospects.py::relance_effectuee.
export function useRelanceEffectuee() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (prospectId: number) =>
      apiFetch<Prospect>(`/prospects/${prospectId}/relance-effectuee`, { method: "POST" }),
    onSuccess: (_data, prospectId) => {
      queryClient.invalidateQueries({ queryKey: prospectsResource.keys.detail(prospectId) });
      queryClient.invalidateQueries({ queryKey: prospectsResource.keys.lists() });
      queryClient.invalidateQueries({ queryKey: ["prospects", "score", prospectId] });
      queryClient.invalidateQueries({ queryKey: ["prospects", "historique", prospectId] });
    },
  });
}

// Bouton "Contacter par téléphone" de la fiche prospect : journalise l'appel,
// programme la relance à +7 jours et, si le prospect n'a pas répondu, lui
// envoie un SMS/email pour l'en informer — voir
// backend/routers/prospects.py::contacter_telephone.
export function useContacterTelephone() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ prospectId, repondu }: { prospectId: number; repondu: boolean }) =>
      apiFetch<Prospect>(`/prospects/${prospectId}/contacter-telephone`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ repondu }),
      }),
    onSuccess: (_data, { prospectId }) => {
      queryClient.invalidateQueries({ queryKey: prospectsResource.keys.detail(prospectId) });
      queryClient.invalidateQueries({ queryKey: prospectsResource.keys.lists() });
      queryClient.invalidateQueries({ queryKey: ["prospects", "score", prospectId] });
      queryClient.invalidateQueries({ queryKey: ["prospects", "historique", prospectId] });
    },
  });
}
