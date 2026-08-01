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

interface LienDocumentsResult {
  token: string;
  url: string;
  expire_le: string;
  message_sms_suggere: string;
}

export function useGenererLienDocumentsProspect() {
  return useMutation({
    mutationFn: (prospectId: number) =>
      apiFetch<LienDocumentsResult>(`/prospects/${prospectId}/token-documents`, { method: "POST" }),
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
    mutationFn: ({ prospectId, canal }: { prospectId: number; canal: "sms" | "email" }) =>
      apiFetch<EnvoiLienResult>(`/prospects/${prospectId}/envoyer-lien-documents`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ canal }),
      }),
  });
}
