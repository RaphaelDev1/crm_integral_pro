"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch, backendFetch } from "@/lib/api";
import { createResourceHooks } from "@/lib/hooks/useResource";
import type {
  AlerteOverride,
  AlerteOverrideInput,
  AntiBiaisConseiller,
  Canal,
  CategorieConseil,
  ClientConseil,
  ClientConseilInput,
  CrossSellSuggestion,
  DashboardIaConseil,
  FournisseurConseil,
  NextQuestionOut,
  OffreConseil,
  OffreConseilInput,
  RapportVeilleMarche,
  RecommandationOut,
  ScoreClient,
  SessionFacture,
  SessionPublicOut,
  SessionTrame,
  SouscriptionConseil,
  SouscriptionConseilInput,
} from "@/lib/types-ia-conseil";

// Sous-système "IA Conseil" — API préfixée /api/v1 (isolée du CRM existant,
// voir PLAN_IMPLEMENTATION_4_PHASES.md). `apiFetch` passe toujours par le
// proxy BFF (lib/api.ts) : jamais d'appel direct au backend depuis le client.

export const iaConseilClientsResource = createResourceHooks<ClientConseil, ClientConseilInput, ClientConseilInput>(
  "ia-conseil-clients",
  "/api/v1/clients"
);

export const iaConseilSouscriptionsResource = createResourceHooks<SouscriptionConseil, SouscriptionConseilInput>(
  "ia-conseil-souscriptions",
  "/api/v1/souscriptions"
);

export interface CommissionsParConseiller {
  conseiller_id: number | null;
  commission_prevue_totale: number;
  commission_encaissee_totale: number;
  nb_souscriptions: number;
}

export function useIaConseilCommissions() {
  return useQuery({
    queryKey: ["ia-conseil-commissions"],
    queryFn: () => apiFetch<CommissionsParConseiller[]>("/api/v1/souscriptions/commissions"),
  });
}

// Dashboard conseiller enrichi (§2.5).
export function useDashboardIaConseil() {
  return useQuery({
    queryKey: ["ia-conseil-dashboard"],
    queryFn: () => apiFetch<DashboardIaConseil>("/api/v1/dashboard/ia-conseil"),
  });
}

// Audit anti-biais commercial (§2.6) — réservé Admin, 403 sinon.
export function useAntiBiaisCommercial() {
  return useQuery({
    queryKey: ["ia-conseil-anti-biais"],
    queryFn: () => apiFetch<AntiBiaisConseiller[]>("/api/v1/dashboard/anti-biais"),
  });
}

export function useIaConseilCategories() {
  return useQuery({
    queryKey: ["ia-conseil-categories"],
    queryFn: () => apiFetch<CategorieConseil[]>("/api/v1/catalogue/categories"),
    staleTime: 5 * 60 * 1000,
  });
}

export function useIaConseilFournisseurs(categorieSlug?: string) {
  return useQuery({
    queryKey: ["ia-conseil-fournisseurs", categorieSlug ?? ""],
    queryFn: () =>
      apiFetch<FournisseurConseil[]>(
        categorieSlug ? `/api/v1/catalogue/fournisseurs?categorie=${categorieSlug}` : "/api/v1/catalogue/fournisseurs"
      ),
    staleTime: 5 * 60 * 1000,
  });
}

export function useIaConseilOffres(categorieSlug?: string) {
  return useQuery({
    queryKey: ["ia-conseil-offres", categorieSlug ?? ""],
    queryFn: () =>
      apiFetch<OffreConseil[]>(categorieSlug ? `/api/v1/catalogue/offres?categorie=${categorieSlug}` : "/api/v1/catalogue/offres"),
  });
}

const OFFRES_ADMIN_KEY = ["ia-conseil-offres"];

export function useCreerOffreAdmin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (values: OffreConseilInput) =>
      apiFetch<OffreConseil>("/api/v1/admin/offres", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(values),
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: OFFRES_ADMIN_KEY }),
  });
}

export function useModifierOffreAdmin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, values }: { id: string; values: Partial<OffreConseilInput> }) =>
      apiFetch<OffreConseil>(`/api/v1/admin/offres/${id}`, {
        method: "PUT",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(values),
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: OFFRES_ADMIN_KEY }),
  });
}

export function useSupprimerOffreAdmin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiFetch<void>(`/api/v1/admin/offres/${id}`, { method: "DELETE" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: OFFRES_ADMIN_KEY }),
  });
}

// ==============================================================================
//  SESSION DE TRAME — cycle de vie complet (créer, question suivante, répondre,
//  recommandations, finaliser). Chaque réponse est déjà persistée serveur
//  immédiatement (voir backend/routers/ia_conseil_sessions.py::repondre) ; le
//  flux temps réel (useSessionTrameLive) pousse le même résultat via SSE pour
//  les autres onglets/écrans ouverts sur la même session (partage visio).
// ==============================================================================

export function useCreerSessionTrame() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: { client_id: string; categorie_slug: string; canal?: Canal | null }) =>
      apiFetch<SessionTrame>("/api/v1/sessions", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(payload),
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["ia-conseil-sessions"] }),
  });
}

export function useSessionTrame(sessionId: string | undefined) {
  return useQuery({
    queryKey: ["ia-conseil-sessions", sessionId ?? ""],
    queryFn: () => apiFetch<SessionTrame>(`/api/v1/sessions/${sessionId}`),
    enabled: sessionId !== undefined,
  });
}

export function useNextQuestion(sessionId: string | undefined) {
  return useQuery({
    queryKey: ["ia-conseil-sessions", sessionId ?? "", "next-question"],
    queryFn: () => apiFetch<NextQuestionOut>(`/api/v1/sessions/${sessionId}/next-question`),
    enabled: sessionId !== undefined,
  });
}

export function useRecommandations(sessionId: string | undefined, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ["ia-conseil-sessions", sessionId ?? "", "recommandations"],
    queryFn: () => apiFetch<RecommandationOut[]>(`/api/v1/sessions/${sessionId}/recommandations`),
    enabled: sessionId !== undefined && (options?.enabled ?? true),
  });
}

export function useRepondre(sessionId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: { question_id: string; valeur: unknown }) =>
      apiFetch<NextQuestionOut>(`/api/v1/sessions/${sessionId}/answer`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(payload),
      }),
    onSuccess: (resultat) => {
      queryClient.setQueryData(["ia-conseil-sessions", sessionId, "next-question"], resultat);
      queryClient.invalidateQueries({ queryKey: ["ia-conseil-sessions", sessionId, "recommandations"] });
      queryClient.invalidateQueries({ queryKey: ["ia-conseil-sessions", sessionId] });
    },
  });
}

// Lève une alerte critique bloquante pour un couple (offre, règle) de cette
// session — justification obligatoire (§2.1). N'invalide aucun cache : le
// front relance simplement la création de souscription après cet appel.
export function useOverrideAlerte(sessionId: string) {
  return useMutation({
    mutationFn: (payload: AlerteOverrideInput) =>
      apiFetch<AlerteOverride>(`/api/v1/sessions/${sessionId}/override-alerte`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(payload),
      }),
  });
}

export function useCreerLienPartage() {
  return useMutation({
    mutationFn: (sessionId: string) =>
      apiFetch<{ token: string }>(`/api/v1/sessions/${sessionId}/share-token`, { method: "POST" }),
  });
}

// Vue publique (lien partageable, §1.5.1) — aucune session conseiller
// requise : le proxy BFF (apiFetch) relaie la requête que le cookie
// httpOnly soit présent ou non, le backend n'exige que le `token` en query
// param sur cet endpoint (voir ia_conseil_sessions.py::obtenir_session_publique).
export function usePublicSession(sessionId: string | undefined, token: string | undefined) {
  return useQuery({
    queryKey: ["ia-conseil-public-session", sessionId ?? "", token ?? ""],
    queryFn: () => apiFetch<SessionPublicOut>(`/api/v1/sessions/${sessionId}/public?token=${encodeURIComponent(token ?? "")}`),
    enabled: Boolean(sessionId && token),
    refetchInterval: 4000,
  });
}

// Suggestions inter-catégories hors contexte de trame (§2.4) — fiche client.
export function useCrossSell(clientId: string | undefined) {
  return useQuery({
    queryKey: ["ia-conseil-clients", clientId ?? "", "cross-sell"],
    queryFn: () => apiFetch<CrossSellSuggestion[]>(`/api/v1/clients/${clientId}/cross-sell`),
    enabled: clientId !== undefined,
  });
}

export function useFinaliserSession(sessionId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => apiFetch<SessionTrame>(`/api/v1/sessions/${sessionId}/finalize`, { method: "POST" }),
    onSuccess: (session) => {
      queryClient.setQueryData(["ia-conseil-sessions", sessionId], session);
    },
  });
}

// ==============================================================================
//  FACTURE (§3.1) — upload pendant une session, analyse en tâche de fond
//  (statut suivi par polling ici, ou par le flux temps réel qui pousse le
//  même événement "facture_analysee" — voir useSessionTrameLive côté page).
// ==============================================================================

export function useTeleverserFacture(sessionId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (fichier: File) => {
      const formData = new FormData();
      formData.append("fichier", fichier);
      const res = await backendFetch(`/api/v1/sessions/${sessionId}/facture`, { method: "POST", body: formData });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        throw new Error((body as { detail?: string } | null)?.detail ?? "Échec de l'envoi de la facture.");
      }
      return res.json() as Promise<SessionFacture>;
    },
    onSuccess: (facture) => {
      queryClient.setQueryData(["ia-conseil-sessions", sessionId, "facture", facture.id], facture);
    },
  });
}

export function useFacture(sessionId: string, factureId: string | undefined) {
  return useQuery({
    queryKey: ["ia-conseil-sessions", sessionId, "facture", factureId ?? ""],
    queryFn: () => apiFetch<SessionFacture>(`/api/v1/sessions/${sessionId}/facture/${factureId}`),
    enabled: factureId !== undefined,
    // Analyse en tâche de fond (Celery) : on repasse toutes les 2s tant que
    // le statut n'est pas final, le flux temps réel accélère généralement
    // la mise à jour du cache avant que ce polling n'ait besoin d'agir.
    refetchInterval: (query) => (query.state.data?.statut === "en_attente" ? 2000 : false),
  });
}

export function useAppliquerFacture(sessionId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ factureId, reponses }: { factureId: string; reponses: Record<string, unknown> }) =>
      apiFetch<NextQuestionOut>(`/api/v1/sessions/${sessionId}/facture/${factureId}/appliquer`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ reponses }),
      }),
    onSuccess: (resultat) => {
      queryClient.setQueryData(["ia-conseil-sessions", sessionId, "next-question"], resultat);
      queryClient.invalidateQueries({ queryKey: ["ia-conseil-sessions", sessionId, "recommandations"] });
      queryClient.invalidateQueries({ queryKey: ["ia-conseil-sessions", sessionId] });
    },
  });
}

// ==============================================================================
//  VEILLE MARCHÉ (§3.4) — revue admin des rapports hebdomadaires.
// ==============================================================================

export function useRapportsVeilleMarche(statut?: RapportVeilleMarche["statut"]) {
  return useQuery({
    queryKey: ["ia-conseil-veille-marche", statut ?? ""],
    queryFn: () =>
      apiFetch<RapportVeilleMarche[]>(
        statut ? `/api/v1/admin/veille-marche/rapports?statut=${statut}` : "/api/v1/admin/veille-marche/rapports"
      ),
  });
}

export function useIntegrerOffreVeilleMarche() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ rapportId, index }: { rapportId: string; index: number }) =>
      apiFetch<OffreConseil>(`/api/v1/admin/veille-marche/rapports/${rapportId}/offres/${index}/integrer`, { method: "POST" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: OFFRES_ADMIN_KEY }),
  });
}

// §3.5 — prévision de churn + scoring client (fiche client).
export function useScoreClient(clientId: string | undefined) {
  return useQuery({
    queryKey: ["ia-conseil-clients", clientId ?? "", "scores"],
    queryFn: () => apiFetch<ScoreClient>(`/api/v1/clients/${clientId}/scores`),
    enabled: clientId !== undefined,
  });
}
