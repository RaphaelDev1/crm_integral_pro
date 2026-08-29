"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";
import { createResourceHooks } from "@/lib/hooks/useResource";
import type { ClientCreateInput, ClientUpdateInput } from "@/lib/schemas/client";
import type { AlerteOffre, Client, ClientDocument, HistoriqueAction } from "@/lib/types";

export const clientsResource = createResourceHooks<Client, ClientCreateInput, ClientUpdateInput>(
  "clients",
  "/clients"
);

export function useClientDocuments(clientId: number | undefined) {
  return useQuery({
    queryKey: ["clients", "documents", clientId ?? ""],
    queryFn: () => apiFetch<ClientDocument[]>(`/clients/${clientId}/documents`),
    enabled: clientId !== undefined,
  });
}

// Crée (ou réutilise) le ClientConseil IA Conseil rattaché à ce client — voir
// backend/services/ia_conseil_bridge.py. Utilisé par l'étape "Trame" du
// diagnostic pour pouvoir lancer des sessions de trame adaptative.
export function useIaConseilClientClient() {
  return useMutation({
    mutationFn: (clientId: number) => apiFetch<{ id: string }>(`/clients/${clientId}/ia-conseil-client`, { method: "POST" }),
  });
}

export function useSupprimerDocumentClient(clientId: number | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (documentId: number) =>
      apiFetch<void>(`/clients/${clientId}/documents/${documentId}`, { method: "DELETE" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["clients", "documents", clientId ?? ""] });
    },
  });
}

export function useValiderDocumentClient(clientId: number | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      documentId,
      statutKyc,
      motifRejet,
    }: {
      documentId: number;
      statutKyc: "valide" | "rejete";
      motifRejet?: string;
    }) =>
      apiFetch<ClientDocument>(`/clients/${clientId}/documents/${documentId}/statut`, {
        method: "PATCH",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ statut_kyc: statutKyc, motif_rejet: motifRejet || undefined }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["clients", "documents", clientId ?? ""] });
    },
  });
}

export function useClientHistorique(clientId: number | undefined) {
  return useQuery({
    queryKey: ["clients", "historique", clientId ?? ""],
    queryFn: () => apiFetch<HistoriqueAction[]>(`/clients/${clientId}/historique`),
    enabled: clientId !== undefined,
  });
}

export function useClientAlertes(clientId: number | undefined) {
  return useQuery({
    queryKey: ["clients", "alertes", clientId ?? ""],
    queryFn: () => apiFetch<AlerteOffre[]>(`/alertes-offres?statut=en_attente&client_id=${clientId}`),
    enabled: clientId !== undefined,
  });
}

interface LienPortailResult {
  token: string;
  url: string;
  expire_le: string;
  message_sms_suggere: string;
}

export function useGenererLienPortail() {
  return useMutation({
    mutationFn: (clientId: number) =>
      apiFetch<LienPortailResult>(`/clients/${clientId}/token-portail`, { method: "POST" }),
  });
}

export function useEnvoyerRelance() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, values }: { id: number; values: { date_relance: string; statut_relance: string } }) =>
      // Endpoint dédié, distinct de PUT /clients/{id} (verrouillé aux Admin une
      // fois la fiche enregistrée) — programmer une relance reste ouvert au
      // conseiller propriétaire, voir backend/routers/clients.py::programmer_relance.
      apiFetch<Client>(`/clients/${id}/relance`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(values),
      }),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: clientsResource.keys.detail(variables.id) });
      queryClient.invalidateQueries({ queryKey: ["clients", "historique", variables.id] });
    },
  });
}
